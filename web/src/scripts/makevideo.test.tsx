import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { editor } from "../test/people";
import { renderApp } from "../test/render";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

// Make a video from a script (v5 E_EditorScripts, E_ScriptMakeVideo): any finished version, no Publish first.
const at = "2026-11-02T10:00:00Z";
const v = (slot: number, o: object = {}) => ({ slot, status: "approved", title: "", seconds: 32 + slot * 3, project_id: null, text: `BO: version ${slot}.`, estimate_credits: 170.2 + slot * 6, ...o });
const script = { id: 7, brand_id: 1, title: "Bo tries salmon", kind: "story", look: "house", published: true, created_by_id: 1, created_by_name: "Reed", created_at: at, versions: [v(0), v(1), v(2, { project_id: 70 })], versions_left: 2 };
afterEach(() => vi.unstubAllGlobals());

test("an editor's ready row has Make a video: the panel picks a version (its planned price) and shape, and sends it for approval", async () => {
  setViewport(1440);
  const calls = fakeServer({
    "GET /auth/me": [200, editor],
    "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
    "GET /looks": [200, [{ id: "house", name: "House", blurb: "", on: true, own_sample: false, lanes: [] }]],
    "GET /jobs": [200, []],
    "GET /scripts": [200, [script]],
    "GET /scripts/7": [200, script],
    "GET /freestyles/estimate": [200, { credits: 187.4 }],
    "POST /freestyles": [201, { id: 9, brand_id: 1, project_id: 80, status: "waiting", thread: [] }],
  });
  renderApp("/b/1/scripts");
  expect(await screen.findByRole("link", { name: "New video from a script" })).toHaveAttribute("href", "/b/1/videos/new?from=script");
  await userEvent.click(await screen.findByRole("button", { name: "Make a video from Bo tries salmon" }));
  const panel = await screen.findByRole("dialog", { name: "Make a video from Bo tries salmon" });
  expect(await within(panel).findByText("about 177 credits (planned)")).toBeInTheDocument();
  expect(within(panel).getByText("0:38 · has a video")).toBeInTheDocument();
  expect(within(panel).getByRole("radio", { name: /^A/ })).toHaveFocus(); // it opens on the version picker, not Close
  await userEvent.click(within(panel).getByRole("radio", { name: /^B/ }));
  await userEvent.click(within(panel).getByRole("radio", { name: "1:1" }));
  await userEvent.click(await within(panel).findByRole("button", { name: "Send for approval · up to 188 credits" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /freestyles")?.body).toEqual({ type: "dialogue", script_id: 7, slot: 1, shape: "1:1" }));
  expect(document.body.textContent).not.toMatch(/\$/);
});
