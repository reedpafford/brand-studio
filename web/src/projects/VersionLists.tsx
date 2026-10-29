import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, must } from "../api/client";
import { useMayManageVideo } from "./ReleaseVideo";
import { VersionList } from "./Versions";

type Maker = { id: number; name: string } | null;
const n = (k: number, one: string) => `${k} ${one}${k === 1 ? "" : "s"}`;

/** OR3's presses are whoever made the video's, or the owner's (403 otherwise, #957): for anyone else they're hidden. */
export function useMayChangeVideo(projectId: number) {
  const may = useMayManageVideo();
  const project = useQuery({ queryKey: ["project", projectId], queryFn: async () => (await api.GET("/projects/{project_id}", { params: { path: { project_id: projectId } } })).data ?? null });
  return !!project.data && may(project.data);
}

/** Each step's own lists and everything made from it: going back marks later steps Out of date (or current again). */
function useRefresh(projectId: number) {
  const queryClient = useQueryClient();
  return (...more: unknown[][]) => Promise.all([["breakdown", projectId], ["storyboard", projectId], ["project-clips", projectId], ...more].map((queryKey) => queryClient.invalidateQueries({ queryKey })));
}

/** OR3: the storyboard's versions, the one in hand first, then up to 10 earlier. Undo uses index 0 (the one replaced). */
export function StoryboardVersions({ projectId, hold }: { projectId: number; hold: string | null }) {
  const may = useMayChangeVideo(projectId);
  const refresh = useRefresh(projectId);
  const key = ["storyboard-versions", projectId];
  const rows = useQuery({ enabled: may, queryKey: key, queryFn: async () => (await must(api.GET("/projects/{project_id}/storyboard/versions", { params: { path: { project_id: projectId } } }))).data! }).data ?? [];
  const go = (index: number) => must(api.POST("/projects/{project_id}/storyboard/versions/{index}/use", { params: { path: { project_id: projectId, index } } }));
  const use = async (index: string) => {
    await go(Number(index));
    await refresh(key);
    return async () => {
      await go(0);
      await refresh(key);
    };
  };
  return (
    <VersionList
      title="Storyboard versions"
      said="The earlier storyboard is back. Clips made from the other one show Out of date."
      hold={hold}
      onUse={use}
      versions={rows.map((r) => ({ key: String(r.index ?? "now"), made_at: r.made_at, made_by: r.made_by, note: n(r.frames, "frame"), current: r.current }))}
    />
  );
}

/** OR3: one clip prompt's versions (index 0 is in hand; at most 10). Going back clears Looks good; Undo uses index 1. */
export function ClipVersions({ projectId, clipRowId, label, versions, hold }: { projectId: number; clipRowId: number; label: string; hold?: string | null; versions: { index: number; made_at: string | null; made_by: Maker; current: boolean }[] }) {
  const may = useMayChangeVideo(projectId);
  const refresh = useRefresh(projectId);
  const go = (index: number) => must(api.POST("/projects/{project_id}/clips/{clip_id}/versions/{index}/use", { params: { path: { project_id: projectId, clip_id: clipRowId, index } } }));
  const use = async (index: string) => {
    await go(Number(index));
    await refresh();
    return async () => {
      await go(1);
      await refresh();
    };
  };
  if (!may) return null;
  return (
    <VersionList
      title={`Prompt versions for clip ${label}`}
      said={`Clip ${label} has its earlier prompt back. Its take shows Out of date.`}
      hold={hold}
      onUse={use}
      versions={versions.map((v) => ({ key: String(v.index), made_at: v.made_at, made_by: v.made_by, current: v.current }))}
    />
  );
}

const SOURCE: Record<string, string> = { claude: "Made by Claude", edit: "Edited", library: "From the script", earlier: "Gone back to" };

/** OR3: the breakdown's versions, newest first (20). Undo goes back to the one replaced (`was_id`). */
export function BreakdownVersions({ projectId, hold }: { projectId: number; hold?: string | null }) {
  const may = useMayChangeVideo(projectId);
  const refresh = useRefresh(projectId);
  const key = ["breakdown-versions", projectId];
  const rows = useQuery({ enabled: may, queryKey: key, queryFn: async () => (await must(api.GET("/projects/{project_id}/breakdown/versions", { params: { path: { project_id: projectId } } }))).data! }).data ?? [];
  const go = async (id: number) => (await must(api.POST("/projects/{project_id}/breakdown/versions/{version_id}/use", { params: { path: { project_id: projectId, version_id: id } } }))).data;
  const use = async (id: string) => {
    const was = (await go(Number(id)))?.was_id;
    await refresh(key);
    return was
      ? async () => {
          await go(was);
          await refresh(key);
        }
      : null;
  };
  return (
    <VersionList
      title="Breakdown versions"
      said="The earlier breakdown is back. Stills and clips made for the other one show Out of date; those made for this one are current again."
      hold={hold}
      onUse={use}
      versions={rows.map((r) => ({ key: String(r.id), made_at: r.made_at, made_by: r.made_by, note: SOURCE[r.source] ?? r.source, current: r.current }))}
    />
  );
}
