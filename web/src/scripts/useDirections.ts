import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText, must } from "../api/client";
import { GOING, useJobs } from "../clip/History";
import type { EnhanceState } from "../projects/Enhance";
import { useToast } from "../toast";

const SLOT = 0;

/** Suggest directions for a library script's original, in the same shape as a video's Enhance so the same lines and buttons work. */
export function useDirections(scriptId: number, text: string): EnhanceState {
  const queryClient = useQueryClient();
  const toast = useToast();
  const path = { script_id: scriptId, slot: SLOT };
  const jobs = useJobs();
  const last = jobs.data?.filter((j) => j.kind === "write-claude" && j.step === "enhance" && j.script_id === scriptId).sort((a, b) => b.id - a.id)[0];
  const running = !!last && GOING.includes(last.status);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["directions", scriptId] });

  const marks = useQuery({
    queryKey: ["directions", scriptId, "marks", last?.status],
    queryFn: async () => (await api.GET("/scripts/{script_id}/drafts/{slot}/suggestions", { params: { path } })).data ?? [],
  });
  const notes = useQuery({
    queryKey: ["directions", scriptId, "notes", last?.status],
    queryFn: async () => (await api.GET("/scripts/{script_id}/drafts/{slot}/notes", { params: { path } })).data ?? [],
  });
  const estimate = useQuery({ queryKey: ["directions", scriptId, "estimate"], queryFn: async () => (await api.GET("/scripts/{script_id}/drafts/{slot}/enhance/estimate", { params: { path } })).data ?? null });

  const start = useMutation({
    mutationFn: async () => {
      const { error, response } = await api.POST("/scripts/{script_id}/drafts/{slot}/enhance", { params: { path } });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });
  const decide = useMutation({
    mutationFn: ({ id, verb }: { id: number; verb: "accept" | "reject" }) =>
      must(api.POST(verb === "accept" ? "/scripts/{script_id}/drafts/{slot}/suggestions/{suggestion_id}/accept" : "/scripts/{script_id}/drafts/{slot}/suggestions/{suggestion_id}/reject", { params: { path: { ...path, suggestion_id: id } } })),
    onSuccess: refresh,
  });
  const acceptMany = useMutation({
    mutationFn: async (ids: number[]) => {
      for (const suggestion_id of ids) await must(api.POST("/scripts/{script_id}/drafts/{slot}/suggestions/{suggestion_id}/accept", { params: { path: { ...path, suggestion_id } } }));
    },
    onSettled: refresh,
  });
  const putWords = async (words: string) => {
    const { error, response } = await api.PUT("/scripts/{script_id}/drafts/{slot}", { params: { path }, body: { text: words } });
    if (!response.ok) throw new Error(errorText(error));
  };
  const [gone, setGone] = useState<string[]>([]);
  const acceptedCount = (marks.data ?? []).filter((m) => m.status === "accepted").length;
  // Apply adds the accepted directions as lines; Undo saves the words from before.
  const apply = useMutation({
    mutationFn: async () => {
      await must(api.POST("/scripts/{script_id}/drafts/{slot}/apply", { params: { path } }));
    },
    onSuccess: async () => {
      await Promise.all([queryClient.invalidateQueries({ queryKey: ["script-lib", scriptId] }), refresh()]);
      toast(`Added ${acceptedCount} direction${acceptedCount === 1 ? "" : "s"}.`, async () => {
        await putWords(text);
        await Promise.all([queryClient.invalidateQueries({ queryKey: ["script-lib", scriptId] }), refresh()]);
      });
    },
  });
  const [filter, setFilter] = useState<string | null>(null);
  const [focusId, setFocusId] = useState<number | null>(null);
  const shown = (marks.data ?? []).filter((m) => m.status !== "rejected" && (!filter || m.kind === filter));
  const key = (n: { line: number; text: string }) => `${last?.id ?? 0}:${n.line}:${n.text}`;
  const visibleNotes = (notes.data ?? []).filter((n) => !gone.includes(key(n)));
  return { marks: marks.data ?? [], notes: visibleNotes, last, running, cost: estimate.data?.credits, start, decide, apply, acceptMany, dismiss: (n) => setGone((g) => [...g, key(n)]), filter, setFilter, focusId, setFocusId, shown } as EnhanceState;
}
