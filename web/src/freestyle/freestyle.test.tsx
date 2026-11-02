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
const held = fs({ status: "waiting", created_by_name: "Eli", thread: [said("Eli", SCRIPT), move("Waiting for the owner's OK.", "held")] });
function server(me: object, routes: Record<string, [number, unknown]> = {}) {
  return fakeServer({
    "GET /auth/me": [200, me],
    "GET /brands": [200, [{ id: 1, name: "fomo", colours: [] }]],
    "GET /looks": [200, [look("house", "House"), look("pixar", "Disney Pixar"), look("zack", "Zack D", false)]],
    "GET /jobs": [200, []],
    "GET /freestyles": [200, []],
    "GET /freestyles/estimate": [200, { credits: 27 }],
    ...routes,
  });
}
afterEach(() => vi.unstubAllGlobals());

async function write(text = SCRIPT) {
  await userEvent.type(await screen.findByLabelText("Paste a script, or describe the clip"), text);
}

test("Reed makes a One clip freestyle: Enter sends it with the picked settings and it runs at once", async () => {
  setViewport(1440);
  const calls = server(owner, { "POST /freestyles": [201, fs()], "GET /freestyles/9": [200, fs()], "GET /freestyles?everyone=true": [200, [{ ...fs(), created_by_name: "Eli" }]] });
  renderApp("/freestyle");
  await screen.findByRole("option", { name: "Disney Pixar" });
  await userEvent.selectOptions(screen.getByLabelText("Style"), "Disney Pixar");
  await userEvent.selectOptions(screen.getByLabelText("Brand"), "fomo");
  expect(within(screen.getByLabelText("Style")).queryByRole("option", { name: "Zack D" })).toBeNull(); // only the switched-on looks
  await write();
  expect(await screen.findByText("up to 27 credits")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument();
  await userEvent.keyboard("{Enter}");
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /freestyles")?.body).toEqual({ type: "one_clip", look: "pixar", shape: "9:16", brand_id: 1, text: SCRIPT }));
  const top = await screen.findByRole("region", { name: "This freestyle" });
  expect(within(top).getByText("Working")).toBeInTheDocument();
  expect(within(screen.getByRole("list", { name: "Thread" })).getByText("Making the clip.")).toBeInTheDocument();
  expect(within(screen.getByRole("list", { name: "Thread" })).getByText("Disney Pixar")).toBeInTheDocument(); // the first message's tags
  await userEvent.click(screen.getByRole("button", { name: "Everyone's" }));
  expect(await screen.findByText(/Working · today · Eli/)).toBeInTheDocument();
});

test("an editor's send reads Send for approval, waits for Reed, and Withdraw takes it back", async () => {
  setViewport(1440);
  const calls = server(editor, { "POST /freestyles": [201, held], "GET /freestyles/9": [200, held], "POST /freestyles/9/withdraw": [200, { ...held, status: "withdrawn" }] });
  renderApp("/freestyle");
  expect(await screen.findByText("Each send goes to the owner first. Nothing is spent until they say yes.")).toBeInTheDocument();
  expect(screen.queryByRole("group", { name: "Whose" })).toBeNull(); // Mine | Everyone's is Reed's
  await write();
  await userEvent.click(screen.getByRole("button", { name: "Send for approval" }));
  const top = await screen.findByRole("region", { name: "This freestyle" });
  expect(await within(top).findByText("Waiting for approval")).toBeInTheDocument();
  expect(within(top).getByText("up to 27 credits")).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/\$/);
  await userEvent.click(within(top).getByRole("button", { name: "Withdraw" }));
  expect(await within(top).findByText("Withdrawn")).toBeInTheDocument();
  expect(calls.some((c) => c.key === "POST /freestyles/9/withdraw")).toBe(true);
});

test("a later change: the settings are read-only, Shift+Enter makes a new line, and a busy send's words show", async () => {
  setViewport(1440);
  const done = fs({ status: "delivered", file_id: 5, created_by_name: "Eli" });
  const calls = server(editor, { "GET /freestyles/9": [200, done], "POST /freestyles/9/messages": [409, { detail: "Wait for the last send to finish, or stop it." }] });
  renderApp("/freestyle/9");
  const box = await screen.findByLabelText("Ask for a change");
  expect(screen.queryByLabelText("Type")).toBeNull();
  expect(within(screen.getByRole("form", { name: "Your change" })).getByText("Disney Pixar")).toBeInTheDocument();
  await userEvent.type(box, "Make it night.{Shift>}{Enter}{/Shift}Rain too.{Enter}");
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /freestyles/9/messages")?.body).toEqual({ text: "Make it night.\nRain too." }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Wait for the last send to finish, or stop it.");
});

test("Dialogue, Song and Narrated are offered but off, with the line that One clip works now", async () => {
  setViewport(390);
  server(editor);
  renderApp("/freestyle");
  const type = await screen.findByLabelText("Type");
  for (const name of ["Dialogue", "Song", "Narrated"]) expect(within(type).getByRole("option", { name })).toBeDisabled();
  expect(within(type).getByRole("option", { name: "One clip" })).toBeEnabled();
  expect(type).toHaveValue("one_clip");
  expect(screen.getByText("Dialogue, Song and Narrated are coming next; One clip works now.")).toBeInTheDocument();
});

test("Stop shows while it's being made and stops it", async () => {
  setViewport(1440);
  const calls = server(owner, { "GET /freestyles/9": [200, fs()], "POST /freestyles/9/stop": [200, fs({ status: "stopped" })] });
  renderApp("/freestyle/9");
  const top = await screen.findByRole("region", { name: "This freestyle" });
  await userEvent.click(await within(top).findByRole("button", { name: "Stop" }));
  expect(await within(top).findByText("Stopped")).toBeInTheDocument();
  expect(within(top).queryByRole("button", { name: "Stop" })).toBeNull();
  expect(calls.some((c) => c.key === "POST /freestyles/9/stop")).toBe(true);
});

test("once delivered it plays, and Download MP4 saves the file", async () => {
  setViewport(1440);
  server(owner, { "GET /freestyles/9": [200, fs({ status: "delivered", file_id: 5 })] });
  renderApp("/freestyle/9");
  expect(await screen.findByLabelText("The freestyle")).toHaveAttribute("src", "/api/files/5");
  const download = screen.getByRole("link", { name: "Download MP4" });
  expect(download).toHaveAttribute("href", "/api/files/5");
  expect(download).toHaveAttribute("download", "mia-the-market-opened-at-nine.mp4");
});

test("the rail and the phone tabs have Freestyle at /freestyle, and the old Quick clip address opens it", async () => {
  setViewport(1440);
  server(owner, { "GET /scripts": [200, []] });
  const { unmount } = renderApp("/b/1/clip");
  expect(await screen.findByRole("heading", { name: "Freestyle" })).toBeInTheDocument();
  expect(within(screen.getByRole("navigation", { name: "Main" })).getByRole("link", { name: "Freestyle" })).toHaveAttribute("aria-current", "page");
  unmount();
  setViewport(390);
  renderApp("/b/1/scripts");
  const tabs = await screen.findByRole("navigation", { name: "Tabs" });
  expect(within(tabs).getByRole("link", { name: "Freestyle" })).toHaveAttribute("href", "/freestyle");
});
