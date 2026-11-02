import type { components } from "../api/schema";
import type { Tone } from "../components";
import { budgetUsed } from "../projects/budget";

type Project = components["schemas"]["ProjectOut"];

/** A video's four steps as the lists show them. Storyboard counts as Clips: its stills are the clips' first frames. */
export const VIDEO_STEPS = ["Plan", "Cast", "Clips", "Final cut"] as const;
const AT: Record<string, number> = { breakdown: 0, assets: 1, storyboard: 2, clips: 2, downloads: 3, done: 4 };

/** Where a video made from a script is (0–3), or 4 once finished; null for a video made the earlier way. */
export const videoAt = (p: Pick<Project, "script_draft_id" | "step" | "finished_at">) => (!p.script_draft_id ? null : p.finished_at ? 4 : (AT[p.step ?? ""] ?? 0));

/** A video's status in words: what the Videos tabs and groups are made of. */
export function videoStatus(p: Pick<Project, "needs_you" | "finished_at" | "final_out_of_date" | "archived_at">): { label: string; tone: Tone } {
  if (p.archived_at) return { label: "Archived", tone: "neutral" };
  if (p.finished_at) return p.final_out_of_date ? { label: "Finished · changes waiting", tone: "warning" } : { label: "Finished", tone: "success" };
  if (p.needs_you) return { label: "Needs you", tone: "warning" };
  return { label: "Making", tone: "accent" };
}

/** "120 / 600": the credits counted against the budget, without the director's own time. */
export const creditsOf = (p: Pick<Project, "credits_used" | "budget_credits" | "director_credits">) => `${Math.round(budgetUsed(p))} / ${Math.round(p.budget_credits)}`;

/** Where a video opens: the new page for one made from a script version (Final cut when it is done), the earlier six-step page for the rest.
 *  A finished video whose clips changed since opens at Clips, where the changes wait (#749 LW2). */
export const videoTo = (p: Pick<Project, "script_draft_id" | "brand_id" | "id" | "final_out_of_date" | "finished_at">) =>
  p.script_draft_id ? `/b/${p.brand_id}/videos/${p.id}${p.final_out_of_date ? "?step=clips" : p.finished_at ? "?step=downloads" : ""}` : `/b/${p.brand_id}/projects/${p.id}`;
