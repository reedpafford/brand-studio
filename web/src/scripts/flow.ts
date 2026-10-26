import type { StepState } from "../components";
import type { Script } from "./useScript";

/** The writing flow: seven steps. Directions, Variations and Breakdown are optional. */
export const WRITING_STEPS = [
  { id: "description", label: "Description" },
  { id: "script", label: "Script" },
  { id: "directions", label: "Directions" },
  { id: "variations", label: "Variations" },
  { id: "cast", label: "Cast" },
  { id: "breakdown", label: "Breakdown" },
  { id: "publish", label: "Publish" },
] as const;
export type WritingStep = (typeof WRITING_STEPS)[number]["id"];

/** Steps that are built so far; the rest show in the picker but can't be opened yet. */
const BUILT: WritingStep[] = ["description", "script", "directions", "variations", "cast", "publish"];
/** Skippable steps that are not built yet: Next steps over them, and the picker marks them as skipped. */
export const SKIPPED: WritingStep[] = ["breakdown"];

export const stepFromParam = (p: string | null): WritingStep => (WRITING_STEPS.find((s) => s.id === p)?.id ?? "description") as WritingStep;

export const hasWords = (s: Script) => (s.versions.find((v) => v.slot === 0)?.text ?? "").trim() !== "";

export function lockReason(step: WritingStep, s: Script): string | null {
  if (!BUILT.includes(step)) return "Coming soon";
  if ((step === "directions" || step === "cast" || step === "publish") && !hasWords(s)) return "Write the script first";
  return null;
}

export function stepStates(current: WritingStep, s: Script): { id: WritingStep; label: string; state: StepState; reason?: string }[] {
  return WRITING_STEPS.map((x) => {
    const reason = lockReason(x.id, s);
    const done = x.id === "description" || (x.id === "script" && hasWords(s)) || (x.id === "cast" && hasWords(s) && (s.cast?.length ?? 0) > 0) || (x.id === "publish" && s.published);
    const state: StepState = x.id === current ? "current" : reason !== null ? "todo" : done ? "done" : "open";
    return { id: x.id, label: x.label, state, ...(reason ? { reason } : {}) };
  });
}

/** The step before and after, stepping over the optional ones that are not built yet. */
export function around(step: WritingStep) {
  const open = WRITING_STEPS.filter((x) => BUILT.includes(x.id));
  const i = open.findIndex((x) => x.id === step);
  return { prev: open[i - 1], next: open[i + 1] };
}
