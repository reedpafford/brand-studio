import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { blocking } from "./problems";
import { api, errorText } from "../api/client";
import { useBreakdown } from "./BreakdownPane";
import type { Progress } from "./steps";
import { useFrames } from "./StoryboardPane";
import { useLatestScript } from "./ScriptTab";

export function useProjectClips(projectId: number) {
  return useQuery({
    queryKey: ["project-clips", projectId],
    queryFn: async () => (await api.GET("/projects/{project_id}/clips", { params: { path: { project_id: projectId } } })).data ?? [],
  });
}

/** The stitched video's query, shared so the Videos list can ask once for every project. */
export const videoQuery = (projectId: number) => ({
  queryKey: ["project-video", projectId] as const,
  queryFn: async () => {
    const { data, response } = await api.GET("/projects/{project_id}/video", { params: { path: { project_id: projectId } } });
    if (response.status === 404) return null;
    if (!data) throw new Error("load");
    return data;
  },
});

/** The stitched video, or null when none has been made yet. */
export function useProjectVideo(projectId: number) {
  return useQuery(videoQuery(projectId));
}

/** The cut (GET …/cut): the one that plays and the one being made, polled while it's made. */
export function useCut(projectId: number) {
  const queryClient = useQueryClient();
  const cut = useQuery({
    queryKey: ["project-cut", projectId],
    queryFn: async () => (await api.GET("/projects/{project_id}/cut", { params: { path: { project_id: projectId } } })).data ?? null,
    refetchInterval: (q) => (q.state.data?.making ? 2000 : false),
  });
  const number = cut.data?.number;
  const seen = useRef(number);
  useEffect(() => {
    if (seen.current !== number) void queryClient.invalidateQueries({ queryKey: ["project-video", projectId] });
    seen.current = number;
  }, [number, projectId, queryClient]);
  return cut;
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
    frames: { total: f.length, approved: f.filter((x) => x.approved).length, stale: f.some((x) => x.stale) },
    clips: { total: c.length, approved: c.filter((x) => x.approved).length, stale: c.some((x) => x.stale) },
    // The server only compares picked takes; an edit upstream unapproves or dates clips without changing them.
    video: { made: !!video.data, outOfDate: !!video.data?.out_of_date || c.some((x) => !x.approved || x.stale || x.take_stale) },
  };
  // The newest picture this video has, for its poster: the final video, else an approved take, else a frame.
  const takeFile = [...c].reverse().find((x) => x.approved && x.file_id)?.file_id ?? null;
  const frameFile = [...f].reverse().find((x) => x.file_id)?.file_id ?? null;
  const media = { video: video.data?.file_id ?? takeFile, image: video.data || takeFile ? null : frameFile, seconds: Math.round(c.reduce((n, x) => n + x.seconds, 0)), clips: bd?.breakdown.clips.length ?? 0 };
  return { progress, loading, script, breakdown, media };
}
