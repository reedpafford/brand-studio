import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useBrandPieces } from "../clip/BrandPieces";
import { Elapsed, GOING, useJobs } from "../clip/History";
import { Clapperboard } from "lucide-react";
import { Banner, EmptyState, Skeleton } from "../components";
import { WaitingBadge } from "./Meter";
import { errorText as errorClass } from "../ui";
import { BreakdownView } from "./BreakdownView";
import { refName, useRoleNames } from "./names";
import { BreakdownVersions } from "./VersionLists";


/** Claude's scenes → shots → clips for the working script. Read-only here; editing comes next. */
/** The newest breakdown for the project, or null when there is none (or no script). */
export function useBreakdown(projectId: number, scriptVersion: number) {
  return useQuery({
    queryKey: ["breakdown", projectId, scriptVersion],
    queryFn: async () => {
      const { data, response } = await api.GET("/projects/{project_id}/breakdown", { params: { path: { project_id: projectId } } });
      if (response.status === 404 || response.status === 409) return null;
      if (!data) throw new Error("load");
      return data;
    },
  });
}

export function BreakdownPane(props: { projectId: number; brandId: number; scriptVersion: number; plannedSeconds: number; used: number; budget: number; line: number | null; onShowLines: (lines: number[]) => void; onDirty?: (dirty: boolean) => void }) {
  const { projectId, brandId, scriptVersion } = props;
  const queryClient = useQueryClient();
  const { pieces } = useBrandPieces(brandId);
  const current = useBreakdown(projectId, scriptVersion);
  const jobs = useJobs();

  // The video's shots are the director's to make (S8: no Make the breakdown or Redo here; the owner's script plan keeps
  // its own). The run making them: any job the server says is a breakdown (a song or narrated video's is song_breakdown /
  // narrated_breakdown; approving the plan starts it).
  const mine = jobs.data?.filter((j) => j.project_id === projectId && !!j.step?.endsWith("breakdown")).sort((a, b) => b.id - a.id)[0];
  const running = !!mine && GOING.includes(mine.status);
  const failed = mine?.status === "failed";
  // When the run finishes, fetch the new breakdown.
  const finished = mine?.status === "succeeded" ? mine.id : null;
  useEffect(() => {
    if (finished === null) return;
    queryClient.invalidateQueries({ queryKey: ["breakdown", projectId] });
    // A new breakdown version replaces the frames and clips made from the old one.
    queryClient.invalidateQueries({ queryKey: ["storyboard", projectId] });
    queryClient.invalidateQueries({ queryKey: ["project-clips", projectId] });
    queryClient.invalidateQueries({ queryKey: ["assets", projectId] }); // which roles the new shots use
  }, [finished, projectId, queryClient]);

  const roles = useRoleNames(projectId);
  const name = (id: string | null) => (id ? refName(id, pieces, roles) : "");
  if (current.isPending) return <p className="text-muted">Loading…</p>;
  if (current.isError) return <p role="alert" className={errorClass}>Could not load the breakdown. Try again.</p>;
  const row = current.data;

  if (running)
    return (
      <section className="space-y-3" aria-label="Breakdown">
        {mine?.status === "needs_owner_approval" ? (
          <WaitingBadge />
        ) : (
          <p className="text-sm text-muted" role="status">
            Making the breakdown…{" "}
            {mine && <Elapsed since={mine.created_at} />}
          </p>
        )}
        {[0, 1].map((i) => (
          <Skeleton key={i} className="h-40" />
        ))}
      </section>
    );

  if (!row)
    return (
      <section className="space-y-3" aria-label="Breakdown">
        {failed ? (
          <Banner title="The breakdown didn't finish.">Nothing was charged. Tell the director in the chat to try again.</Banner>
        ) : (
          <EmptyState icon={Clapperboard} title="No breakdown yet">
            The director splits the script into scenes, shots and clips once the plan is approved. Nothing is filmed yet.
          </EmptyState>
        )}
      </section>
    );

  // #957 refuses Go back while this video's later steps are being made (an Update everything after this run's jobs among them).
  const waiting = (jobs.data ?? []).filter((j) => j.project_id === projectId && GOING.includes(j.status));
  const versionsHold = waiting.some((j) => j.step?.endsWith("breakdown"))
    ? "Wait for the breakdown being made."
    : waiting.some((j) => ["storyboard", "frame", "clip_prompts", "change"].includes(j.step ?? "") || j.frame_id != null)
      ? "Wait for the storyboard, stills and clip prompts being made."
      : null;
  return (
    <div className="space-y-4">
      <BreakdownView key={row.id} row={row} projectId={projectId} brandId={brandId} scriptVersion={scriptVersion} plannedSeconds={props.plannedSeconds} makeButton={() => null} failed={failed} problem={null} name={name} line={props.line} onShowLines={props.onShowLines} onDirty={props.onDirty} />
      <BreakdownVersions projectId={projectId} hold={versionsHold} />
    </div>
  );
}
