import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import { useMe } from "../auth/useMe";
import type { components } from "../api/schema";

export type Script = components["schemas"]["app__routes__script_library__ScriptOut"];
export type ScriptPatch = components["schemas"]["ScriptPatch"];

/** One script with its versions' words, from the library API. */
export function useScript(id: number) {
  return useQuery({
    queryKey: ["script-lib", id],
    queryFn: async () => {
      const { data, response } = await api.GET("/scripts/{script_id}", { params: { path: { script_id: id } } });
      if (response.status === 404) return null;
      if (!data) throw new Error("load");
      return data;
    },
  });
}

/** Change the description fields (title, what it's for, reference, notes) until the script is published. */
export function usePatchScript(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: ScriptPatch) => {
      const { data, error } = await api.PATCH("/scripts/{script_id}", { params: { path: { script_id: id } }, body });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["script-lib", id], data);
      return queryClient.invalidateQueries({ queryKey: ["scripts"] });
    },
  });
}

/** Write the original's words (slot 0) while the script is a draft. */
export function useWriteWords(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (text: string) => {
      const { data, error } = await api.PUT("/scripts/{script_id}/drafts/{slot}", { params: { path: { script_id: id, slot: 0 } }, body: { text } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["script-lib", id], data);
      return queryClient.invalidateQueries({ queryKey: ["scripts"] });
    },
  });
}

/** The week's credits used and allowed, for an editor making their own script; null for anyone else. */
export function useWeek(script: { created_by_id: number | null } | null | undefined): { used: number; allowed: number } | null {
  const { data: me } = useMe();
  const allowance = useQuery({ enabled: me?.role !== undefined && me.role !== "owner", queryKey: ["allowance"], queryFn: async () => (await api.GET("/credits/me")).data ?? null });
  const a = allowance.data;
  if (!a || !script || script.created_by_id !== me?.id || me?.role === "owner") return null;
  return { used: a.quick_clip_credits_used, allowed: a.quick_clip_credits_allowed };
}

/** The week's allowance against a price, in words: null when it fits. */
export function weekStop(a: { quick_clip_credits_used: number; quick_clip_credits_allowed: number }, cost: number): string | null {
  if (a.quick_clip_credits_used + cost <= a.quick_clip_credits_allowed) return null;
  const allowed = Math.round(a.quick_clip_credits_allowed);
  // All of it used, or not enough left for this one: say which, with the numbers the header shows.
  return a.quick_clip_credits_used >= a.quick_clip_credits_allowed ? `You've used this week's ${allowed} credits. It resets Monday.` : `That's more than this week's ${allowed} free credits (${Math.round(a.quick_clip_credits_used)} used). It resets on Monday.`;
}

/** Why a paid step is stopped for this person, or null. An editor on their own script is billed to their weekly allowance and is declined past it (there is no Ask Reed); anyone else's script is billed to the video's budget, and Reed is never limited. */
export function useAllowanceStop(script: { created_by_id: number | null } | null | undefined, cost: number | undefined): string | null {
  const { data: me } = useMe();
  const allowance = useQuery({ enabled: me?.role !== undefined && me.role !== "owner", queryKey: ["allowance"], queryFn: async () => (await api.GET("/credits/me")).data ?? null });
  const a = allowance.data;
  if (cost === undefined || !a || !script || script.created_by_id !== me?.id || me?.role === "owner") return null;
  return weekStop(a, cost);
}
