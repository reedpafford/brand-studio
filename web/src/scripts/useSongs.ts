import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { useToast } from "../toast";
import { clock } from "./TakePlayer";

export type SongTake = components["schemas"]["SongTakeOut"];
const BUSY: SongTake["status"][] = ["making", "timing"];

/** A song script version's takes (song ads, flows S4; one request makes 2), asked again every 3 s while one is being made or timed. */
export function useSongs(scriptId: number, enabled = true) {
  return useQuery({
    enabled,
    queryKey: ["songs", scriptId],
    queryFn: async () => {
      const { data, error } = await api.GET("/scripts/{script_id}/drafts/{slot}/songs", { params: { path: { script_id: scriptId, slot: 0 } } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    refetchInterval: (q) => (q.state.data?.takes.some((t) => BUSY.includes(t.status)) ? 3000 : false),
  });
}

/** Make, Try again, Use timing spread evenly, Preferred and Delete, each with Undo where the flows ask for it.
 * A narration (flows N1) is a take of kind "narration": its toasts say "Narration 2 is the one used". */
export function useSongActions(scriptId: number, words: { noun: string; picked: string } = { noun: "Take", picked: "is Preferred" }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const refresh = () => Promise.all([queryClient.invalidateQueries({ queryKey: ["songs", scriptId] }), queryClient.invalidateQueries({ queryKey: ["allowance"] })]);
  const ok = async <T,>(call: Promise<{ data?: T; error?: unknown; response: Response }>) => {
    const { data, error, response } = await call;
    if (!response.ok) throw new Error(errorText(error));
    return data as T;
  };
  const take = (id: number) => ({ params: { path: { take_id: id } } });

  const make = useMutation({
    mutationFn: () => ok(api.POST("/scripts/{script_id}/drafts/{slot}/songs", { params: { path: { script_id: scriptId, slot: 0 } } })),
    onSuccess: (data) => {
      queryClient.setQueryData(["songs", scriptId], data);
      return refresh();
    },
  });
  const tryAgain = useMutation({ mutationFn: (id: number) => ok(api.POST("/songs/{take_id}/try-again", take(id))), onSuccess: refresh });
  const spread = useMutation({ mutationFn: (id: number) => ok(api.POST("/songs/{take_id}/spread-timing", take(id))), onSuccess: refresh });
  const prefer = useMutation({
    mutationFn: (id: number) => ok(api.POST("/songs/{take_id}/preferred", take(id))),
    onSuccess: async (data) => {
      await refresh();
      const was = data?.was_preferred_id;
      toast(`${words.noun} ${data?.take.number} ${words.picked}.`, was ? () => void ok(api.POST("/songs/{take_id}/preferred", take(was))).then(refresh) : undefined);
    },
  });
  // "Use the first 0:55": with no other take Preferred, the trimmed take also becomes the one used (flows S4).
  // One toast, one Undo: un-trimming puts the whole take back (the server drops Preferred from a take over the cap).
  const trim = useMutation({
    mutationFn: async ({ t, prefer }: { t: SongTake; prefer: boolean }) => {
      const trimmed = await ok(api.POST("/songs/{take_id}/trim", take(t.id)));
      if (prefer) await ok(api.POST("/songs/{take_id}/preferred", take(t.id)));
      return { trimmed, prefer };
    },
    onSuccess: async ({ trimmed, prefer }) => {
      await refresh();
      const first = trimmed?.trim_to ? clock(trimmed.trim_to) : "part";
      toast(`Take ${trimmed?.number} now uses its first ${first}${prefer ? " and is Preferred" : ""}. The whole take is kept.`, () => void ok(api.DELETE("/songs/{take_id}/trim", take(trimmed!.id))).then(refresh));
    },
    onError: refresh, // a trim that landed before a refused Preferred still shows
  });
  const remove = useMutation({
    mutationFn: async (t: SongTake) => {
      await ok(api.DELETE("/songs/{take_id}", take(t.id)));
      return t;
    },
    onSuccess: async (t) => {
      await refresh();
      toast(`${words.noun} ${t.number} deleted.`, () => void ok(api.POST("/songs/{take_id}/restore", take(t.id))).then(refresh));
    },
  });
  return { make, tryAgain, spread, prefer, trim, remove };
}
