import type { StepState } from "../components";
import type { Script } from "./useScript";

/** The writing flow: six steps. Directions, Variations and Breakdown are optional. */
export const WRITING_STEPS = [
  { id: "script", label: "Script" },
  { id: "directions", label: "Directions" },
  { id: "variations", label: "Variations" },
  { id: "cast", label: "Cast" },
  { id: "breakdown", label: "Breakdown" },
  { id: "publish", label: "Publish" },
] as const;

/** A song script (song ads): the lyrics and style, the takes, then Cast, Breakdown and Publish as a story's. No Directions or Variations (flows S1–S7). */
export const SONG_STEPS = [
  { id: "song", label: "Song" },
  { id: "takes", label: "Takes" },
  { id: "cast", label: "Cast" },
  { id: "breakdown", label: "Breakdown" },
  { id: "publish", label: "Publish" },
] as const;

type WritingStep = (typeof WRITING_STEPS)[number]["id"] | (typeof SONG_STEPS)[number]["id"];

/** What the song steps need to know about the takes: is one Preferred, and does any exist. */
export type SongState = { preferred: boolean; takes: number };

export const stepsFor = (s: Pick<Script, "kind">) => (s.kind === "song" ? SONG_STEPS : WRITING_STEPS);

export const stepFromParam = (s: Pick<Script, "kind">, p: string | null): WritingStep => {
  const steps = stepsFor(s);
  return (steps.find((x) => x.id === p)?.id ?? steps[0].id) as WritingStep;
};

export const hasWords = (s: Script) => (s.versions.find((v) => v.slot === 0)?.text ?? "").trim() !== "";

export function lockReason(step: WritingStep, s: Script, song?: SongState): string | null {
  if (s.kind === "song") {
    if (step === "song") return null;
    if (!hasWords(s)) return "Write or pick the lyrics first";
    if (step === "takes") return null;
    // Cast, Breakdown and Publish follow the Preferred take (flows S5–S7).
    if (!song?.preferred) return song && song.takes > 0 ? "Pick the preferred take first" : "Make the song first";
    return null;
  }
  if ((step === "directions" || step === "cast" || step === "breakdown" || step === "publish") && !hasWords(s)) return "Write the script first";
  return null;
}

export function stepStates(current: WritingStep, s: Script, song?: SongState): { id: WritingStep; label: string; state: StepState; reason?: string }[] {
  return stepsFor(s).map((x) => {
    const reason = lockReason(x.id, s, song);
    const words = (x.id === "script" || x.id === "song") && hasWords(s);
    const done = words || (x.id === "takes" && !!song?.preferred) || (x.id === "cast" && hasWords(s) && (s.cast?.length ?? 0) > 0) || (x.id === "breakdown" && s.versions.some((v) => v.has_breakdown)) || (x.id === "publish" && s.published);
    const state: StepState = x.id === current ? "current" : reason !== null ? "todo" : done ? "done" : "open";
    return { id: x.id, label: x.label, state, ...(reason ? { reason } : {}) };
  });
}

/** The step before and after. */
export function around(s: Pick<Script, "kind">, step: WritingStep) {
  const steps = stepsFor(s);
  const i = steps.findIndex((x) => x.id === step);
  return { prev: steps[i - 1], next: steps[i + 1] };
}
