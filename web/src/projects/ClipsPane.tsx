import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Banner, useToast } from "../components";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { useJobs } from "../clip/History";
import { btnPrimary, btnSecondary, card, errorText as errorClass } from "../ui";
import { blockerNames, useSheetBlocks } from "./sheetBlocks";
import { useFrames } from "./StoryboardPane";
import { blocking } from "./problems";
import { useOwnScriptStop } from "./useOwnScriptStop";
import { usePressed } from "./usePressed";
import { useProblemWords } from "./ProblemText";
import { type ChangeState } from "./ChangeBox";
import { useApproveAll } from "./ApproveAll";
import { RewriteNote, RewriteOne } from "./RewriteClips";
import { ClipCard } from "./ClipCard";

type Clip = components["schemas"]["ProjectClipOut"];
const GOING = ["queued", "running", "needs_owner_approval"];

export function ClipsPane(props: { ownScript?: boolean; review?: boolean; projectId: number; brandId: number; aspect: string; projectName: string; used: number; budget: number }) {
  const { projectId } = props;
  const queryClient = useQueryClient();
  const path = { project_id: projectId };
  const jobs = useJobs();
  const frames = useFrames(projectId);
  const blocks = useSheetBlocks(projectId, props.brandId);
  // "Looks good" on a prompt is kept on the server (saving an edit counts as read; a rewritten prompt clears it).
  const promptOk = useMutation({
    mutationFn: async ({ clip, undo }: { clip: Clip; undo?: boolean }) => {
      const args = { params: { path: { ...path, clip_id: clip.id } } };
      const { response, error } = undo ? await api.DELETE("/projects/{project_id}/clips/{clip_id}/prompt-ok", args) : await api.POST("/projects/{project_id}/clips/{clip_id}/prompt-ok", args);
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project-clips", projectId] }),
  });
  const stopFor = useOwnScriptStop(props.ownScript, { used: props.used, budget: props.budget });
  const { words, fix } = useProblemWords(projectId, props.brandId);
  const [writing, setWriting] = useState<number | null>(null);
  const jobOf = (id: number) => jobs.data?.find((j) => j.id === id);
  const pressed = usePressed();
  // A job the list never shows is waited on only briefly (a run that was lost must not read "Writing…" for ever).
  const going = (id: number | undefined) => id !== undefined && (jobOf(id) ? GOING.includes(jobOf(id)!.status) : !(id === writing && pressed.unseen));
  // The newest take job for a clip row (it survives a reload, since the job says which clip it is for).
  const takeJob = (clipRowId: number) =>
    (jobs.data ?? []).filter((j) => j.project_clip_id === clipRowId && j.step === "clip_take").sort((a, b) => b.id - a.id)[0];
  const serverGoing = (step: string) => (jobs.data ?? []).filter((j) => j.project_id === projectId && j.step === step && GOING.includes(j.status));
  const writingNow = going(writing ?? undefined) || serverGoing("clip_prompts").length > 0;
  const takesGoing = serverGoing("clip_take").length;
  const anyGoing = writingNow || takesGoing > 0;

  const clips = useQuery({
    queryKey: ["project-clips", projectId],
    queryFn: async () => (await api.GET("/projects/{project_id}/clips", { params: { path } })).data ?? [],
    refetchInterval: (q) => (anyGoing || q.state.data?.some((c) => (c.change as ChangeState)?.status === "changing") ? 3000 : false),
  });
  const rates = useQuery({ queryKey: ["rates"], queryFn: async () => (await api.GET("/credits/rates")).data ?? [] });
  const rate = (kind: string) => rates.data?.find((r) => r.kind === kind)?.credits_per_unit;
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["project-clips", projectId] });
    queryClient.invalidateQueries({ queryKey: ["project-video", projectId] });
  };
  // When a run or a take finishes, bring in what it made. The clips only refetch while a job is
  // going, so a job that finishes between two polls (or before it is ever seen running, like the
  // free stand-ins) would otherwise leave the card saying "Not made" until a reload.
  const finishedKey = (jobs.data ?? [])
    .filter((j) => j.project_id === projectId && (j.step === "clip_take" || j.step === "clip_prompts") && j.status === "succeeded")
    .map((j) => j.id)
    .join(",");
  useEffect(() => {
    if (!finishedKey) return;
    queryClient.invalidateQueries({ queryKey: ["project-clips", projectId] });
    queryClient.invalidateQueries({ queryKey: ["project-video", projectId] });
  }, [finishedKey, projectId, queryClient]);

  const write = useMutation({
    mutationFn: async (clipId?: string) => {
      const { data, error } = await api.POST("/projects/{project_id}/clips/prompts", { params: { path }, ...(clipId ? { body: { clip_id: clipId } } : {}) });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (job) => {
      setWriting(job.id);
      pressed.press();
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["rewrite-price", projectId] });
    },
  });
  const generate = useMutation({
    mutationFn: async ({ clip, note }: { clip: Clip; note?: string }) => {
      const { data, error } = await api.POST("/projects/{project_id}/clips/{clip_id}/generate", {
        params: { path: { ...path, clip_id: clip.id } },
        ...(note ? { body: { note } } : {}),
      });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });
  const review = useMutation({
    mutationFn: async (act: { clip: Clip; take?: number; undo?: boolean }) => {
      const args = { params: { path: { ...path, clip_id: act.clip.id } } };
      const { error, response } = act.undo
        ? await api.DELETE("/projects/{project_id}/clips/{clip_id}/approve", args)
        : act.take !== undefined
          ? await api.POST("/projects/{project_id}/clips/{clip_id}/takes/{take_id}/pick", { params: { path: { ...path, clip_id: act.clip.id, take_id: act.take } } })
          : await api.POST("/projects/{project_id}/clips/{clip_id}/approve", args);
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: refresh,
  });
  const edit = useMutation({
    mutationFn: async ({ clip, prompt }: { clip: Clip; prompt: string }) => {
      const { data, error } = await api.PUT("/projects/{project_id}/clips/{clip_id}", { params: { path: { ...path, clip_id: clip.id } }, body: { prompt, references: clip.references } });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: refresh,
  });
  // "Fix this clip's prompt": free, never charged. The answer is fixed now, on its way (Claude is rewriting it), or not possible.
  const toast = useToast();
  const [fixing, setFixing] = useState<Record<number, number>>({}); // clip → the job fixing it
  const [fixSaid, setFixSaid] = useState<Record<number, string>>({});
  const undoFix = async (clip: Clip, before: string) => {
    await edit.mutateAsync({ clip, prompt: before });
    setFixSaid((m) => Object.fromEntries(Object.entries(m).filter(([id]) => Number(id) !== clip.id)));
  };
  const fixPrompt = useMutation({
    mutationFn: async (clip: Clip) => {
      const { data, error } = await api.POST("/projects/{project_id}/clips/{clip_id}/fix", { params: { path: { ...path, clip_id: clip.id } } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: async (r, clip) => {
      setFixSaid((m) => Object.fromEntries(Object.entries(m).filter(([id]) => Number(id) !== clip.id)));
      if (r.job) setFixing((f) => ({ ...f, [clip.id]: r.job!.id }));
      if (r.fixed === false) setFixSaid((m) => ({ ...m, [clip.id]: r.reason }));
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      await refresh();
      if (r.fixed === true) toast(`Fixed clip ${clip.clip_id}'s prompt.`, () => void undoFix(clip, r.before));
    },
    onError: (e, clip) => setFixSaid((m) => ({ ...m, [clip.id]: e.message })),
  });
  const fixBusy = (c: Clip) => (fixPrompt.isPending && fixPrompt.variables?.id === c.id) || (fixing[c.id] !== undefined && !!jobOf(fixing[c.id]) && GOING.includes(jobOf(fixing[c.id])!.status));
  // When the rewrite Claude was doing has finished, bring in the new prompt.
  const fixDone = Object.entries(fixing).filter(([, j]) => jobOf(j) && !GOING.includes(jobOf(j)!.status)).map(([id]) => id).join(",");
  useEffect(() => {
    if (fixDone) refresh();
  }, [fixDone]); // eslint-disable-line react-hooks/exhaustive-deps
  const realImage = useMutation({
    mutationFn: async ({ clip, shot, on }: { clip: Clip; shot: string; on: boolean }) => {
      const { data, error } = await api.PUT("/projects/{project_id}/clips/{clip_id}/inserts/{shot_id}", {
        params: { path: { ...path, clip_id: clip.id, shot_id: shot } },
        body: { use_real_image: on },
      });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: refresh, // the take and its approval stay; only the finished video goes out of date
  });
  const rows = clips.data ?? [];
  const approveAll = useApproveAll({
    projectId,
    kind: "clips",
    noun: "clip",
    rows,
    ready: rows.filter((c) => c.picked_take_id !== null && !c.approved && !c.stale && blocking(c.problems, c.kept).length === 0).length,
    waiting: rows.filter((c) => !c.approved).length,
  });
  if (clips.isPending || frames.isPending) return <p className="text-muted">Loading…</p>;
  if (clips.isError) return <p role="alert" className={errorClass}>Could not load the clips. Try again.</p>;
  const list = clips.data;
  // Past a limit an editor's button is disabled with the reason (the week on their own script, the video's budget otherwise); nobody is asked to approve.
  const price = (n: number | undefined) => (n === undefined ? "" : ` · ${Math.round(n)} credits`);
  const err = write.error ?? generate.error ?? review.error ?? edit.error ?? realImage.error ?? promptOk.error;
  const takeCost = (c: Clip) => c.take_credits;
  const busyFor = (c: Clip) => going(takeJob(c.id)?.id);
  // In the new flow every prompt is read and marked "Looks good" before takes are paid for.
  const toRead = (c: Clip) => !!props.review && c.takes.length === 0 && !c.prompt_ok;
  const unread = list.filter(toRead).length;
  const missing = list.filter((c) => c.takes.length === 0 && !toRead(c) && blocking(c.problems, c.kept).length === 0 && !c.stale && !busyFor(c) && blocks.forClip(c.clip_id).length === 0);
  const waitingForSheet = list.filter((c) => c.takes.length === 0 && blocks.forClip(c.clip_id).length > 0);
  const allCost = missing.reduce((n, c) => n + c.take_credits, 0);
  const approved = list.filter((c) => c.approved).length;
  const stale = list.filter((c) => c.stale);
  const writeCost = rate("write-claude");
  const declined = stopFor(writeCost) ?? stopFor(allCost) ?? list.map((c) => stopFor(takeCost(c))).find(Boolean) ?? null;

  if (writingNow && list.length === 0)
    return (
      <section className={`${card} space-y-3`} aria-label="Clips">
        <p className="text-muted">Writing your clip prompts…</p>
        <div className="h-24 rounded-md bg-surface-2" aria-hidden />
      </section>
    );

  // The newest run that wrote the prompts, if it failed: say so, with a way to try again.
  const promptRun = (jobs.data ?? []).filter((j) => j.project_id === projectId && j.step === "clip_prompts").sort((a, b) => b.id - a.id)[0];
  const promptsFailed = promptRun?.status === "failed" || (writing !== null && pressed.unseen && !jobOf(writing));

  if (list.length === 0)
    return (
      <section className={`${card} space-y-3`} aria-label="Clips">
        {promptsFailed && (
          <Banner title={promptRun?.status === "failed" ? "The clip prompts didn't finish." : "We lost track of the clip prompts."}>
            {promptRun?.status === "failed" ? "Nothing was charged. Write them again below." : "If they finish, they show up here. Or write them again below."}
          </Banner>
        )}
        <p className="text-[length:var(--text-xl)] font-semibold">No clips yet.</p>
        <p className="text-muted">Each clip is made from its storyboard frame and the breakdown.</p>
        <button className={`${btnPrimary} min-h-11 sm:min-h-9`} disabled={write.isPending || !!stopFor(writeCost)} onClick={() => write.mutate(undefined)}>
          Write clip prompts
          {price(writeCost)}
        </button>
        {err && <p role="alert" className={errorClass}>{err.message}</p>}
        {declined && <p className="text-sm text-warning">{declined}</p>}
      </section>
    );

  return (
    <div className="space-y-4" aria-label="Clips">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[length:var(--text-md)] font-semibold">
          Clips <span className="font-normal text-muted">· {list.length} · {approved} approved</span>
        </h2>
        <span className="flex w-full flex-wrap gap-2 sm:w-auto">
          {approveAll.button}
        {missing.length > 0 && (
          <button
            className={`${stale.length > 0 ? btnSecondary : btnPrimary} min-h-11 sm:min-h-9`} // the rewrite is the step's amber while any clip is stale
            disabled={generate.isPending || unread > 0 || stale.length > 0 || !!stopFor(allCost)}
            onClick={async () => {
              for (const c of missing) await generate.mutateAsync({ clip: c }).catch(() => undefined);
            }}
          >
            {props.review ? "Make the takes" : "Make missing"}
            {price(allCost)}
          </button>
        )}
        </span>
      </div>
      {approveAll.line}
      {declined && <p className="text-sm text-warning">{declined}</p>}
      {stale.length > 0 && <RewriteNote projectId={projectId} count={stale.length} writing={writingNow} busy={write.isPending} stopFor={stopFor} onRewrite={() => write.mutate(undefined)} />}
      {stale.length > 0 && <p className="text-sm text-muted">Rewrite the clips made for an older breakdown first ({stale.length}).</p>}
      {unread > 0 && <p className="text-sm text-muted">Read each prompt and press Looks good before the takes are made ({unread} left).</p>}
      {err && <p role="alert" className={errorClass}>{err.message}</p>}
      {waitingForSheet.length > 0 && (
        <p className="text-sm text-warning">
          {waitingForSheet.length} clip{waitingForSheet.length === 1 ? " waits" : "s wait"} for a sheet ({blockerNames(waitingForSheet.flatMap((c) => blocks.forClip(c.clip_id)))}).
        </p>
      )}
      <ul className="space-y-4">
        {list.map((c) => {
          const job = takeJob(c.id);
          return (
            <ClipCard
              key={c.id}
              clip={c}
              projectId={projectId}
              words={words}
              fix={fix}
              aspect={props.aspect}
              poster={frames.data?.find((f) => f.clip_id === c.clip_id)?.file_id ?? null}
              projectName={props.projectName}
              job={job}
              busy={busyFor(c)}
              blockers={blocks.forClip(c.clip_id)}
              toRead={toRead(c)}
              onLooksGood={() => promptOk.mutate({ clip: c })}
              onUndoLooksGood={() => promptOk.mutate({ clip: c, undo: true })}
              showPrompt={!!props.review && c.takes.length === 0}
              brandId={props.brandId}
              cost={takeCost(c)}
              stopped={!!stopFor(takeCost(c))}
              stopFor={stopFor}
              review={!!props.review}
              onGenerate={(note) => generate.mutate({ clip: c, note })}
              onPick={(take) => review.mutate({ clip: c, take })}
              onApprove={() => review.mutate({ clip: c })}
              onRealImage={(shot, on) => realImage.mutate({ clip: c, shot, on })}
              onUnapprove={() => review.mutate({ clip: c, undo: true })}
              onSave={(prompt) => edit.mutate({ clip: c, prompt })}
              fixBusy={fixBusy(c)}
              fixSaid={fixSaid[c.id] ?? null}
              onFix={() => fixPrompt.mutate(c)}
              onUndoFix={(before) => undoFix(c, before)}
              undoing={edit.isPending && edit.variables?.clip.id === c.id}
              rewrite={(c.stale || (c.free_fix_used && blocking(c.problems, c.kept).length > 0)) && !writingNow ? <RewriteOne projectId={projectId} clipId={c.clip_id} busy={write.isPending} stopFor={stopFor} onRewrite={() => write.mutate(c.clip_id)} /> : null}
            />
          );
        })}
      </ul>
    </div>
  );
}
