import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";
import { editor } from "../test/people";

const project = {
  id: 9, brand_id: 1, name: "Mia buys the dip", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "",
  cast_ids: [4], reference_file_id: null, estimate_credits: 30, budget_credits: 600, credits_used: 0, budget_pct: 0, created_by_id: 2,
};
const script = { version: 5, source: "paste", words: 9, created_by_id: 2, created_at: "2026-10-23T10:00:00Z", text: "Mia scrolls her phone." };
const breakdown = { id: 1, script_version: 5, source: "claude", stale: false, problems: [], breakdown: { hook: "Hook.", scenes: [{ id: 1, heading: "KITCHEN", look: "", shots: [] }], clips: [] } };
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, editor],
  "GET /brands": [200, [{ id: 1, name: "fomo", colours: [] }]],
  "GET /projects/9": [200, project],
  "GET /projects/9/script": [200, script],
  "GET /projects/9/breakdown": [200, breakdown],
  "GET /projects/9/script/suggestions": [200, []],
  "GET /projects/9/script/notes": [200, []],
  "GET /models": [200, [{ id: "nano-banana-2.1", kind: "image", name: "Nano Banana 2.1", default: true, credits_per_unit: { "1K": 3 } }]],
  "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 6 }, { kind: "image-nano-banana-2.1", unit: "image", credits_per_unit: 3 }]],
  "GET /jobs": [200, []],
  "GET /library/character": [200, [{ id: 4, name: "Mia", image_file_ids: [] }]],
  "GET /library/place": [200, []],
  "GET /library/prop": [200, []],
  "GET /brands/1/screens": [200, [{ id: 3, name: "Chart down", file_id: 9, tags: [], default_for: [], brand_id: 1 }]],
};

function open(query = "?stage=storyboard") {
  renderApp(`/b/1/projects/9${query}`);
}

afterEach(() => vi.unstubAllGlobals());

const by = { id: 2, name: "Eli" };

test("E: the breakdown's versions go back to an earlier one, and Undo goes back to the one replaced", async () => {
  setViewport(1440);
  const versions = [
    { id: 3, made_at: "2026-10-29T11:00:00Z", made_by: by, source: "edit", script_version: 5, current: true },
    { id: 1, made_at: "2026-10-29T09:00:00Z", made_by: null, source: "claude", script_version: 5, current: false },
  ];
  const calls = fakeServer({ ...base, "GET /projects/9/breakdown/versions": [200, versions], "POST /projects/9/breakdown/versions/1/use": [200, { ...breakdown, id: 4, was_id: 3 }], "POST /projects/9/breakdown/versions/3/use": [200, { ...breakdown, id: 5, was_id: 4 }] });
  open("?stage=breakdown");
  await userEvent.click(await screen.findByText("Breakdown versions · 2"));
  const list = screen.getByRole("list", { name: "Breakdown versions" });
  expect(within(list).getByText(/Made by Claude/)).toBeInTheDocument();
  await userEvent.click(within(list).getByRole("button", { name: "Go back to this" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/breakdown/versions/1/use")).toBe(true));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/breakdown/versions/3/use")).toBe(true));
});

test("Go back on the breakdown waits while stills are being made, and says why", async () => {
  setViewport(1440);
  const versions = [
    { id: 3, made_at: null, made_by: null, source: "edit", script_version: 5, current: true },
    { id: 1, made_at: null, made_by: null, source: "claude", script_version: 5, current: false },
  ];
  fakeServer({ ...base, "GET /jobs": [200, [{ id: 8, project_id: 9, step: "frame", frame_id: 1, status: "running", kind: "image" }]], "GET /projects/9/breakdown/versions": [200, versions] });
  open("?stage=breakdown");
  await userEvent.click(await screen.findByText("Breakdown versions · 2"));
  const back = within(screen.getByRole("list", { name: "Breakdown versions" })).getByRole("button", { name: /Go back to this/ });
  await vi.waitFor(() => expect(back).toBeDisabled());
  expect(back).toHaveAccessibleDescription(/Wait for the storyboard, stills and clip prompts being made/);
});
