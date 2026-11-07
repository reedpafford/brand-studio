import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { editor, owner } from "../test/people";
import { renderApp } from "../test/render";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { recutRefused } from "./ClipOpen";
import { cutOut } from "../test/cut";

// The Clips tab (v6 S6-01 to S6-06, P-10, P-11, S-gaps-08): a short video's grid, the list grouped by scene with its
// filters, one clip open with its stills and takes, what the director's watch found and did, and its priced presses.
const project = { id: 50, brand_id: 1, name: "Beer gut doctor rant", freestyle_id: null, aspect_ratio: "9:16", look: "dr-pickle", credits_used: 60, budget_credits: 164, created_by_id: 1, created_by_name: "Reed", folder_id: 4, script_draft_id: 7, product_variants: {}, plan_status: "approved", kind: "narrated" };
const money = (credits: number, usd: number | null) => ({ credits, usd });
const head = (rate: number | null) => ({ title: "Beer gut doctor rant", status: { kind: "done", words: "Delivered", reason: null, at: null, made: 0, total: 0 }, spent: money(96, rate && 9.84), up_to: money(164, rate && 16.86), budget: money(164, rate && 16.86), folder: null, format: "Presenter", style: "Dr. Pickle", seconds: 58, song: false, usd_per_credit: rate });
const shot = (id: string, action: string, line: string | null = null) => ({ id, script_lines: [], speaker: null, line, action, reaction: null, camera: "Close", seconds: 4, character_ids: [], place_id: null, moment: null, screen_ids: [] });
/** n clips, three a scene; clip 3 has two takes: take 1 dropped by the watch, take 2 its remake in the cut. */
function video(n: number) {
  const scenes = Array.from({ length: Math.ceil(n / 3) }, (_, s) => ({ id: s + 1, heading: ["Hook", "What beer does", "The bloat"][s] ?? `Part ${s + 1}`, look: "", shots: Array.from({ length: Math.min(3, n - s * 3) }, (_, k) => shot(`${s + 1}.${k + 1}`, `Shot ${s * 3 + k + 1}`, s * 3 + k === 2 ? "Every pint sits there and ferments." : null)) }));
  const plan = scenes.flatMap((s) => s.shots).map((x, i) => ({ id: `c${i + 1}`, shot_ids: [x.id], seconds: 4, seam: "" }));
  const take = (id: number, number: number, o: object = {}) => ({ id, number, file_id: 500 + id, created_at: "2026-11-04T10:00:00Z", verdict: "clean", mutes: [], model: "Seedance 2.0", ...o });
  const clips = plan.map((c, i) => ({
    id: i + 1, clip_id: c.id, seconds: 4, prompt: `Glossy 3D torso ${i + 1}. No one speaks.`, references: [], problems: [], kept: [], file_id: 600 + i, picked_take_id: i === 2 ? 32 : 10 + i, approved: true, prompt_ok: true, take_credits: 3, stale: false, inserts: [], change: null, versions: [], spent: i === 2 ? 6.2 : 3, stills: 1,
    sound: { state: "none", how: "", asked: "", credits: 0.1 },
    takes: i === 2 ? [take(31, 1, { from_still: 799, watch: { state: "done", action: "redo", found: "Cartoon eyes landed on the stomach at 0:02.", did: "Remade it on Seedance 2.0 with “no face on the organs” in the prompt.", remake_credits: 3.1, faults: [] } }), take(32, 2, { remade_from: 1 })] : [take(10 + i, 1)],
    model: { id: "seedance-2.0", name: "Seedance 2.0", why: "Dr. Pickle’s default for B-roll.", by: "map" },
  }));
  const frames = plan.map((c, i) => ({ id: 70 + i, clip_id: c.id, shot_id: c.shot_ids[0], prompt: "p", reference_ids: [], problems: [], kept: [], file_id: 700 + i, approved: true, stale: false, still_stale: false, redrawn: false, earlier: i === 2 ? [{ file_id: 799, prompt: "old" }] : [], change: null, still_credits: 1 }));
  return { breakdown: { id: 1, script_version: 1, source: "claude", stale: false, problems: [], kept: [], breakdown: { hook: "", scenes, clips: plan } }, clips, frames };
}
function server(me: object, n: number, routes: Record<string, [number, unknown]> = {}) {
  const v = video(n);
  return fakeServer({
    "GET /auth/me": [200, me],
    "GET /brands": [200, [{ id: 1, name: "Resilia", colours: [] }]],
    "GET /looks": [200, [{ id: "dr-pickle", name: "Dr. Pickle", blurb: "", on: true, own_sample: false, lanes: [] }]],
    "GET /jobs": [200, []],
    "GET /projects/50": [200, project],
    "GET /projects/50/director": [200, { status: "ended", ended: "", turns: [], credits: 96, spent_usd: null, start_blocked: "", thread: [], unread: 0, run_price: 0 }],
    "GET /projects/50/idea": [200, head(me === editor ? null : 0.1028)],
    "GET /projects/50/clips": [200, v.clips],
    "GET /projects/50/storyboard": [200, v.frames],
    "GET /projects/50/breakdown": [200, v.breakdown],
    "GET /projects/50/script": [200, { version: 1, source: "paste", words: 9, created_by_id: 1, created_at: "2026-11-04T10:00:00Z", text: "DR. PICKLE: Every pint sits there and ferments." }],
    "GET /projects/50/assets": [200, []],
    "GET /projects/50/video": [200, { file_id: 900, take_ids: [], out_of_date: false }],
    "GET /projects/50/locks": [200, { locks: { cast: false, look: false, length: false, song: false, end_line: false, screens: [], roles: [] }, outfits: {} }],
    "GET /projects/50/clips/3/change": [200, { credits: 3.4 }],
    "GET /projects/50/storyboard/frames/72/change": [200, { credits: 3.5 }],
    "GET /projects/50/director/progress": [200, null],
    ...routes,
  });
}
const open = (q = "") => renderApp(`/b/1/videos/50?tab=clips${q}`);
afterEach(() => vi.unstubAllGlobals());

test("S6-01: a short video opens as cards: each clip's length, state and what it shows; a press opens it in the list (S-gaps-08 1)", async () => {
  setViewport(1440);
  server(owner, 6);
  open();
  expect(await screen.findByText("6 clips · 24 s · all in the cut")).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: /^Open clip \d$/ })).toHaveLength(6);
  expect(screen.getByText("Shot 2")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Open clip 3" }));
  expect(await screen.findByRole("region", { name: "Clip 3" })).toBeInTheDocument();
  const list = screen.getByRole("list", { name: "Clips by scene" });
  expect(within(list).getByRole("button", { name: /Scene 1 · Hook/ })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "All clips" }));
  expect(await screen.findByRole("button", { name: "Open clip 1" })).toBeInTheDocument();
});

test("S6-03: Swap B-roll on a clip in the cut offers the cut editor's choices and swaps it, free", async () => {
  setViewport(1440);
  const swaps = [{ kind: "in_cut", take_id: 32, label: "In the cut", file_id: 532, poster_file_id: null }, { kind: "take", take_id: 31, label: "Take 1", file_id: 531, poster_file_id: null }];
  const swap = { id: 7, kind: "swap", said: "Swapped clip 3", at: 0, director: false, by: "Reed", undone: false, applies: true, in_cut: false };
  const calls = server(owner, 24, {
    "GET /projects/50/cut": [200, cutOut()],
    "GET /projects/50/cut/swaps/c3": [200, swaps],
    "POST /projects/50/cut/edits": [201, cutOut({ edits: [{ ...swap, id: 6 }, swap] })],
    "POST /projects/50/cut/edits/7/undo": [200, cutOut()],
  });
  open("&clip=c3");
  const c = await screen.findByRole("region", { name: "Clip 3" });
  await userEvent.click(await within(c).findByRole("button", { name: "Swap B-roll · free" }));
  const list = await within(c).findByRole("list", { name: "Swap B-roll for" });
  expect(within(list).queryByRole("button", { name: "Swap for In the cut" })).toBeNull(); // what's in the cut isn't offered
  await userEvent.click(within(list).getByRole("button", { name: "Swap for Take 1" }));
  await vi.waitFor(() => expect(calls.find((x) => x.key === "POST /projects/50/cut/edits")?.body).toEqual({ snap: false, kind: "swap", piece: "c3", take_id: 31 }));
  expect(await screen.findByText("Swapped for Take 1, free. Make the cut in the Cut tab to see it.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" })); // the toast's: this swap, the newest edit
  expect(await screen.findByText("Swap undone.")).toBeInTheDocument();
  expect(calls.some((x) => x.key === "POST /projects/50/cut/edits/7/undo")).toBe(true);
});

test("S6-02 / S6-03: one clip open: what the watch found and did, its stills and takes, model and why, words, cost, prompt and priced presses", async () => {
  setViewport(1440);
  server(owner, 24);
  open("&clip=c3");
  const c = await screen.findByRole("region", { name: "Clip 3" });
  expect(within(c).getByText("Scene 1 · Hook · 4 s · B-roll")).toBeInTheDocument();
  expect(within(c).getByText("What I found watching take 1:")).toBeInTheDocument();
  expect(within(c).getByText(/Cartoon eyes landed on the stomach at 0:02\./)).toBeInTheDocument();
  expect(within(c).getByText(/Remade it on Seedance 2\.0 with “no face on the organs” in the prompt\. \$0\.32\./)).toBeInTheDocument();
  const row = within(c).getByRole("list", { name: "Stills and takes" });
  expect(within(row).getByText("Still · in use")).toBeInTheDocument();
  expect(within(row).getByText("Still 1")).toBeInTheDocument();
  expect(within(row).getByText("Take 1")).toBeInTheDocument();
  expect(within(row).getByText("Dropped: cartoon eyes landed on the stomach at 0:02")).toBeInTheDocument();
  expect(within(row).getByText("Still 2")).toBeInTheDocument(); // the one in use, numbered after the earlier one
  expect(within(row).getByText("Take 2 · in the cut")).toBeInTheDocument();
  expect(within(row).getByText("Remade on Seedance 2.0")).toBeInTheDocument();
  expect(within(c).getByText("Dr. Pickle’s default for B-roll.")).toBeInTheDocument();
  expect(within(c).getByText("“Every pint sits there and ferments.”")).toBeInTheDocument();
  expect(within(c).getByText("$0.64 (1 still, 2 takes)")).toBeInTheDocument();
  expect(within(c).getByText("Glossy 3D torso 3. No one speaks.")).toBeInTheDocument();
  expect(await within(c).findByRole("button", { name: "Change the still… · up to $0.36" })).toBeInTheDocument();
  expect(await within(c).findByRole("button", { name: "Change this… · up to $0.35" })).toBeInTheDocument();
  expect(within(c).getByRole("button", { name: "Another take · up to $0.31" })).toBeInTheDocument();
  expect(within(c).getByRole("button", { name: "Add sound effects · up to $0.02" })).toBeInTheDocument();
  expect(within(c).getByRole("link", { name: "Download" })).toHaveAttribute("href", "/api/files/532");
  expect(screen.getByText("Grouped by scene")).toBeInTheDocument();
});

test("S6-06: an editor sees credits, never dollars", async () => {
  setViewport(1440);
  server(editor, 24);
  open("&clip=c3");
  const c = await screen.findByRole("region", { name: "Clip 3" });
  expect(within(c).getByRole("button", { name: "Another take · up to 3 credits" })).toBeInTheDocument();
  expect(within(c).getByRole("button", { name: "Add sound effects · under 1 credit" })).toBeInTheDocument();
  expect(within(c).getByText("7 credits (1 still, 2 takes)")).toBeInTheDocument();
  expect(screen.queryByText(/\$/)).toBeNull();
});

test("Use this take while a cut is being made keeps the pick and says it goes in the next cut (rule 22)", async () => {
  setViewport(1440);
  server(owner, 24, {
    "POST /projects/50/clips/3/takes/31/use": [200, {}],
    "POST /projects/50/cut": [409, { detail: "Cut 2 is being made. It's ready in a moment." }],
  });
  open("&clip=c3");
  const c = await screen.findByRole("region", { name: "Clip 3" });
  await userEvent.click(await within(c).findByRole("button", { name: "Use this take · free" }));
  expect(await screen.findByText("Cut 2 is being made; your pick goes in the next cut. Make it from the Cut tab once Cut 2 is ready.")).toBeInTheDocument();
});

test("a cut that can't be made after Use this take says the server's reason", () => {
  expect(recutRefused("This piece lip-syncs the voice: it can't run longer than its picture.")).toBe(
    "Your pick is kept, but the cut wasn’t made: This piece lip-syncs the voice: it can't run longer than its picture.",
  );
});

test("the presses: Another take, Change this… with a note, Edit the prompt, Use this take (free, then the cut is made again), Use this still", async () => {
  setViewport(1440);
  const calls = server(owner, 24, {
    "POST /projects/50/clips/3/generate": [201, {}],
    "POST /projects/50/clips/3/change": [201, {}],
    "PUT /projects/50/clips/3": [200, {}],
    "POST /projects/50/clips/3/takes/31/use": [200, {}],
    "POST /projects/50/cut": [202, { number: 2, making: { number: 2 }, versions: [], going: [] }],
    "POST /projects/50/storyboard/frames/72/pick": [200, {}],
    "POST /projects/50/storyboard/frames/72/approve": [200, {}],
  });
  open("&clip=c3");
  const c = await screen.findByRole("region", { name: "Clip 3" });
  await userEvent.click(within(c).getByRole("button", { name: /^Another take/ }));
  await vi.waitFor(() => expect(calls.find((x) => x.key === "POST /projects/50/clips/3/generate")?.body).toEqual({ note: "" }));
  await userEvent.click(within(c).getByRole("button", { name: /^Change this…/ }));
  await userEvent.type(within(c).getByLabelText("Change this…"), "slower pour");
  await userEvent.click(within(c).getByRole("button", { name: /^Change it/ }));
  await vi.waitFor(() => expect(calls.find((x) => x.key === "POST /projects/50/clips/3/change")?.body).toEqual({ note: "slower pour" }));
  await userEvent.click(await within(c).findByRole("button", { name: "Edit" }));
  const box = within(c).getByLabelText("The director’s prompt");
  await userEvent.clear(box);
  await userEvent.type(box, "A new prompt.");
  await userEvent.click(within(c).getByRole("button", { name: "Save the prompt" }));
  await vi.waitFor(() => expect(calls.find((x) => x.key === "PUT /projects/50/clips/3")?.body).toEqual({ prompt: "A new prompt.", references: [] }));
  await userEvent.click(await within(c).findByRole("button", { name: "Use this take · free" }));
  await vi.waitFor(() => expect(calls.some((x) => x.key === "POST /projects/50/clips/3/takes/31/use")).toBe(true));
  await vi.waitFor(() => expect(calls.some((x) => x.key === "POST /projects/50/cut")).toBe(true)); // the cut, made again by itself
  // Take 1 was made from still 1: picking that still back brings take 1 back, free, with no new take (S-gaps-08 2).
  await userEvent.click(within(c).getByRole("button", { name: "Use this still · free · take 1 comes back" }));
  await vi.waitFor(() => expect(calls.find((x) => x.key === "POST /projects/50/storyboard/frames/72/pick")?.body).toEqual({ file_id: 799 }));
  await vi.waitFor(() => expect(calls.filter((x) => x.key === "POST /projects/50/clips/3/takes/31/use")).toHaveLength(2));
  expect(calls.filter((x) => x.key === "POST /projects/50/clips/3/generate")).toHaveLength(1);
});

const cell = (n: number, state: string, o: object = {}) => ({ clip_id: `c${n}`, number: n, scene: Math.ceil(n / 3), label: `Shot ${n}`, seconds: 6, model: "Omni 720p", state, frame_file_id: 700 + n, take_id: state === "todo" || state === "making" ? null : n, note: "", percent: null, minutes_left: null, credits: null, changed: false, watched: true, found: false, ...o });
function progress(n: number) {
  const states: Record<number, [string, object?]> = { 5: ["flagged", { note: "Her voice drifts · remake or keep", found: true }], 6: ["making", { percent: 45, minutes_left: 3, note: "The still is ready; the take is being made" }], 7: ["failed", { note: "The service was busy. Nothing was charged.", credits: "free" }], 8: ["redone", { found: true }] };
  const scenes = Array.from({ length: Math.ceil(n / 3) }, (_, s) => ({ id: s + 1, name: `Part ${s + 1}`, total: 3, done: 3, clips: [1, 2, 3].map((k) => s * 3 + k).filter((x) => x <= n).map((x) => cell(x, states[x]?.[0] ?? "done", states[x]?.[1])) }));
  return { status: "working", clips: n, made: n - 2, scenes, counts: { all: n, needs_you: 2, flagged: 2, redone: 1 } };
}

test("S6-04 / S6-05: a long video lists by scene with filters and counts from the run, a search, and each row's state", async () => {
  setViewport(1440);
  server(owner, 40, { "GET /projects/50/director/progress": [200, progress(40)] });
  open("&clip=c5");
  const tabs = await screen.findByRole("tablist", { name: "Show" });
  expect(within(tabs).getAllByRole("tab").map((t) => t.textContent)).toEqual(["All 40", "Needs you 2", "Flagged 2", "Redone 1"]);
  expect(screen.getByText("38 of 40 made")).toBeInTheDocument();
  const list = screen.getByRole("list", { name: "Clips by scene" });
  expect(within(list).getByRole("button", { name: /2\. Part 2/ })).toHaveAttribute("aria-expanded", "true"); // the open clip's scene
  expect(within(list).getByRole("button", { name: /5\. Part 5/ })).toHaveAttribute("aria-expanded", "false");
  expect(within(list).getByText("Her voice drifts · remake or keep")).toBeInTheDocument();
  expect(within(list).getByText("Making · about 3 min")).toBeInTheDocument();
  expect(within(list).getByRole("progressbar", { name: "Clip 6 made so far" })).toHaveAttribute("aria-valuenow", "45");
  await userEvent.click(within(tabs).getByRole("tab", { name: "Needs you 2" }));
  expect(within(list).getByText("The service was busy. Nothing was charged.")).toBeInTheDocument(); // a filter unfolds every scene
  expect(within(list).getAllByText(/^Clip \d+$/).map((b) => b.textContent)).toEqual(["Clip 5", "Clip 7"]);
  await userEvent.click(within(tabs).getByRole("tab", { name: "All 40" }));
  await userEvent.type(screen.getByLabelText("Find a clip or a line"), "Shot 31");
  expect(within(list).getAllByText(/^Clip \d+$/).map((b) => b.textContent)).toEqual(["Clip 31"]);
});

test("S6-04: a clip the watch flagged asks: Remake it at its price (with the watch's note), or Keep it", async () => {
  setViewport(1440);
  const v = video(24);
  const flagged = { ...v.clips[4], takes: [{ ...v.clips[4].takes[0], watch: { state: "done", action: "flagged", found: "Dana’s voice drifts: it sounds higher than in scene 1.", did: "", note: "same voice as scene 1", faults: [] } }] };
  const calls = server(owner, 24, { "GET /projects/50/clips": [200, v.clips.map((c, i) => (i === 4 ? flagged : c))], "POST /projects/50/clips/5/takes/14/keep": [200, {}], "POST /projects/50/clips/5/generate": [201, {}], "GET /projects/50/clips/5/change": [200, { credits: 3 }] });
  open("&clip=c5");
  const c = await screen.findByRole("region", { name: "Clip 5" });
  expect(within(c).getByText("Dana’s voice drifts: it sounds higher than in scene 1.")).toBeInTheDocument();
  await userEvent.click(within(c).getByRole("button", { name: "Remake it · up to $0.31" }));
  await vi.waitFor(() => expect(calls.find((x) => x.key === "POST /projects/50/clips/5/generate")?.body).toEqual({ note: "same voice as scene 1" }));
  await userEvent.click(within(c).getByRole("button", { name: "Keep it" }));
  await vi.waitFor(() => expect(calls.some((x) => x.key === "POST /projects/50/clips/5/takes/14/keep")).toBe(true));
});

test("P-10 / P-11: on a phone the scenes fold, a clip in the cut says Done, and a tap opens it full screen with Back", async () => {
  setViewport(390);
  server(owner, 24);
  open();
  const list = await screen.findByRole("list", { name: "Clips by scene" });
  expect(within(list).getByRole("button", { name: /1\. Hook/ })).toBeInTheDocument();
  expect(within(list).getAllByText("Done").length).toBeGreaterThan(0);
  await userEvent.click(within(list).getByRole("button", { name: /Clip 3/ }));
  const c = await screen.findByRole("region", { name: "Clip 3" });
  expect(within(c).getByText("Found:")).toBeInTheDocument();
  expect(within(c).getByRole("button", { name: "Another take · up to $0.31" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Back to the clips" }));
  expect(await screen.findByRole("list", { name: "Clips by scene" })).toBeInTheDocument();
});

test("rule 22: a clip whose prompt has a problem says so, with its free one-click fix and Undo; a refused prompt is reworded the same way", async () => {
  setViewport(1440);
  const v = video(24);
  const bad = { ...v.clips[2], problems: ["The prompt says 12 s but the clip is 4 s."] };
  const calls = server(owner, 24, {
    "GET /projects/50/clips": [200, v.clips.map((c, i) => (i === 2 ? bad : c))],
    "POST /projects/50/clips/3/fix": [200, { fixed: true, before: "the old prompt", after: "the new prompt", reason: "", job: null, clip: bad }],
    "PUT /projects/50/clips/3": [200, {}],
  });
  open("&clip=c3");
  const c = await screen.findByRole("region", { name: "Clip 3" });
  expect(within(c).getByText("The prompt says 12 s but the clip is 4 s.")).toBeInTheDocument();
  await userEvent.click(within(c).getByRole("button", { name: "Fix this clip’s prompt · free" }));
  await vi.waitFor(() => expect(calls.some((x) => x.key === "POST /projects/50/clips/3/fix")).toBe(true));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.find((x) => x.key === "PUT /projects/50/clips/3")?.body).toEqual({ prompt: "the old prompt", references: [] }));
});

test("rule 13: a brand screen in the clip can use the real image, free", async () => {
  setViewport(1440);
  const v = video(24);
  const withScreen = { ...v.clips[2], inserts: [{ shot_id: "1.3", asset_id: "screen:4", name: "fomo home", start: 1, end: 2.5, use_real_image: false }] };
  const calls = server(owner, 24, { "GET /projects/50/clips": [200, v.clips.map((c, i) => (i === 2 ? withScreen : c))], "PUT /projects/50/clips/3/inserts/1.3": [200, {}] });
  open("&clip=c3");
  const c = await screen.findByRole("region", { name: "Clip 3" });
  await userEvent.click(within(c).getByRole("checkbox", { name: /Use the real image: fomo home/ }));
  await vi.waitFor(() => expect(calls.find((x) => x.key === "PUT /projects/50/clips/3/inserts/1.3")?.body).toEqual({ use_real_image: true }));
});

test("QA: a change that stopped says why with Try again; a clip made for an older plan rewrites its prompt first; a Review link's ?to= opens its clip", async () => {
  setViewport(1440);
  const v = video(24);
  const stopped = { ...v.clips[2], change: { note: "slower pour", status: "failed", error: "The prompt was edited meanwhile. Try the note again." } };
  const old = { ...v.clips[3], stale: true };
  const calls = server(owner, 24, {
    "GET /projects/50/clips": [200, v.clips.map((c, i) => (i === 2 ? stopped : i === 3 ? old : c))],
    "POST /projects/50/clips/3/change": [201, {}],
    "GET /projects/50/clips/prompts/price": [200, { clip_ids: ["c4"], credits: 1 }],
    "POST /projects/50/clips/prompts": [201, {}],
    "GET /projects/50/clips/4/change": [200, { credits: 3 }],
  });
  open("&to=Clip c3");
  const c = await screen.findByRole("region", { name: "Clip 3" });
  expect(within(c).getByText("The prompt was edited meanwhile. Try the note again.")).toBeInTheDocument();
  await userEvent.click(within(c).getByRole("button", { name: "Try again" }));
  await vi.waitFor(() => expect(calls.find((x) => x.key === "POST /projects/50/clips/3/change")?.body).toEqual({ note: "slower pour" }));
  await userEvent.click(screen.getByRole("button", { name: /^Clip 4/ }));
  const four = await screen.findByRole("region", { name: "Clip 4" });
  expect(within(four).getByText(/made for an older plan/)).toBeInTheDocument();
  expect(within(four).queryByRole("button", { name: /^Change this…/ })).toBeNull();
  await userEvent.click(await within(four).findByRole("button", { name: "Rewrite its prompt · up to $0.11" }));
  await vi.waitFor(() => expect(calls.find((x) => x.key === "POST /projects/50/clips/prompts")?.body).toEqual({ clip_id: "c4" }));
});

test("a clip held for the cast and places OK says who it waits for, with Open Cast (#1331)", async () => {
  setViewport(1440);
  const v = video(24);
  const fresh = { ...v.clips[3], picked_take_id: null, takes: [], approved: false };
  const gateOut = { state: "ready", approved_by: null, approved_at: null, asked: true, items: [{ ref: "char:9", kind: "character", name: "Nate", library_item_id: 9, version: 1, source: "video", preview_file_id: null, readiness: "ready", approval: "new", sig: "s", clip_ids: ["c4"] }], waiting: ["Nate"], not_ready: [], paused_clips: ["c4"], update: { stills: [], clips: [], credits: 0 } };
  server(owner, 24, { "GET /projects/50/clips": [200, v.clips.map((c, i) => (i === 3 ? fresh : c))], "GET /projects/50/cast": [200, gateOut], "GET /projects/50/clips/4/change": [200, { credits: 3 }] });
  open("&clip=c4");
  const c = await screen.findByRole("region", { name: "Clip 4" });
  expect(within(c).getByText("Nate waits for the cast and places OK. Approve them in Cast to go on.")).toBeInTheDocument();
  await userEvent.click(within(c).getByRole("button", { name: "Open Cast" }));
  expect(await screen.findByRole("tab", { name: /Cast/, selected: true })).toBeInTheDocument();
});

test("Reed 6: the review lists what the checks found with its action, and a check that didn't run never reads as fine", async () => {
  setViewport(1440);
  const v = video(24);
  const c3 = v.clips[2];
  const picked = { ...c3.takes[1], check: { id: 81, status: "advice", findings: [{ index: 0, kind: "face", text: "Mom's face may differ from her sheet", note: "keep Mom's face as on her sheet", fix: "" }] }, words: { id: 82, status: "failed", findings: [] }, mutes: [] };
  const withMute = { ...picked, check: { id: 81, status: "advice", findings: [...picked.check.findings, { index: 1, kind: "sound", text: "An unscripted gasp at 1.2 s", note: "", fix: "", at: 1.2, mute: [1.1, 1.5] }] } };
  const calls = server(owner, 24, {
    "GET /projects/50/clips": [200, v.clips.map((c, i) => (i === 2 ? { ...c3, takes: [c3.takes[0], withMute] } : c))],
    "POST /projects/50/checks/81/findings/0/dismiss": [200, {}],
    "POST /projects/50/clips/3/mute": [200, { ...c3, takes: [c3.takes[0], { ...withMute, mutes: [[1.1, 1.5]] }] }],
  });
  open("&clip=c3");
  const review = await screen.findByRole("region", { name: "Review" });
  expect(within(review).getByText("Words: the check didn’t finish, so it isn’t known. Watch it yourself.")).toBeInTheDocument();
  expect(within(review).queryByText(/Looks fine|nothing found/)).toBeNull();
  expect(within(review).getByText("Mom's face may differ from her sheet")).toBeInTheDocument();
  expect(await within(review).findAllByRole("button", { name: "Fix it with a note · up to $0.35" })).toHaveLength(1); // the change's price, not a take's
  await userEvent.click(within(review).getAllByRole("button", { name: /Fix it with a note/ })[0]);
  expect(screen.getByLabelText("Change this…")).toHaveValue("keep Mom's face as on her sheet");
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  await userEvent.click(within(screen.getByRole("region", { name: "Review" })).getByRole("button", { name: /Mute this stretch/ }));
  await vi.waitFor(() => expect(calls.find((x) => x.key === "POST /projects/50/clips/3/mute")?.body).toEqual({ start: 1.1, end: 1.5 }));
  await userEvent.click(within(screen.getByRole("region", { name: "Review" })).getAllByRole("button", { name: "Keep it" })[0]);
  await vi.waitFor(() => expect(calls.some((x) => x.key === "POST /projects/50/checks/81/findings/0/dismiss")).toBe(true));
});

test("Reed 4 and 5: History keeps earlier prompts (going back makes nothing), and What changed shows before and after with Restore", async () => {
  setViewport(1440);
  const v = video(24);
  const c3 = { ...v.clips[2], versions: [{ index: 0, made_at: "2026-11-04T10:00:00Z", made_by: null, current: true, prompt: "Now prompt." }, { index: 1, made_at: "2026-11-04T09:00:00Z", made_by: { id: 1, name: "Reed" }, current: false, prompt: "Earlier prompt." }], change: { note: "slower pour", status: "done", before: "Earlier prompt.", after: "Now prompt.", was_take_id: 31 } };
  const calls = server(owner, 24, { "GET /projects/50/clips": [200, v.clips.map((c, i) => (i === 2 ? c3 : c))], "POST /projects/50/clips/3/versions/1/use": [200, c3], "POST /projects/50/clips/3/takes/31/use": [200, c3] });
  open("&clip=c3");
  const c = await screen.findByRole("region", { name: "Clip 3" });
  await userEvent.click(within(c).getByText("History · 1 earlier prompt"));
  expect(within(c).getAllByText("Earlier prompt.").length).toBeGreaterThan(0);
  await userEvent.click(within(c).getByRole("button", { name: "Go back to this prompt" }));
  expect(within(c).getByText(/Free\. Nothing is made: the take in the cut stays as it is\./)).toBeInTheDocument();
  await userEvent.click(within(c).getByRole("button", { name: "Use this prompt again" }));
  await vi.waitFor(() => expect(calls.some((x) => x.key === "POST /projects/50/clips/3/versions/1/use")).toBe(true));
  expect(calls.some((x) => x.key === "POST /projects/50/clips/3/generate")).toBe(false); // never makes a take
  await userEvent.click(within(c).getByText("What changed"));
  expect(within(c).getByText("This clip: “slower pour”")).toBeInTheDocument();
  await userEvent.click(within(c).getByRole("button", { name: /Restore the earlier version/ }));
  await vi.waitFor(() => expect(calls.some((x) => x.key === "POST /projects/50/clips/3/takes/31/use")).toBe(true));
});

test("Reed 9: the notes saved on the script stay readable in the Script tab", async () => {
  setViewport(1440);
  server(owner, 6, { "GET /projects/50/script/notes": [200, [{ line: 1, text: "Say 'ferments' slowly." }]] });
  renderApp("/b/1/videos/50?tab=script");
  const notes = await screen.findByRole("region", { name: "Notes on the script" });
  expect(within(notes).getByText("Say 'ferments' slowly.")).toBeInTheDocument();
});


test("QA: a kept finding stays said with Undo and never reads as nothing found; a muted stretch shows as muted; a failed watch says so", async () => {
  setViewport(1440);
  const v = video(24);
  const c3 = v.clips[2];
  const picked = { ...c3.takes[1], check: { id: 81, status: "ok", findings: [], kept: [{ index: 0, kind: "face", text: "Mom's face may differ from her sheet", note: "" }] }, words: { id: 82, status: "advice", findings: [{ index: 0, kind: "sound", text: "A gasp", note: "", mute: [1.1, 1.5] }] }, mutes: [[1.1, 1.5]], watch: { state: "failed", faults: [] } };
  const calls = server(owner, 24, { "GET /projects/50/clips": [200, v.clips.map((c, i) => (i === 2 ? { ...c3, takes: [c3.takes[0], picked] } : c))], "POST /projects/50/checks/81/findings/0/restore": [200, {}] });
  open("&clip=c3");
  const review = await screen.findByRole("region", { name: "Review" });
  expect(within(review).queryByText(/nothing found/)).toBeNull();
  expect(within(review).getByText("1 kept as it is")).toBeInTheDocument();
  expect(within(review).getByText("The director’s watch didn’t finish, so it isn’t known. Watch it yourself.")).toBeInTheDocument();
  expect(within(review).queryByRole("button", { name: /Mute this stretch/ })).toBeNull();
  expect(within(review).getByText("Muted in the cut.")).toBeInTheDocument();
  await userEvent.click(within(review).getAllByRole("button", { name: "Undo" })[0]);
  await vi.waitFor(() => expect(calls.some((x) => x.key === "POST /projects/50/checks/81/findings/0/restore")).toBe(true));
});

test("Reed 9: Rename is in the video's ⋯ menu, with Undo", async () => {
  setViewport(1440);
  const calls = server(owner, 6, { "PATCH /projects/50": [200, project] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "More for Beer gut doctor rant" }));
  await userEvent.click(await screen.findByRole("menuitem", { name: "Rename…" }));
  const box = screen.getByLabelText("Name");
  await userEvent.clear(box);
  await userEvent.type(box, "Beer gut, take two");
  await userEvent.click(screen.getByRole("button", { name: "Rename" }));
  await vi.waitFor(() => expect(calls.find((x) => x.key === "PATCH /projects/50")?.body).toEqual({ name: "Beer gut, take two" }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((x) => x.key === "PATCH /projects/50").at(-1)?.body).toEqual({ name: "Beer gut doctor rant" }));
});

test("QA: when the change's price can't be read, Fix it with a note says why instead of waiting", async () => {
  setViewport(1440);
  const v = video(24);
  const c3 = v.clips[2];
  const picked = { ...c3.takes[1], check: { id: 81, status: "advice", findings: [{ index: 0, kind: "face", text: "Mom's face may differ", note: "keep her face" }] } };
  server(owner, 24, { "GET /projects/50/clips": [200, v.clips.map((c, i) => (i === 2 ? { ...c3, takes: [c3.takes[0], picked] } : c))], "GET /projects/50/clips/3/change": [409, { detail: "This clip was made for an older breakdown." }] });
  open("&clip=c3");
  const review = await screen.findByRole("region", { name: "Review" });
  await vi.waitFor(() => expect(within(review).getByRole("button", { name: /Fix it with a note/ })).toBeDisabled());
  expect(within(review).getByText("This clip was made for an older breakdown.")).toBeInTheDocument();
});

test("Reed, rule 21: saving an edited prompt makes nothing; the clip reads out of date with Another take at its price, and the takes stay", async () => {
  setViewport(1440);
  const v = video(24);
  const c3 = v.clips[2];
  const stale = { ...c3, take_stale: true };
  const calls = server(owner, 24, { "GET /projects/50/clips": [200, v.clips.map((c, i) => (i === 2 ? c3 : c))], "PUT /projects/50/clips/3": [200, stale] });
  open("&clip=c3");
  const c = await screen.findByRole("region", { name: "Clip 3" });
  await userEvent.click(within(c).getByRole("button", { name: "Edit" }));
  await userEvent.type(within(c).getByLabelText("The director’s prompt"), " Slower.");
  await userEvent.click(within(c).getByRole("button", { name: "Save the prompt" }));
  expect(await screen.findByText(/Prompt saved\. Nothing was made/)).toBeInTheDocument();
  expect(calls.some((x) => x.key === "POST /projects/50/clips/3/generate")).toBe(false);
});

test("rule 21: an out-of-date take stays in the cut, with Another take at its price", async () => {
  setViewport(1440);
  const v = video(24);
  server(owner, 24, { "GET /projects/50/clips": [200, v.clips.map((c, i) => (i === 2 ? { ...c, take_stale: true } : c))] });
  open("&clip=c3");
  const c = await screen.findByRole("region", { name: "Clip 3" });
  expect(within(c).getByText(/Out of date: the take in the cut was made before the prompt or its pictures changed/)).toBeInTheDocument();
  expect(within(c).getAllByRole("button", { name: "Another take · up to $0.31" }).length).toBeGreaterThan(0);
  expect(within(c).getByText("Take 2 · in the cut")).toBeInTheDocument();
});

test("QA rule 22: Another take says why it can't start yet, instead of failing on the press", async () => {
  setViewport(1440);
  const v = video(24);
  server(owner, 24, { "GET /projects/50/clips": [200, v.clips.map((c, i) => (i === 2 ? { ...c, problems: ["The prompt says 12 s but the clip is 4 s."] } : c))] });
  open("&clip=c3");
  const c = await screen.findByRole("region", { name: "Clip 3" });
  expect(within(c).getByRole("button", { name: /^Another take/ })).toBeDisabled();
  expect(within(c).getByText("Fix this clip’s prompt first (above, free).")).toBeInTheDocument();
});

test("a stopped video's data never breaks Clips: a clip too long for its model (S3-11), a plan scene with no shots, a clip with no takes", async () => {
  setViewport(1440);
  const v = video(3);
  const cell = { clip_id: "c1", number: 1, scene: 1, label: "Shot 1", seconds: 115, model: "Seedance 2.0", state: "too_long", frame_file_id: null, take_id: null, note: "It's 115 s; the model makes 12 s.", percent: null, minutes_left: null, credits: null, changed: false, watched: true, found: false };
  const run = { status: "needs_fix", clips: 1, made: 0, scenes: [{ id: 1, name: "Hook", total: 1, done: 0, clips: [cell] }], counts: { all: 1, needs_you: 1, flagged: 0, redone: 0 } };
  const older = { ...v.breakdown, breakdown: { ...v.breakdown.breakdown, scenes: [{ id: 1, heading: "Hook", look: "" }], clips: [{ id: "c1", seconds: 115, seam: "" }] } };
  server(owner, 3, { "GET /projects/50/director/progress": [200, run], "GET /projects/50/breakdown": [200, older], "GET /projects/50/clips": [200, [{ ...v.clips[0], picked_take_id: null, takes: [] }]], "GET /projects/50/storyboard": [200, []] });
  open();
  expect(await screen.findByText("Too long for its model")).toBeInTheDocument(); // it said "undefined is not iterable" and took the page down
  expect(screen.queryByRole("alert", { name: /couldn’t show/ })).toBeNull();
});

test("rule 21 (S-gaps-08): a still its check flagged shows in the open clip with its Advice, Change the still… with the note, and Keep it", async () => {
  setViewport(1440);
  const v = video(6);
  const flagged = { id: 81, status: "advice", findings: [{ index: 0, kind: "anatomy", text: "His left hand has six fingers.", note: "Give him five fingers on each hand.", fix: "Change the still with that note, or keep it." }], kept: [] };
  const frames = v.frames.map((f) => (f.clip_id === "c3" ? { ...f, check: flagged } : f));
  const calls = server(owner, 6, { "GET /projects/50/storyboard": [200, frames], "POST /projects/50/checks/81/findings/0/dismiss": [200, {}] });
  open("&clip=c3");
  const c = await screen.findByRole("region", { name: "Clip 3" });
  const check = within(c).getByRole("region", { name: "The still's check" });
  expect(within(check).getByText("His left hand has six fingers.")).toBeInTheDocument();
  expect(within(check).queryByText("Change the still with that note, or keep it.")).toBeNull(); // a take's words: the presses say it
  expect(within(check).getByText("a new still and a new take")).toBeInTheDocument();
  await userEvent.click(await within(check).findByRole("button", { name: "Change the still… · up to $0.36" }));
  expect(within(c).getByLabelText("Change the still…")).toHaveValue("Give him five fingers on each hand.");
  await userEvent.click(within(c).getByRole("button", { name: "Cancel" }));
  await userEvent.click(within(within(c).getByRole("region", { name: "The still's check" })).getByRole("button", { name: "Keep it" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/50/checks/81/findings/0/dismiss")).toBe(true));
});

test("a clean still's check says so", async () => {
  setViewport(1440);
  const v = video(6);
  const frames = v.frames.map((f) => (f.clip_id === "c3" ? { ...f, check: { id: 82, status: "ok", findings: [], kept: [] } } : f));
  server(owner, 6, { "GET /projects/50/storyboard": [200, frames] });
  open("&clip=c3");
  const c = await screen.findByRole("region", { name: "Clip 3" });
  expect(within(c).getByText("The still: checked, nothing found.")).toBeInTheDocument();
});

test("a still's check with no price to read: its Change the still… is greyed with why, as the clip's own", async () => {
  setViewport(1440);
  const v = video(6);
  const flagged = { id: 81, status: "advice", findings: [{ index: 0, kind: "anatomy", text: "His left hand has six fingers.", note: "Five fingers.", fix: "" }], kept: [] };
  const frames = v.frames.map((f) => (f.clip_id === "c3" ? { ...f, check: flagged } : f));
  server(owner, 6, { "GET /projects/50/storyboard": [200, frames], "GET /projects/50/storyboard/frames/72/change": [409, { detail: "Its look isn't approved yet." }] });
  open("&clip=c3");
  const c = await screen.findByRole("region", { name: "Clip 3" });
  const check = within(c).getByRole("region", { name: "The still's check" });
  await vi.waitFor(() => expect(within(check).getByRole("button", { name: /^Change the still…/ })).toBeDisabled());
  expect(within(check).getByRole("button", { name: /^Change the still…/ })).toHaveAccessibleDescription("Its look isn't approved yet.");
});
