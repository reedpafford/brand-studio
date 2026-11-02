import { useEffect, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import type { Tone } from "../components";

/** Freestyle (Reed's redesign, replaces Quick clip): a video from a pasted script or a described clip, changed by chatting.
 *  Every editor send waits for Reed before anything is spent; Reed's own run at once. Next-Server's /freestyles (#1159).
 *  Dialogue is made by the director; the owner's OK covers its whole price (`up_to`, #1171). */
export type Freestyle = components["schemas"]["FreestyleOut"];
export type Row = components["schemas"]["FreestyleRow"];
export type Kind = Freestyle["type"];
export type Shape = Freestyle["shape"];
export type Settings = { type: Kind; look: string; shape: Shape; brand_id: number | null };

export const TYPES: { id: Kind; name: string; soon?: boolean }[] = [
  { id: "dialogue", name: "Dialogue" },
  { id: "song", name: "Song", soon: true },
  { id: "narrated", name: "Narrated", soon: true },
  { id: "one_clip", name: "One clip" },
];
export const SOON = "Song and Narrated are coming next; One clip and Dialogue work now.";export const SHAPES: Shape[] = ["9:16", "1:1", "16:9"];
export const typeName = (t: Kind) => TYPES.find((x) => x.id === t)?.name ?? t;

/** A status as a dot and words: the colour is the second signal. */
export const STATUS: Record<Freestyle["status"], { words: string; tone: Tone }> = {
  waiting: { words: "Waiting for approval", tone: "warning" },
  working: { words: "Working", tone: "accent" },
  delivered: { words: "Delivered", tone: "success" },
  declined: { words: "Declined", tone: "danger" },
  stopped: { words: "Stopped", tone: "neutral" },
  withdrawn: { words: "Withdrawn", tone: "neutral" },
  failed: { words: "Didn't finish", tone: "danger" },
};
export const busy = (s: Freestyle["status"] | undefined) => s === "waiting" || s === "working";

async function call<T>(p: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await p;
  if (!response.ok || data === undefined) throw new Error(errorText(error));
  return data;
}

/** Yours, newest first; `everyone` (Reed only): the whole team's. Refreshed while any of them is waiting or working. */
export function useFreestyles(everyone: boolean) {
  return useQuery({
    queryKey: ["freestyles", everyone],
    queryFn: () => call(api.GET("/freestyles", { params: { query: { everyone } } })),
    refetchInterval: (q) => (q.state.data?.some((r) => busy(r.status)) ? 5_000 : false),
  });
}

/** One freestyle, asked again every 4 s while it waits for Reed or is being made; a new status refreshes the list. */
export function useFreestyle(id: number | null) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["freestyle", id],
    enabled: id !== null,
    queryFn: () => call(api.GET("/freestyles/{freestyle_id}", { params: { path: { freestyle_id: id! } } })),
    refetchInterval: (q) => (busy(q.state.data?.status) ? 4_000 : false),
  });
  const status = query.data?.status;
  useEffect(() => {
    if (status) void queryClient.invalidateQueries({ queryKey: ["freestyles"] });
  }, [status, queryClient]);
  return query;
}

/** The value, once it has stopped changing for a moment. */
function useSettled<T>(value: T, ms = 400) {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return settled;
}

/** What a send would cost, at most. Free: the server queues nothing and asks no model. */
export function useEstimate(s: Settings, text: string) {
  const query = useSettled({ type: s.type, look: s.look, shape: s.shape, text: text.trim() });
  return useQuery({
    queryKey: ["freestyle-estimate", query],
    enabled: !!query.text && !!query.look,
    retry: false,
    placeholderData: keepPreviousData,
    queryFn: async () => (await call(api.GET("/freestyles/estimate", { params: { query } }))).credits,
  });
}

/** Every change to one freestyle goes through here: the answer replaces the cached freestyle and refreshes the list. */
export function useFreestyleActions(id: number | null) {
  const queryClient = useQueryClient();
  const done = (fs: Freestyle) => {
    queryClient.setQueryData(["freestyle", fs.id], fs);
    queryClient.invalidateQueries({ queryKey: ["freestyles"] });
  };
  const path = { params: { path: { freestyle_id: id ?? 0 } } };
  const fresh = { onSuccess: done };
  return {
    create: useMutation({ mutationFn: (body: Settings & { text: string }) => call(api.POST("/freestyles", { body })), ...fresh }),
    change: useMutation({ mutationFn: (text: string) => call(api.POST("/freestyles/{freestyle_id}/messages", { ...path, body: { text } })), ...fresh }),
    rename: useMutation({ mutationFn: (title: string) => call(api.PATCH("/freestyles/{freestyle_id}", { ...path, body: { title } })), ...fresh }),
    withdraw: useMutation({ mutationFn: () => call(api.POST("/freestyles/{freestyle_id}/withdraw", path)), ...fresh }),
    stop: useMutation({ mutationFn: () => call(api.POST("/freestyles/{freestyle_id}/stop", path)), ...fresh }),
  };
}
