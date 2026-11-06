/** An earlier-way video's six steps (its card and its held requests name them). */
export const STEPS = [
  { id: "brief", label: "Brief" },
  { id: "script", label: "Script" },
  { id: "shots", label: "Shots" },
  { id: "storyboard", label: "Storyboard" },
  { id: "clips", label: "Clips" },
  { id: "final", label: "Final video" },
] as const;
export type StepId = (typeof STEPS)[number]["id"];

/** What exists so far, in the few facts the steps care about. */
export type Progress = {
  script: boolean;
  shots: { made: boolean; stale: boolean; problems: number };
  frames: { total: number; approved: number; stale: boolean };
  clips: { total: number; taken: number; stale: boolean }; // taken: clips with their take (V6 has no per-clip Approve)
  video: { made: boolean; outOfDate: boolean };
};

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/** Why a step can't be opened right now, or null when it can. */
export function lockReason(step: StepId, p: Progress): string | null {
  if (step === "brief" || step === "script") return null;
  if (!p.script) return "Finish Script first";
  if (step === "shots") return null;
  if (!p.shots.made) return "Make the shots first";
  if (p.shots.stale) return "Make new shots first";
  if (p.shots.problems > 0) return `Fix the ${plural(p.shots.problems, "problem")} in Shots first`;
  if (step === "storyboard") return null;
  const left = p.frames.total - p.frames.approved;
  if (p.frames.total === 0) return "Make the storyboard first";
  if (left > 0 || p.frames.stale) return p.frames.stale ? "Redo the out of date frames first" : `Approve every storyboard frame first (${left} left)`;
  if (step === "clips") return null;
  const untaken = p.clips.total - p.clips.taken; // as the cut asks (M2): a take for each clip, never an Approve
  if (p.clips.total === 0) return "Make the clips first";
  if (untaken > 0) return `Make every clip’s take first (${untaken} left)`;
  return null;
}

/** Where a link to a locked step should land: the first step that isn't finished (or the one before it, if it is locked). */
export function firstUnfinished(p: Progress): StepId {
  let before: StepId = "script";
  for (const s of STEPS) {
    if (s.id === "brief") continue;
    if (!isDone(s.id, p)) return lockReason(s.id, p) === null ? s.id : before;
    before = s.id;
  }
  return "final";
}

function isDone(step: StepId, p: Progress): boolean {
  switch (step) {
    case "brief":
      return true;
    case "script":
      return p.script;
    case "shots":
      return p.shots.made && !p.shots.stale && p.shots.problems === 0;
    case "storyboard":
      return p.frames.total > 0 && p.frames.approved === p.frames.total && !p.frames.stale;
    case "clips":
      return p.clips.total > 0 && p.clips.taken === p.clips.total && !p.clips.stale;
    case "final":
      return p.video.made && !p.video.outOfDate;
  }
}
