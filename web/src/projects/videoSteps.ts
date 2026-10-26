import type { StepState } from "../components";
import { isDone, isStale, lockReason, type Progress, type StepId } from "./steps";

/** A video made from a library version has five steps. The old six-step page keeps `steps.ts`. */
export const VIDEO_STEPS = [
  { id: "breakdown", label: "Breakdown", old: "shots" },
  { id: "assets", label: "Assets", old: "shots" },
  { id: "storyboard", label: "Storyboard", old: "storyboard" },
  { id: "clips", label: "Clips", old: "clips" },
  { id: "downloads", label: "Downloads", old: "final" },
] as const satisfies readonly { id: string; label: string; old: StepId }[];
export type VideoStepId = (typeof VIDEO_STEPS)[number]["id"];

export const videoStepFromParams = (params: URLSearchParams): VideoStepId => VIDEO_STEPS.find((s) => s.id === params.get("step"))?.id ?? "breakdown";

export type VideoProgress = Progress & { assets: { total: number; ready: number } };

/** Why a step can't be opened right now, or null when it can. Assets come before anything is drawn. */
export function videoLock(step: VideoStepId, p: VideoProgress): string | null {
  if (step === "breakdown") return null;
  const shots = lockReason("storyboard", p); // the shots are made, current and clear of problems
  if (shots || step === "assets") return shots;
  const left = p.assets.total - p.assets.ready;
  if (left > 0) return `Approve every asset first (${left} left)`;
  return lockReason(VIDEO_STEPS.find((s) => s.id === step)!.old, p);
}

/** Where a link to a locked step should land: the first earlier step that isn't finished (or is out of date), since that is what blocks it. */
export function videoBlocker(step: VideoStepId, p: VideoProgress): VideoStepId {
  const before = VIDEO_STEPS.slice(0, VIDEO_STEPS.findIndex((s) => s.id === step));
  return before.find((s) => !done(s.id, p) || (s.id !== "assets" && isStale(s.id === "breakdown" ? "shots" : s.old, p)))?.id ?? "breakdown";
}

function done(step: VideoStepId, p: VideoProgress): boolean {
  if (step === "breakdown") return isDone("shots", p);
  if (step === "assets") return p.assets.ready === p.assets.total;
  return isDone(VIDEO_STEPS.find((s) => s.id === step)!.old, p);
}

export function videoStepStates(current: VideoStepId, p: VideoProgress): { id: VideoStepId; label: string; state: StepState; reason?: string }[] {
  return VIDEO_STEPS.map((s) => {
    const reason = videoLock(s.id, p);
    const stale = s.id !== "assets" && isStale(s.id === "breakdown" ? "shots" : s.old, p);
    const state: StepState = s.id === current ? "current" : reason !== null ? "todo" : stale ? "stale" : done(s.id, p) ? "done" : "open";
    return { id: s.id, label: s.label, state, reason: reason ?? undefined };
  });
}

export const videoNext = (step: VideoStepId) => VIDEO_STEPS[VIDEO_STEPS.findIndex((s) => s.id === step) + 1] ?? null;
