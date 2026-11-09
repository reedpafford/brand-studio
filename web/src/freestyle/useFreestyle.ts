import { useEffect, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import type { Tone } from "../components";
import { useFormatName } from "../scripts/useFormats";

/** Freestyle (Reed's redesign, replaces Quick clip): a video from a pasted script or a described clip, changed by chatting.
 *  Every editor send waits for Reed before anything is spent; Reed's own run at once. Next-Server's /freestyles (#1159).
 *  Dialogue is made by the director; the owner's OK covers its whole price (`up_to`, #1171). */
export type Freestyle = components["schemas"]["FreestyleOut"];
export type Row = components["schemas"]["FreestyleRow"];
export type Kind = Freestyle["type"];
export type Shape = Freestyle["shape"];
export type Settings = { type: Kind; look: string; shape: Shape; brand_id: number | null };

/** What the director makes now: a format's engine (a script's kind) but the song's, which comes next. */
export const directed = (engine: string) => engine !== "song";
export const SHAPES: Shape[] = ["9:16", "1:1", "16:9"];
export function useTypeName() {
  const formatName = useFormatName();
  return (t: Kind) => (t === "one_clip" ? "One clip" : formatName(t));
}

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

/** Where a send lands: on its video; an editor's held send (out of the lists until the owner's OK, #1190) by its
 *  freestyle, under its brand. An editor's that started at once (a published script inside its budget) is a video. */
export const sentTo = (fs: Freestyle, owner: boolean, brandId: number) =>
  (owner || fs.status !== "waiting") && fs.project_id && fs.brand_id ? `/b/${fs.brand_id}/videos/${fs.project_id}` : `/b/${fs.brand_id ?? brandId}/freestyle/${fs.id}`;

/** A refused send, with the server's words and, for "this version already has a video" (409), that video and the price
 *  of making another (the Producer, #1190). */
export class SendError extends Error {
  constructor(
    message: string,
    readonly hasVideo?: { project_id: number; up_to: number | null },
  ) {
    super(message);
  }
}

async function call<T>(p: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await p;
  if (response.ok && data !== undefined) return data;
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  if (detail && typeof detail === "object" && "project_id" in detail) {
    const d = detail as { project_id: number; up_to?: number | null; text?: string; message?: string };
    throw new SendError(d.text ?? d.message ?? "This version already has a video.", { project_id: d.project_id, up_to: d.up_to ?? null });
  }
  throw new SendError(errorText(error));
}

/** What a send is made from: pasted words (with their settings), or a script's version, whose type, look and brand are
 *  the script's (#1190). `make_another`: a second video from a version that has one. */
export type Source = { text: string; settings: Settings } | { script_id: number; slot: number; shape: Shape; make_another?: boolean };
const body = (s: Source) => ("text" in s ? { ...s.settings, text: s.text } : { type: "dialogue" as const, ...s });

/** Yours, newest first; `everyone` (Reed only): the whole team's. Refreshed while any of them is waiting or working. */
export function useFreestyles(everyone: boolean) {
  return useQuery({
    queryKey: ["freestyles", everyone],
    queryFn: () => call(api.GET("/freestyles", { params: { query: { everyone } } })),
    refetchInterval: (q) => (q.state.data?.some((r) => busy(r.status)) ? 5_000 : false),
  });
}

/** One freestyle, asked again every 4 s while it waits for Reed or is being made (`poll`: on its video's page the server
 *  says when it changes instead, videos/live.ts); a new status refreshes the list. */
export function useFreestyle(id: number | null, poll = true) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["freestyle", id],
    enabled: id !== null,
    queryFn: () => call(api.GET("/freestyles/{freestyle_id}", { params: { path: { freestyle_id: id! } } })),
    refetchInterval: (q) => (poll && busy(q.state.data?.status) ? 4_000 : false),
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

/** What a send would cost, at most, in whole credits. Free: the server queues nothing and asks no model. */
export function useEstimate(source: Source | null) {
  const query = useSettled(!source ? null : "text" in source ? { type: source.settings.type, look: source.settings.look, shape: source.settings.shape, text: source.text.trim() } : { script_id: source.script_id, slot: source.slot, shape: source.shape });
  return useQuery({
    queryKey: ["freestyle-estimate", query],
    enabled: !!query && ("script_id" in query || (!!query.text && !!query.look)),
    retry: false,
    placeholderData: keepPreviousData,
    queryFn: async () => (await call(api.GET("/freestyles/estimate", { params: { query: query! } }))).credits,
  });
}

/** Every change to one freestyle goes through here: the answer replaces the cached freestyle and refreshes the list. */
export function useFreestyleActions(id: number | null) {
  const queryClient = useQueryClient();
  const done = (fs: Freestyle) => {
    queryClient.setQueryData(["freestyle", fs.id], fs);
    queryClient.invalidateQueries({ queryKey: ["freestyles"] });
    if (fs.project_id) {
      // its video's chat and cards: a locked line's reply comes at once (S3-14), a new run's start card too
      void queryClient.invalidateQueries({ queryKey: ["director", fs.project_id] });
      void queryClient.invalidateQueries({ queryKey: ["asks", fs.project_id] });
    }
  };
  const path = { params: { path: { freestyle_id: id ?? 0 } } };
  const fresh = { onSuccess: done };
  return {
    create: useMutation({ mutationFn: (s: Source) => call(api.POST("/freestyles", { body: body(s) })), ...fresh }),
    change: useMutation({ mutationFn: (text: string) => call(api.POST("/freestyles/{freestyle_id}/messages", { ...path, body: { text } })), ...fresh }),
    rename: useMutation({ mutationFn: (title: string) => call(api.PATCH("/freestyles/{freestyle_id}", { ...path, body: { title } })), ...fresh }),
    withdraw: useMutation({ mutationFn: () => call(api.POST("/freestyles/{freestyle_id}/withdraw", path)), ...fresh }),
    stop: useMutation({ mutationFn: () => call(api.POST("/freestyles/{freestyle_id}/stop", path)), ...fresh }),
  };
}
