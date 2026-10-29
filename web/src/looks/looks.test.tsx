import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

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
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/looks"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

test("an Off look offers Make a sample of the brand's hero at its price; House is always on", async () => {
  setViewport(1440);
  const calls = fakeServer(routes({ "GET /looks/pixar/sample": [200, sample()], "POST /looks/pixar/sample": [201, sample({ status: "making" })] }));
  open();
  const card = await screen.findByLabelText("Disney Pixar");
  expect(within(card).getByText("Off for editors")).toBeInTheDocument();
  expect(await within(card).findByText(/One still and one 5 s clip of Bo/)).toBeInTheDocument();
  await userEvent.click(within(card).getByRole("button", { name: /Make a sample · 6 credits/ }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /looks/pixar/sample")?.body).toEqual({ brand_id: 1, character_id: 5 }));
  expect(within(screen.getByLabelText("House")).getByText("The house look is always on.")).toBeInTheDocument();
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

test("a ready sample shows its still and clip; Switch on for editors, with Undo", async () => {
  setViewport(1440);
  const calls = fakeServer(routes({ "GET /looks/pixar/sample": [200, sample({ status: "ready", still_id: 80, clip_id: 81 })], "PATCH /looks/pixar": [200, { ...pixar, on: true }] }));
  open();
  const card = await screen.findByLabelText("Disney Pixar");
  expect(await within(card).findByLabelText("Disney Pixar sample clip")).toHaveAttribute("src", "/api/files/81");
  await userEvent.click(within(card).getByRole("button", { name: "Switch on for editors" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /looks/pixar")?.body).toEqual({ on: true }));
  expect(await screen.findByText("Disney Pixar is on for editors.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "PATCH /looks/pixar").at(-1)?.body).toEqual({ on: false }));
});

test("a failed sample says why with Try again; an On look offers Switch off", async () => {
  setViewport(1440);
  fakeServer(routes({ "GET /looks": [200, [house, pixar, { ...pixar, id: "zack", name: "Zack D", on: true }]], "GET /looks/pixar/sample": [200, sample({ status: "failed", reason: "The still was refused. Nothing was charged." })], "GET /looks/zack/sample": [200, sample()] }));
  open();
  const card = await screen.findByLabelText("Disney Pixar");
  expect(await within(card).findByText("The still was refused. Nothing was charged.")).toBeInTheDocument();
  expect(within(card).getByRole("button", { name: /Try again · 6 credits/ })).toBeInTheDocument();
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
