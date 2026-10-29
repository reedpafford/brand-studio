import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";
import { owner } from "../test/people";

const version = (slot: number, o: object = {}) => ({ slot, status: "approved", title: "x", seconds: 0, project_id: null, text: "MIA: Hell no!", words: 3, target_seconds: null, premise: "", changes: [], problems: [], has_breakdown: false, approved_at: null, estimate_credits: 0, clips: 0, ...o });
const script = {
  id: 7, brand_id: 1, title: "Bo tries salmon", description: "x", reference_id: null, reel_imported: false, new_lines: false, published: false, status: "draft", created_by_id: 1, created_by_name: "Reed", created_at: "2026-10-24T10:00:00Z", versions_left: 0, notes: "", reference_replace: "", cast: [],
  versions: [version(0), version(1)],
};
const plan = {
  breakdown: { hook: "Hook.", scenes: [{ id: 1, heading: "KITCHEN", look: "", shots: [{ id: "1.1", seconds: 4, camera: "close-up", description: "Mia says no", character_ids: ["slot:31"], place_id: null, screen_ids: [], script_lines: [1], line: "MIA: Hell no!", speaker: "MIA", clip_id: "c1" }] }], clips: [{ id: "c1", seconds: 4, shot_ids: ["1.1"] }] },
  problems: ["Advice: shot 1.1: a slow hook"], seconds: 4, running: false, kept: [] as string[], stale: false,
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
  renderApp("/b/1/scripts/7?step=breakdown");
}
afterEach(() => vi.unstubAllGlobals());

test("an unplanned version offers the breakdown at its price, and Next: Publish stays the amber button", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "POST /scripts/7/drafts/0/breakdown": [201, { id: 90, kind: "write-claude", status: "queued", step: "breakdown", script_id: 7 }] }));
  open();
  await userEvent.click(await screen.findByRole("tab", { name: "Shots" }));
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
  await userEvent.click(await screen.findByRole("tab", { name: "Shots" }));
  expect(await screen.findByText(/Planning shots…/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Make the breakdown/ })).toBeNull();
});

test("each version has its own tab; a planned one shows its plan, with advice closed, and no video-only row", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts/7/drafts/0/breakdown": [200, plan], "GET /scripts/7": [200, { ...script, versions: [version(0, { has_breakdown: true, estimate_credits: 55.2 }), version(1)] }] }));
  open();
  expect(await screen.findByRole("tab", { name: "A · Planned" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "B" })).toBeInTheDocument();
  expect(await screen.findByText("Planned · 4 s · 1 clip · about 56 credits to make")).toBeInTheDocument(); // credits round up
  expect(screen.getByText("Advice (1)")).toBeInTheDocument();
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

test("a plan made for older words says so, with Make it again; its advice can be kept and the keep undone", async () => {
  setViewport(1440);
  const advice = plan.problems[0];
  const calls = fakeServer(base({
    "GET /scripts/7/drafts/0/breakdown": [200, { ...plan, stale: true, kept: [advice] }],
    "GET /scripts/7": [200, { ...script, versions: [version(0, { has_breakdown: true }), version(1)] }],
    "DELETE /scripts/7/drafts/0/breakdown/keep": [200, { ...plan, kept: [] }],
  }));
  open();
  expect(await screen.findByText("This plan was made for older words. Make it again so the shots match.")).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Make it again · 6 credits" })).toHaveLength(1); // the banner's, not a second one in the bar
  expect(screen.getByText("Advice (0)")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Undo keep/, hidden: true }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /scripts/7/drafts/0/breakdown/keep")).toBe(true));
});

test("Keep anyway on a plan's advice calls the plan's keep route", async () => {
  setViewport(1440);
  const calls = fakeServer(base({
    "GET /scripts/7/drafts/0/breakdown": [200, plan],
    "GET /scripts/7": [200, { ...script, versions: [version(0, { has_breakdown: true }), version(1)] }],
    "POST /scripts/7/drafts/0/breakdown/keep": [200, plan],
  }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: /Keep anyway/, hidden: true }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts/7/drafts/0/breakdown/keep")?.body).toEqual({ problem: plan.problems[0] }));
});

// S6 (#934): the owner's scene plan on a version, before its shots preview.
const scenes = [{ id: "s1", part: "Hook", place: "Kitchen", time: "Morning", cast_ids: [], lines: [{ n: 1, text: "MIA: Hell no!", action: "Mia pushes the bowl away.", star: false }] }];
const scenePlan = (o: object = {}) => ({ status: "ready", approved_by: null, approved_at: null, source: "claude", structure: null, cast: [], scenes, summary: null, advice: [], job: null, estimate_credits: 3, approve_credits: 3, change_scene_credits: 3, stop: null, ...o });

test("a version opens on its scene plan: none yet says it's optional, and Make the plan is priced and starts it", async () => {
  setViewport(390);
  const calls = fakeServer(base({ "GET /credits/rates": [200, [{ kind: "write-claude", credits_per_unit: 3 }]], "GET /scripts/7/drafts/0/plan": [404, { detail: "This version has no plan yet." }], "POST /scripts/7/drafts/0/plan": [201, { id: 91, kind: "write-claude", status: "queued" }] }));
  open();
  expect(await screen.findByText(/Skip it and it's made when an editor starts/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Next: Publish" })).toBeEnabled();
  await userEvent.click(screen.getByRole("button", { name: "Make the plan · 3 credits" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/drafts/0/plan")).toBe(true));
});

test("a ready plan has no Change this scene… or Earlier plans here; Approve the plan is free and moves on to Shots", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "GET /credits/rates": [200, []], "GET /scripts/7/drafts/0/plan": [200, scenePlan({ earlier: [{ id: 1, version: 1, source: "claude", made_at: null }] })], "POST /scripts/7/drafts/0/plan/approve": [200, scenePlan({ status: "approved" })] }));
  open();
  expect(await screen.findByLabelText("Scene 1")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Change this scene/ })).toBeNull();
  expect(screen.queryByText(/Earlier plans/)).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: /^Approve the plan/ }));
  await vi.waitFor(() => expect(calls.map((c) => c.key)).toContain("POST /scripts/7/drafts/0/plan/approve"));
  expect(await screen.findByRole("tab", { name: "Shots", selected: true })).toBeInTheDocument();
});

test("a preview made before the owner's plan says Made for an older plan, with Make the preview again", async () => {
  setViewport(1440);
  const older = { ...script, versions: [version(0, { preview_older_plan: true }), version(1)] };
  const calls = fakeServer(base({ "GET /scripts/7": [200, older], "GET /scripts/7/drafts/0/breakdown": [200, plan], "POST /scripts/7/drafts/0/breakdown": [201, { id: 92, kind: "write-claude", status: "queued", step: "breakdown", script_id: 7 }] }));
  open();
  expect(await screen.findByText("Made for an older plan.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Make the preview again · 6 credits" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/drafts/0/breakdown")).toBe(true));
});
