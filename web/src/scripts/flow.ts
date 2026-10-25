import type { StepState } from "../components";
import type { Script } from "./useScript";

/** The writing flow: seven steps. Directions, Variations and Breakdown are optional. */
export const WRITING_STEPS = [
  { id: "description", label: "Description" },
  { id: "script", label: "Script" },
  { id: "directions", label: "Directions" },
  { id: "variations", label: "Variations" },
  { id: "characters", label: "Characters" },
  { id: "breakdown", label: "Breakdown" },
  { id: "publish", label: "Publish" },
] as const;
export type WritingStep = (typeof WRITING_STEPS)[number]["id"];

/** Steps that are built so far; the rest show in the picker but can't be opened yet. */
const BUILT: WritingStep[] = ["description", "script"];

export const stepFromParam = (p: string | null): WritingStep => (WRITING_STEPS.find((s) => s.id === p)?.id ?? "description") as WritingStep;

export const hasWords = (s: Script) => (s.versions.find((v) => v.slot === 0)?.text ?? "").trim() !== "";

export const lockReason = (step: WritingStep): string | null => (BUILT.includes(step) ? null : "Coming soon");

export function stepStates(current: WritingStep, s: Script): { id: WritingStep; label: string; state: StepState; reason?: string }[] {
  return WRITING_STEPS.map((x) => {
    const reason = lockReason(x.id);
    const done = x.id === "description" || (x.id === "script" && hasWords(s));
    const state: StepState = x.id === current ? "current" : reason !== null ? "todo" : done ? "done" : "open";
    return { id: x.id, label: x.label, state, ...(reason ? { reason } : {}) };
  });
}
