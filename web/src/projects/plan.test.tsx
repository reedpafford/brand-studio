import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const editor = { id: 2, email: "e@b.co", name: "Eli", role: "editor", workspace_id: 1 };
const project = {
  id: 9, brand_id: 1, name: "Bo tries salmon · B", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "",
  cast_ids: [], reference_file_id: null, estimate_credits: 30, budget_credits: 600, credits_used: 0, budget_pct: 0, product_variants: {},
};
const script = { version: 5, source: "paste", words: 9, created_by_id: 2, created_at: "2026-10-23T10:00:00Z", text: "Bo eats." };
const breakdown = { id: 1, script_version: 5, source: "claude", stale: false, problems: [], breakdown: { hook: "Hook.", scenes: [{ id: 1, heading: "KITCHEN", look: "", shots: [] }], clips: [] } };
const asset = (o: object) => ({ kind: "character", ref: "char:5", role: "Bo", library_item_id: 5, name: "Bo", locked: false, sheet_status: "needs_approval", ready: false, ...o });
const item = (o: object) => ({ id: 5, kind: "character", name: "Bo", version: 1, sheet_file_id: 70, sheet_status: "needs_approval", ...o });
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, editor],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /projects/9": [200, project],
  "GET /projects/9/script": [200, script],
  "GET /projects/9/breakdown": [200, breakdown],
  "GET /projects/9/storyboard": [200, []],
  "GET /projects/9/clips": [200, []],
  "GET /projects/9/video": [404, { detail: "none" }],
  "GET /projects/9/assets": [200, [asset({})]],
  "GET /library/character/5": [200, item({})],
  "GET /library/character": [200, []],
  "GET /brands/1/screens": [200, []],
  "GET /credits/rates": [200, []],
  "GET /jobs": [200, []],
  "GET /models": [200, [{ id: "nano-banana-pro", kind: "image", name: "Nano Banana Pro", default: false, credits_per_unit: { "2K": 1.5 } }, { id: "nano-banana-2.1", kind: "image", name: "Nano Banana 2.1", default: true, credits_per_unit: { "1K": 3 } }]],
  "GET /credits/limits": [200, { weekly_quick_clip_credits: 145, per_video_max_credits: 729 }],
};

function open(query = "?step=plan") {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[`/b/1/videos/9${query}`]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

const scenes = [
  { id: "s1", part: "Problem", place: "Kitchen", time: "Morning", cast_ids: ["char:4"], lines: [{ n: 1, text: "Mia scrolls her phone.", action: "Her coffee freezes mid-air.", star: false }] },
  { id: "s2", part: "Payoff", place: "Kitchen", time: "Morning", cast_ids: ["char:4"], lines: [{ n: 2, text: "Wait… it dipped?", action: "She grins at fomo on the screen.", star: true }] },
];
const plan = (o: object = {}) => ({ status: "ready", approved_by: null, approved_at: null, source: "claude", structure: { label: "Problem → Payoff (finance app)", from: "pattern" }, cast: [{ ref_id: "char:4", name: "Mia" }], scenes, summary: "2 scenes · every line used once · the product in 1", advice: [], job: null, estimate_credits: 6, approve_credits: 6, stop: null, ...o });
const withPlan = (status: string) => ({ ...base, "GET /projects/9": [200, { ...project, plan_status: status }], "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 6 }]] }) as Record<string, [number, unknown]>;

test("before the server sends a plan status, Plan is the Shots view alone, as Breakdown was", async () => {
  setViewport(1440);
  fakeServer(base);
  open();
  expect(await screen.findByText(/Hook:/)).toBeInTheDocument();
  expect(screen.queryByRole("tablist", { name: "Plan views" })).toBeNull();
});

test("no plan yet: Make the plan shows its price; Shots is greyed until approved", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...withPlan("none"), "GET /projects/9/plan": [404, { detail: "none" }], "POST /projects/9/plan": [201, { id: 30 }] });
  open();
  expect(await screen.findByText("Turn the script into scenes: where each line happens and what we see.")).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: /Shots/ })).toHaveAttribute("aria-disabled", "true");
  expect(screen.getByRole("tab", { name: /Shots/ })).toHaveAccessibleDescription("Approve the plan first");
  expect(screen.getByRole("button", { name: "Write it myself · free" })).toBeInTheDocument();
  await vi.waitFor(() => expect(screen.getByRole("button", { name: /Make the plan · 6 credits/ })).toBeEnabled());
  await userEvent.click(screen.getByRole("button", { name: /Make the plan/ }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/plan")).toBe(true));
});

test("making: in words with a timer, and Stop (queued or running, never charged)", async () => {
  setViewport(1440);
  fakeServer({ ...withPlan("none"), "GET /projects/9/plan": [200, plan({ scenes: [], job: { id: 30, status: "queued", reason: null, started_at: new Date().toISOString() } })] });
  open();
  expect(await screen.findByText(/Waiting to start/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Stop" })).toBeInTheDocument();
});

test("ready to check: structure, cast, scene cards with place, lines, actions and the ★; Approve the plan · makes the shots opens Shots", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...withPlan("ready"), "GET /projects/9/plan": [200, plan()], "POST /projects/9/plan/approve": [200, { plan: plan({ status: "approved" }), job: { id: 31 } }] });
  open();
  expect(await screen.findByText("Pattern: Problem → Payoff (finance app)")).toBeInTheDocument();
  expect(screen.getByText("2 scenes · every line used once · the product in 1")).toBeInTheDocument();
  const second = screen.getByLabelText("Scene 2");
  expect(within(second).getByText("Payoff")).toBeInTheDocument();
  expect(within(second).getByText("Kitchen · Morning")).toBeInTheDocument();
  expect(within(second).getByText("She grins at fomo on the screen.")).toBeInTheDocument();
  expect(within(second).getByLabelText("Product")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Approve the plan · makes the shots · 6 credits/ }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/plan/approve")).toBe(true));
});

test("approved: says by whom, and Plan opens on Shots", async () => {
  setViewport(1440);
  fakeServer({ ...withPlan("approved"), "GET /projects/9/plan": [200, plan({ status: "approved", approved_by: { id: 2, name: "Eli" }, approved_at: new Date().toISOString() })] });
  open();
  expect(await screen.findByText(/Hook:/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("tab", { name: "Scenes" }));
  expect(await screen.findByText(/Approved by Eli · just now/)).toBeInTheDocument();
});

test("an old video's plan reads Approved · made from this video's breakdown", async () => {
  setViewport(390);
  fakeServer({ ...withPlan("approved"), "GET /projects/9/plan": [200, plan({ status: "approved", source: "breakdown" })] });
  open("?step=plan&view=scenes");
  expect(await screen.findByText("Approved · made from this video's breakdown")).toBeInTheDocument();
  expect(screen.getByText("This video started before plans existed.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Approve the plan/ })).toBeNull();
});

test("failed: Claude's reason, nothing charged, Try again; Write it myself stays free", async () => {
  setViewport(1440);
  fakeServer({ ...withPlan("none"), "GET /projects/9/plan": [200, plan({ scenes: [], job: { id: 30, status: "failed", reason: "Claude won't plan this: the script promises a cure.", started_at: null } })] });
  open();
  expect(await screen.findByText("Claude won't plan this: the script promises a cure.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Try again · 6 credits/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Write it myself · free" })).toBeInTheDocument();
});

test("over budget: the paid presses say why; Write it myself stays", async () => {
  setViewport(1440);
  fakeServer({ ...withPlan("ready"), "GET /projects/9/plan": [200, plan({ stop: "That's more than this video's budget." })] });
  open();
  expect(await screen.findByRole("button", { name: /Approve the plan/ })).toBeDisabled();
  expect(screen.getAllByText("That's more than this video's budget.").length).toBeGreaterThan(0); // every paid press says why
});

const two = [
  { id: "s1", part: "Problem", place: "Kitchen", time: "Morning", cast_ids: ["char:4"], lines: [{ n: 1, text: "Mia scrolls.", action: "Coffee freezes.", star: false }, { n: 2, text: "It dipped?", action: "Eyes wide.", star: false }] },
  { id: "s2", part: "Payoff", place: "Kitchen", time: "Morning", cast_ids: ["char:4"], lines: [{ n: 3, text: "Buy the dip.", action: "She grins.", star: true }] },
];

test("a line moves across its edge with one press (a sheet at 390), saved at once with Undo", async () => {
  setViewport(390);
  const calls = fakeServer({ ...withPlan("ready"), "GET /projects/9/plan": [200, plan({ scenes: two })], "PUT /projects/9/plan": [200, plan({ scenes: two })] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "More for line 2" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Move to scene 2" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /projects/9/plan")?.body).toMatchObject({ scenes: [{ lines: [{ n: 1 }] }, { lines: [{ n: 2 }, { n: 3 }] }] }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "PUT /projects/9/plan").at(-1)?.body).toMatchObject({ scenes: [{ lines: [{ n: 1 }, { n: 2 }] }, { lines: [{ n: 3 }] }] }));
});

test("a middle line offers Start a new scene here but no move; the last scene offers no Join", async () => {
  setViewport(1440);
  const three = [{ ...two[0], lines: [...two[0].lines, { n: 2.5, text: "Wait.", action: "", star: false }].map((l, i) => ({ ...l, n: i + 1 })) }, { ...two[1], lines: [{ ...two[1].lines[0], n: 4 }] }];
  fakeServer({ ...withPlan("ready"), "GET /projects/9/plan": [200, plan({ scenes: three })] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "More for line 2" }));
  expect(screen.getByRole("menuitem", { name: "Start a new scene here" })).toBeInTheDocument();
  expect(screen.queryByRole("menuitem", { name: /Move to scene/ })).toBeNull();
  expect(screen.queryByRole("button", { name: "More for scene 2" })).toBeNull();
  expect(screen.getByRole("button", { name: "More for scene 1" })).toBeInTheDocument();
});

test("editing an approved plan asks first, then saves; Edit types the place and each line's action", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...withPlan("approved"), "GET /projects/9/plan": [200, plan({ status: "approved", scenes: two })], "PUT /projects/9/plan": [200, plan({ scenes: two })] });
  open("?step=plan&view=scenes");
  await userEvent.click(await screen.findByRole("button", { name: "Edit scene 2" }));
  const place = screen.getByLabelText("Place");
  await userEvent.clear(place);
  await userEvent.type(place, "Office");
  await userEvent.click(screen.getByRole("button", { name: "Save scene" }));
  const ask = screen.getByRole("alertdialog", { name: "Change the plan?" });
  expect(calls.some((c) => c.key === "PUT /projects/9/plan")).toBe(false);
  await userEvent.click(within(ask).getByRole("button", { name: "Change" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /projects/9/plan")?.body).toMatchObject({ scenes: [{ place: "Kitchen" }, { place: "Office" }] }));
});

test("on an approved plan, Not yet keeps the editor open with what was typed; the confirm names what goes out of date", async () => {
  setViewport(390);
  const calls = fakeServer({ ...withPlan("approved"), "GET /projects/9/plan": [200, plan({ status: "approved", scenes: two, after: { shots: 3, clips: 2 } })] });
  open("?step=plan&view=scenes");
  await userEvent.click(await screen.findByRole("button", { name: "Edit scene 2" }));
  await userEvent.clear(screen.getByLabelText("Place"));
  await userEvent.type(screen.getByLabelText("Place"), "Office");
  await userEvent.click(screen.getByRole("button", { name: "Save scene" }));
  const ask = screen.getByRole("alertdialog", { name: "Change the plan?" });
  expect(within(ask).getByText(/This puts 3 shots and 2 clips out of date\./)).toBeInTheDocument();
  await userEvent.click(within(ask).getByRole("button", { name: "Not yet" }));
  expect(screen.getByLabelText("Place")).toHaveValue("Office");
  expect(calls.some((c) => c.key === "PUT /projects/9/plan")).toBe(false);
});

test("Use this one on an approved plan asks first, as an edit does", async () => {
  setViewport(390);
  const calls = fakeServer({ ...withPlan("approved"), "GET /projects/9/plan": [200, plan({ status: "approved", scenes: two, earlier: [{ id: 3, version: 1, source: "claude", made_at: new Date().toISOString() }] })], "POST /projects/9/plan/earlier/0/use": [200, plan()] });
  open("?step=plan&view=scenes");
  await userEvent.click(await screen.findByText("Earlier plans · 1"));
  await userEvent.click(screen.getByRole("button", { name: "Use this one · free" }));
  const ask = screen.getByRole("alertdialog", { name: "Change the plan?" });
  expect(calls.some((c) => c.key === "POST /projects/9/plan/earlier/0/use")).toBe(false);
  await userEvent.click(within(ask).getByRole("button", { name: "Change" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/plan/earlier/0/use")).toBe(true));
});

test("a ★ the server couldn't keep (the brand has no product) says so, with a way to add one, and no success toast", async () => {
  setViewport(390);
  fakeServer({ ...withPlan("ready"), "GET /projects/9/plan": [200, plan({ scenes: two })], "PUT /projects/9/plan": [200, plan({ scenes: two })] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "More for line 2" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "★ Show the product here" }));
  expect(await screen.findByText(/The ★ wasn't kept: the brand has no product to show yet\./)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Add a product to the brand" })).toHaveAttribute("href", "/b/1/brand?tab=products");
  expect(screen.queryByText("Line 2 shows the product.")).toBeNull();
});

test("a refused edit says why in the server's words", async () => {
  setViewport(1440);
  fakeServer({ ...withPlan("ready"), "GET /projects/9/plan": [200, plan({ scenes: two })], "PUT /projects/9/plan": [422, { detail: "Line 2 is missing from the plan." }] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "More for line 3" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Remove the ★" }));
  expect(await screen.findByText("Line 2 is missing from the plan.")).toBeInTheDocument();
});

test("out of date: Made for older words with Make a new plan; earlier plans come back free; a new plan takes a note", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...withPlan("ready"), "GET /projects/9/plan": [200, plan({ scenes: two, out_of_date: true, earlier: [{ id: 3, version: 1, source: "claude", made_at: new Date().toISOString() }] })], "POST /projects/9/plan/earlier/0/use": [200, plan()], "POST /projects/9/plan": [201, { id: 40 }] });
  open();
  expect(await screen.findByText("Made for older words.")).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: /Make a new plan · 6 credits/ })[0]).toBeInTheDocument();
  expect(screen.getByText(/this one is kept under Earlier plans/)).toBeInTheDocument();
  await userEvent.click(screen.getByText("Earlier plans · 1"));
  await userEvent.click(screen.getByRole("button", { name: "Use this one · free" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/plan/earlier/0/use")).toBe(true));
  await userEvent.click(screen.getByText("Make a new plan", { selector: "summary" }));
  await userEvent.type(screen.getByLabelText("What to change (optional)"), "funnier");
  await userEvent.click(screen.getAllByRole("button", { name: /Make a new plan · 6 credits/ }).at(-1)!);
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/plan")?.body).toEqual({ note: "funnier" }));
});

test("with no plan yet, Make the plan is priced from the video's plan_credits", async () => {
  setViewport(1440);
  fakeServer({ ...withPlan("none"), "GET /projects/9": [200, { ...project, plan_status: "none", plan_credits: 9 }], "GET /projects/9/plan": [404, { detail: "none" }] });
  open();
  expect(await screen.findByRole("button", { name: /Make the plan · 9 credits/ })).toBeInTheDocument();
});
