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

function open(query = "?step=cast") {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[`/b/1/videos/9${query}`]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const frame = { id: 1, clip_id: "c1", shot_id: "1.1", prompt: "p", reference_ids: [], problems: [], kept: [], file_id: 40, approved: false, stale: false, earlier: [], change: null };
const clip = (o: object) => ({ id: 3, clip_id: "c1", seconds: 8, prompt: "Bo sniffs the salmon", references: [], problems: [], kept: [], file_id: 51, takes: [], picked_take_id: null, approved: false, stale: false, take_credits: 24, inserts: [], ...o });
const take = (id: number, number: number, check: object | null = null) => ({ id, number, file_id: 50 + id, created_at: `2026-10-26T10:4${number}:00`, check });
const face = { index: 0, kind: "face", text: "Bo's face may differ from his sheet", note: "Make Bo's face match his sheet" };
const outfit = { index: 1, kind: "outfit", text: "The outfit changed: the red bandana is missing", note: "Put the red bandana back on Bo" };
const advice = { id: 7, status: "advice", findings: [face, outfit] };
const review = (o: object = {}) => ({ on: true, credits_per_check: 1, items: [{ kind: "still", id: 1, clip_id: "c1", label: "Still 1.1", findings: 2 }, { kind: "take", id: 2, clip_id: "c2", label: "Clip c2 · take 2", findings: 1 }], ...o });
const routes = (o: Record<string, [number, unknown]> = {}) => ({
  ...base,
  "GET /projects/9/assets": [200, []] as [number, unknown],
  "GET /projects/9/storyboard": [200, [frame]] as [number, unknown],
  "GET /projects/9/storyboard/frames/1/change": [200, { credits: 2 }] as [number, unknown],
  "GET /projects/9/clips/3/change": [200, { credits: 24 }] as [number, unknown],
  ...o,
});

afterEach(() => vi.unstubAllGlobals());

test("a still with Advice shows a quiet notes chip; Change this… fills the change box with its note, Looks fine dismisses it", async () => {
  setViewport(1440);
  const calls = fakeServer(routes({ "GET /projects/9/storyboard": [200, [{ ...frame, check: advice }]], "POST /projects/9/checks/7/findings/1/dismiss": [200, { ...advice, findings: [face] }], "POST /projects/9/checks/7/findings/1/restore": [200, advice] }));
  open("?step=storyboard");
  await userEvent.click(await screen.findByRole("button", { name: "2 notes on clip c1" }));
  const notes = screen.getByLabelText("Notes for clip c1");
  expect(within(notes).getByText("The outfit changed: the red bandana is missing")).toBeInTheDocument();
  await userEvent.click(within(notes).getAllByRole("button", { name: "Looks fine" })[1]);
  expect(calls.some((c) => c.key === "POST /projects/9/checks/7/findings/1/dismiss")).toBe(true);
  expect(await screen.findByText("Marked as fine.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/checks/7/findings/1/restore")).toBe(true));
  await userEvent.click(within(notes).getAllByRole("button", { name: "Change this…" })[0]);
  expect(screen.getByLabelText("Change this… c1")).toHaveValue("Make Bo's face match his sheet");
  await vi.waitFor(() => expect(screen.getByLabelText("Change this… c1")).toHaveFocus());
  expect(screen.queryByLabelText("Notes for clip c1")).toBeNull();
});

test("at 390 the notes open in a sheet", async () => {
  setViewport(390);
  fakeServer(routes({ "GET /projects/9/storyboard": [200, [{ ...frame, check: advice }]] }));
  open("?step=storyboard");
  await userEvent.click(await screen.findByRole("button", { name: "2 notes on clip c1" }));
  const sheet = screen.getByRole("dialog", { name: "2 notes on clip c1" });
  expect(within(sheet).getAllByRole("button", { name: "Change this…" })).toHaveLength(2);
});

test("a clean check is only ✓ checked in the chip; checking and a failed check are one muted line", async () => {
  setViewport(1440);
  const clips = [
    clip({ id: 3, clip_id: "c1", takes: [take(1, 1, { id: 8, status: "ok", findings: [] })], picked_take_id: 1, approved: true }),
    clip({ id: 4, clip_id: "c2", takes: [take(2, 1, { id: 9, status: "checking", findings: [] })], picked_take_id: 2 }),
    clip({ id: 5, clip_id: "c3", takes: [take(3, 1, { id: 10, status: "failed", findings: [] })], picked_take_id: 3 }),
  ];
  fakeServer(routes({ "GET /projects/9/storyboard": [200, [{ ...frame, approved: true }]], "GET /projects/9/clips": [200, clips] }));
  open("?step=clips");
  const c1 = await screen.findByLabelText("Clip c1");
  expect(within(c1).getByText("Approved · ✓ checked")).toBeInTheDocument();
  expect(within(screen.getByLabelText("Clip c2")).getByText("Checking…")).toBeInTheDocument();
  expect(within(screen.getByLabelText("Clip c2")).getByRole("button", { name: "Approve take" })).toBeEnabled();
  expect(within(screen.getByLabelText("Clip c3")).getByText("Couldn't check this one.")).toBeInTheDocument();
});

test("the Clips header has the Review chip and the summary line; a row goes to its card", async () => {
  setViewport(1440);
  const clips = [clip({ id: 4, clip_id: "c2", takes: [take(2, 2, { id: 9, status: "advice", findings: [face] })], picked_take_id: 2 })];
  fakeServer(routes({ "GET /projects/9/storyboard": [200, [{ ...frame, approved: true }]], "GET /projects/9/clips": [200, clips], "GET /projects/9/checks": [200, review()] }));
  open("?step=clips");
  expect(await screen.findByText("AI check: 3 notes on 2 clips")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "2 items with Advice ▸" }));
  const list = screen.getByLabelText("Review");
  expect(within(list).getByText("Storyboard")).toBeInTheDocument();
  await userEvent.click(within(list).getByRole("button", { name: "Clip c2 · take 2 · 1 note" }));
  await vi.waitFor(() => expect(screen.getByLabelText("Clip c2")).toHaveFocus());
});

test("over budget the step says once that checks are paused", async () => {
  setViewport(390);
  fakeServer(routes({ "GET /projects/9/checks": [200, review({ items: [], paused: true })] }));
  open("?step=storyboard");
  expect(await screen.findByText("Not checked: the video was at its budget.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /with Advice/ })).toBeNull();
});

test("Final cut has the Review list open by default", async () => {
  setViewport(1440);
  const done = clip({ approved: true, takes: [take(2, 2)], picked_take_id: 2 });
  fakeServer(routes({ "GET /projects/9/storyboard": [200, [{ ...frame, approved: true }]], "GET /projects/9/clips": [200, [done]], "GET /projects/9/video": [200, { file_id: 60, take_ids: [2], out_of_date: false }], "GET /projects/9/checks": [200, review()] }));
  open("?step=downloads");
  const list = await screen.findByLabelText("Review");
  expect(within(list).getByRole("button", { name: "Still 1.1 · 2 notes" })).toBeInTheDocument();
});

test("a Review row on Final cut opens Clips and puts focus on the card", async () => {
  setViewport(390);
  const c1 = clip({ approved: true, takes: [take(1, 1)], picked_take_id: 1 });
  const c2 = clip({ id: 4, clip_id: "c2", approved: true, takes: [take(2, 2, { id: 9, status: "advice", findings: [face] })], picked_take_id: 2 });
  fakeServer(routes({ "GET /projects/9/storyboard": [200, [{ ...frame, approved: true }]], "GET /projects/9/clips": [200, [c1, c2]], "GET /projects/9/video": [200, { file_id: 60, take_ids: [1, 2], out_of_date: false }], "GET /projects/9/checks": [200, review()] }));
  open("?step=downloads");
  await userEvent.click(within(await screen.findByLabelText("Review")).getByRole("button", { name: "Clip c2 · take 2 · 1 note" }));
  await vi.waitFor(() => expect(screen.getByLabelText("Clip c2")).toHaveFocus(), { timeout: 4000 });
});

test("without checks on the server nothing shows", async () => {
  setViewport(1440);
  fakeServer(routes({ "GET /projects/9/storyboard": [200, [{ ...frame, check: null }]] }));
  open("?step=storyboard");
  expect(await screen.findByLabelText("Frame c1")).toBeInTheDocument();
  expect(screen.queryByText(/AI check|notes on|✓ checked/)).toBeNull();
});

test("Approve all approves items with Advice too, and says how many", async () => {
  setViewport(390);
  const clips = [clip({ id: 4, clip_id: "c2", prompt_ok: true, takes: [take(2, 2, advice)], picked_take_id: 2 })];
  fakeServer(routes({ "GET /projects/9/storyboard": [200, [{ ...frame, approved: true }]], "GET /projects/9/clips": [200, clips], "POST /projects/9/clips/approve-all": [200, { approved: [4], skipped: [], approved_with_advice: 1 }] }));
  open("?step=clips");
  await userEvent.click(await screen.findByRole("button", { name: "Approve all" }));
  expect(await screen.findByText(/1 approved with Advice, listed under items with Advice\./)).toBeInTheDocument();
});
