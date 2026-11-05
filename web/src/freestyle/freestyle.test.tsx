import { screen } from "@testing-library/react";
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
  expect(await screen.findByRole("list", { name: "Conversation with the director" })).toBeInTheDocument(); // its video's chat (S3)
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
  expect(await words()).toHaveFocus(); // the box is ready to type in on load
  await userEvent.type(await words(), "no new page");
  expect(screen.getByLabelText("Paste a script, or describe the video")).toHaveValue("no new page");
});
