import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const owner = { id: 1, email: "reed@b.co", name: "Reed", role: "owner", workspace_id: 1 };
const version = (slot: number, o: object = {}) => ({ slot, status: "approved", title: "x", seconds: 0, project_id: null, text: "MIA: Hell no!", words: 3, target_seconds: null, premise: "", changes: [], problems: [], has_breakdown: false, approved_at: null, estimate_credits: 0, clips: 0, ...o });
const script = {
  id: 7, brand_id: 1, title: "Bo tries salmon", description: "x", reference_id: null, reel_imported: false, new_lines: false, published: false, status: "draft", created_by_id: 1, created_by_name: "Reed", created_at: "2026-10-24T10:00:00Z", versions_left: 0, notes: "", reference_replace: "", cast: [],
  versions: [version(0), version(1)],
};
const plan = {
  breakdown: { hook: "Hook.", scenes: [{ id: 1, heading: "KITCHEN", look: "", shots: [{ id: "1.1", seconds: 4, camera: "close-up", description: "Mia says no", character_ids: ["slot:31"], place_id: null, screen_ids: [], script_lines: [1], line: "MIA: Hell no!", speaker: "MIA", clip_id: "c1" }] }], clips: [{ id: "c1", seconds: 4, shot_ids: ["1.1"] }] },
  problems: ["Advice: shot 1.1: a slow hook"], seconds: 4, running: false,
};
const base = (o: Record<string, [number, unknown]> = {}): Record<string, [number, unknown]> => ({
  "GET /auth/me": [200, owner],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /references": [200, []],
  "GET /projects": [200, []],
  "GET /jobs": [200, []],
  "GET /scripts/7": [200, script],
  "GET /scripts/7/cast": [200, [{ id: 31, role: "Mia", kind: "Main", appears_in: [0], description: "", position: 0, library_item_id: null, sheet_file_id: null, locked: false }]],
  "GET /scripts/7/drafts/0/breakdown": [200, { breakdown: null, problems: [], seconds: 0, running: false }],
  "GET /scripts/7/drafts/0/breakdown/estimate": [200, { credits: 6 }],
  "GET /scripts/7/drafts/1/breakdown": [200, { breakdown: null, problems: [], seconds: 0, running: false }],
  "GET /scripts/7/drafts/1/breakdown/estimate": [200, { credits: 6 }],
  "GET /library/character": [200, []],
  "GET /library/place": [200, []],
  "GET /library/prop": [200, []],
  "GET /brands/1/screens": [200, []],
  ...o,
});
function open() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/b/1/scripts/7?step=breakdown"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
afterEach(() => vi.unstubAllGlobals());

test("an unplanned version offers the breakdown at its price, and Next: Publish stays the amber button", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "POST /scripts/7/drafts/0/breakdown": [201, { id: 90, kind: "write-claude", status: "queued", step: "breakdown", script_id: 7 }] }));
  open();
  expect(await screen.findByText("Plan the shots now, or let it happen when an editor starts this version.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Next: Publish" })).toBeEnabled();
  await userEvent.click(screen.getByRole("button", { name: "Make the breakdown · 6 credits" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/drafts/0/breakdown")).toBe(true));
  // This fake server never says it is running, so the run reads as finished with no plan: it can be tried again.
  expect(await screen.findByText("The breakdown didn't finish.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Try again · 6 credits" })).toBeInTheDocument();
});

test("a run in progress shows Planning shots and no button", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts/7/drafts/0/breakdown": [200, { breakdown: null, problems: [], seconds: 0, running: true }] }));
  open();
  expect(await screen.findByText(/Planning shots…/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Make the breakdown/ })).toBeNull();
});

test("each version has its own tab; a planned one shows its plan, with advice closed and no Keep anyway, and no video-only row", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts/7/drafts/0/breakdown": [200, plan], "GET /scripts/7": [200, { ...script, versions: [version(0, { has_breakdown: true, estimate_credits: 55.2 }), version(1)] }] }));
  open();
  expect(await screen.findByRole("tab", { name: "A · Planned" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "B" })).toBeInTheDocument();
  expect(await screen.findByText("Planned · 4 s · 1 clip · about 56 credits to make")).toBeInTheDocument(); // credits round up
  expect(screen.getByText("Advice (1)")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Keep anyway/ })).toBeNull();
  expect(screen.queryByText("Where will it be posted?")).toBeNull();
  expect(screen.getByText("Mia · cast at Assets")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Make it again · 6 credits" }));
  expect(await screen.findByRole("alertdialog", { name: "Make the breakdown again?" })).toBeInTheDocument();
});

test("Reed can remove a plan after a confirm, and Undo puts the same plan back", async () => {
  setViewport(1440);
  const calls = fakeServer(base({
    "GET /scripts/7/drafts/0/breakdown": [200, plan],
    "GET /scripts/7": [200, { ...script, versions: [version(0, { has_breakdown: true }), version(1)] }],
    "DELETE /scripts/7/drafts/0/breakdown": [200, { breakdown: null, problems: [], seconds: 0, running: false }],
    "PUT /scripts/7/drafts/0/breakdown": [200, plan],
  }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "More for this plan" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Remove the plan" }));
  const dialog = await screen.findByRole("alertdialog", { name: "Remove this plan?" });
  expect(dialog).toHaveTextContent("An editor's video will plan its shots when they start.");
  await userEvent.click(within(dialog).getByRole("button", { name: "Remove" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /scripts/7/drafts/0/breakdown")).toBe(true));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /scripts/7/drafts/0/breakdown")?.body).toEqual(plan.breakdown));
});
