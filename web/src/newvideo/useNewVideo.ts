import { useEffect, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { SendError, type Freestyle } from "../freestyle/useFreestyle";

export type Estimate = components["schemas"]["app__routes__freestyles__EstimateOut"];
/** A send. Home adds the brand's products, whether the words are an idea (the server writes the script first) rather
 *  than a script kept word for word, and the mode. */
export type Send = components["schemas"]["FreestyleIn"];
/** How a run starts: the plan and price wait for an OK ("ask"), or it starts once the plan is ready ("auto", the owner's). */
export type Mode = NonNullable<Send["mode"]>;

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

/** The press's price: the estimate, the last one while the new one comes (`stale`), or why there is none (`failed`).
 *  A price that failed is never kept silently (Reed, 10 Nov: every long script showed the same $33.12). */
export type Price = { est?: Estimate; stale?: boolean; failed?: string | null };

/** What a send could charge at most (rules 34, 36), the owner's in dollars too, and why it would wait for the owner. Free:
 *  the server queues nothing and asks no model. A POST, as the send is: a long script doesn't fit in an address.
 *  `whole`: price the send exactly as it will be posted (the new look's New video), not the fields picked out here. */
export function useEstimate(send: Send | null, whole = false): Price {
  const q = useSettled(whole ? send : send && { type: send.type, look: send.look, shape: send.shape, text: send.text?.trim() || undefined, script_id: send.script_id, slot: send.slot ?? undefined, brand_id: send.brand_id ?? undefined, broll_look: send.broll_look ?? undefined, cast_ids: send.cast_ids ?? undefined, product_ids: send.product_ids ?? undefined, idea: send.idea ?? undefined });
  const query = useQuery({
    queryKey: ["new-video-estimate", q],
    enabled: !!q && (!!q.script_id || (!!q.text && !!q.look)),
    retry: false,
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data, error } = await api.POST("/freestyles/estimate", { body: q! });
      if (!data) throw new Error(errorText(error));
      return data;
    },
  });
  if (query.isError) return { failed: query.error.message };
  return { est: query.data, stale: query.isPlaceholderData };
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
