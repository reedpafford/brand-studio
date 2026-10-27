import { useEffect, useRef, useState, type ReactNode } from "react";
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
import { blocking } from "./problems";
import { AdviceList, useKeep } from "./Keep";
import { useMe } from "../auth/useMe";
import { refName, useRoleNames } from "./names";
import { useProblemWords } from "./ProblemText";
import { useOwnScriptStop } from "./useOwnScriptStop";
import { Badge, Banner, useToast, wholeCredits } from "../components";
import { RotateCcw } from "lucide-react";
import { usePressed } from "./usePressed";
import { ChangeBox, type ChangeState } from "./ChangeBox";
import { useApproveAll } from "./ApproveAll";
import { SoftenedNote, SoftenIt, type Softened } from "./Soften";

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

/** `oneStep` (the new video page): Make storyboard writes the frames and then draws every still. `clips` is how many stills that is. */
export function StoryboardPane(props: { castRedraw?: { [key: string]: unknown } | null; ownScript?: boolean; oneStep?: boolean; clips?: number; projectId: number; brandId: number; aspect: string; used: number; budget: number }) {
  const { projectId, brandId } = props;
  const queryClient = useQueryClient();
  const toast = useToast();
  const path = { project_id: projectId };
  const { pieces } = useBrandPieces(brandId);
  const jobs = useJobs();
  const blocks = useSheetBlocks(projectId, brandId);
  // The stills I started: frame id → job id (the server doesn't say which job is which frame yet).
  const [drawing, setDrawing] = useState<Record<number, number>>({});
  const [writing, setWriting] = useState<number | null>(null);
  // The frames that were here when the storyboard was asked for again. The server replaces them, so once the run has finished
  // they must not be shown (or drawn on): pressing one answers "No such frame." until the page is reloaded.
  const [replaced, setReplaced] = useState<number[]>([]);
  const [lightbox, setLightbox] = useState<Frame | null>(null);
  const auto = useRef(false);
  const stopFor = useOwnScriptStop(props.ownScript, { used: props.used, budget: props.budget }); // the frames were just asked for, and the stills follow
  const jobOf = (id: number) => jobs.data?.find((j) => j.id === id);
  // Still going: the run that writes the frames, and the stills I started. Between pressing and the job showing in the list it counts as going.
  // A job the list never shows is waited on only briefly (a run that was lost must not read "Writing…" for ever).
  const pressed = usePressed();
  const going = (id: number | undefined) => id !== undefined && (jobOf(id) ? GOING.includes(jobOf(id)!.status) : !(id === writing && pressed.unseen));
  // What the server says is going for this project (so a reload mid-run still shows it).
  const mineGoing = (step: string) => (jobs.data ?? []).filter((j) => j.project_id === projectId && j.step === step && GOING.includes(j.status));
  const writingNow = going(writing ?? undefined) || mineGoing("storyboard").length > 0;
  const stillsGoing = mineGoing("frame").length;
  const drawingNow = Object.fromEntries(Object.entries(drawing).map(([f, j]) => [f, going(j)]));
  const anyGoing = writingNow || stillsGoing > 0 || Object.values(drawingNow).some(Boolean);

  const frames = useQuery({
    queryKey: ["storyboard", projectId],
    queryFn: async () => (await api.GET("/projects/{project_id}/storyboard", { params: { path } })).data ?? [],
    refetchInterval: (q) => (anyGoing || q.state.data?.some((f) => (f.change as ChangeState)?.status === "changing") ? 3000 : false),
  });
  // The run is done but the list on screen is still the old one: wait for the new frames.
  const stillOld = writing !== null && jobOf(writing)?.status === "succeeded" && (frames.data ?? []).some((f) => replaced.includes(f.id));
  const rates = useQuery({ queryKey: ["rates"], queryFn: async () => (await api.GET("/credits/rates")).data ?? [] });
  const rate = (kind: string) => rates.data?.find((r) => r.kind === kind)?.credits_per_unit;
  const writeCost = rate("write-claude");
  const imageCost = rate("image");
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["storyboard", projectId] });

  const roles = useRoleNames(projectId);
  const nameOf = (id: string) => refName(id, pieces, roles);
  const { words, fix } = useProblemWords(projectId, brandId);

  const make = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/projects/{project_id}/storyboard", { params: { path }, body: { per_shot: false } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (job) => {
      setReplaced((queryClient.getQueryData<Frame[]>(["storyboard", projectId]) ?? []).map((f) => f.id));
      setWriting(job.id);
      pressed.press();
      auto.current = !!props.oneStep;
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

  // "Soften it": only the words the image model refuses, said gently, for free. Undo puts the earlier prompt back.
  const [softenedNow, setSoftenedNow] = useState<Record<number, Softened>>({});
  const soften = useMutation({
    mutationFn: async (frame: Frame) => {
      const { data, error } = await api.POST("/projects/{project_id}/storyboard/frames/{frame_id}/soften", { params: { path: { ...path, frame_id: frame.id } } });
      if (!data) throw new Error(errorText(error));
      return { frame, was: { before: data.before, after: data.after } };
    },
    onSuccess: async ({ frame, was }) => {
      setSoftenedNow((s) => ({ ...s, [frame.id]: was }));
      await refresh();
      toast("Softened. The earlier prompt is kept.", async () => {
        await undoSoften(frame, was.before);
      });
    },
  });
  const undoSoften = async (frame: Frame, before: string) => {
    await edit.mutateAsync({ frame, prompt: before });
    setSoftenedNow((s) => Object.fromEntries(Object.entries(s).filter(([id]) => Number(id) !== frame.id)));
  };
  // Undo of "Change this…": an earlier still comes back with the prompt it was made from. Free.
  const pick = useMutation({
    mutationFn: async ({ frame, file }: { frame: Frame; file: number }) => {
      const { error, response } = await api.POST("/projects/{project_id}/storyboard/frames/{frame_id}/pick", { params: { path: { ...path, frame_id: frame.id } }, body: { file_id: file } });
      if (!response.ok) throw new Error(errorText(error));
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

  // The frames are written: draw the stills that are missing, once.
  useEffect(() => {
    const todo = (frames.data ?? []).filter((f) => f.file_id === null && !blocking(f.problems).length && blocks.forShot(f.shot_id).length === 0);
    if (!auto.current || writingNow || stillOld || frames.isFetching || todo.length === 0) return;
    auto.current = false;
    void (async () => {
      for (const f of todo) await render.mutateAsync({ frame: f }).catch(() => undefined);
    })();
  });

  const rows = frames.data ?? [];
  const approveAll = useApproveAll({
    projectId,
    kind: "storyboard",
    noun: "frame",
    rows,
    ready: rows.filter((f) => f.file_id !== null && !f.approved && !f.stale && !f.still_stale && blocking(f.problems).length === 0).length,
    waiting: rows.filter((f) => !f.approved).length,
  });
  if (frames.isPending) return <p className="text-muted">Loading…</p>;
  if (frames.isError) return <p role="alert" className={errorClass}>Could not load the storyboard. Try again.</p>;
  const list = frames.data;
  // After a cast change the stills that show the old cast are redrawn by themselves when the video can pay for it; otherwise they say "Out of date".
  const outOfDate = list.filter((f) => f.still_stale);
  const redrawn = list.filter((f) => f.redrawn && !f.approved);
  const cast = props.castRedraw as { redrawn_for_cast?: { count: number; credits: number }; redraw_refused?: { count: number; credits: number; reason: string } } | null | undefined;
  const redrawCost = imageCost === undefined ? undefined : imageCost * outOfDate.length;
  const castNote =
    cast?.redraw_refused && outOfDate.length > 0 ? (
      <Banner tone="warning" title={cast.redraw_refused.reason} />
    ) : cast?.redrawn_for_cast && redrawn.length > 0 ? (
      <Banner tone="info" title={`Redrew ${cast.redrawn_for_cast.count} still${cast.redrawn_for_cast.count === 1 ? "" : "s"} for the new cast · ${wholeCredits(cast.redrawn_for_cast.credits)} credits`} />
    ) : null;
  // Past what the video can spend, an editor is declined with the reason; Reed decides for himself.
  const redrawBlocked = outOfDate.length === 0 ? null : stopFor(redrawCost);
  const missing = list.filter((f) => f.file_id === null && !blocking(f.problems).length && !drawingNow[f.id] && blocks.forShot(f.shot_id).length === 0);
  const waitingForSheet = list.filter((f) => f.file_id === null && blocks.forShot(f.shot_id).length > 0);
  // Past a limit an editor's button is disabled with the reason (the week on their own script, the video's budget otherwise); nobody is asked to approve.
  const price = (n: number | undefined) => (n === undefined ? "" : ` · ${n} credits`);
  // One press in the new flow writes the frames and draws every still: one total decides the price and the budget check.
  const makeTotal = props.oneStep && props.clips && imageCost !== undefined && writeCost !== undefined ? writeCost + imageCost * props.clips : writeCost;
  const makeLabel = list.length ? "Redo storyboard" : "Make storyboard";
  const allCost = imageCost === undefined ? undefined : imageCost * missing.length;
  const declined = stopFor(makeTotal) ?? stopFor(allCost) ?? stopFor(imageCost);
  const err = make.error ?? render.error ?? edit.error ?? approve.error;
  const approvedCount = list.filter((f) => f.approved).length;

  const makeButton = (
    <button
      className={`${list.length ? btnSecondary : btnPrimary} min-h-11 sm:min-h-9`}
      disabled={writingNow || stillOld || make.isPending || !!stopFor(makeTotal)}
      onClick={() => {
        const made = list.filter((f) => f.file_id !== null).length;
        const ask = made > 0 ? `Replace these frames? The ${made} still${made === 1 ? "" : "s"} you've made will be dropped.` : "Replace these frames? New ones are written from the current breakdown.";
        if (list.length && !window.confirm(ask)) return;
        make.mutate();
      }}
    >
      {makeLabel}
      {price(makeTotal)}
    </button>
  );

  if (writingNow || stillOld)
    return (
      <section className={`${card} space-y-3`} aria-label="Storyboard">
        <p className="text-muted">Writing your frames…</p>
        {[0, 1].map((i) => (
          <div key={i} className="h-24 rounded-md bg-surface-2" aria-hidden />
        ))}
      </section>
    );

  // The newest run that wrote the frames, if it failed: say so, with a way to try again.
  const frameRun = (jobs.data ?? []).filter((j) => j.project_id === projectId && j.step === "storyboard").sort((a, b) => b.id - a.id)[0];
  const framesFailed = frameRun?.status === "failed" || (writing !== null && pressed.unseen && !jobOf(writing));

  if (list.length === 0)
    return (
      <section className={`${card} space-y-3`} aria-label="Storyboard">
        {framesFailed && (
          <Banner title={frameRun?.status === "failed" ? "The frames didn't finish." : "We lost track of the frames."}>
            {frameRun?.status === "failed" ? "Nothing was charged. Make them again below." : "If they finish, they show up here. Or make them again below."}
          </Banner>
        )}
        <p className="text-[length:var(--text-xl)] font-semibold">No frames yet.</p>
        <p className="text-muted">One still per clip, so you can check the look before making video.</p>
        {makeButton}
        {err && <p role="alert" className={errorClass}>{err.message}</p>}
        {declined && <p className="text-sm text-warning">{declined}</p>}
      </section>
    );

  return (
    <div className="space-y-4" aria-label="Storyboard">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[length:var(--text-md)] font-semibold">
          Storyboard <span className="font-normal text-muted">· {list.length} frame{list.length === 1 ? "" : "s"} · {approvedCount} approved</span>
        </h2>
        <span className="flex w-full flex-wrap gap-2 sm:w-auto">
          {approveAll.button}
          {missing.length > 0 && (
            <button
              className={outOfDate.length > 0 ? btnSecondary : btnPrimary}
              disabled={render.isPending || !!stopFor(allCost)}
              onClick={async () => {
                for (const f of missing) await render.mutateAsync({ frame: f }).catch(() => undefined);
              }}
            >
              Make all stills
              {price(allCost)}
            </button>
          )}
          {outOfDate.length > 0 && (
            <button className={btnPrimary} disabled={render.isPending || redrawBlocked !== null} onClick={async () => { for (const f of outOfDate) await render.mutateAsync({ frame: f }).catch(() => undefined); }}>
              Redraw {outOfDate.length} still{outOfDate.length === 1 ? "" : "s"}
              {price(redrawCost)}
            </button>
          )}
          {makeButton}
        </span>
      </div>
      {approveAll.line}
      {castNote}
      {redrawBlocked && redrawBlocked !== declined && <p className="text-sm text-warning">{redrawBlocked}</p>}
      {err && <p role="alert" className={errorClass}>{err.message}</p>}
        {declined && <p className="text-sm text-warning">{declined}</p>}
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
              projectId={projectId}
              aspect={props.aspect}
              busy={busy}
              failed={job?.status === "failed"}
              blockers={blocks.forShot(f.shot_id)}
              brandId={brandId}
              nameOf={nameOf}
              words={words}
              fix={fix}
              cost={imageCost}
              stopped={!!stopFor(imageCost)}
              stopFor={stopFor}
              oneStep={!!props.oneStep}
              onPick={(file) => pick.mutate({ frame: f, file })}
              onRender={(note) => render.mutate({ frame: f, note })}
              onApprove={(yes) => approve.mutate({ frame: f, yes })}
              onSave={(prompt) => edit.mutate({ frame: f, prompt })}
              softening={soften.isPending}
              softened={softenedNow[f.id] ?? ((f.softened as Softened | null | undefined) ?? null)}
              softenedBySelf={!softenedNow[f.id]}
              onSoften={() => soften.mutate(f)}
              onUndoSoften={(before) => undoSoften(f, before)}
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
  projectId: number;
  aspect: string;
  busy: boolean;
  failed: boolean;
  blockers: Blocker[];
  brandId: number;
  nameOf: (id: string) => string;
  words: (p: string) => string;
  fix: (p: string) => ReactNode;
  cost: number | undefined;
  stopped: boolean;
  stopFor: (cost: number | undefined) => string | null;
  oneStep: boolean;
  onPick: (file: number) => void;
  onRender: (note?: string) => void;
  onApprove: (yes: boolean) => void;
  onSave: (prompt: string) => void;
  softening: boolean;
  softened: Softened | null;
  softenedBySelf: boolean;
  onSoften: () => void;
  onUndoSoften: (before: string) => void;
  onOpen: () => void;
}) {
  const { frame: f } = props;
  const keep = useKeep(props.projectId, { of: "frame", id: f.id });
  const owner = useMe().data?.role === "owner";
  const [editing, setEditing] = useState<string | null>(null);
  const [redo, setRedo] = useState<string | null>(null);
  const phone = useMedia("(max-width: 639px)");
  const verb = f.file_id === null ? "Make still" : "Redo";
  const price = props.cost !== undefined ? ` · ${props.cost} credits` : "";
  const redoForm = (
    <div className="space-y-2">
      <label className="block text-sm">
        What should change? (optional)
        <textarea className={input} rows={3} maxLength={500} value={redo ?? ""} onChange={(e) => setRedo(e.target.value)} />
      </label>
      <button
        className={`${btnPrimary} min-h-11 sm:min-h-9`}
        disabled={props.stopped}
        onClick={() => {
          props.onRender((redo ?? "").trim());
          setRedo(null);
        }}
      >
        Redo
        {price}
      </button>
    </div>
  );
  return (
    <li className="space-y-2 text-sm" aria-label={`Frame ${f.clip_id}`}>
      <div className={`relative grid place-items-center overflow-hidden rounded-md bg-surface-2 ${f.approved ? "border-2 border-accent" : "border border-border"}`} style={{ aspectRatio: ratio(props.aspect) }}>
        {f.approved && <span className="absolute right-2 top-2 rounded-full bg-accent px-2 py-0.5 text-xs font-medium text-on-accent">✓ Approved</span>}
        {!f.approved && f.still_stale && (
          <span className="absolute left-2 top-2">
            <Badge tone="warning">Out of date</Badge>
          </span>
        )}
        {!f.approved && !f.still_stale && f.redrawn && (
          <span className="absolute left-2 top-2">
            <Badge icon={RotateCcw}>Redrawn</Badge>
          </span>
        )}
        {props.busy ? (
          <span className="text-muted">Drawing…</span>
        ) : f.file_id !== null && (f.change as ChangeState)?.status === "changing" ? (
          <>
            <img src={fileUrl(f.file_id)} alt={`Still for clip ${f.clip_id}`} className="h-full w-full object-cover opacity-50" />
            <span className="absolute inset-0 grid place-items-center text-sm font-medium">Making the change…</span>
          </>
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
      {blocking(f.problems).length > 0 && (
        <ul className="list-disc space-y-0.5 pl-5 text-xs text-danger" aria-label={`Problems for ${f.clip_id}`}>
          {blocking(f.problems).map((p) => (
            <li key={p}>
              {props.words(p)}
              {props.fix(p)}
              {/may refuse/.test(p) && <SoftenIt busy={props.softening} onSoften={props.onSoften} />}
            </li>
          ))}
        </ul>
      )}
      {props.softened && <SoftenedNote note={props.softenedBySelf ? "We softened this frame so it can be drawn." : "Softened. Here is what changed."} was={props.softened} busy={props.softening} onUndo={() => props.onUndoSoften(props.softened!.before)} />}
      <AdviceList label={props.words} problems={f.problems} kept={f.kept} onKeep={(problem, undo) => keep.mutate({ problem, undo })} busy={keep.isPending} owner={owner} name={`Advice for ${f.clip_id}`} />
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
              <button className={`${btnSecondary} min-h-11 sm:min-h-9`} disabled={props.stopped || props.busy || blocking(f.problems).length > 0 || props.blockers.length > 0} onClick={() => props.onRender()}>
                {verb}
                {price}
              </button>
            ) : (
              <>
                <button
                  className={`${btnSecondary} min-h-11 sm:min-h-9`}
                  disabled={props.busy || (!f.approved && (f.stale || blocking(f.problems).length > 0))}
                  onClick={() => props.onApprove(!f.approved)}
                >
                  {f.approved ? "Undo approve" : "Approve"}
                </button>
                <button className={`${btnSecondary} min-h-11 sm:min-h-9`} disabled={props.stopped || props.busy || blocking(f.problems).length > 0 || props.blockers.length > 0} onClick={() => (props.oneStep ? props.onRender() : setRedo(redo === null ? "" : null))} aria-expanded={props.oneStep ? undefined : redo !== null}>
                  {props.oneStep ? "Make another" : verb}
                  {price}
                </button>
              </>
            )}
            <button className={`${linkText} min-h-11 sm:min-h-9`} aria-label={`Edit the prompt for clip ${f.clip_id}`} onClick={() => setEditing(f.prompt)}>
              {props.oneStep ? "Advanced: edit the prompt" : "Edit prompt"}
            </button>
          </div>
          {props.oneStep && f.file_id !== null && (
            <ChangeBox
              kind="frame"
              projectId={props.projectId}
              id={f.id}
              label={f.clip_id}
              change={f.change as ChangeState}
              hold={props.busy ? "This one is still being made" : f.stale ? "Make the storyboard again first" : null}
              stopFor={props.stopFor}
              onUndo={f.earlier.length ? () => props.onPick((f.earlier.at(-1) as { file_id: number }).file_id) : undefined}
            />
          )}
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
