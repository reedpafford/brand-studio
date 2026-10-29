import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import { Banner, Button } from "../components";
import type { CostAction } from "./CostBar";

const STEP = { storyboard: { label: "Storyboard", go: "storyboard" }, stills: { label: "Storyboard", go: "storyboard" }, clip_prompts: { label: "Clips", go: "clips" } } as const;

/** Update everything after this (audit M14 part 2): one server press redoes the storyboard, its stills and the clip prompts in
 *  order, priced first. `action` is the cost bar's press while the storyboard is out of date; `note` says what it runs, or where
 *  a run stopped with that step's own way on. */
export function useUpdateAfter(projectId: number, on: boolean, stopFor: (cost: number | undefined) => string | null, open: (step: string) => void): { action: CostAction | null; note: ReactNode; stopped: boolean } {
  const queryClient = useQueryClient();
  const path = { project_id: projectId };
  const plan = useQuery({
    enabled: on,
    queryKey: ["update-after", projectId],
    queryFn: async () => (await api.GET("/projects/{project_id}/update-after", { params: { path, query: { from: "plan" } } })).data ?? null,
    refetchInterval: (q) => (q.state.data?.running ? 3000 : false),
  });
  const press = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/projects/{project_id}/update-after", { params: { path, query: { from: "plan" } } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["update-after", projectId], data);
      for (const key of ["jobs", "storyboard", "project-clips", "project"]) void queryClient.invalidateQueries({ queryKey: [key] });
    },
  });
  const d = on ? plan.data : null;
  if (!d) return { action: null, note: null, stopped: false };
  const stopped = d.stopped_at && d.reason && !d.running ? STEP[d.stopped_at] : null;
  // Only when the storyboard itself is to be redone; a clip rewrite alone is the Clips step's own press.
  const redo = d.steps.some((s) => s.step !== "clip_prompts");
  const note = stopped ? (
    <Banner tone="warning" title={`Stopped at ${stopped.label}`} action={<Button variant="secondary" onClick={() => open(stopped.go)}>Open {stopped.label}</Button>}>
      {d.reason}
    </Banner>
  ) : redo && !d.running ? (
    <p className="text-sm text-muted">Update everything after this: {d.steps.map((s) => s.what).join(" · ")}.</p>
  ) : null;
  const action: CostAction | null = d.running
    ? { label: "Updating…", busy: true, onPress: () => {} }
    : redo && d.credits > 0
      ? { label: "Update everything after this", price: d.credits, reason: press.error?.message ?? stopFor(d.credits), busy: press.isPending, onPress: () => press.mutate() }
      : null;
  return { action, note, stopped: !!stopped };
}
