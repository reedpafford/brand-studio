import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const owner = { id: 1, email: "reed@b.co", name: "Reed", role: "owner", workspace_id: 1 };
const script = (o: object = {}) => ({
  id: 7, brand_id: 1, title: "Bo tries salmon", description: "x", reference_id: null, reel_imported: false, new_lines: false, published: false, status: "draft", created_by_id: 1, created_by_name: "Reed", created_at: "2026-10-24T10:00:00Z", versions_left: 0, notes: "", reference_replace: "", cast: [],
  versions: [{ slot: 0, status: "draft", title: "x", seconds: 0, project_id: null, text: "MIA: Hell no!\nBO: Salmon?", words: 5, target_seconds: null, premise: "", changes: [], problems: [], has_breakdown: false, approved_at: null }], ...o,
});
const mark = (o: object = {}) => ({ id: 1, key: "a", kind: "camera", line: 1, quote: "Hell no!", start: 0, end: 8, placement: "after", text: "Slow push-in on Mia's face.", screen_id: null, reason: "It is the turn.", status: "pending", ...o });
const base = (o: Record<string, [number, unknown]> = {}): Record<string, [number, unknown]> => ({
  "GET /auth/me": [200, owner],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /references": [200, []],
  "GET /projects": [200, []],
  "GET /jobs": [200, []],
  "GET /scripts/7": [200, script()],
  "GET /scripts/7/drafts/0/suggestions": [200, []],
  "GET /scripts/7/drafts/0/notes": [200, []],
  "GET /scripts/7/drafts/0/enhance/estimate": [200, { credits: 4 }],
  ...o,
});
function open() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/b/1/scripts/7?step=directions"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
afterEach(() => vi.unstubAllGlobals());

test("Directions opens with its card, the price on Suggest directions, and Next to skip it", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "POST /scripts/7/drafts/0/enhance": [201, { id: 90, kind: "write-claude", status: "queued", step: "enhance", script_id: 7, created_at: new Date().toISOString() }] }));
  open();
  expect(await screen.findByText("Claude suggests camera moves, movement, reactions and where brand screens show. Your words never change.")).toBeInTheDocument();
  expect(await screen.findByRole("button", { name: "Next: Variations" })).toBeEnabled();
  await userEvent.click(await screen.findByRole("button", { name: "Suggest directions · 4 credits" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/drafts/0/enhance")).toBe(true));
});

test("suggestions sit under their line with Accept and Reject; Add 1 direction shows only once one is accepted, and Next is still there", async () => {
  setViewport(1440);
  const calls = fakeServer(base({
    "GET /scripts/7/drafts/0/suggestions": [200, [mark(), mark({ id: 2, key: "b", kind: "reaction", line: 2, text: "Bo blinks twice.", status: "accepted" })]],
    "POST /scripts/7/drafts/0/suggestions/1/accept": [200, mark({ status: "accepted" })],
    "POST /scripts/7/drafts/0/apply": [200, script()],
  }));
  open();
  expect(await screen.findByText(/Slow push-in on Mia's face\./)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Add 1 direction" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "Next: Variations" })).toBeEnabled();
  await userEvent.click(screen.getByRole("button", { name: "Accept: Slow push-in on Mia's face." }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/drafts/0/suggestions/1/accept")).toBe(true));
  await userEvent.click(screen.getByRole("button", { name: "Add 1 direction" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/drafts/0/apply")).toBe(true));
  expect(await screen.findByText("Added 1 direction.")).toBeInTheDocument();
});

test("Undo after adding saves the earlier words back", async () => {
  setViewport(1440);
  const calls = fakeServer(base({
    "GET /scripts/7/drafts/0/suggestions": [200, [mark({ status: "accepted" })]],
    "POST /scripts/7/drafts/0/apply": [200, script()],
    "PUT /scripts/7/drafts/0": [200, script()],
  }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Add 1 direction" }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /scripts/7/drafts/0")?.body).toEqual({ text: "MIA: Hell no!\nBO: Salmon?" }));
});

test("an editor past the week's allowance can't press Suggest directions", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /auth/me": [200, { ...owner, id: 2, role: "editor" }], "GET /scripts/7": [200, script({ created_by_id: 2 })], "GET /credits/me": [200, { quick_clip_credits_used: 145, quick_clip_credits_allowed: 145 }] }));
  open();
  await vi.waitFor(() => expect(screen.getByRole("button", { name: /^Suggest directions/ })).toHaveAccessibleDescription("You've used this week's 145 credits. It resets on Monday."));
  expect(screen.getByRole("button", { name: /^Suggest directions/ })).toBeDisabled();
});

test("Directions waits for the script's words", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts/7": [200, script({ versions: [{ ...script().versions[0], text: "", words: 0 }] })] }));
  open();
  await screen.findByRole("heading", { name: "Bo tries salmon", level: 1 });
  expect(screen.queryByText("Claude suggests camera moves, movement, reactions and where brand screens show. Your words never change.")).toBeNull();
});

test("the words stay editable from Directions: Edit the script opens the Script step, with a note once suggestions exist", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts/7/drafts/0/suggestions": [200, [mark()]] }));
  open();
  expect(await screen.findByText("Changing the words clears these suggestions; ask Claude again after.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Edit the script" }));
  expect(await screen.findByLabelText("Your script")).toBeInTheDocument(); // the Script step's editor
});

test("no Edit the script on a published script", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts/7": [200, script({ published: true })] }));
  open();
  await screen.findByText("Claude suggests camera moves, movement, reactions and where brand screens show. Your words never change.");
  expect(screen.queryByRole("button", { name: "Edit the script" })).toBeNull();
});

test("with nothing accepted there is no Add button, and Next just goes on", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts/7/drafts/0/suggestions": [200, [mark()]] }));
  open();
  await screen.findByText(/Slow push-in on Mia's face\./);
  expect(screen.queryByRole("button", { name: /^Add \d+ direction/ })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Next: Variations" }));
  expect(await screen.findByRole("radio", { name: "None" })).toBeInTheDocument(); // the Variations step, no question asked
});

test("Next with accepted directions not added asks once, and Stay keeps you here; Leave goes on", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts/7/drafts/0/suggestions": [200, [mark({ status: "accepted" }), mark({ id: 2, key: "b", kind: "reaction", line: 2, text: "Bo blinks twice.", status: "accepted" })]] }));
  open();
  await screen.findByText(/Slow push-in on Mia's face\./);
  await userEvent.click(screen.getByRole("button", { name: "Next: Variations" }));
  expect(await screen.findByRole("alertdialog", { name: "Leave without adding 2 directions?" })).toBeInTheDocument();
  expect(screen.getByText("They stay accepted but are not added to the script. Leaving doesn't add them.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Stay" }));
  expect(screen.getByRole("button", { name: "Add 2 directions" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Next: Variations" }));
  await userEvent.click(screen.getByRole("button", { name: "Leave" }));
  expect(await screen.findByRole("radio", { name: "None" })).toBeInTheDocument();
});
