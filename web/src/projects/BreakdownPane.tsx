import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { useBrandPieces } from "../clip/BrandPieces";
import { useJobs } from "../clip/History";
import { btnPrimary, btnSecondary, card, errorText as errorClass } from "../ui";

type Shot = components["schemas"]["Shot"];
type Clip = components["schemas"]["Clip"];
const GOING = ["queued", "running", "needs_owner_approval"];

const lines = (n: number[]) => (n.length === 0 ? "" : n.length === 1 ? `line ${n[0]}` : `lines ${Math.min(...n)}–${Math.max(...n)}`);

/** Claude's scenes → shots → clips for the working script. Read-only here; editing comes next. */
export function BreakdownPane(props: { projectId: number; brandId: number; scriptVersion: number; plannedSeconds: number; used: number; budget: number }) {
  const { projectId, brandId, scriptVersion } = props;
  const queryClient = useQueryClient();
  const path = { project_id: projectId };
  const { pieces } = useBrandPieces(brandId);
  const [startedJob, setStartedJob] = useState<number | null>(null);
  const [asked, setAsked] = useState(false);

  const current = useQuery({
    queryKey: ["breakdown", projectId, scriptVersion],
    queryFn: async () => {
      const { data, response } = await api.GET("/projects/{project_id}/breakdown", { params: { path } });
      if (response.status === 404 || response.status === 409) return null;
      if (!data) throw new Error("load");
      return data;
    },
  });
  const jobs = useJobs();
  const rates = useQuery({ queryKey: ["rates"], queryFn: async () => (await api.GET("/credits/rates")).data ?? [] });
  const cost = rates.data?.find((r) => r.kind === "write-claude")?.credits_per_unit;

  // Our own run: the job we started, or any job the server says is a breakdown.
  const mine = jobs.data?.filter((j) => j.project_id === projectId && (j.id === startedJob || (j as { step?: string }).step === "breakdown")).sort((a, b) => b.id - a.id)[0];
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
      className={opts.primary ? btnPrimary : btnSecondary}
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

  const bd = row.breakdown;
  const shots = bd.scenes.flatMap((s) => s.shots);
  const total = Math.round(bd.clips.reduce((sum, c) => sum + c.seconds, 0));
  const blockedBy = row.stale ? "Make a new breakdown first." : row.problems.length > 0 ? `Fix the ${row.problems.length} problem${row.problems.length === 1 ? "" : "s"} first.` : "Storyboard is coming soon.";

  return (
    <div className="space-y-4" aria-label="Breakdown">
      {row.stale && (
        <div className="space-y-2 rounded-md bg-warning-soft p-3 text-sm text-warning" role="status">
          <p>Made for script v{row.script_version}. The script is now v{scriptVersion}.</p>
          {makeButton("Make a new breakdown")}
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[length:var(--text-md)] font-semibold">
          Breakdown <span className="font-normal text-muted">· {row.source === "edit" ? "edited" : "made by Claude"} for script v{row.script_version}</span>
        </h2>
        {!row.stale && makeButton("Redo", { ask: row.source === "edit" ? "Replace this breakdown? Your edits are kept in History." : undefined })}
      </div>
      {failed && <p role="alert" className={errorClass}>The breakdown didn't finish. Nothing was charged for the failed part.</p>}
      {problem}
      {row.problems.length > 0 && (
        <section className="space-y-1 rounded-md bg-danger-soft p-3 text-sm text-danger" aria-label="Problems">
          <h3 className="font-semibold">Problems ({row.problems.length})</h3>
          <ul className="list-disc pl-5">
            {row.problems.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </section>
      )}
      {bd.hook && <p className="text-sm">Hook: “{bd.hook}”</p>}
      <p className="text-sm text-muted">
        {bd.scenes.length} scene{bd.scenes.length === 1 ? "" : "s"} · {shots.length} shot{shots.length === 1 ? "" : "s"} · {bd.clips.length} clip{bd.clips.length === 1 ? "" : "s"} · {total} s (planned {props.plannedSeconds} s)
      </p>
      {bd.scenes.map((scene) => (
        <section key={scene.id} className="space-y-2" aria-label={`Scene ${scene.id}`}>
          <h3 className="font-semibold">Scene {scene.id} — {scene.heading}</h3>
          {scene.look && <p className="text-sm text-muted">{scene.look}</p>}
          {bd.clips
            .filter((c) => c.shot_ids.some((id) => scene.shots.some((s) => s.id === id)))
            .map((clip) => (
              <ClipBand key={clip.id} clip={clip} shots={scene.shots.filter((s) => clip.shot_ids.includes(s.id))} name={name} />
            ))}
        </section>
      ))}
      <div className="space-y-1">
        <button className={btnPrimary} disabled>
          Next: Storyboard →
        </button>
        <p className="text-sm text-muted">{blockedBy}</p>
      </div>
    </div>
  );
}

function ClipBand({ clip, shots, name }: { clip: Clip; shots: Shot[]; name: (id: string | null) => string }) {
  return (
    <div className="rounded-md border border-border bg-surface" aria-label={`Clip ${clip.id}`}>
      <div className="border-b border-border px-3 py-1 text-xs font-medium text-muted">
        Clip {clip.id} · {clip.seconds} s
      </div>
      <ul className="divide-y divide-border">
        {shots.map((s) => (
          <li key={s.id} className="space-y-1 px-3 py-2 text-sm" aria-label={`Shot ${s.id}`}>
            <div className="flex flex-wrap items-baseline gap-x-3">
              <span className="font-medium">{s.id}</span>
              <span className="text-muted">{s.seconds} s</span>
              <span className="text-muted">{s.camera}</span>
              <span className="ml-auto text-xs text-muted">{lines(s.script_lines)}</span>
            </div>
            <p>{s.action}</p>
            {s.line && (
              <p className="font-script">
                {s.speaker ? `${s.speaker.toUpperCase()}: ` : ""}“{s.line}”
              </p>
            )}
            {s.reaction && <p className="text-muted">Reaction: {s.reaction}</p>}
            <p className="flex flex-wrap gap-2 text-xs">
              {s.character_ids.map((id) => (
                <span key={id} className="rounded-sm bg-surface-2 px-2 py-0.5">● {name(id)}</span>
              ))}
              {s.place_id && <span className="rounded-sm bg-surface-2 px-2 py-0.5">⌂ {name(s.place_id)}</span>}
              {s.moment && <span className="rounded-sm bg-accent-soft px-2 py-0.5 text-accent-text">{s.moment}</span>}
              {s.screen_ids.map((id) => (
                <span key={id} className="rounded-sm bg-accent-soft px-2 py-0.5 text-accent-text">★ {name(id)}</span>
              ))}
            </p>
          </li>
        ))}
      </ul>
      <div className="border-t border-border px-3 py-1 text-xs text-muted">{clip.seam === "end" ? "end" : `ends: ${clip.seam}`}</div>
    </div>
  );
}
