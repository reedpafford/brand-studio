import type { components } from "../api/schema";
import type { Tone } from "../components";

type Project = components["schemas"]["ProjectOut"];

/** A video's status in words: what the Videos tabs and groups are made of. */
export function videoStatus(p: Pick<Project, "needs_you" | "finished_at" | "final_out_of_date" | "archived_at">): { label: string; tone: Tone } {
  if (p.archived_at) return { label: "Archived", tone: "neutral" };
  if (p.finished_at) return p.final_out_of_date ? { label: "Finished · changes waiting", tone: "warning" } : { label: "Finished", tone: "success" };
  if (p.needs_you) return { label: "Needs you", tone: "warning" };
  return { label: "Making", tone: "accent" };
}

/** Where a video opens: the new page for one made from a script version (Final cut when it is done), the earlier six-step page for the rest.
 *  A finished video whose clips changed since opens at Clips, where the changes wait (#749 LW2). */
export const videoTo = (p: Pick<Project, "script_draft_id" | "brand_id" | "id" | "final_out_of_date" | "finished_at">) =>
  p.script_draft_id ? `/b/${p.brand_id}/videos/${p.id}${p.final_out_of_date ? "?step=clips" : p.finished_at ? "?step=downloads" : ""}` : `/b/${p.brand_id}/projects/${p.id}`;
