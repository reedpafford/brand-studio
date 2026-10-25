import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
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
    shots: { made: !!bd, stale: !!bd?.stale, problems: bd?.problems.length ?? 0 },
    frames: { total: f.length, approved: f.filter((x) => x.approved).length, stale: f.some((x) => x.stale) },
    clips: { total: c.length, approved: c.filter((x) => x.approved).length, stale: c.some((x) => x.stale) },
    video: { made: !!video.data, outOfDate: !!video.data?.out_of_date },
  };
  // The newest picture this video has, for its poster: the final video, else an approved take, else a frame.
  const takeFile = [...c].reverse().find((x) => x.approved && x.file_id)?.file_id ?? null;
  const frameFile = [...f].reverse().find((x) => x.file_id)?.file_id ?? null;
  const media = { video: video.data?.file_id ?? takeFile, image: video.data || takeFile ? null : frameFile, seconds: Math.round(c.reduce((n, x) => n + x.seconds, 0)), clips: bd?.breakdown.clips.length ?? 0 };
  return { progress, loading, script, breakdown, media };
}
