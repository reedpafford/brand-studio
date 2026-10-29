import { screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";
import { editor } from "../test/people";

const project = {
  id: 9, brand_id: 1, name: "Mia buys the dip", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "",
  cast_ids: [4], reference_file_id: null, estimate_credits: 30, budget_credits: 60, credits_used: 0, budget_pct: 0,
};
const script = { version: 5, source: "paste", words: 9, created_by_id: 2, created_at: "2026-10-23T10:00:00Z", text: "Mia scrolls her phone.\nMIA: Wait… it dipped?" };
const shot = (o: object) => ({
  id: "1.1", script_lines: [1], speaker: null, line: null, action: "Mia scrolls her phone, coffee in hand.", reaction: null, camera: "Wide, slow push-in",
  seconds: 3, character_ids: ["char:4"], place_id: "place:2", moment: null, screen_ids: [], ...o,
});
const breakdown = (o: object = {}) => ({
  id: 1, script_version: 5, source: "claude", stale: false, problems: [],
  breakdown: {
    hook: "Mia's coffee freezes mid-air as the chart drops.",
    scenes: [{ id: 1, heading: "INT. KITCHEN — MORNING", look: "Cold blue light.", shots: [shot({}), shot({ id: "1.2", script_lines: [2], speaker: "Mia", line: "Wait… it dipped?", reaction: "eyes snap wide", seconds: 2, moment: "loss", screen_ids: ["screen:3"] })] }],
    clips: [{ id: "c1", shot_ids: ["1.1", "1.2"], seconds: 5, seam: "end" }],
  },
  ...o,
});
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, editor],
  "GET /brands": [200, [{ id: 1, name: "fomo", colours: [] }]],
  "GET /projects/9": [200, project],
  "GET /projects/9/script": [200, script],
  "GET /projects/9/script/suggestions": [200, []],
  "GET /projects/9/script/notes": [200, []],
  "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 6 }]],
  "GET /jobs": [200, []],
  "GET /library/character": [200, [{ id: 4, name: "Mia", image_file_ids: [] }]],
  "GET /library/place": [200, [{ id: 2, name: "Kitchen", image_file_ids: [] }]],
  "GET /library/prop": [200, []],
  "GET /brands/1/screens": [200, [{ id: 3, name: "Chart down", file_id: 9, tags: [], default_for: ["loss"], brand_id: 1 }]],
};

function open() {
  renderApp("/b/1/projects/9?stage=breakdown");
}

afterEach(() => vi.unstubAllGlobals());

const timed = { take_id: 1, shots: { "1.1": { start: 0, end: 3.4, sung: false, guessed: false }, "1.2": { start: 3.4, end: 6, sung: true, guessed: true } } };

test("a song breakdown: each shot shows its stretch of the song, Sung or B-roll, and Timing guessed", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown({ song: timed })] });
  open();
  const clip = await screen.findByLabelText("Clip c1");
  const first = within(clip).getByLabelText("Shot 1.1");
  expect(within(first).getByText("0:00–0:03")).toBeInTheDocument();
  expect(within(first).getByText("B-roll")).toBeInTheDocument();
  expect(within(first).queryByText("3 s")).toBeNull();
  const second = within(clip).getByLabelText("Shot 1.2");
  expect(within(second).getByText("0:03–0:06")).toBeInTheDocument();
  expect(within(second).getByText("Sung")).toBeInTheDocument();
  expect(within(second).getByText("Timing guessed")).toBeInTheDocument();
});

test("at 390, a shot the song's timing doesn't cover says Needs timing instead of a made-up time", async () => {
  setViewport(390);
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown({ song: { take_id: 1, shots: { "1.1": timed.shots["1.1"] } } })] });
  open();
  const second = await screen.findByLabelText("Shot 1.2");
  expect(within(second).getByText("Needs timing")).toBeInTheDocument();
  expect(within(screen.getByLabelText("Shot 1.1")).getByText("0:00–0:03")).toBeInTheDocument();
});

test("a breakdown without a song keeps its seconds", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown()] });
  open();
  const first = await screen.findByLabelText("Shot 1.1");
  expect(within(first).getByText("3 s")).toBeInTheDocument();
  expect(within(first).queryByText("B-roll")).toBeNull();
});

test("a shot under 2 s reads in tenths, so it never says 0:03–0:03", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown({ song: { take_id: 1, shots: { "1.1": { start: 3.2, end: 3.84, sung: false, guessed: false } } } })] });
  open();
  expect(within(await screen.findByLabelText("Shot 1.1")).getByText("0:03.2–0:03.8")).toBeInTheDocument();
});
