import type { ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import { Button } from "../components";

type Target = { of: "breakdown" } | { of: "frame"; id: number } | { of: "clip"; id: number };

/** "Keep it anyway" for one piece of advice on the breakdown, a frame or a clip. Advice never blocks; keeping it puts it away. */
export function useKeep(projectId: number, target: Target) {
  const queryClient = useQueryClient();
  const path = { project_id: projectId };
  return useMutation({
    mutationFn: async ({ problem, undo }: { problem: string; undo?: boolean }) => {
      const body = { problem };
      const query = { problem };
      const { response, error } = undo
        ? target.of === "breakdown"
          ? await api.DELETE("/projects/{project_id}/breakdown/keep", { params: { path, query } })
          : target.of === "frame"
            ? await api.DELETE("/projects/{project_id}/storyboard/frames/{frame_id}/keep", { params: { path: { ...path, frame_id: target.id }, query } })
            : await api.DELETE("/projects/{project_id}/clips/{clip_id}/keep", { params: { path: { ...path, clip_id: target.id }, query } })
        : target.of === "breakdown"
          ? await api.POST("/projects/{project_id}/breakdown/keep", { params: { path }, body })
          : target.of === "frame"
            ? await api.POST("/projects/{project_id}/storyboard/frames/{frame_id}/keep", { params: { path: { ...path, frame_id: target.id } }, body })
            : await api.POST("/projects/{project_id}/clips/{clip_id}/keep", { params: { path: { ...path, clip_id: target.id } }, body });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [{ breakdown: "breakdown", frame: "storyboard", clip: "project-clips" }[target.of], projectId] }),
  });
}

const PREFIX = "Advice: ";
export const isAdvice = (p: string) => p.startsWith(PREFIX);

/** Advice under one closed line, "Advice (n)", in a neutral tone; the count leaves out advice already kept. Real problems are shown elsewhere. */
export function AdviceList({ problems, kept = [], onKeep, busy, owner, extra, name = "Advice" }: { problems: string[]; kept?: string[]; onKeep?: (problem: string, undo?: boolean) => void; busy?: boolean; owner?: boolean; extra?: (problem: string) => ReactNode; name?: string }) {
  const advice = problems.filter(isAdvice);
  if (advice.length === 0) return null;
  const open = advice.filter((p) => !kept.includes(p));
  return (
    <details className="rounded-md border border-border bg-surface-2 px-3 text-sm" aria-label={name}>
      <summary className="flex min-h-control cursor-pointer items-center text-muted sm:min-h-control-dense">Advice ({open.length})</summary>
      <ul className="pb-2">
        {advice.map((p) => (
          <li key={p} className={`flex flex-wrap items-center gap-x-2 ${kept.includes(p) ? "text-muted" : ""}`}>
            <span className="flex-1 py-2">{p.slice(PREFIX.length)}</span>
            {extra?.(p)}
            {!onKeep ? null : kept.includes(p) ? (
              <>
                <span className="text-xs">{owner ? "Kept" : "Kept · Reed will see it"}</span>
                <Button variant="ghost" dense busy={busy} aria-label={`Undo keep: ${p.slice(PREFIX.length)}`} onClick={() => onKeep(p, true)}>
                  Undo
                </Button>
              </>
            ) : (
              <Button variant="ghost" dense busy={busy} aria-label={`Keep anyway: ${p.slice(PREFIX.length)}`} onClick={() => onKeep(p)}>
                Keep anyway
              </Button>
            )}
          </li>
        ))}
      </ul>
    </details>
  );
}
