import { screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";
import { editor } from "../test/people";

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
  renderApp(`/b/1/videos/9${query}`);
}

afterEach(() => vi.unstubAllGlobals());

const bo = asset({ ref: "char:5", library_item_id: 5, role: "Bo", name: "Bo", sheet_status: "approved", ready: true, shots: 3 });
const noah = asset({ ref: "slot:8", slot_id: 8, library_item_id: null, role: "Noah", name: "", sheet_status: "missing", ready: false, shots: 0, look_credits: 4, look_usual_credits: 2 });

test("a role no shot uses says so quietly: no Needs a look, no Make a look, no price", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/assets": [200, [bo, noah]], "GET /projects/9/assets/missing-looks": [200, { slot_ids: [], roles: [] }] });
  open();
  const card = await screen.findByLabelText("Noah");
  expect(within(card).getByText("Not in this video's shots")).toBeInTheDocument();
  expect(within(card).queryByText("Needs a look")).toBeNull();
  expect(within(card).queryByRole("button")).toBeNull();
  expect(screen.queryByText(/Make a look/)).toBeNull();
});

test("it stays out of every count: the steps are not blocked and the header counts only the used assets", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/assets": [200, [bo, noah]], "GET /projects/9/assets/missing-looks": [200, { slot_ids: [], roles: [] }] });
  open();
  await screen.findByLabelText("Noah");
  expect(screen.getByText("1 in the cast · 1 approved")).toBeInTheDocument();
  const steps = screen.getByRole("list", { name: "Steps" });
  expect(within(steps).getByRole("button", { name: "Storyboard" })).not.toHaveAccessibleDescription(/Approve the cast first/);
});
