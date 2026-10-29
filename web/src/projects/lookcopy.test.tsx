import { fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const editor = { id: 2, email: "e@b.co", name: "Eli", role: "editor", workspace_id: 1 };
const project = {
  id: 9, brand_id: 1, name: "Bo tries salmon · B", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "",
  cast_ids: [], reference_file_id: null, estimate_credits: 30, budget_credits: 600, credits_used: 0, budget_pct: 0, product_variants: {}, created_by_id: 2,
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

afterEach(() => vi.unstubAllGlobals());

const bo = asset({ sheet_status: "missing", ready: false, shots: 3, look_needed: "Disney Pixar", look_credits: 4, look_usual_credits: 2 });
const copied = asset({ sheet_status: "needs_approval", ready: false, shots: 3, look_copy_id: 12 });
const looks = { "GET /projects/9/assets/missing-looks": [200, { slot_ids: [], roles: [] }] } as Record<string, [number, unknown]>;

test("a character with no sheet in the video's look offers its own copy for this video, priced, and makes it", async () => {
  setViewport(390);
  const calls = fakeServer({ ...base, ...looks, "GET /projects/9/assets": [200, [bo]], "POST /projects/9/assets/looks/5/copy": [200, { job_id: 3 }] });
  open();
  const card = await screen.findByLabelText("Bo");
  const make = within(card).getByRole("button", { name: /Make a Disney Pixar look for this video/ });
  expect(make).toHaveTextContent("4");
  expect(within(card).queryByText(/Make its look in Cast & places/)).toBeNull();
  fireEvent.click(make);
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/assets/looks/5/copy")).toBe(true));
});

test("the video's own look is approved by its own id, with Undo", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, ...looks, "GET /projects/9/assets": [200, [copied]], "POST /library/character/12/sheet/approve": [200, {}], "DELETE /library/character/12/sheet/approve": [200, {}] });
  open();
  const card = await screen.findByLabelText("Bo");
  expect(within(card).getByText("This video's own look")).toBeInTheDocument();
  fireEvent.click(within(card).getByRole("button", { name: "Approve this look" }));
  fireEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /library/character/12/sheet/approve")).toBe(true));
  expect(calls.some((c) => c.key === "POST /library/character/12/sheet/approve")).toBe(true);
  expect(calls.some((c) => c.key === "POST /library/character/5/sheet/approve")).toBe(false);
});

test("a video's own look that didn't draw says so and offers Try again on the copy, priced", async () => {
  setViewport(390);
  const failed = asset({ sheet_status: "none", ready: false, shots: 3, look_needed: null, look_copy_id: 12, look_credits: 4, look_usual_credits: 2 });
  const calls = fakeServer({ ...base, ...looks, "GET /projects/9/assets": [200, [failed]], "POST /library/character/12/sheet": [201, {}] });
  open();
  const card = await screen.findByLabelText("Bo");
  expect(within(card).getByRole("alert")).toHaveTextContent("The look didn't finish. Nothing was charged.");
  const again = within(card).getByRole("button", { name: /Try again/ });
  expect(again).toHaveTextContent("4");
  fireEvent.click(again);
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /library/character/12/sheet")?.body).toMatchObject({ change: "" }));
});

test("beside Approve this look, Redo draws the copy again", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, ...looks, "GET /projects/9/assets": [200, [copied]], "POST /library/character/12/sheet": [201, {}] });
  open();
  const card = await screen.findByLabelText("Bo");
  fireEvent.click(within(card).getByRole("button", { name: /Redo/ }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /library/character/12/sheet")).toBe(true));
  expect(calls.some((c) => c.key === "POST /library/character/5/sheet")).toBe(false);
});
