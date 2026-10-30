import type { StepState } from "../components";
import { isDone, isStale, lockReason, type Progress, type StepId } from "./steps";

/** A video made from a library version has five steps (item 1b): Plan (Scenes | Shots, Shots being the breakdown),
 *  Cast (the looks; the library stays "Cast & places"), Storyboard, Clips, Final cut. The old six-step page keeps `steps.ts`. */
export const VIDEO_STEPS = [
  { id: "plan", label: "Plan", old: "shots" },
  { id: "cast", label: "Cast", old: "shots" },
  { id: "storyboard", label: "Storyboard", old: "storyboard" },
  { id: "clips", label: "Clips", old: "clips" },
  { id: "downloads", label: "Final cut", old: "final" }, // the address keeps "downloads", so old links still land here
] as const satisfies readonly { id: string; label: string; old: StepId }[];
type VideoStepId = (typeof VIDEO_STEPS)[number]["id"];

// Old addresses keep working: ?step=breakdown opens Plan (on Shots), ?step=assets opens Cast.
const OLD: Record<string, VideoStepId> = { breakdown: "plan", assets: "cast" };
export const videoStepFromParams = (params: URLSearchParams): VideoStepId => {
  const asked = params.get("step") ?? "";
  return OLD[asked] ?? VIDEO_STEPS.find((s) => s.id === asked)?.id ?? "plan";
};

export type VideoProgress = Progress & { assets: { total: number; ready: number; seen: boolean } };

/** Why a step can't be opened right now, or null when it can. The cast comes before anything is drawn. */
export function videoLock(step: VideoStepId, now: VideoProgress): string | null {
  if (step === "plan") return null;
  if (step === "downloads" && now.video.made) return null; // the finished video is always reachable (#749 LW1)
  // Work already made stays open when an earlier step changes: it says "out of date" there, and its paid presses
  // wait (videoHold). Problems in the shots still come first.
  const kept = (step === "storyboard" && now.frames.total > 0) || (step === "clips" && now.clips.total > 0);
  // (Out-of-date frames read as unapproved, so clips already made don't wait on them either.)
  const frames = step === "clips" ? { ...now.frames, stale: false, approved: now.frames.total } : { ...now.frames, stale: false };
  const p = kept ? { ...now, shots: { ...now.shots, stale: false }, frames } : now;
  // The shots are made, current and clear of problems. They live in Plan, on its Shots view.
  const shots = lockReason("storyboard", p)?.replace("in Shots first", "in Plan first").replace("Make the shots first", "Make the shots in Plan first").replace("Make new shots first", "Make new shots in Plan first") ?? null;
  if (shots || step === "cast") return shots;
  const left = p.assets.total - p.assets.ready;
  if (left > 0 && !kept) return `Approve the cast first (${left} left)`; // made work stays open: its presses wait instead (videoHold)
  return lockReason(VIDEO_STEPS.find((s) => s.id === step)!.old, p);
}

/** Why a step's paid presses wait while its work stays viewable, and the step that puts it right: an earlier step changed
 *  after it was made (audit M14). */
export function videoHold(step: VideoStepId, now: VideoProgress): { why: string; at: VideoStepId } | null {
  const made = (step === "storyboard" && now.frames.total > 0) || (step === "clips" && now.clips.total > 0);
  if (!made) return null;
  if (now.shots.stale) return { why: "The plan changed after these were made. Make new shots in Plan first.", at: "plan" };
  if (step === "clips" && now.frames.stale) return { why: "The plan changed after these were made. Make the storyboard again first.", at: "storyboard" };
  // A look the cast needs isn't ready (one added, or the video's look changed and a sheet isn't made in it yet).
  const left = now.assets.total - now.assets.ready;
  if (left > 0) return { why: `${left === 1 ? "A look in the cast isn't" : `${left} looks in the cast aren't`} ready. Make or approve ${left === 1 ? "it" : "them"} in Cast first.`, at: "cast" };
  return null;
}

/** Where a link to a locked step should land: the first earlier step that isn't finished (or is out of date), since that is what blocks it. */
export function videoBlocker(step: VideoStepId, p: VideoProgress): VideoStepId {
  const before = VIDEO_STEPS.slice(0, VIDEO_STEPS.findIndex((s) => s.id === step));
  // Cast blocks only when a look isn't ready: never having opened it (its ✓ waits for that) doesn't (A15, Next-Layout's 390 walk).
  const blocks = (id: VideoStepId) => (id === "cast" ? p.assets.ready < p.assets.total : !done(id, p) || isStale(VIDEO_STEPS.find((s) => s.id === id)!.old, p));
  return before.find((s) => blocks(s.id))?.id ?? "plan";
}

function done(step: VideoStepId, p: VideoProgress): boolean {
  // Plan is done when the plan is approved and its shots are made. Until the plan has a status of its own
  // (Builder-Server-8's plan_status), the made shots decide; existing videos read as approved from their breakdown.
  if (step === "plan") return isDone("shots", p);
  if (step === "cast") return p.assets.seen && p.assets.ready === p.assets.total; // no ✓ before it has been looked at (#749 LW9)
  return isDone(VIDEO_STEPS.find((s) => s.id === step)!.old, p);
}

export function videoStepStates(current: VideoStepId, p: VideoProgress): { id: VideoStepId; label: string; state: StepState; reason?: string }[] {
  return VIDEO_STEPS.map((s) => {
    const reason = videoLock(s.id, p);
    const stale = s.id !== "cast" && isStale(s.old, p);
    const state: StepState = s.id === current ? "current" : reason !== null ? "todo" : stale ? "stale" : done(s.id, p) ? "done" : "open";
    return { id: s.id, label: s.label, state, reason: reason ?? undefined };
  });
}

export const videoNext = (step: VideoStepId) => VIDEO_STEPS[VIDEO_STEPS.findIndex((s) => s.id === step) + 1] ?? null;
