import { useOnChange } from "../useOnChange";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { blocking } from "./problems";
import { api, errorText, polled } from "../api/client";
import { useBreakdown } from "./BreakdownPane";
import type { Progress } from "./steps";
import { useLatestScript } from "./ScriptTab";

/** The video's storyboard stills. */
export function useFrames(projectId: number) {
  return useQuery({
    queryKey: ["storyboard", projectId],
    enabled: projectId > 0, // no video yet (the page before it loads): never /projects/0
    queryFn: () => polled(api.GET("/projects/{project_id}/storyboard", { params: { path: { project_id: projectId } } }), []),
  });
}

export function useProjectClips(projectId: number) {
  return useQuery({
    queryKey: ["project-clips", projectId],
    enabled: projectId > 0,
    queryFn: () => polled(api.GET("/projects/{project_id}/clips", { params: { path: { project_id: projectId } } }), []),
  });
}

/** The stitched video's query, shared so the Videos list can ask once for every project. */
export const videoQuery = (projectId: number) => ({
  queryKey: ["project-video", projectId] as const,
  enabled: projectId > 0,
  queryFn: async () => {
    const { data, response } = await api.GET("/projects/{project_id}/video", { params: { path: { project_id: projectId } } });
    if (response.ok || response.status === 404) return data ?? null; // none yet: 204
    throw new Error("load");
  },
});

/** The stitched video, or null when none has been made yet. */
export function useProjectVideo(projectId: number) {
  return useQuery(videoQuery(projectId));
}

/** The cut (GET …/cut): the one that plays and the one being made, polled while it's made. `opening`: a further
 *  version's cut (2, 3, …) of a video whose script has several openings, kept apart from the cut itself; for the first
 *  it reads nothing, as the first version's cut is the cut itself. */
export function useCut(projectId: number, opening?: number) {
  const queryClient = useQueryClient();
  const cut = useQuery({
    queryKey: opening == null ? ["project-cut", projectId] : ["project-cut", projectId, opening],
    enabled: opening == null || opening > 1,
    queryFn: () => polled(api.GET("/projects/{project_id}/cut", { params: { path: { project_id: projectId }, query: opening == null ? undefined : { opening } } }), null),
    // while it's made, while the director edits it, or while a sound effect is made
    refetchInterval: (q) => {
      const c = q.state.data;
      return c && (c.making || c.director.editing || c.timeline.sfx.some((s) => s.state === "making")) ? 2000 : false;
    },
  });
  // A new cut number: the stitched video is read again (not when the page first reads it: it has just read it).
  useOnChange(cut.isPending || opening != null ? undefined : (cut.data?.number ?? null), () => void queryClient.invalidateQueries({ queryKey: ["project-video", projectId] }));
  return cut;
}

/** The video's versions (GET …/cut/versions): one for each opening of its script over the same body, each with its
 *  cut's file once made and whether it is out of date. A video with one opening is its one version. */
export function useCutVersions(projectId: number) {
  return useQuery({
    queryKey: ["cut-versions", projectId],
    queryFn: () => polled(api.GET("/projects/{project_id}/cut/versions", { params: { path: { project_id: projectId } } }), []),
  });
}

/** Make the cut (free): the next Cut is made on the server while the one before plays. */
export function useMakeCut(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/projects/{project_id}/cut", { params: { path: { project_id: projectId } } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data) => queryClient.setQueryData(["project-cut", projectId], data),
  });
}

/** What each step needs to know about the steps before it. */
export function useProgress(projectId: number) {
  const script = useLatestScript(projectId);
  const breakdown = useBreakdown(projectId, script.data?.version ?? 0);
  const frames = useFrames(projectId);
  const clips = useProjectClips(projectId);
  const video = useProjectVideo(projectId);
  const loading = script.isPending || breakdown.isPending || frames.isPending || clips.isPending || video.isPending;
  const bd = breakdown.data;
  const f = frames.data ?? [];
  const c = clips.data ?? [];
  const progress: Progress = {
    script: !!script.data,
    shots: { made: !!bd, stale: !!bd?.stale, problems: blocking(bd?.problems ?? [], bd?.kept ?? []).length },
    frames: { total: f.length, drawn: f.filter((x) => x.file_id).length, stale: f.some((x) => x.stale) },
    clips: { total: c.length, taken: c.filter((x) => x.picked_take_id).length, stale: c.some((x) => x.stale) },
    // The server compares picked takes; an edit upstream dates clips without changing them. Approval never counts (M2).
    video: { made: !!video.data, outOfDate: !!video.data?.out_of_date || c.some((x) => !x.picked_take_id || x.stale || x.take_stale) },
  };
  // The newest picture this video has, for its poster: the final video, else an approved take, else a frame.
  const takeFile = [...c].reverse().find((x) => x.approved && x.file_id)?.file_id ?? null;
  const frameFile = [...f].reverse().find((x) => x.file_id)?.file_id ?? null;
  const media = { video: video.data?.file_id ?? takeFile, image: video.data || takeFile ? null : frameFile, seconds: Math.round(c.reduce((n, x) => n + x.seconds, 0)), clips: bd?.breakdown.clips.length ?? 0 };
  return { progress, loading, script, breakdown, media };
}
