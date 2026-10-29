import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import { useBrandPieces } from "../clip/BrandPieces";
import { useJobs } from "../clip/History";
import { Clapperboard, RotateCcw } from "lucide-react";
import { Banner, Button, EmptyState, Skeleton } from "../components";
import { WaitingBadge } from "./Meter";
import { Elapsed } from "../clip/History";
import { useOwnScriptStop } from "./useOwnScriptStop";
import { errorText as errorClass } from "../ui";
import { BreakdownView } from "./BreakdownView";
import { refName, useRoleNames } from "./names";
import { BreakdownVersions } from "./VersionLists";

const GOING = ["queued", "running", "needs_owner_approval"];

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

export function BreakdownPane(props: { ownScript?: boolean; projectId: number; brandId: number; scriptVersion: number; plannedSeconds: number; used: number; budget: number; line: number | null; onShowLines: (lines: number[]) => void; onDirty?: (dirty: boolean) => void }) {
  const { projectId, brandId, scriptVersion } = props;
  const queryClient = useQueryClient();
  const path = { project_id: projectId };
  const { pieces } = useBrandPieces(brandId);
  const [startedJob, setStartedJob] = useState<number | null>(null);
  const [asked, setAsked] = useState(false);
  const stopFor = useOwnScriptStop(props.ownScript, { used: props.used, budget: props.budget });

  const current = useBreakdown(projectId, scriptVersion);
  const jobs = useJobs();
  const rates = useQuery({ queryKey: ["rates"], queryFn: async () => (await api.GET("/credits/rates")).data ?? [] });
  // What Make the shots charges (Next-Server's price sweep): the writing call, plus the clip prompts' rewrite once the
  // video has them. Read with fetch until it is in the generated schema; a server without it falls back to the rate.
  const price = useQuery({
    queryKey: ["breakdown-price", projectId],
    queryFn: async () => {
      const r = await fetch(`${location.origin}/api/projects/${projectId}/breakdown/price`, { credentials: "include" });
      return r.ok ? ((await r.json()) as { credits: number }).credits : null;
    },
  });
  const cost = price.isPending ? null : (price.data ?? rates.data?.find((r) => r.kind === "write-claude")?.credits_per_unit); // null: not known yet, the press waits

  // Our own run: the job we started, or any job the server says is a breakdown (a song or narrated
  // video's is song_breakdown / narrated_breakdown; Approve the plan starts it from another step).
  const mine = jobs.data?.filter((j) => j.project_id === projectId && (j.id === startedJob || !!j.step?.endsWith("breakdown"))).sort((a, b) => b.id - a.id)[0];
  // Between pressing the button and the job showing up in the list, it is already running.
  const running = (!!mine && GOING.includes(mine.status)) || (startedJob !== null && !mine);
  const failed = mine?.status === "failed";

  const make = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/projects/{project_id}/breakdown", { params: { path } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (job) => {
      setStartedJob(job.id);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
  // When our run finishes, fetch the new breakdown.
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

  // Past a limit an editor's paid button is disabled with the reason; nobody is asked to approve.
  const stop = stopFor(cost ?? undefined);
  const makeButton = (label: string, opts: { ask?: string; primary?: boolean } = {}) => (
    <Button
      variant={opts.primary ? "primary" : "secondary"}
      icon={label === "Redo" ? RotateCcw : undefined}
      price={cost}
      busy={make.isPending}
      disabled={running || asked || !!stop}
      reason={stop}
      onClick={() => {
        if (opts.ask && !window.confirm(opts.ask)) return;
        setAsked(false);
        make.mutate();
      }}
    >
      {label}
    </Button>
  );
  const problem = make.error ? <p role="alert" className={errorClass}>{make.error.message}</p> : null;

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
        {failed && (
          <Banner title="The breakdown didn't finish." action={makeButton("Try again")}>
            Nothing was charged.
          </Banner>
        )}
        {!failed && (
          <EmptyState icon={Clapperboard} title="No breakdown yet" action={makeButton("Make the breakdown", { primary: true })}>
            Claude splits your script into scenes, shots and clips. Nothing is filmed yet.
          </EmptyState>
        )}
        {problem}
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
      <BreakdownView key={row.id} row={row} projectId={projectId} brandId={brandId} scriptVersion={scriptVersion} plannedSeconds={props.plannedSeconds} makeButton={makeButton} failed={failed} problem={problem} name={name} line={props.line} onShowLines={props.onShowLines} onDirty={props.onDirty} />
      <BreakdownVersions projectId={projectId} hold={versionsHold} />
    </div>
  );
}
