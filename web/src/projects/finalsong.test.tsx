import { screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";
import { editor } from "../test/people";

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
  renderApp(`/b/1/videos/9${query}`);
}

const frame = { id: 1, clip_id: "c1", shot_id: "1.1", prompt: "p", reference_ids: [], problems: [], kept: [], file_id: 40, approved: true, stale: false };
const clip = (o: object) => ({ id: 3, clip_id: "c1", seconds: 8, prompt: "Bo sniffs the salmon", references: [], problems: [], kept: [], file_id: null, takes: [], picked_take_id: null, approved: false, stale: false, take_credits: 24, inserts: [], ...o });
const toClips = { ...base, "GET /projects/9/assets": [200, []] as [number, unknown], "GET /projects/9/storyboard": [200, [frame]] as [number, unknown] };
const take = (id: number, number: number) => ({ id, number, file_id: 50 + id, created_at: `2026-10-26T10:4${number}:00` });
const done = clip({ approved: true, file_id: 51, takes: [take(1, 1), take(2, 2)], picked_take_id: 2 });

afterEach(() => vi.unstubAllGlobals());

const songTake = (o: object = {}) => ({ id: 1, number: 2, status: "ready", failed_reason: null, retry_helps: true, file_id: 80, seconds: 31, made_at: "2026-10-28T10:42:00Z", preferred: false, out_of_date: false, peaks: [], advice: [], timing_guessed: false, refused_for: null, video_credits: 34, over_cap: false, fits_until: null, trim_to: null, in_video: false, ...o });
const songs = (takes: object[], song_take_id = 1) => ({ songs_on: true, estimate_credits: 1, video_estimate_credits: 40, keep_lines: null, takes, song_take_id });

test("a song video's final cut names the take laid under it and downloads the song", async () => {
  setViewport(390);
  fakeServer({ ...toClips, "GET /projects/9/clips": [200, [done]], "GET /projects/9/video": [200, { file_id: 60, take_ids: [2], out_of_date: false, song_take_id: 1 }], "GET /projects/9/songs": [200, songs([songTake()])] });
  open("?step=downloads");
  const song = await screen.findByLabelText("The song");
  expect(within(song).getByText("Song: take 2, laid under the whole video")).toBeInTheDocument();
  expect(within(song).getByRole("link", { name: /Download the song/ })).toHaveAttribute("href", "/api/files/80");
});

test("when the video now uses another take, the final cut says so: Make it again lays it under", async () => {
  setViewport(1440);
  fakeServer({ ...toClips, "GET /projects/9/clips": [200, [done]], "GET /projects/9/video": [200, { file_id: 60, take_ids: [2], out_of_date: true, song_take_id: 1 }], "GET /projects/9/songs": [200, songs([songTake(), songTake({ id: 4, number: 3 })], 4)] });
  open("?step=downloads");
  expect(await screen.findByText("This video now uses take 3. Make it again to lay it under (free).")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Make it again" })).toBeEnabled();
  expect(screen.getByText(/The song changed since this video was made\./)).toBeInTheDocument();
});

test("a video without a song shows no song line and never asks for songs", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...toClips, "GET /projects/9/clips": [200, [done]], "GET /projects/9/video": [200, { file_id: 60, take_ids: [2], out_of_date: false }] });
  open("?step=downloads");
  expect(await screen.findByText("Final cut ready")).toBeInTheDocument();
  expect(screen.queryByLabelText("The song")).toBeNull();
  expect(calls.some((c) => c.key === "GET /projects/9/songs")).toBe(false);
});

test("if the take in the cut was deleted since, the line about the take in use still shows", async () => {
  setViewport(1440);
  fakeServer({ ...toClips, "GET /projects/9/clips": [200, [done]], "GET /projects/9/video": [200, { file_id: 60, take_ids: [2], out_of_date: true, song_take_id: 1 }], "GET /projects/9/songs": [200, songs([songTake({ id: 4, number: 3 })], 4)] });
  open("?step=downloads");
  expect(await screen.findByText("Song: an earlier take, laid under the whole video")).toBeInTheDocument();
  expect(screen.getByText("This video now uses take 3. Make it again to lay it under (free).")).toBeInTheDocument();
});

test("a narrated video's final cut names its narration, downloads it, and the banner says the narration changed", async () => {
  setViewport(390);
  const narration = (o: object = {}) => songTake({ kind: "narration", voice: "Sarah", ...o });
  fakeServer({ ...toClips, "GET /projects/9/clips": [200, [done]], "GET /projects/9/video": [200, { file_id: 60, take_ids: [2], out_of_date: true, song_take_id: 1, narration: { voice: "Sarah", music: true } }], "GET /projects/9/songs": [200, songs([narration(), narration({ id: 4, number: 3 })], 4)] });
  open("?step=downloads");
  const it = await screen.findByLabelText("The narration");
  expect(within(it).getByText("Narration 2, read over the whole video")).toBeInTheDocument();
  expect(within(it).getByText("Narration: Sarah · music under it")).toBeInTheDocument();
  expect(within(it).getByText("This video now uses narration 3. Make it again to lay it under (free).")).toBeInTheDocument();
  expect(within(it).getByRole("link", { name: /Download the narration/ })).toHaveAttribute("download", "narration-2.mp3");
  expect(await screen.findByText(/The narration changed since this video was made\./)).toBeInTheDocument();
});
