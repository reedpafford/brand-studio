import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { useBrandPieces } from "../clip/BrandPieces";
import { useJobs } from "../clip/History";
import { fileUrl } from "../api/upload";
import { btnPrimary, btnSecondary, card, errorText as errorClass, input, linkText } from "../ui";
import { Sheet } from "./Sheet";

type Frame = components["schemas"]["FrameOut"];
const GOING = ["queued", "running", "needs_owner_approval"];
const ratio = (a: string) => a.replace(":", " / ");

/** One still per clip: Claude writes the frame prompts, then each still is drawn. */
export function StoryboardPane(props: { projectId: number; brandId: number; aspect: string; used: number; budget: number }) {
  const { projectId, brandId } = props;
  const queryClient = useQueryClient();
  const path = { project_id: projectId };
  const { pieces } = useBrandPieces(brandId);
  const jobs = useJobs();
  // The stills I started: frame id → job id (the server doesn't say which job is which frame yet).
  const [drawing, setDrawing] = useState<Record<number, number>>({});
  const [writing, setWriting] = useState<number | null>(null);
  const [lightbox, setLightbox] = useState<Frame | null>(null);
  const jobOf = (id: number) => jobs.data?.find((j) => j.id === id);
  // Still going: the run that writes the frames, and the stills I started. Between pressing and the job showing in the list it counts as going.
  const going = (id: number | undefined) => id !== undefined && (!jobOf(id) || GOING.includes(jobOf(id)!.status));
  const writingNow = going(writing ?? undefined);
  const drawingNow = Object.fromEntries(Object.entries(drawing).map(([f, j]) => [f, going(j)]));
  const anyGoing = writingNow || Object.values(drawingNow).some(Boolean);

  const frames = useQuery({
    queryKey: ["storyboard", projectId],
    queryFn: async () => (await api.GET("/projects/{project_id}/storyboard", { params: { path } })).data ?? [],
    refetchInterval: () => (anyGoing ? 3000 : false),
  });
  const rates = useQuery({ queryKey: ["rates"], queryFn: async () => (await api.GET("/credits/rates")).data ?? [] });
  const rate = (kind: string) => rates.data?.find((r) => r.kind === kind)?.credits_per_unit;
  const writeCost = rate("write-claude");
  const imageCost = rate("image");
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["storyboard", projectId] });

  const nameOf = (id: string) => {
    if (id === "previous") return "previous frame";
    const [kind, n] = id.split(":");
    return pieces.find((p) => p.key === `${kind === "char" ? "character" : kind}-${n}`)?.name ?? id;
  };

  const make = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/projects/{project_id}/storyboard", { params: { path }, body: { per_shot: false } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (job) => {
      setWriting(job.id);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
  const render = useMutation({
    mutationFn: async (frame: Frame) => {
      const { data, error } = await api.POST("/projects/{project_id}/storyboard/frames/{frame_id}/render", { params: { path: { ...path, frame_id: frame.id } } });
      if (!data) throw new Error(errorText(error));
      return { frame, job: data };
    },
    onSuccess: ({ frame, job }) => {
      setDrawing((d) => ({ ...d, [frame.id]: job.id }));
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
  const edit = useMutation({
    mutationFn: async ({ frame, prompt }: { frame: Frame; prompt: string }) => {
      const { data, error } = await api.PUT("/projects/{project_id}/storyboard/frames/{frame_id}", { params: { path: { ...path, frame_id: frame.id } }, body: { prompt, reference_ids: frame.reference_ids } });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: refresh,
  });

  // When a run or a still finishes, bring in what it made.
  const finishedKey = [writing, ...Object.values(drawing)].filter((j): j is number => j !== null && !going(j)).join(",");
  useEffect(() => {
    if (finishedKey) queryClient.invalidateQueries({ queryKey: ["storyboard", projectId] });
  }, [finishedKey, projectId, queryClient]);

  if (frames.isPending) return <p className="text-muted">Loading…</p>;
  if (frames.isError) return <p role="alert" className={errorClass}>Could not load the storyboard. Try again.</p>;
  const list = frames.data;
  const missing = list.filter((f) => f.file_id === null && !f.problems.length && !drawingNow[f.id]);
  const over = (cost: number | undefined) => cost !== undefined && props.used + cost > props.budget;
  const price = (n: number | undefined) => (n === undefined ? "" : ` · ${n} credits`);
  const makeLabel = over(writeCost) ? "Ask Reed to approve" : list.length ? "Redo storyboard" : "Make storyboard";
  const allCost = imageCost === undefined ? undefined : imageCost * missing.length;
  const err = make.error ?? render.error ?? edit.error;

  const makeButton = (
    <button
      className={list.length ? btnSecondary : btnPrimary}
      disabled={writingNow || make.isPending}
      onClick={() => {
        if (list.length && !window.confirm("Replace these frames? New ones are written from the current breakdown.")) return;
        make.mutate();
      }}
    >
      {makeLabel}
      {price(writeCost)}
    </button>
  );

  if (writingNow)
    return (
      <section className={`${card} space-y-3`} aria-label="Storyboard">
        <p className="text-muted">Writing your frames…</p>
        {[0, 1].map((i) => (
          <div key={i} className="h-24 rounded-md bg-surface-2" aria-hidden />
        ))}
      </section>
    );

  if (list.length === 0)
    return (
      <section className={`${card} space-y-3`} aria-label="Storyboard">
        <p className="text-[length:var(--text-xl)] font-semibold">No frames yet.</p>
        <p className="text-muted">One still per clip, so you can check the look before making video.</p>
        {makeButton}
        {err && <p role="alert" className={errorClass}>{err.message}</p>}
      </section>
    );

  return (
    <div className="space-y-4" aria-label="Storyboard">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[length:var(--text-md)] font-semibold">
          Storyboard <span className="font-normal text-muted">· {list.length} frame{list.length === 1 ? "" : "s"}</span>
        </h2>
        <span className="flex gap-2">
          {missing.length > 0 && (
            <button
              className={btnPrimary}
              disabled={render.isPending}
              onClick={async () => {
                for (const f of missing) await render.mutateAsync(f).catch(() => undefined);
              }}
            >
              {over(allCost) ? "Ask Reed to approve" : "Make all stills"}
              {price(allCost)}
            </button>
          )}
          {makeButton}
        </span>
      </div>
      {err && <p role="alert" className={errorClass}>{err.message}</p>}
      <ul className="grid gap-4 sm:grid-cols-2">
        {list.map((f) => {
          const job = drawing[f.id] !== undefined ? jobOf(drawing[f.id]) : undefined;
          const busy = !!drawingNow[f.id];
          return (
            <FrameCard
              key={f.id}
              frame={f}
              aspect={props.aspect}
              busy={busy}
              failed={job?.status === "failed"}
              nameOf={nameOf}
              cost={imageCost}
              over={over(imageCost)}
              onRender={() => render.mutate(f)}
              onSave={(prompt) => edit.mutate({ frame: f, prompt })}
              onOpen={() => setLightbox(f)}
            />
          );
        })}
      </ul>
      {lightbox && lightbox.file_id !== null && (
        <Sheet title={`Clip ${lightbox.clip_id} · shot ${lightbox.shot_id}`} onClose={() => setLightbox(null)}>
          <img src={fileUrl(lightbox.file_id)} alt={`Still for clip ${lightbox.clip_id}`} className="w-full rounded-md" />
          <details className="text-sm text-muted">
            <summary>Prompt Claude wrote</summary>
            <p className="mt-1 whitespace-pre-wrap">{lightbox.prompt}</p>
          </details>
        </Sheet>
      )}
    </div>
  );
}

function FrameCard(props: {
  frame: Frame;
  aspect: string;
  busy: boolean;
  failed: boolean;
  nameOf: (id: string) => string;
  cost: number | undefined;
  over: boolean;
  onRender: () => void;
  onSave: (prompt: string) => void;
  onOpen: () => void;
}) {
  const { frame: f } = props;
  const [editing, setEditing] = useState<string | null>(null);
  const label = props.over ? "Ask Reed to approve" : f.file_id === null ? "Make still" : "Redo still";
  return (
    <li className="space-y-2 text-sm" aria-label={`Frame ${f.clip_id}`}>
      <div className="grid place-items-center overflow-hidden rounded-md border border-border bg-surface-2" style={{ aspectRatio: ratio(props.aspect) }}>
        {props.busy ? (
          <span className="text-muted">Drawing…</span>
        ) : f.file_id !== null ? (
          <button type="button" className="h-full w-full" aria-label={`Open the still for clip ${f.clip_id}`} onClick={props.onOpen}>
            <img src={fileUrl(f.file_id)} alt={`Still for clip ${f.clip_id}`} className="h-full w-full object-cover" />
          </button>
        ) : (
          <span className="text-muted">No still yet</span>
        )}
      </div>
      <div className="font-medium">
        {f.clip_id} · shot {f.shot_id}
      </div>
      {f.stale && <span className="inline-block rounded-sm bg-warning-soft px-2 py-0.5 text-xs font-medium text-warning">Breakdown changed: redo this frame</span>}
      {props.failed && <span className="inline-block rounded-sm bg-danger-soft px-2 py-0.5 text-xs font-medium text-danger">Didn't finish · credits returned</span>}
      <p className="flex flex-wrap gap-1 text-xs">
        {f.reference_ids.map((id) => (
          <span key={id} className="rounded-sm bg-surface-2 px-2 py-0.5">
            {id.startsWith("screen") ? "★ " : id.startsWith("char") ? "● " : id.startsWith("place") ? "⌂ " : ""}
            {props.nameOf(id)}
          </span>
        ))}
      </p>
      {f.problems.length > 0 && (
        <ul className="list-disc space-y-0.5 pl-5 text-xs text-danger" aria-label={`Problems for ${f.clip_id}`}>
          {f.problems.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      )}
      {editing !== null ? (
        <div className="space-y-2">
          <textarea className={input} rows={5} aria-label={`Prompt for clip ${f.clip_id}`} value={editing} onChange={(e) => setEditing(e.target.value)} />
          <div className="flex gap-2">
            <button className={btnPrimary} onClick={() => { props.onSave(editing); setEditing(null); }}>
              Save prompt
            </button>
            <button className={btnSecondary} onClick={() => setEditing(null)}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <button
            className={`${btnSecondary} min-h-11 sm:min-h-9`}
            disabled={props.busy || f.problems.length > 0}
            onClick={props.onRender}
          >
            {label}
            {props.cost !== undefined && ` · ${props.cost} credits`}
          </button>
          <button className={`${linkText} min-h-11 sm:min-h-9`} aria-label={`Edit the prompt for clip ${f.clip_id}`} onClick={() => setEditing(f.prompt)}>
            Edit prompt
          </button>
        </div>
      )}
    </li>
  );
}
