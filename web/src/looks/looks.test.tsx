import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";

const owner = { id: 1, email: "o@b.co", name: "Olu", role: "owner", workspace_id: 1 };
const editor = { ...owner, id: 2, role: "editor" };
const house = { id: "house", name: "House", blurb: "Our own look", on: true, sample_still_id: null };
const pixar = { id: "pixar", name: "Disney Pixar", blurb: "Soft 3D feature-film look", on: false, sample_still_id: null };
const sample = (o: object = {}) => ({ status: "none", reason: null, credits: 6, hero: { id: 5, name: "Bo" }, characters: [], still_id: null, clip_id: null, look: pixar, ...o });
const routes = (o: Record<string, [number, unknown]> = {}) => ({
  "GET /auth/me": [200, owner] as [number, unknown],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]] as [number, unknown],
  "GET /looks": [200, [house, pixar]] as [number, unknown],
  ...o,
});

function open() {
  renderApp("/looks");
}

afterEach(() => vi.unstubAllGlobals());

test("an Off look offers Make a sample of the brand's hero at its price; House is always on", async () => {
  setViewport(1440);
  const calls = fakeServer(routes({ "GET /looks/pixar/sample": [200, sample()], "POST /looks/pixar/sample": [201, sample({ status: "making" })] }));
  open();
  const card = await screen.findByLabelText("Disney Pixar");
  expect(within(card).getByText("Off for editors")).toBeInTheDocument();
  expect(await within(card).findByText(/One still and one 5 s clip of Bo/)).toBeInTheDocument();
  await userEvent.click(within(card).getByRole("button", { name: /Make a sample · up to 6 credits/ }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /looks/pixar/sample")?.body).toEqual({ brand_id: 1, character_id: 5 }));
  expect(within(screen.getByLabelText("House")).getByText("The house look is always on.")).toBeInTheDocument();
});

test("on the test site, the sample says before the press whether it's real or a stand-in", async () => {
  setViewport(390);
  const note = "Test site: the budget for real samples is used up, so this sample will be a stand-in.";
  fakeServer(routes({ "GET /looks/pixar/sample": [200, sample({ test_site: note })] }));
  open();
  const card = await screen.findByLabelText("Disney Pixar");
  expect(await within(card).findByText(note)).toBeInTheDocument();
});

test("with no hero, Who's in the sample? offers the brand's characters or the look's own sample character", async () => {
  setViewport(390);
  const calls = fakeServer(routes({ "GET /looks/pixar/sample": [200, sample({ hero: null, characters: [{ id: 7, name: "Mia" }] })], "POST /looks/pixar/sample": [201, sample({ status: "making" })] }));
  open();
  const card = await screen.findByLabelText("Disney Pixar");
  const who = await within(card).findByLabelText("Who's in the sample?");
  await userEvent.click(within(card).getByRole("button", { name: /Make a sample/ }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /looks/pixar/sample")?.body).toEqual({ brand_id: 1, character_id: null }));
  await userEvent.selectOptions(who, "7");
  await userEvent.click(within(card).getByRole("button", { name: /Make a sample/ }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /looks/pixar/sample").at(-1)?.body).toEqual({ brand_id: 1, character_id: 7 }));
});

test("a look with its own sample character offers no hero and no Who's in the sample? (Flow-QA on #1015)", async () => {
  setViewport(390);
  const skeleton = { ...pixar, own_sample: true };
  const calls = fakeServer(routes({ "GET /looks/pixar/sample": [200, sample({ hero: null, look: skeleton })], "POST /looks/pixar/sample": [201, sample({ status: "making", hero: null, look: skeleton })] }));
  open();
  const card = await screen.findByLabelText("Disney Pixar");
  expect(await within(card).findByText(/of the look's own sample character/)).toBeInTheDocument();
  expect(within(card).queryByLabelText("Who's in the sample?")).toBeNull();
  await userEvent.click(within(card).getByRole("button", { name: /Make a sample/ }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /looks/pixar/sample")?.body).toEqual({ brand_id: 1, character_id: null }));
});

test("a ready sample shows the whole portrait still (never cropped); tapping it opens the full still and the clip, with Switch on there", async () => {
  setViewport(1440);
  const calls = fakeServer(routes({ "GET /looks/pixar/sample": [200, sample({ status: "ready", still_id: 80, clip_id: 81 })], "PATCH /looks/pixar": [200, { ...pixar, on: true }] }));
  open();
  const card = await screen.findByLabelText("Disney Pixar");
  const thumb = await within(card).findByAltText("Disney Pixar sample");
  expect(thumb).toHaveClass("object-contain");
  expect(thumb).not.toHaveClass("object-cover");
  expect(within(card).getByText("▶ 5 s clip")).toBeInTheDocument();
  await userEvent.click(within(card).getByRole("button", { name: "Open the Disney Pixar sample" }));
  const viewer = await screen.findByRole("dialog", { name: "Disney Pixar sample" });
  expect(within(viewer).getByAltText("Disney Pixar sample, full size")).toHaveAttribute("src", "/api/files/80");
  const clip = within(viewer).getByLabelText("Disney Pixar sample clip");
  expect(clip).toHaveAttribute("src", "/api/files/81");
  expect(clip).toHaveAttribute("controls");
  expect(clip).toHaveAttribute("autoplay");
  await userEvent.click(within(viewer).getByRole("button", { name: "Switch on for editors" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /looks/pixar")?.body).toEqual({ on: true }));
  expect(await screen.findByText("Disney Pixar is on for editors.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "PATCH /looks/pixar").at(-1)?.body).toEqual({ on: false }));
});

test("while the clip is being made the still shows with Clip coming…, on the card and in the viewer, and the clip appears when it lands", async () => {
  setViewport(390);
  const routesNow: Record<string, [number, unknown]> = routes({ "GET /looks/pixar/sample": [200, sample({ status: "making", still_id: 80 })] });
  fakeServer(routesNow);
  open();
  const card = await screen.findByLabelText("Disney Pixar");
  expect(await within(card).findByAltText("Disney Pixar sample")).toHaveAttribute("src", "/api/files/80");
  expect(within(card).getByText("Clip coming…")).toBeInTheDocument();
  await userEvent.click(within(card).getByRole("button", { name: "Open the Disney Pixar sample" }));
  const viewer = await screen.findByRole("dialog", { name: "Disney Pixar sample" });
  expect(within(viewer).getByText("Clip coming… It shows here when it's ready.")).toBeInTheDocument();
  routesNow["GET /looks/pixar/sample"] = [200, sample({ status: "ready", still_id: 80, clip_id: 81 })]; // the clip lands
  expect(await within(viewer).findByLabelText("Disney Pixar sample clip", undefined, { timeout: 6000 })).toHaveAttribute("src", "/api/files/81");
  expect(within(viewer).getByRole("button", { name: "Switch on for editors" })).toBeInTheDocument();
}, 15000);

test("a refused clip after its still shows the still with the reason and Try again, never Clip coming… for ever (QA-3, Zack D tonight)", async () => {
  setViewport(390);
  const reason = "The video model wouldn't make this clip. Nothing was charged for it.";
  fakeServer(routes({ "GET /looks/pixar/sample": [200, sample({ status: "failed", reason, still_id: 80 })] }));
  open();
  const card = await screen.findByLabelText("Disney Pixar");
  expect(await within(card).findByAltText("Disney Pixar sample")).toHaveAttribute("src", "/api/files/80");
  expect(within(card).getByText(reason)).toBeInTheDocument();
  expect(within(card).getByRole("button", { name: /^Try again/ })).toBeInTheDocument();
  expect(within(card).queryByText(/Clip coming/)).toBeNull();
  await userEvent.click(within(card).getByRole("button", { name: "Open the Disney Pixar sample" }));
  const viewer = await screen.findByRole("dialog", { name: "Disney Pixar sample" });
  expect(within(viewer).getByText(reason)).toBeInTheDocument();
  expect(within(viewer).getByRole("button", { name: /^Try again/ })).toBeInTheDocument();
  expect(within(viewer).queryByText(/Clip coming/)).toBeNull();
});

test("a failed sample says why with Try again; an On look offers Switch off", async () => {
  setViewport(1440);
  fakeServer(routes({ "GET /looks": [200, [house, pixar, { ...pixar, id: "zack", name: "Zack D", on: true }]], "GET /looks/pixar/sample": [200, sample({ status: "failed", reason: "The still was refused. Nothing was charged." })], "GET /looks/zack/sample": [200, sample()] }));
  open();
  const card = await screen.findByLabelText("Disney Pixar");
  expect(await within(card).findByText("The still was refused. Nothing was charged.")).toBeInTheDocument();
  expect(within(card).getByRole("button", { name: /Try again · up to 6 credits/ })).toBeInTheDocument();
  expect(within(screen.getByLabelText("Zack D")).getByRole("button", { name: "Switch off" })).toBeInTheDocument();
});

test("editors don't get the Looks page", async () => {
  setViewport(1440);
  fakeServer(routes({ "GET /auth/me": [200, editor] }));
  open();
  expect(await screen.findByText("Only the owner manages looks.")).toBeInTheDocument();
});

test("Make another sample keeps the character picked for it", async () => {
  setViewport(1440);
  const calls = fakeServer(routes({ "GET /looks/pixar/sample": [200, sample({ status: "ready", hero: null, characters: [{ id: 7, name: "Mia" }], still_id: 80, clip_id: 81 })], "POST /looks/pixar/sample": [201, sample({ status: "making" })] }));
  open();
  const card = await screen.findByLabelText("Disney Pixar");
  await userEvent.click(await within(card).findByRole("button", { name: /Make another sample/ }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /looks/pixar/sample")?.body).toEqual({ brand_id: 1, character_id: null }));
});
