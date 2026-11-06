import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";

export type Cut = components["schemas"]["CutOut"];
export type Piece = components["schemas"]["PieceOut"];
export type EditBody = Omit<components["schemas"]["EditIn"], "snap"> & {
  snap?: boolean;
};
export type Fix = components["schemas"]["CutFixIn"]["fix"];

const path = (projectId: number) => ({
  params: { path: { project_id: projectId } },
});

/** The cut's edits (free): each answers the whole cut again, so the page shows the server's own timeline. */
export function useCutEdits(projectId: number) {
  const queryClient = useQueryClient();
  const keep = (data: Cut) => {
    queryClient.setQueryData(["project-cut", projectId], data);
    void queryClient.invalidateQueries({ queryKey: ["cut-swaps", projectId] }); // "In the cut" moved
  };
  let others: () => void = () => {};
  const onMutate = () => others(); // the newest press's error only
  const done = (r: { data?: Cut; error?: unknown }) => {
    if (!r.data) throw new Error(errorText(r.error));
    return r.data;
  };
  const edit = useMutation({
    mutationFn: async (body: EditBody) =>
      done(
        await api.POST("/projects/{project_id}/cut/edits", {
          ...path(projectId),
          body: { snap: false, ...body },
        }),
      ),
    onMutate,
    onSuccess: keep,
  });
  const undoOne = useMutation({
    mutationFn: async (editId: number) =>
      done(
        await api.POST("/projects/{project_id}/cut/edits/{edit_id}/undo", {
          params: { path: { project_id: projectId, edit_id: editId } },
        }),
      ),
    onMutate,
    onSuccess: keep,
  });
  const step = useMutation({
    mutationFn: async (which: "undo" | "redo" | "undo-all") =>
      done(
        which === "undo"
          ? await api.POST("/projects/{project_id}/cut/undo", path(projectId))
          : which === "redo"
            ? await api.POST("/projects/{project_id}/cut/redo", path(projectId))
            : await api.POST("/projects/{project_id}/cut/undo-all", path(projectId)),
      ),
    onMutate,
    onSuccess: keep,
  });
  const fix = useMutation({
    mutationFn: async (which: Fix) =>
      done(
        await api.POST("/projects/{project_id}/cut/fix", {
          ...path(projectId),
          body: { fix: which },
        }),
      ),
    onMutate,
    onSuccess: keep,
  });
  const all = [edit, undoOne, step, fix];
  others = () => all.forEach((m) => m.isError && m.reset());
  const error = all.find((m) => m.isError)?.error ?? null;
  return {
    edit,
    undoOne,
    step,
    fix,
    error,
    busy: edit.isPending || undoOne.isPending || step.isPending || fix.isPending,
  };
}

/** What a B-roll piece can swap to: as it is, its clip's other takes, the other clips', and the Library. */
export function useSwaps(projectId: number, piece: string | null) {
  return useQuery({
    queryKey: ["cut-swaps", projectId, piece],
    enabled: !!piece,
    queryFn: async () =>
      (
        await api.GET("/projects/{project_id}/cut/swaps/{piece}", {
          params: { path: { project_id: projectId, piece: piece ?? "" } },
        })
      ).data ?? [],
  });
}

/** Music the cut can swap to: the brand's music beds and songs. */
export function useMusicChoices(projectId: number, on: boolean) {
  return useQuery({
    queryKey: ["cut-music", projectId],
    enabled: on,
    queryFn: async () => (await api.GET("/projects/{project_id}/cut/music", path(projectId))).data ?? [],
  });
}

/** 0:14, as the cut writes a time; `tenths` gives 0:14.6. */
export const clock = (t: number, tenths = false) => {
  const whole = Math.floor(t);
  const s = `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
  return tenths ? `${s}.${Math.min(9, Math.round((t - whole) * 10))}` : s;
};

/** "Clip 7" for c7, and for a piece split off it (c7.12). */
export const clipLabel = (piece: string) => `Clip ${piece.split(".")[0].replace(/^c/, "")}`;
