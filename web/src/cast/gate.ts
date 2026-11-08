import { useQuery } from "@tanstack/react-query";
import { errorText } from "../api/client";

/** v6-castgate's checkpoint (#1331, GET /projects/{id}/cast): the whole set of characters and places, each with where its
 *  look came from, whether it's ready, and how it stands against the last "Approve cast & places". */
export type CastItem = {
  ref: string; // char:12, slot:3 (a role with no look yet), place:7
  kind: "character" | "place";
  name: string;
  library_item_id: number | null;
  version: number | null;
  source: "library" | "uploaded" | "video" | "script" | null;
  preview_file_id: number | null;
  readiness: "ready" | "needs_look" | "drawing" | "waiting_for_owner";
  look_fit?: { seen: string; problem: string } | null; // the look check says its sheet is wrong
  approval: "approved" | "changed" | "new";
  sig: string;
  clip_ids: string[];
  // A look made for this video: who made it and when, its last revision and the picture before it; null for a brand look.
  made_by?: string | null;
  made_at?: string | null;
  revised_by?: string | null;
  revised_at?: string | null;
  revised_why?: string | null;
  was_preview_file_id?: number | null;
  changes?: ("look" | "words" | "voice")[]; // what changed since the OK (approval "changed")
  // A character's voice now, and its voice at the last OK when it changed (sample_url is #1314's API path).
  voice?: { name: string; sample_url: string | null } | null;
  was_voice?: { name: string; sample_url: string | null } | null;
};
export type Cast = {
  state: "none" | "not_ready" | "ready" | "approved";
  approved_by: string | null;
  approved_at: string | null;
  asked: boolean;
  items: CastItem[];
  waiting: string[];
  not_ready: { ref: string; name: string; why: string }[];
  paused_clips: string[];
  update: { stills: string[]; clips: string[]; credits: number; clips_credits?: number; kept_items?: { kind: "still" | "clip"; id: string; by: string; at: string }[] };
  previews?: { credits: number; usd: number | null; budget_credits: number; budget_usd: number | null };
  can_approve?: boolean; // the video's maker or the owner; others see the state, read only
};

/** The checkpoint, or null on a server without it yet (then the cards show their own states). */
export function useCast(projectId: number) {
  return useQuery({
    queryKey: ["cast", projectId],
    retry: false,
    refetchInterval: (q) => (q.state.data?.items.some((i) => i.readiness === "drawing") ? 3000 : false),
    queryFn: async (): Promise<Cast | null> => {
      const r = await fetch(`/api/projects/${projectId}/cast`, { credentials: "same-origin" });
      if (r.status === 404) return null; // a server without the checkpoint yet
      if (!r.ok) throw new Error(errorText(await r.json().catch(() => null)));
      return (await r.json()) as Cast;
    },
  });
}

async function call(method: string, url: string, body?: unknown) {
  const r = await fetch(`/api${url}`, { method, credentials: "same-origin", headers: { "content-type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  const out = await r.json().catch(() => null);
  if (!r.ok) throw new Error(errorText(out));
  return out as Cast;
}

/** Waiting items the look check says are wrong (video 268: a man drawn for Bruno the dog): approved only "anyway". */
export const wrongLooks = (items: CastItem[]) => items.filter((i) => i.approval !== "approved" && i.look_fit);
/** "Approve cast & places": the items as this person saw them (each one's sig); 409 if anything changed meanwhile. */
export const approveCast = (projectId: number, items: CastItem[]) => call("POST", `/projects/${projectId}/cast/approve`, { seen: Object.fromEntries(items.map((i) => [i.ref, i.sig])), ...(wrongLooks(items).length ? { anyway: true } : {}) });
/** A place's look for this video: one of the brand's places, an uploaded photo (free), or made (paid, its "up to" first). */
export const pickPlace = (projectId: number, itemId: number, libraryItemId: number) => call("PUT", `/projects/${projectId}/cast/places/${itemId}`, { library_item_id: libraryItemId });
export const uploadPlace = (projectId: number, itemId: number, fileId: number) => call("POST", `/projects/${projectId}/cast/places/${itemId}/upload`, { file_id: fileId });
export const makePlace = (projectId: number, itemId: number) => call("POST", `/projects/${projectId}/cast/places/${itemId}/make-look`);
/** Keep them: the stills and clips made with an earlier look stay as they are (null: everything listed). Free. */
export const keepOld = (projectId: number, clips: string[] | null, stills: string[] | null) => call("POST", `/projects/${projectId}/cast/keep`, { ...(clips ? { clips } : {}), ...(stills ? { stills } : {}) });
