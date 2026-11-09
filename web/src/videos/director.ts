import { useQuery } from "@tanstack/react-query";
import { api, polled } from "../api/client";
import type { components } from "../api/schema";

type Clip = components["schemas"]["ProjectClipOut"];

// Never on screen: tool names, codes, ids, JSON or model names (the Producer's condition). A line with any left is dropped
// for the plain step it belongs to.
export const NOT_PLAIN = /\b[a-z]+_[a-z_]+\b|[{}[\]<>]|"\w+"\s*:|\b[a-z]\d+\b|\bid\b|\b(claude|gpt|opus|sonnet|haiku)\b/i;

/** The server's words for a move, made plain: "c3" is clip 3 and "take 12" is that clip's take number. */
export function plain(line: string, clips: Clip[]): string {
  const out = line
    .replace(/^Refused(?: again)?:\s*(.)/, (_all, first: string) => first.toUpperCase()) // the server's "Refused:" is for the director; the status says it couldn't
    .replace(/\btake (\d+) for c(\d+)\b/g, (_all, id: string, n: string) => {
      const t = clips.find((c) => c.clip_id === `c${n}`)?.takes.find((k) => k.id === Number(id));
      return t ? `take ${t.number} for clip ${n}` : `a take for clip ${n}`;
    })
    .replace(/\bc(\d+)\b/g, "clip $1");
  return NOT_PLAIN.test(out) ? "" : out;
}

/** The video's director run (its moves, price and notes), read again when the server says it changed (./live.ts). */
export function useDirectorRun(projectId: number, enabled = true) {
  return useQuery({
    queryKey: ["director", projectId],
    enabled,
    queryFn: () => polled(api.GET("/projects/{project_id}/director", { params: { path: { project_id: projectId } } }), null),
  });
}
