import { useEffect, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { SendError, type Freestyle } from "../freestyle/useFreestyle";

export type Estimate = components["schemas"]["app__routes__freestyles__EstimateOut"];
export type Send = components["schemas"]["FreestyleIn"];

/** The value, once it has stopped changing for a moment. */
function useSettled<T>(value: T, ms = 400) {
  const key = JSON.stringify(value) ?? "";
  const [settled, setSettled] = useState(key);
  useEffect(() => {
    const t = setTimeout(() => setSettled(key), ms);
    return () => clearTimeout(t);
  }, [key, ms]);
  return (settled ? JSON.parse(settled) : null) as T;
}

/** What a send could charge at most (rules 34, 36), the owner's in dollars too, and why it would wait for the owner. Free:
 *  the server queues nothing and asks no model. */
export function useEstimate(send: Send | null) {
  const q = useSettled(send && { type: send.type, look: send.look, shape: send.shape, text: send.text?.trim() || undefined, script_id: send.script_id, slot: send.slot ?? undefined, broll_look: send.broll_look ?? undefined });
  return useQuery({
    queryKey: ["new-video-estimate", q],
    enabled: !!q && (!!q.script_id || (!!q.text && !!q.look)),
    retry: false,
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data, error } = await api.GET("/freestyles/estimate", { params: { query: q! } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
  });
}

/** Make it: one send, as the freestyle route takes it; a version that has a video answers 409 with it (SendError). */
export function useSend(onSent: (fs: Freestyle) => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Send) => {
      const { data, error, response } = await api.POST("/freestyles", { body });
      if (response.ok && data) return data;
      const detail = (error as { detail?: unknown } | undefined)?.detail;
      if (detail && typeof detail === "object" && "project_id" in detail) {
        const d = detail as { project_id: number; up_to?: number | null; text?: string };
        throw new SendError(d.text ?? "This version already has a video.", { project_id: d.project_id, up_to: d.up_to ?? null });
      }
      throw new SendError(errorText(error));
    },
    onSuccess: (fs) => {
      queryClient.setQueryData(["freestyle", fs.id], fs);
      void queryClient.invalidateQueries({ queryKey: ["freestyles"] });
      onSent(fs);
    },
  });
}

/** "$16.86": the owner's price, never below the charge (the server rounds up to the cent). */
export const usd = (n: number) => `$${n.toFixed(2)}`;
