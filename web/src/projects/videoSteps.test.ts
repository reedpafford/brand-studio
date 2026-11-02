import { expect, test } from "vitest";
import { videoPickerStates, type VideoProgress } from "./videoSteps";

// Shots made, the cast approved, nothing drawn yet: the base the cases below change.
const base: VideoProgress = {
  script: true,
  shots: { made: true, stale: false, problems: 0 },
  frames: { total: 0, approved: 0, stale: false },
  clips: { total: 0, approved: 0, stale: false },
  video: { made: false, outOfDate: false },
  assets: { total: 1, ready: 1, seen: true },
};
const make = (p: Partial<VideoProgress>, at: "cast" | "storyboard" | "clips" | "downloads" = "cast") => videoPickerStates(at, { ...base, ...p })[2];

test("the picker has four steps, and Make is one of them", () => {
  expect(videoPickerStates("plan", base).map((s) => s.label)).toEqual(["Plan", "Cast", "Make", "Final cut"]);
});

test("Make is locked, with why, until the cast is approved", () => {
  const m = make({ assets: { total: 2, ready: 1, seen: true } });
  expect(m.state).toBe("todo");
  expect(m.reason).toMatch(/Approve the cast first \(1 left\)/);
});

test("Make is open while the stills or clips are under way, and opens on Stills until clips exist", () => {
  expect(make({})).toMatchObject({ state: "open", id: "storyboard" });
  expect(make({ frames: { total: 2, approved: 2, stale: false }, clips: { total: 2, approved: 1, stale: false } })).toMatchObject({ state: "open", id: "clips" });
});

test("Make gets its ✓ once every clip is approved", () => {
  expect(make({ frames: { total: 2, approved: 2, stale: false }, clips: { total: 2, approved: 2, stale: false } }, "downloads").state).toBe("done");
});

test("Make shows out of date (⚠) when either tab is", () => {
  expect(make({ frames: { total: 2, approved: 2, stale: true }, clips: { total: 2, approved: 2, stale: false } }, "downloads").state).toBe("stale");
  expect(make({ frames: { total: 2, approved: 2, stale: false }, clips: { total: 2, approved: 2, stale: true } }, "downloads").state).toBe("stale");
});

test("Make is the current step on either tab", () => {
  expect(make({ frames: { total: 1, approved: 1, stale: false } }, "storyboard").state).toBe("current");
  expect(make({ frames: { total: 1, approved: 1, stale: false }, clips: { total: 1, approved: 0, stale: false } }, "clips").state).toBe("current");
});
