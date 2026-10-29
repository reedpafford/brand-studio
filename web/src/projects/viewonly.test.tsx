import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

// Eli looks at Sam's video: only Sam or the owner may change it (the server refuses the rest with a 403).
const owner = { id: 1, email: "reed@b.co", name: "Reed", role: "owner", workspace_id: 1 };
const eli = { id: 2, email: "e@b.co", name: "Eli", role: "editor", workspace_id: 1 };
const project = {
  id: 9, brand_id: 1, name: "Bo tries salmon · B", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "",
  cast_ids: [], reference_file_id: null, estimate_credits: 30, budget_credits: 600, credits_used: 0, budget_pct: 0, product_variants: {}, created_by_id: 3, created_by_name: "Sam",
};
const asset = { kind: "character", ref: "char:5", role: "Bo", library_item_id: 5, name: "Bo", locked: false, sheet_status: "approved", ready: true };
const frame = { id: 1, clip_id: "c1", shot_id: "1.1", prompt: "p", reference_ids: [], problems: [], kept: [], file_id: 40, approved: false, stale: false, earlier: [], change: null };
const take = (id: number, number: number) => ({ id, number, file_id: 50 + id, created_at: `2026-10-26T10:4${number}:00` });
const clip = { id: 3, clip_id: "c1", seconds: 8, prompt: "Bo sniffs the salmon", references: [], problems: [], kept: [], file_id: 51, takes: [take(1, 1)], picked_take_id: 1, approved: false, stale: false, take_credits: 24, inserts: [] };
const settings = {
  look: "house", video_model: null, image_model: null, aspect_ratio: "9:16", product_variants: {}, language: "en",
  video_models: [{ id: "seedance-2.5", name: "Seedance 2.5", credits_per_second: 1, lip_sync: true, default: true, over_cap: false }], image_models: [], shapes: ["9:16", "1:1"], flavours: {},
};
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, eli],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /projects/9": [200, project],
  "GET /projects/9/script": [200, { version: 5, source: "paste", words: 9, created_by_id: 3, created_at: "2026-10-23T10:00:00Z", text: "Bo eats." }],
  "GET /projects/9/breakdown": [200, { id: 1, script_version: 5, source: "claude", stale: false, problems: [], breakdown: { hook: "Hook.", scenes: [{ id: 1, heading: "KITCHEN", look: "", shots: [] }], clips: [] } }],
  "GET /projects/9/storyboard": [200, [frame]],
  "GET /projects/9/clips": [200, [clip]],
  "GET /projects/9/video": [200, { file_id: 60, take_ids: [1], out_of_date: false }],
  "GET /projects/9/assets": [200, [asset]],
  "GET /projects/9/assets/missing-looks": [200, { slot_ids: [], roles: [], credits: 0, usual_credits: 0, reason: null }],
  "GET /library/character": [200, []],
  "GET /library/character/5": [200, { id: 5, kind: "character", name: "Bo", version: 1, sheet_file_id: 70, sheet_status: "approved" }],
  "GET /brands/1/screens": [200, []],
  "GET /credits/rates": [200, []],
  "GET /jobs": [200, []],
  "GET /looks": [200, [{ id: "house", name: "House", blurb: "", on: true, sample_still_id: null }]],
  "GET /projects/9/settings": [200, settings],
  "GET /models": [200, []],
};

function open(step: string) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[`/b/1/videos/9?step=${step}`]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
afterEach(() => vi.unstubAllGlobals());

// A press that changes the video starts with one of these words; reads (Show all, See the change, the steps, the script) don't.
const CHANGES = /^(Make|Approve|Redraw|Draw|Edit|Save|Switch|Use|Delete|Remove|Change|Add|Undo|Write|Keep|Fix|Update|Pick|Unapprove|Rewrite|Soften|Try|Start|Merge|Read|Restore)\b/;
const live = () => within(screen.getByRole("main")).queryAllByRole("button").filter((b) => !(b as HTMLButtonElement).disabled);
const presses = () => within(screen.getByRole("main")).queryAllByRole("button");

for (const [step, ready] of [
  ["plan", () => screen.findByRole("heading", { name: "Plan", level: 2 })],
  ["cast", () => screen.findByLabelText("Bo")],
  ["storyboard", () => screen.findByLabelText("Frame c1")],
  ["clips", () => screen.findByRole("heading", { name: "Clips", level: 2 })],
  ["downloads", () => screen.findByRole("link", { name: /Download MP4/ })],
] as const) {
  test(`at ${step}, an editor on someone else's video can look: one banner, every changing press greyed out, reads still live`, async () => {
    setViewport(1440);
    fakeServer(base);
    open(step);
    await ready();
    expect(screen.getAllByText("This is Sam's video. You can look, but only Sam or the owner can change it.")).toHaveLength(1); // one banner, not one per card
    await vi.waitFor(() => expect(presses().length).toBeGreaterThan(3));
    expect(live().map((b) => b.textContent?.trim() || b.getAttribute("aria-label")).filter((n) => CHANGES.test(n ?? ""))).toEqual([]);
    for (const f of within(screen.getByRole("main")).queryAllByRole("textbox")) expect(f.matches("[readonly], :disabled")).toBe(true);
    for (const b of within(screen.getByRole("list", { name: "Steps" })).getAllByRole("button")) expect(b).toBeEnabled(); // moving between steps is looking
    expect(screen.getByRole("button", { name: "Show script" })).toBeEnabled();
    const bar = screen.getByRole("region", { name: "Cost" });
    for (const b of within(bar).queryAllByRole("button").filter((b) => !/^Next:/.test(b.textContent ?? ""))) {
      expect(b).toBeDisabled();
      expect(b).toHaveAccessibleDescription("Only Sam or the owner can change this video."); // the step's own press says why
    }
    if (step === "downloads") expect(screen.getByRole("link", { name: /Download MP4/ })).toHaveAttribute("href", expect.stringContaining("/api/files/60"));
  });
}

test("the owner and the video's maker get no banner and live presses", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /auth/me": [200, owner] });
  open("storyboard");
  await screen.findByLabelText("Frame c1");
  expect(screen.queryByText(/This is Sam's video/)).toBeNull();
  await vi.waitFor(() => expect(live().some((b) => CHANGES.test(b.textContent?.trim() ?? ""))).toBe(true));
});

test("on an approved plan a second editor can still switch between Shots and Scenes to read it (Flow-QA on #977)", async () => {
  setViewport(1440);
  const scenes = [{ id: "s1", part: "Problem", place: "Kitchen", time: "Morning", cast_ids: [], lines: [{ n: 1, text: "Bo eats.", action: "He sniffs.", star: false }] }];
  fakeServer({
    ...base,
    "GET /projects/9": [200, { ...project, plan_status: "approved" }],
    "GET /projects/9/plan": [200, { status: "approved", approved_by: { id: 3, name: "Sam" }, approved_at: "2026-10-28T10:00:00Z", source: "claude", structure: { label: "Problem → Payoff", from: "pattern" }, cast: [], scenes, summary: "1 scene", advice: [], job: null, estimate_credits: 6, approve_credits: 6, stop: null }],
  });
  open("plan");
  await userEvent.click(await screen.findByRole("tab", { name: "Scenes" }));
  expect(await screen.findByRole("tab", { name: "Scenes", selected: true })).toBeInTheDocument();
  expect(screen.getByText("Bo eats.")).toBeInTheDocument();
});
