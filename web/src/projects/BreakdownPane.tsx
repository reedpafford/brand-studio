import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import { useBrandPieces } from "../clip/BrandPieces";
import { useJobs } from "../clip/History";
import { btnPrimary, btnSecondary, card, errorText as errorClass } from "../ui";
import { BreakdownView } from "./BreakdownView";

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

export function BreakdownPane(props: { projectId: number; brandId: number; scriptVersion: number; plannedSeconds: number; used: number; budget: number; line: number | null; onShowLines: (lines: number[]) => void; onNext: () => void }) {
  const { projectId, brandId, scriptVersion } = props;
  const queryClient = useQueryClient();
  const path = { project_id: projectId };
  const { pieces } = useBrandPieces(brandId);
  const [startedJob, setStartedJob] = useState<number | null>(null);
  const [asked, setAsked] = useState(false);

  const current = useBreakdown(projectId, scriptVersion);
  const jobs = useJobs();
  const rates = useQuery({ queryKey: ["rates"], queryFn: async () => (await api.GET("/credits/rates")).data ?? [] });
  const cost = rates.data?.find((r) => r.kind === "write-claude")?.credits_per_unit;

  // Our own run: the job we started, or any job the server says is a breakdown.
  const mine = jobs.data?.filter((j) => j.project_id === projectId && (j.id === startedJob || j.step === "breakdown")).sort((a, b) => b.id - a.id)[0];
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
    if (finished !== null) queryClient.invalidateQueries({ queryKey: ["breakdown", projectId] });
  }, [finished, projectId, queryClient]);

  const name = (id: string | null) => {
    if (!id) return "";
    const [kind, n] = id.split(":");
    const key = `${kind === "char" ? "character" : kind}-${n}`;
    return pieces.find((p) => p.key === key)?.name ?? id;
  };
  const price = cost === undefined ? "" : ` · ${cost} credits`;

  if (current.isPending) return <p className="text-muted">Loading…</p>;
  if (current.isError) return <p role="alert" className={errorClass}>Could not load the breakdown. Try again.</p>;
  const row = current.data;

  // Paid buttons say so when this call would take the project past its budget; the server then holds it for approval.
  const overBudget = cost !== undefined && props.used + cost > props.budget;
  const makeButton = (label: string, opts: { ask?: string; primary?: boolean } = {}) => (
    <button
      className={`${opts.primary ? btnPrimary : btnSecondary} min-h-11 sm:min-h-9`}
      disabled={running || make.isPending || asked}
      onClick={() => {
        if (opts.ask && !window.confirm(opts.ask)) return;
        setAsked(false);
        make.mutate();
      }}
    >
      {overBudget ? "Ask Reed to approve" : label}
      {price}
    </button>
  );
  const problem = make.error ? <p role="alert" className={errorClass}>{make.error.message}</p> : null;

  if (running)
    return (
      <section className={`${card} space-y-3`} aria-label="Breakdown">
        <p className="text-muted">{mine?.status === "needs_owner_approval" ? "Waiting for Reed to approve" : "Breaking down your script…"}</p>
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-16 rounded-md bg-surface-2" aria-hidden />
        ))}
      </section>
    );

  if (!row)
    return (
      <section className={`${card} space-y-3`} aria-label="Breakdown">
        <p className="text-[length:var(--text-xl)] font-semibold">No breakdown yet.</p>
        <p className="text-muted">Claude splits your script into scenes, shots and clips. Nothing is generated yet.</p>
        {failed && <p role="alert" className={errorClass}>The breakdown didn't finish. Nothing was charged for the failed part.</p>}
        {makeButton(failed ? "Try again" : "Make breakdown", { primary: true })}
        {problem}
      </section>
    );

  return <BreakdownView key={row.id} row={row} projectId={projectId} brandId={brandId} scriptVersion={scriptVersion} plannedSeconds={props.plannedSeconds} makeButton={makeButton} failed={failed} problem={problem} name={name} line={props.line} onShowLines={props.onShowLines} onNext={props.onNext} />;
}
