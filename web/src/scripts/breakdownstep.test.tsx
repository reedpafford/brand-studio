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
  "GET /scripts/7/drafts/0/plan": [404, { detail: "This version has no plan yet." }],
  "GET /scripts/7/drafts/1/plan": [404, { detail: "This version has no plan yet." }],
  "GET /credits/rates": [200, [{ kind: "write-claude", credits_per_unit: 3 }]],
  ...o,
});
function open(v = "") {
  renderApp(`/b/1/scripts/7?step=breakdown${v}`);
}
afterEach(() => vi.unstubAllGlobals());

test("an unplanned version offers Plan the shots at its price, and Next: Cast stays (secondary)", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "POST /scripts/7/drafts/0/breakdown": [201, { id: 90, kind: "write-claude", status: "queued", step: "breakdown", script_id: 7 }] }));
  open();
  expect(await screen.findByRole("heading", { name: "Breakdown · version A" })).toBeInTheDocument();
  expect(screen.getByText("Not planned yet. Plan the shots now, or let each video plan its own when it starts.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Next: Cast" })).toBeEnabled();
  await userEvent.click(screen.getByRole("button", { name: "Plan the shots · up to 6 credits" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/drafts/0/breakdown")).toBe(true));
  // This fake server never says it is running, so the run reads as finished with no plan: it can be tried again.
  expect(await screen.findByText("The breakdown didn't finish.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Try again · up to 6 credits" })).toBeInTheDocument();
});

test("a run in progress shows Planning… and no button", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts/7/drafts/0/breakdown": [200, { breakdown: null, problems: [], seconds: 0, running: true }] }));
  open();
  expect(await screen.findByText(/Planning…/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Plan the shots/ })).toBeNull();
});

test("a planned version is a clip table grouped by scene, with the summary, Plan again asking first, and the Version picker", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts/7/drafts/0/breakdown": [200, plan], "GET /scripts/7": [200, { ...script, versions: [version(0, { has_breakdown: true, estimate_credits: 55.2 }), version(1)] }] }));
  open();
  expect(await screen.findByText("Planned · 1 scene · 1 clip · 4 s · about 56 credits to make (planned)")).toBeInTheDocument(); // credits round up
  const table = screen.getByRole("table", { name: "Clips" });
  expect(within(table).getByRole("rowheader")).toHaveTextContent("Scene 1 · KITCHEN");
  const clip = within(table).getByRole("row", { name: "Clip 1: open the shots" });
  expect(clip).toHaveTextContent("MIA: MIA: Hell no!");
  expect(clip).toHaveTextContent("Mia");
  expect(clip).toHaveTextContent("4 s");
  expect(screen.getByRole("combobox", { name: "Version" })).toHaveValue("0");
  expect(screen.getByTitle("Each video picks its shape")).toHaveTextContent("Shape 9:16 · each video picks its shape");
  // The advice names shot 1.1, so it sits under clip 1, with a dot on that row.
  expect(within(clip).getByLabelText("Has a problem")).toBeInTheDocument();
  expect(clip.nextElementSibling).toHaveTextContent("a slow hook");
  await userEvent.click(screen.getByRole("button", { name: "Plan again · up to 6 credits" }));
  expect(await screen.findByRole("alertdialog", { name: "Plan again?" })).toBeInTheDocument();
});

test("a row opens the shot editor, with its advice and a way back", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts/7/drafts/0/breakdown": [200, plan], "GET /scripts/7": [200, { ...script, versions: [version(0, { has_breakdown: true }), version(1)] }] }));
  open();
  await userEvent.click(await screen.findByRole("row", { name: "Clip 1: open the shots" }));
  expect(await screen.findByText("Advice (1)")).toBeInTheDocument();
  expect(screen.getByText("Mia · cast in Cast")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Back to the breakdown" }));
  expect(await screen.findByRole("table", { name: "Clips" })).toBeInTheDocument();
});

test("the Version picker opens version B's breakdown", async () => {
  setViewport(1440);
  fakeServer(base());
  open();
  await userEvent.selectOptions(await screen.findByRole("combobox", { name: "Version" }), "1");
  expect(await screen.findByRole("heading", { name: "Breakdown · version B" })).toBeInTheDocument();
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
  expect(dialog).toHaveTextContent("Each video will plan its own shots when it starts.");
  await userEvent.click(within(dialog).getByRole("button", { name: "Remove" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /scripts/7/drafts/0/breakdown")).toBe(true));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /scripts/7/drafts/0/breakdown")?.body).toEqual(plan.breakdown));
});

test("a plan made for older words says so with Plan again; in the shots its advice keep can be undone", async () => {
  setViewport(1440);
  const advice = plan.problems[0];
  const calls = fakeServer(base({
    "GET /scripts/7/drafts/0/breakdown": [200, { ...plan, stale: true, kept: [advice] }],
    "GET /scripts/7": [200, { ...script, versions: [version(0, { has_breakdown: true }), version(1)] }],
    "DELETE /scripts/7/drafts/0/breakdown/keep": [200, { ...plan, kept: [] }],
  }));
  open();
  expect(await screen.findByText("Made for an older script.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "More for this plan" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Edit the shots" }));
  expect(await screen.findByText("Advice (0)")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Undo keep/, hidden: true }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /scripts/7/drafts/0/breakdown/keep")).toBe(true));
});

test("Keep as is under a clip's problem calls the plan's keep route; Open the shots opens the editor", async () => {
  setViewport(1440);
  const calls = fakeServer(base({
    "GET /scripts/7/drafts/0/breakdown": [200, plan],
    "GET /scripts/7": [200, { ...script, versions: [version(0, { has_breakdown: true }), version(1)] }],
    "POST /scripts/7/drafts/0/breakdown/keep": [200, plan],
  }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Keep as is" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts/7/drafts/0/breakdown/keep")?.body).toEqual({ problem: plan.problems[0] }));
  await userEvent.click(screen.getByRole("button", { name: "Open the shots" }));
  expect(await screen.findByText("Advice (1)")).toBeInTheDocument();
});

// S6 (#934): the owner's scene plan on a version, behind the breakdown's ⋯ menu.
const scenes = [{ id: "s1", part: "Hook", place: "Kitchen", time: "Morning", cast_ids: [], lines: [{ n: 1, text: "MIA: Hell no!", action: "Mia pushes the bowl away.", star: false }] }];
const scenePlan = (o: object = {}) => ({ status: "ready", approved_by: null, approved_at: null, source: "claude", structure: null, cast: [], scenes, summary: null, advice: [], job: null, estimate_credits: 3, approve_credits: 3, change_scene_credits: 3, stop: null, ...o });

test("Plan the scenes first opens the scene plan: none yet says it's optional, and Make the plan is priced and starts it", async () => {
  setViewport(390);
  const calls = fakeServer(base({ "POST /scripts/7/drafts/0/plan": [201, { id: 91, kind: "write-claude", status: "queued" }] }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "More for this plan" }));
  await userEvent.click(await screen.findByRole("menuitem", { name: "Plan the scenes first" }));
  expect(await screen.findByText(/Skip it and it's made when an editor starts/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Make the plan · up to 3 credits" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/drafts/0/plan")).toBe(true));
});

test("a ready scene plan puts Approve the plan in the header; it approves the scene plan", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "GET /scripts/7/drafts/0/breakdown": [200, plan], "GET /scripts/7": [200, { ...script, versions: [version(0, { has_breakdown: true }), version(1)] }], "GET /scripts/7/drafts/0/plan": [200, scenePlan()], "POST /scripts/7/drafts/0/plan/approve": [200, scenePlan({ status: "approved" })] }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Approve the plan" }));
  await vi.waitFor(() => expect(calls.map((c) => c.key)).toContain("POST /scripts/7/drafts/0/plan/approve"));
  expect(await screen.findByText("Plan approved for version A.")).toBeInTheDocument();
});

test("a preview made before the owner's plan says Made for an older plan, with Plan again", async () => {
  setViewport(1440);
  const older = { ...script, versions: [version(0, { preview_older_plan: true, has_breakdown: true }), version(1)] };
  const calls = fakeServer(base({ "GET /scripts/7": [200, older], "GET /scripts/7/drafts/0/breakdown": [200, plan], "POST /scripts/7/drafts/0/breakdown": [201, { id: 92, kind: "write-claude", status: "queued", step: "breakdown", script_id: 7 }] }));
  open();
  const banner = (await screen.findByText("Made for an older plan.")).closest("[role]") ?? document.body;
  await userEvent.click(within(banner as HTMLElement).getAllByRole("button", { name: "Plan again · up to 6 credits" })[0]);
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/drafts/0/breakdown")).toBe(true));
});
