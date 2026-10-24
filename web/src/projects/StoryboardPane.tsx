import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { useBrandPieces } from "../clip/BrandPieces";
import { useJobs } from "../clip/History";
import { fileUrl } from "../api/upload";
import { btnPrimary, btnSecondary, card, errorText as errorClass, input, linkText } from "../ui";
import { useMedia } from "../useMedia";
import { Sheet } from "./Sheet";
import { blockerNames, SheetWarning, useSheetBlocks, type Blocker } from "./sheetBlocks";

type Frame = components["schemas"]["FrameOut"];
const GOING = ["queued", "running", "needs_owner_approval"];
const ratio = (a: string) => a.replace(":", " / ");

/** One still per clip: Claude writes the frame prompts, then each still is drawn. */
/** The project's storyboard frames (shared by the Storyboard and Clips steps). */
export function useFrames(projectId: number) {
  return useQuery({
    queryKey: ["storyboard", projectId],
    queryFn: async () => (await api.GET("/projects/{project_id}/storyboard", { params: { path: { project_id: projectId } } })).data ?? [],
  });
}

export function StoryboardPane(props: { projectId: number; brandId: number; aspect: string; used: number; budget: number; onNext: () => void }) {
  const { projectId, brandId } = props;
  const queryClient = useQueryClient();
  const path = { project_id: projectId };
  const { pieces } = useBrandPieces(brandId);
  const jobs = useJobs();
  const blocks = useSheetBlocks(projectId, brandId);
  // The stills I started: frame id → job id (the server doesn't say which job is which frame yet).
  const [drawing, setDrawing] = useState<Record<number, number>>({});
  const [writing, setWriting] = useState<number | null>(null);
  const [lightbox, setLightbox] = useState<Frame | null>(null);
  const jobOf = (id: number) => jobs.data?.find((j) => j.id === id);
  // Still going: the run that writes the frames, and the stills I started. Between pressing and the job showing in the list it counts as going.
  const going = (id: number | undefined) => id !== undefined && (!jobOf(id) || GOING.includes(jobOf(id)!.status));
  // What the server says is going for this project (so a reload mid-run still shows it).
  const mineGoing = (step: string) => (jobs.data ?? []).filter((j) => j.project_id === projectId && j.step === step && GOING.includes(j.status));
  const writingNow = going(writing ?? undefined) || mineGoing("storyboard").length > 0;
  const stillsGoing = mineGoing("frame").length;
  const drawingNow = Object.fromEntries(Object.entries(drawing).map(([f, j]) => [f, going(j)]));
  const anyGoing = writingNow || stillsGoing > 0 || Object.values(drawingNow).some(Boolean);

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
    mutationFn: async ({ frame, note = "" }: { frame: Frame; note?: string }) => {
      const { data, error } = await api.POST("/projects/{project_id}/storyboard/frames/{frame_id}/render", { params: { path: { ...path, frame_id: frame.id } }, body: { note } });
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

  const approve = useMutation({
    mutationFn: async ({ frame, yes }: { frame: Frame; yes: boolean }) => {
      const args = { params: { path: { ...path, frame_id: frame.id } } };
      const { error, response } = yes
        ? await api.POST("/projects/{project_id}/storyboard/frames/{frame_id}/approve", args)
        : await api.DELETE("/projects/{project_id}/storyboard/frames/{frame_id}/approve", args);
      if (!response.ok) throw new Error(errorText(error));
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
  const missing = list.filter((f) => f.file_id === null && !f.problems.length && !drawingNow[f.id] && blocks.forShot(f.shot_id).length === 0);
  const waitingForSheet = list.filter((f) => f.file_id === null && blocks.forShot(f.shot_id).length > 0);
  const over = (cost: number | undefined) => cost !== undefined && props.used + cost > props.budget;
  const price = (n: number | undefined) => (n === undefined ? "" : ` · ${n} credits`);
  const makeLabel = over(writeCost) ? "Ask Reed to approve" : list.length ? "Redo storyboard" : "Make storyboard";
  const allCost = imageCost === undefined ? undefined : imageCost * missing.length;
  const err = make.error ?? render.error ?? edit.error ?? approve.error;
  const approvedCount = list.filter((f) => f.approved).length;
  const waiting = list.length - approvedCount;

  const makeButton = (
    <button
      className={list.length ? btnSecondary : btnPrimary}
      disabled={writingNow || make.isPending}
      onClick={() => {
        const made = list.filter((f) => f.file_id !== null).length;
        const ask = made > 0 ? `Replace these frames? The ${made} still${made === 1 ? "" : "s"} you've made will be dropped.` : "Replace these frames? New ones are written from the current breakdown.";
        if (list.length && !window.confirm(ask)) return;
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
          Storyboard <span className="font-normal text-muted">· {list.length} frame{list.length === 1 ? "" : "s"} · {approvedCount} approved</span>
        </h2>
        <span className="flex gap-2">
          {missing.length > 0 && (
            <button
              className={btnPrimary}
              disabled={render.isPending}
              onClick={async () => {
                for (const f of missing) await render.mutateAsync({ frame: f }).catch(() => undefined);
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
      {waitingForSheet.length > 0 && (
        <p className="text-sm text-warning">
          {waitingForSheet.length} frame{waitingForSheet.length === 1 ? " waits" : "s wait"} for a sheet ({blockerNames(waitingForSheet.flatMap((f) => blocks.forShot(f.shot_id)))}).
        </p>
      )}
      <ul className="grid gap-4 sm:grid-cols-2">
        {list.map((f) => {
          const frameJobs = (jobs.data ?? []).filter((j) => j.step === "frame" && j.frame_id === f.id).sort((a, b) => b.id - a.id);
          const mine = drawing[f.id] !== undefined ? jobOf(drawing[f.id]) : undefined;
          const job = mine ?? frameJobs[0];
          const busy = !!drawingNow[f.id] || frameJobs.some((j) => GOING.includes(j.status));
          return (
            <FrameCard
              key={f.id}
              frame={f}
              aspect={props.aspect}
              busy={busy}
              failed={job?.status === "failed"}
              blockers={blocks.forShot(f.shot_id)}
              brandId={brandId}
              nameOf={nameOf}
              cost={imageCost}
              over={over(imageCost)}
              onRender={(note) => render.mutate({ frame: f, note })}
              onApprove={(yes) => approve.mutate({ frame: f, yes })}
              onSave={(prompt) => edit.mutate({ frame: f, prompt })}
              onOpen={() => setLightbox(f)}
            />
          );
        })}
      </ul>
      <div className="space-y-1">
        <button className={`${btnPrimary} min-h-11 sm:min-h-9`} disabled={waiting > 0 || list.some((f) => f.stale)} onClick={props.onNext}>
          Next: Clips →
        </button>
        {waiting > 0 && <p className="text-sm text-muted">{`Approve all ${list.length} frame${list.length === 1 ? "" : "s"} first (${waiting} left).`}</p>}
      </div>
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
  blockers: Blocker[];
  brandId: number;
  nameOf: (id: string) => string;
  cost: number | undefined;
  over: boolean;
  onRender: (note?: string) => void;
  onApprove: (yes: boolean) => void;
  onSave: (prompt: string) => void;
  onOpen: () => void;
}) {
  const { frame: f } = props;
  const [editing, setEditing] = useState<string | null>(null);
  const [redo, setRedo] = useState<string | null>(null);
  const phone = useMedia("(max-width: 639px)");
  const verb = props.over ? "Ask Reed to approve" : f.file_id === null ? "Make still" : "Redo";
  const price = props.cost !== undefined ? ` · ${props.cost} credits` : "";
  const redoForm = (
    <div className="space-y-2">
      <label className="block text-sm">
        What should change? (optional)
        <textarea className={input} rows={3} maxLength={500} value={redo ?? ""} onChange={(e) => setRedo(e.target.value)} />
      </label>
      <button
        className={`${btnPrimary} min-h-11 sm:min-h-9`}
        onClick={() => {
          props.onRender((redo ?? "").trim());
          setRedo(null);
        }}
      >
        {props.over ? "Ask Reed to approve" : "Redo"}
        {price}
      </button>
    </div>
  );
  return (
    <li className="space-y-2 text-sm" aria-label={`Frame ${f.clip_id}`}>
      <div className={`relative grid place-items-center overflow-hidden rounded-md bg-surface-2 ${f.approved ? "border-2 border-accent" : "border border-border"}`} style={{ aspectRatio: ratio(props.aspect) }}>
        {f.approved && <span className="absolute right-2 top-2 rounded-full bg-accent px-2 py-0.5 text-xs font-medium text-on-accent">✓ Approved</span>}
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
      <SheetWarning blockers={props.blockers} brandId={props.brandId} />
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
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2">
            {f.file_id === null ? (
              <button className={`${btnSecondary} min-h-11 sm:min-h-9`} disabled={props.busy || f.problems.length > 0 || props.blockers.length > 0} onClick={() => props.onRender()}>
                {verb}
                {price}
              </button>
            ) : (
              <>
                <button
                  className={`${btnSecondary} min-h-11 sm:min-h-9`}
                  disabled={props.busy || (!f.approved && (f.stale || f.problems.length > 0))}
                  onClick={() => props.onApprove(!f.approved)}
                >
                  {f.approved ? "Undo approve" : "Approve"}
                </button>
                <button className={`${btnSecondary} min-h-11 sm:min-h-9`} disabled={props.busy || f.problems.length > 0 || props.blockers.length > 0} onClick={() => setRedo(redo === null ? "" : null)} aria-expanded={redo !== null}>
                  {verb}
                  {price}
                </button>
              </>
            )}
            <button className={`${linkText} min-h-11 sm:min-h-9`} aria-label={`Edit the prompt for clip ${f.clip_id}`} onClick={() => setEditing(f.prompt)}>
              Edit prompt
            </button>
          </div>
          {redo !== null && !phone && redoForm}
          {redo !== null && phone && (
            <Sheet title={`Redo clip ${f.clip_id}`} closeLabel="Cancel" onClose={() => setRedo(null)}>
              {redoForm}
            </Sheet>
          )}
        </div>
      )}
    </li>
  );
}
