import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { useToast } from "../toast";

export type SongTake = components["schemas"]["SongTakeOut"];
const BUSY: SongTake["status"][] = ["making", "timing"];

/** A song script version's takes (song ads, flows S4), asked again every 3 s while one is being made or timed. */
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

/** Make, Try again, Use timing spread evenly, Preferred and Delete, each with Undo where the flows ask for it. */
export function useSongActions(scriptId: number) {
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
    mutationFn: (count: 1 | 2 = 2) => ok(api.POST("/scripts/{script_id}/drafts/{slot}/songs", { params: { path: { script_id: scriptId, slot: 0 } }, body: { count } })),
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
      toast(`Take ${data?.take.number} is Preferred.`, was ? () => void ok(api.POST("/songs/{take_id}/preferred", take(was))).then(refresh) : undefined);
    },
  });
  const remove = useMutation({
    mutationFn: async (t: SongTake) => {
      await ok(api.DELETE("/songs/{take_id}", take(t.id)));
      return t;
    },
    onSuccess: async (t) => {
      await refresh();
      toast(`Take ${t.number} deleted.`, () => void ok(api.POST("/songs/{take_id}/restore", take(t.id))).then(refresh));
    },
  });
  return { make, tryAgain, spread, prefer, remove };
}
