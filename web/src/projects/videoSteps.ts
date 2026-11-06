import { lockReason, type Progress, type StepId } from "./steps";

/** What the video page's panes wait on (v6 S3: the preview panel's Clips tab until screen 8): the stills and the takes
 *  each wait for the steps before them. The old six-step page keeps `steps.ts`. */
const VIDEO_STEPS = [
  { id: "plan", label: "Plan", old: "shots" },
  { id: "cast", label: "Cast", old: "shots" },
  { id: "storyboard", label: "Stills", old: "storyboard" }, // the stills part of Clips
  { id: "clips", label: "Clips", old: "clips" }, // the takes part of Clips
  { id: "downloads", label: "Final cut", old: "final" }, // the address keeps "downloads", so old links still land here
] as const satisfies readonly { id: string; label: string; old: StepId }[];
type VideoStepId = (typeof VIDEO_STEPS)[number]["id"];

export type VideoProgress = Progress & { assets: { total: number; ready: number; seen: boolean } };

/** Why a step can't be opened right now, or null when it can. The cast comes before anything is drawn. */
export function videoLock(step: VideoStepId, now: VideoProgress): string | null {
  if (step === "plan") return null;
  if (step === "downloads" && now.video.made) return null; // the finished video is always reachable (#749 LW1)
  // Work already made stays open when an earlier step changes: it says "out of date" there, and its paid presses
  // wait (videoHold). Problems in the shots still come first.
  const kept = (step === "storyboard" && now.frames.total > 0) || (step === "clips" && now.clips.total > 0);
  // (Out-of-date stills read as undrawn, so clips already made don't wait on them either.)
  const frames = step === "clips" ? { ...now.frames, stale: false, drawn: now.frames.total } : { ...now.frames, stale: false };
  const p = kept ? { ...now, shots: { ...now.shots, stale: false }, frames } : now;
  // The shots are made, current and clear of problems. They live in Plan, on its Shots view; the director makes them (S8).
  const shots = lockReason("storyboard", p)?.replace("in Shots first", "in Plan first").replace("Make the shots first", "The director makes the plan and its shots first").replace("Make new shots first", "The director makes new shots in Plan first") ?? null;
  if (shots || step === "cast") return shots;
  const left = p.assets.total - p.assets.ready;
  if (left > 0 && !kept) return `Approve the cast first (${left} left)`; // made work stays open: its presses wait instead (videoHold)
  // The video page calls the frames stills, everywhere (QA-11: "Make the storyboard first" beside Make the stills).
  return (
    lockReason(VIDEO_STEPS.find((s) => s.id === step)!.old, p)
      ?.replace("Make the storyboard first", "Make the stills first")
      .replace("Redo the out of date frames first", "Redo the out-of-date stills first")
      .replace(/Draw every storyboard frame first/, "Draw every still first") ?? null
  );
}

/** Why a step's paid presses wait while its work stays viewable, and the step that puts it right: an earlier step changed
 *  after it was made (audit M14). */
export function videoHold(step: VideoStepId, now: VideoProgress): { why: string; at: VideoStepId } | null {
  const made = (step === "storyboard" && now.frames.total > 0) || (step === "clips" && now.clips.total > 0);
  if (!made) return null;
  if (now.shots.stale) return { why: "The plan changed after these were made. The director makes new shots from it first.", at: "plan" };
  if (step === "clips" && now.frames.stale) return { why: "The plan changed after these were made. Redo the stills first.", at: "storyboard" };
  // A look the cast needs isn't ready (one added, or the video's look changed and a sheet isn't made in it yet).
  const left = now.assets.total - now.assets.ready;
  if (left > 0) return { why: `${left === 1 ? "A look in the cast isn't" : `${left} looks in the cast aren't`} ready. Make or approve ${left === 1 ? "it" : "them"} in Cast first.`, at: "cast" };
  return null;
}
