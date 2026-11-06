import { expect, test } from "vitest";
import { videoHold, videoLock, type VideoProgress } from "./videoSteps";

// Shots made, the cast approved, nothing drawn yet: the base the cases below change.
const base: VideoProgress = {
  script: true,
  shots: { made: true, stale: false, problems: 0 },
  frames: { total: 0, approved: 0, stale: false },
  clips: { total: 0, taken: 0, stale: false },
  video: { made: false, outOfDate: false },
  assets: { total: 1, ready: 1, seen: true },
};

test("the stills wait, with why, until the cast is approved", () => {
  expect(videoLock("storyboard", { ...base, assets: { total: 2, ready: 1, seen: true } })).toMatch(/Approve the cast first \(1 left\)/);
  expect(videoLock("storyboard", base)).toBeNull();
});

test("the takes wait until every still is approved", () => {
  expect(videoLock("clips", { ...base, frames: { total: 2, approved: 1, stale: false } })).toMatch(/Approve every still first/);
  expect(videoLock("clips", { ...base, frames: { total: 2, approved: 2, stale: false } })).toBeNull();
});

test("made work stays open when an earlier step changes; its paid presses wait, saying where to put it right", () => {
  const made = { ...base, frames: { total: 2, approved: 2, stale: false }, clips: { total: 2, taken: 1, stale: false } };
  expect(videoLock("clips", { ...made, shots: { ...made.shots, stale: true } })).toBeNull();
  expect(videoHold("clips", { ...made, shots: { ...made.shots, stale: true } })).toMatchObject({ at: "plan" });
  expect(videoHold("clips", { ...made, frames: { ...made.frames, stale: true } })).toMatchObject({ at: "storyboard" });
  expect(videoHold("clips", { ...made, assets: { total: 2, ready: 1, seen: true } })).toMatchObject({ at: "cast" });
  expect(videoHold("clips", made)).toBeNull();
});

test("the finished video is always reachable", () => {
  expect(videoLock("downloads", { ...base, assets: { total: 2, ready: 0, seen: true }, video: { made: true, outOfDate: true } })).toBeNull();
});
