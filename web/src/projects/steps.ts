import type { StepState } from "../components";

/** A video has six steps. `?stage=enhance` and `?stage=breakdown` from before still work (they open Script and Shots). */
export const STEPS = [
  { id: "brief", label: "Brief" },
  { id: "script", label: "Script" },
  { id: "shots", label: "Shots" },
  { id: "storyboard", label: "Storyboard" },
  { id: "clips", label: "Clips" },
  { id: "final", label: "Final video" },
] as const;
export type StepId = (typeof STEPS)[number]["id"];
const ALIAS: Record<string, StepId> = { enhance: "script", breakdown: "shots" };

export function stepFromParams(params: URLSearchParams): StepId {
  const asked = params.get("stage") ?? (params.get("tab") === "script" ? "script" : "brief");
  const named = ALIAS[asked] ?? asked;
  return (STEPS.find((s) => s.id === named)?.id ?? "brief") as StepId;
}

/** What exists so far, in the few facts the steps care about. */
export type Progress = {
  script: boolean;
  shots: { made: boolean; stale: boolean; problems: number };
  frames: { total: number; approved: number; stale: boolean };
  clips: { total: number; approved: number; stale: boolean };
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
  const unapproved = p.clips.total - p.clips.approved;
  if (p.clips.total === 0) return "Make the clips first";
  if (unapproved > 0) return `Approve every clip first (${unapproved} left)`;
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

export function isDone(step: StepId, p: Progress): boolean {
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
      return p.clips.total > 0 && p.clips.approved === p.clips.total && !p.clips.stale;
    case "final":
      return p.video.made && !p.video.outOfDate;
  }
}

/** An earlier step changed after this one was done: it says "out of date". */
export function isStale(step: StepId, p: Progress): boolean {
  return (step === "shots" && p.shots.made && p.shots.stale) || (step === "storyboard" && p.frames.stale) || (step === "clips" && p.clips.stale) || (step === "final" && p.video.made && p.video.outOfDate);
}

export function stepStates(current: StepId, p: Progress): { id: StepId; label: string; state: StepState; reason?: string }[] {
  return STEPS.map((s) => {
    const reason = lockReason(s.id, p);
    const state: StepState = s.id === current ? "current" : reason !== null ? "todo" : isStale(s.id, p) ? "stale" : isDone(s.id, p) ? "done" : "open";
    return { id: s.id, label: s.label, state, reason: reason ?? undefined };
  });
}

export const nextOf = (step: StepId): (typeof STEPS)[number] | null => STEPS[STEPS.findIndex((s) => s.id === step) + 1] ?? null;
