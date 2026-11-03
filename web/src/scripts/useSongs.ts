import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { useMe } from "../auth/useMe";
import { useToast } from "../toast";
import { refreshJobs } from "../jobs/refresh";

export type SongTake = components["schemas"]["SongTakeOut"];
const BUSY: SongTake["status"][] = ["making", "timing"];

/** A song script version's takes (song ads, flows S4; one request makes 2), asked again every 3 s while one is being made or timed. */
/** A script's takes, also loaded ahead by a new script so its page opens with the editor already there. */
export const songsQuery = (scriptId: number) => ({
  queryKey: ["songs", scriptId],
  queryFn: async () => {
    const { data, error } = await api.GET("/scripts/{script_id}/drafts/{slot}/songs", { params: { path: { script_id: scriptId, slot: 0 } } });
    if (!data) throw new Error(errorText(error));
    return data;
  },
});

export function useSongs(scriptId: number, enabled = true) {
  return useQuery({
    enabled,
    ...songsQuery(scriptId),
    refetchInterval: (q) => (q.state.data?.takes.some((t) => BUSY.includes(t.status) || t.music_status === "making") ? 3000 : false),
  });
}

/** Make, Try again, Use timing spread evenly, Preferred and Delete, each with Undo where the flows ask for it.
 * A narration (flows N1) is a take of kind "narration": its toasts say "Narration 2 is the one used". */
export function useSongActions(scriptId: number, words: { noun: string; picked: string } = { noun: "Take", picked: "is Preferred" }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  // An editor's paid song, narration or music on a script waits for the owner (#1068): its press says so, and the
  // waiting banner (["jobs"]) picks it up.
  const editor = useMe().data?.role === "editor";
  const ask = (label: string, price: number | null | undefined) => (editor && price ? "Send for approval" : label);
  const SENDS = "Songs, narration and music on a script wait for the owner's OK. Nothing is charged until they say yes.";
  const sends = (price: number | null | undefined) => (editor && price ? SENDS : null);
  const refresh = () => Promise.all([queryClient.invalidateQueries({ queryKey: ["songs", scriptId] }), queryClient.invalidateQueries({ queryKey: ["allowance"] }), refreshJobs(queryClient)]);
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
      if (editor) toast("Sent for approval. It waits for the owner's OK; nothing is charged until then.");
      return refresh();
    },
  });
  const tryAgain = useMutation({ mutationFn: (id: number) => ok(api.POST("/songs/{take_id}/try-again", take(id))), onSuccess: refresh });
  // A narration's music failed: Try the music again, at music_credits; the narration stays as it is (#912).
  const musicAgain = useMutation({ mutationFn: (id: number) => ok(api.POST("/songs/{take_id}/music-again", take(id))), onSuccess: refresh });
  const spread = useMutation({ mutationFn: (id: number) => ok(api.POST("/songs/{take_id}/spread-timing", take(id))), onSuccess: refresh });
  const prefer = useMutation({
    mutationFn: (id: number) => ok(api.POST("/songs/{take_id}/preferred", take(id))),
    onSuccess: async (data) => {
      await refresh();
      const was = data?.was_preferred_id;
      toast(`${words.noun} ${data?.take.number} ${words.picked}.`, was ? () => void ok(api.POST("/songs/{take_id}/preferred", take(was))).then(refresh) : undefined);
    },
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
  return { make, tryAgain, musicAgain, spread, prefer, remove, ask, sends };
}
