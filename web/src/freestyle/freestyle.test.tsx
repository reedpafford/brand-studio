import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { editor, owner } from "../test/people";
import { renderApp } from "../test/render";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const SCRIPT = "MIA: The market opened at nine.";
const at = new Date().toISOString();
const look = (id: string, name: string, on = true) => ({ id, name, blurb: "", on, own_sample: false, lanes: [] });
const said = (who: string, text: string) => ({ id: "m1", kind: "message", at, who, text, status: null, why: "" });
const move = (text: string, status: string) => ({ id: "t5", kind: "move", at, who: "Director", text, status, why: "" });
const fs = (o: object = {}) => ({
  id: 9, title: SCRIPT, type: "one_clip", look: "pixar", shape: "9:16", brand_id: 1, status: "working", created_by_name: "Reed", created_at: at, credits: 27, file_id: null,
  thread: [said("Reed", SCRIPT), move("Making the clip.", "running")], ...o,
});
const version = (slot: number, o: object = {}) => ({ slot, status: "approved", title: "", seconds: 32 + slot * 3, project_id: null, text: `BO: version ${slot}.`, estimate_credits: 170 + slot, ...o });
const scriptRow = { id: 7, brand_id: 1, title: "Bo tries salmon", kind: "story", look: "house", folder_id: null, versions: [version(0), version(1)], created_at: at };
function server(me: object, routes: Record<string, [number, unknown]> = {}) {
  return fakeServer({
    "GET /auth/me": [200, me],
    "GET /brands": [200, [{ id: 1, name: "fomo", colours: [] }]],
    "GET /looks": [200, [look("house", "House"), look("pixar", "Disney Pixar"), look("zack", "Zack D", false)]],
    "GET /jobs": [200, []],
    "GET /freestyles": [200, []],
    "GET /freestyles/estimate": [200, { credits: 33.2 }],
    ...routes,
  });
}
afterEach(() => vi.unstubAllGlobals());

const words = () => screen.findByLabelText("Paste a script, or describe the video");

test("New video: the owner's Make it carries its whole price, ⌘↵ sends the picked settings with the rail's brand, and it lands on the video", async () => {
  setViewport(1440);
  const calls = server(owner, { "POST /freestyles": [201, fs({ type: "dialogue", project_id: 50 })], "GET /projects/50": [200, { id: 50, brand_id: 1, name: SCRIPT, freestyle_id: 9 }], "GET /freestyles/9": [200, fs({ type: "dialogue", project_id: 50 })] });
  renderApp("/b/1/videos/new");
  expect(await screen.findByRole("heading", { name: "What should the director make?" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^Make it/ })).toBeDisabled(); // nothing typed yet
  await userEvent.click(await screen.findByRole("button", { name: "Style: House" }));
  await userEvent.click(screen.getByRole("menuitemradio", { name: "Disney Pixar" }));
  expect(screen.queryByRole("menuitemradio", { name: "Zack D" })).toBeNull(); // only the switched-on looks
  await userEvent.type(await words(), SCRIPT);
  expect(await screen.findByRole("button", { name: "Make it · up to 34 credits" })).toBeInTheDocument(); // whole credits, rounded up
  await userEvent.keyboard("{Control>}{Enter}{/Control}");
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /freestyles")?.body).toEqual({ type: "dialogue", look: "pixar", shape: "9:16", brand_id: 1, text: SCRIPT }));
  expect(await screen.findByRole("list", { name: "Thread" })).toBeInTheDocument(); // the video's chat
});

test("an editor's press reads Send for approval, and it opens on its waiting view by the freestyle", async () => {
  setViewport(1440);
  const held = fs({ type: "dialogue", status: "waiting", created_by_name: "Eli", project_id: 50, up_to: 34, thread: [said("Eli", SCRIPT), move("Waiting for the owner's OK.", "held")] });
  server(editor, { "POST /freestyles": [201, held], "GET /freestyles/9": [200, held], "GET /projects/50": [404, { detail: "No such project." }] });
  renderApp("/b/1/videos/new");
  await userEvent.type(await words(), SCRIPT);
  expect(screen.getByText("The owner approves it before anything is spent. You can withdraw it until then.")).toBeInTheDocument();
  await userEvent.click(await screen.findByRole("button", { name: "Send for approval · up to 34 credits" }));
  expect(await screen.findByText("Sent to the owner for approval")).toBeInTheDocument();
  expect(screen.getByText("Waiting for approval")).toBeInTheDocument();
  expect(screen.getByText("up to 34 credits")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Withdraw" })).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/\$|Reed/);
});

test("Song and Narrated are offered but off; Dialogue and One clip work, with the line that says so", async () => {
  setViewport(1440);
  server(editor);
  renderApp("/b/1/videos/new");
  await userEvent.click(await screen.findByRole("button", { name: "Type: Dialogue" }));
  for (const name of ["Song", "Narrated"]) expect(screen.getByRole("menuitemradio", { name: new RegExp(`^${name}`) })).toHaveAttribute("aria-disabled", "true");
  for (const name of ["Dialogue", "One clip"]) expect(screen.getByRole("menuitemradio", { name })).not.toHaveAttribute("aria-disabled");
  expect(screen.getByText("One clip and Dialogue work now. Song and Narrated are coming next.")).toBeInTheDocument();
});

test("From a script: find it, pick a version; its words are read-only, type, style and brand locked, and the send names the version", async () => {
  setViewport(1440);
  const calls = server(editor, { "GET /scripts": [200, [scriptRow, { ...scriptRow, id: 8, title: "Drafty", versions: [version(0, { status: "draft" })] }]], "GET /scripts/7": [200, scriptRow], "POST /freestyles": [201, fs({ type: "dialogue", status: "waiting" })], "GET /freestyles/9": [200, fs()] });
  renderApp("/b/1/videos/new");
  await userEvent.click(await screen.findByRole("radio", { name: "From a script" }));
  expect(screen.getByRole("button", { name: "Pick a script" })).toBeDisabled();
  const list = await screen.findByRole("listbox", { name: "Scripts" });
  expect(within(list).queryByText("Drafty")).toBeNull(); // still being written
  await userEvent.click(within(list).getByRole("option", { name: /Bo tries salmon/ }));
  await userEvent.click(await screen.findByRole("radio", { name: "B · 0:35" }));
  expect(screen.getByText("BO: version 1.")).toBeInTheDocument();
  for (const chip of ["Type: Dialogue, from the script", "Style: House, from the script", "Brand: fomo, from the script"]) expect(screen.getByLabelText(chip)).toBeInTheDocument();
  await vi.waitFor(() => expect(calls.some((c) => c.key === "GET /freestyles/estimate")).toBe(true));
  await userEvent.click(await screen.findByRole("button", { name: "Send for approval · up to 34 credits" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /freestyles")?.body).toEqual({ type: "dialogue", script_id: 7, slot: 1, shape: "9:16" }));
});

test("a version that already has a video: Open it, or Make another at the price the server names", async () => {
  setViewport(1440);
  const calls = server(owner, { "GET /scripts": [200, [scriptRow]], "GET /scripts/7": [200, scriptRow], "POST /freestyles": [409, { detail: { text: "This version already has a video.", project_id: 77, up_to: 50 } }] });
  renderApp("/b/1/videos/new?from=script");
  await userEvent.click(await screen.findByRole("option", { name: /Bo tries salmon/ }));
  await userEvent.click(await screen.findByRole("button", { name: "Make it · up to 34 credits" }));
  expect(await screen.findByRole("link", { name: "Open it" })).toHaveAttribute("href", "/b/1/videos/77");
  await userEvent.click(screen.getByRole("button", { name: "Make another · up to 50 credits" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /freestyles").at(-1)?.body).toEqual({ type: "dialogue", script_id: 7, slot: 0, shape: "9:16", make_another: true }));
});

test("the old addresses: /freestyle and Quick clip open New video; a director-made freestyle opens its video", async () => {
  setViewport(1440);
  server(owner, { "GET /freestyles/9": [200, fs({ type: "dialogue", project_id: 50 })], "GET /projects/50": [200, { id: 50, brand_id: 1, name: SCRIPT, freestyle_id: 9 }] });
  const first = renderApp("/freestyle");
  expect(await screen.findByRole("heading", { name: "What should the director make?" })).toBeInTheDocument();
  first.unmount();
  const second = renderApp("/b/1/clip");
  expect(await screen.findByRole("heading", { name: "What should the director make?" })).toBeInTheDocument();
  second.unmount();
  renderApp("/freestyle/9");
  expect(await screen.findByRole("link", { name: "Videos ›" })).toHaveAttribute("href", "/b/1/videos");
});

test("an older One clip freestyle keeps its page: Enter sends a change, and the server's refusal shows in its words", async () => {
  setViewport(1440);
  const calls = server(editor, { "GET /freestyles/9": [200, fs({ status: "delivered", file_id: 5, created_by_name: "Eli" })], "POST /freestyles/9/messages": [409, { detail: "Wait for the last send to finish, or stop it." }] });
  renderApp("/freestyle/9");
  expect(await screen.findByLabelText("The freestyle")).toHaveAttribute("src", "/api/files/5");
  await userEvent.type(screen.getByLabelText("Tell the director what to change"), "Make it night.{Shift>}{Enter}{/Shift}Rain too.{Enter}");
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /freestyles/9/messages")?.body).toEqual({ text: "Make it night.\nRain too." }));
  expect(await screen.findByText("Wait for the last send to finish, or stop it.")).toBeInTheDocument();
});

test("N opens New video from anywhere but a box being typed in", async () => {
  setViewport(1440);
  server(owner, { "GET /scripts": [200, []] });
  renderApp("/b/1/scripts");
  await screen.findByRole("navigation", { name: "Main" });
  await userEvent.keyboard("n");
  expect(await screen.findByRole("heading", { name: "What should the director make?" })).toBeInTheDocument();
  await userEvent.type(await words(), "no new page");
  expect(screen.getByLabelText("Paste a script, or describe the video")).toHaveValue("no new page");
});
