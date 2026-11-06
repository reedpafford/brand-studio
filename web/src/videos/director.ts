import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { refreshJobs } from "../jobs/refresh";

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

/** The video's director run (its moves, price and notes), asked again every 5 s while it runs. */
export function useDirectorRun(projectId: number, enabled = true) {
  return useQuery({
    queryKey: ["director", projectId],
    enabled,
    queryFn: async () => (await api.GET("/projects/{project_id}/director", { params: { path: { project_id: projectId } } })).data ?? null,
    refetchInterval: (q) => (q.state.data?.status === "running" ? 5_000 : false),
  });
}

/** When a move finishes, the panel has new work: refresh it (and the header), and the waiting lists for a held move. */
export function useMovesRefresh(projectId: number, moves: number, status: string) {
  const queryClient = useQueryClient();
  useEffect(() => {
    if (!moves) return;
    void queryClient.invalidateQueries({ predicate: (q) => !["director", "freestyle"].includes(String(q.queryKey[0])) && q.queryKey.includes(projectId) });
    void refreshJobs(queryClient);
  }, [moves, status, projectId, queryClient]);
}
