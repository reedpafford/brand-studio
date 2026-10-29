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
const frame = (o: object) => ({ id: 1, clip_id: "c1", shot_id: "1.1", prompt: "Mia in a cold blue kitchen", reference_ids: ["char:4", "screen:3"], problems: [], file_id: null, stale: false, ...o });
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

const clip = (o: object) => ({ id: 1, clip_id: "c1", seconds: 8, prompt: "Mia taps buy", references: [], problems: [], kept: [], file_id: null, takes: [], picked_take_id: null, approved: false, stale: false, take_credits: 24, inserts: [], ...o });
const by = { id: 2, name: "Eli" };

test("A: a frame's earlier stills can be used again (free), and Undo puts the still in use back", async () => {
  setViewport(390);
  const earlier = [{ file_id: 38, prompt: "Mia, warmer", made_at: "2026-10-29T09:00:00Z", made_by: by }];
  const calls = fakeServer({ ...base, "GET /projects/9/storyboard": [200, [frame({ file_id: 40, earlier })]], "POST /projects/9/storyboard/frames/1/pick": [200, frame({ file_id: 38, was_file_id: 40 })] });
  open();
  const card = await screen.findByLabelText("Frame c1");
  await userEvent.click(within(card).getByText("Earlier stills · 1"));
  await userEvent.click(within(card).getByRole("button", { name: "Use this one" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/storyboard/frames/1/pick")?.body).toEqual({ file_id: 38 }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /projects/9/storyboard/frames/1/pick").at(-1)?.body).toEqual({ file_id: 40 }));
});

test("C: the storyboard's versions go back to an earlier one, with Undo; while stills are being made it says to wait", async () => {
  setViewport(1440);
  const versions = [
    { index: null, made_at: "2026-10-29T11:00:00Z", made_by: by, frames: 2, still_file_ids: [40], current: true },
    { index: 1, made_at: "2026-10-29T09:00:00Z", made_by: by, frames: 3, still_file_ids: [30], current: false },
  ];
  const calls = fakeServer({ ...base, "GET /projects/9/storyboard": [200, [frame({ file_id: 40 })]], "GET /projects/9/storyboard/versions": [200, versions], "POST /projects/9/storyboard/versions/1/use": [200, []], "POST /projects/9/storyboard/versions/0/use": [200, []] });
  open();
  await userEvent.click(await screen.findByText("Storyboard versions · 2"));
  const list = screen.getByRole("list", { name: "Storyboard versions" });
  expect(within(list).getByText("In use")).toBeInTheDocument();
  expect(within(list).getByText(/3 frames/)).toBeInTheDocument();
  await userEvent.click(within(list).getByRole("button", { name: "Go back to this" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/storyboard/versions/1/use")).toBe(true));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/storyboard/versions/0/use")).toBe(true));
});

test("D: a clip prompt's versions go back to an earlier one, and Undo uses the one replaced", async () => {
  setViewport(390);
  const versions = [{ index: 0, made_at: "2026-10-29T11:00:00Z", made_by: null, current: true }, { index: 1, made_at: "2026-10-29T10:00:00Z", made_by: by, current: false }];
  const calls = fakeServer({ ...base, "GET /projects/9/storyboard": [200, [frame({ file_id: 40, approved: true })]], "GET /projects/9/clips/prompts/price": [200, { clip_ids: [], credits: 6 }], "GET /projects/9/video": [404, { detail: "none" }], "GET /projects/9/clips": [200, [clip({ versions })]], "POST /projects/9/clips/1/versions/1/use": [200, clip({})] });
  open("?stage=clips");
  const card = await screen.findByLabelText("Clip c1");
  await userEvent.click(within(card).getByText("Prompt versions for clip c1 · 2"));
  await userEvent.click(within(card).getByRole("button", { name: "Go back to this" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /projects/9/clips/1/versions/1/use")).toHaveLength(1));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /projects/9/clips/1/versions/1/use")).toHaveLength(2));
});

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

test("an editor who didn't make the video sees no earlier stills or versions to go back to (403 on the server)", async () => {
  setViewport(1440);
  const other = { ...base, "GET /projects/9": [200, { ...project, created_by_id: 7 }] as [number, unknown] };
  fakeServer({ ...other, "GET /projects/9/storyboard": [200, [frame({ file_id: 40, earlier: [{ file_id: 38, prompt: "p", made_at: null, made_by: null }] })]], "GET /projects/9/storyboard/versions": [200, [{ index: null, made_at: null, made_by: null, frames: 1, current: true }, { index: 1, made_at: null, made_by: null, frames: 1, current: false }]] });
  open();
  await screen.findByLabelText("Frame c1");
  expect(screen.queryByText(/Earlier stills/)).toBeNull();
  expect(screen.queryByText(/Storyboard versions/)).toBeNull();
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

test("a clip's prompt versions wait while its take is being made", async () => {
  setViewport(1440);
  const versions = [{ index: 0, made_at: null, made_by: null, current: true }, { index: 1, made_at: null, made_by: null, current: false }];
  fakeServer({
    ...base,
    "GET /jobs": [200, [{ id: 8, project_id: 9, project_clip_id: 1, step: "clip_take", status: "running", kind: "video", created_at: "2026-10-29T10:00:00Z", started_at: "2026-10-29T10:00:00Z" }]],
    "GET /projects/9/storyboard": [200, [frame({ file_id: 40, approved: true })]],
    "GET /projects/9/clips/prompts/price": [200, { clip_ids: [], credits: 6 }],
    "GET /projects/9/video": [404, { detail: "none" }],
    "GET /projects/9/clips": [200, [clip({ versions })]],
  });
  open("?stage=clips");
  const card = await screen.findByLabelText("Clip c1");
  await userEvent.click(within(card).getByText("Prompt versions for clip c1 · 2"));
  const back = within(card).getByRole("button", { name: /Go back to this/ });
  await vi.waitFor(() => expect(back).toBeDisabled());
  expect(back).toHaveAccessibleDescription(/Wait for this clip's take or prompt being made/);
});
