import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, FileText, Square } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { useMe } from "../auth/useMe";
import { Button, Dialog, Skeleton, buttonClass, creditsLabel, wholeCredits } from "../components";
import { ChangeBox, useSettingsWords } from "../freestyle/Composer";
import { mmss } from "../freestyle/FromScript";
import { Thread, type Said } from "../freestyle/Thread";
import { useFreestyle, useFreestyleActions, type Freestyle } from "../freestyle/useFreestyle";
import { InTheCut, phaseOf, useDirectorRun, useMovesRefresh } from "../projects/DirectorPanel";
import { LockChips } from "../projects/LockChips";
import { VideoPage } from "../projects/VideoPage";
import { useProjectClips } from "../projects/useProgress";
import { letterOf } from "../scripts/status";
import { useScript } from "../scripts/useScript";
import { refreshJobs } from "../jobs/refresh";
import { useRail } from "../useMedia";
import { serverTime } from "../time";
import { VideoTop, mp4, useVideoProject } from "./VideoTop";

type Project = components["schemas"]["ProjectOut"];

/** /b/:brandId/videos/:id: a video the director makes from a freestyle (P3, freestyle_id) opens on its chat; ?step=
 *  opens its steps (B_VideoSteps). Every other video opens on its steps as before. */
export function VideoRoute() {
  const project = useVideoProject(Number(useParams().projectId));
  const [params] = useSearchParams();
  if (project.isPending) return <Skeleton className="m-8 h-64" />;
  if (project.data?.freestyle_id && !params.get("step")) return <VideoChat p={project.data} freestyleId={project.data.freestyle_id} />;
  return <VideoPage />;
}

/** Where the run is, in the header's and the box's words. A held move mid-run still reads as Working. */
function stateOf(fs: Freestyle, running: boolean) {
  if (running) return "working" as const;
  if (fs.status === "waiting") return fs.file_id ? ("change" as const) : ("waiting" as const);
  return fs.status;
}

/** Which thread item is the delivery the player belongs to: the newest run's deliver turn, or (a change's run since)
 *  the last finished move before the newest person's note. */
function deliveryOf(items: Said[], turns: { tool: string | null; created_at: string }[]) {
  const at = turns.filter((t) => t.tool === "deliver").map((t) => t.created_at).at(-1);
  if (at) return items.find((t) => t.kind === "move" && serverTime(t.at).getTime() === serverTime(at).getTime())?.id;
  const lastNote = items.map((t) => t.kind).lastIndexOf("message");
  return [...items.slice(0, lastNote)].reverse().find((t) => t.kind === "move" && t.status === "done")?.id;
}

/** The chat view (B_VideoWaiting … B_ChangeHeld). `p`: the video, or before the owner's OK to an editor's send (when its
 *  video isn't theirs to read yet) just its id and brand, from the freestyle. */
export function VideoChat({ p, freestyleId }: { p: Pick<Project, "id" | "brand_id">; freestyleId: number }) {
  const me = useMe().data;
  const owner = me?.role === "owner";
  const rail = useRail();
  const queryClient = useQueryClient();
  const q = useFreestyle(freestyleId);
  const fs = q.data;
  const run = useDirectorRun(p.id).data;
  const clips = useProjectClips(p.id).data ?? [];
  const words = useSettingsWords();
  const actions = useFreestyleActions(freestyleId);
  const script = useScript(fs?.script_id ?? 0).data;
  const [stopping, setStopping] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);
  // Newest at the bottom: keep the latest move (and the cut under it) in view as they arrive.
  const newest = `${fs?.thread.length}:${run?.thread?.length}:${fs?.file_id}`;
  useEffect(() => {
    scroller.current?.scrollTo?.({ top: scroller.current.scrollHeight });
  }, [newest]);
  useMovesRefresh(p.id, fs?.thread.length ?? 0, fs?.status ?? "");
  const again = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/projects/{project_id}/director", { params: { path: { project_id: p.id } } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["director", p.id], data);
      void queryClient.invalidateQueries({ queryKey: ["freestyle", freestyleId] });
      return refreshJobs(queryClient);
    },
  });
  if (!fs) return q.isError ? <p role="alert" className="p-6 text-danger">{q.error.message}</p> : <Skeleton className="m-8 h-64" />;

  // A run whose only turn waits for the owner (a change's send) hasn't started; one held mid-run is still working.
  const running = run?.status === "running" && !run.turns.every((t) => t.status === "needs_owner_approval");
  const state = stateOf(fs, running);
  const maker = fs.created_by_name === me?.name;
  // The thread is the freestyle's (its first words, moves and held sends), with the owner's saved notes from the video's
  // own chat, each note marked Answered or Open from there.
  const said = run?.thread ?? [];
  const known = (t: Said) => said.find((x) => x.kind === "message" && x.who === t.who && x.text === t.text);
  const items: Said[] = [...fs.thread.map((t) => (t.kind === "message" ? { ...t, answered: known(t)?.answered } : t)), ...said.filter((x) => x.kind === "message" && !fs.thread.some((t) => t.kind === "message" && t.who === x.who && t.text === x.text)).map((x) => ({ ...x, id: `note-${x.id}` }))].sort((a, b) => serverTime(a.at).getTime() - serverTime(b.at).getTime());
  const delivered = fs.file_id ? deliveryOf(items, run?.turns ?? []) : undefined;
  const heldMove = [...items].reverse().find((t) => t.kind === "move" && t.status === "held")?.id;
  const noted = owner && !running && (run?.unread ?? 0) > 0;
  // Made from a script that was there before it (a pasted script is made with its freestyle).
  const fromScript = !!script && serverTime(script.created_at) < serverTime(fs.created_at);
  const opening = fs.thread.find((t) => t.kind === "message")?.text;
  const slot = script?.versions.find((v) => v.project_id === p.id) ?? script?.versions.find((v) => v.text === opening); // before the OK it has no video
  const seconds = Math.round(clips.reduce((n, c) => n + c.seconds, 0));
  const title = fromScript && slot && slot.slot > 0 ? `${fs.title} · ${letterOf(slot.slot)}` : fs.title;
  const stepsTo = state === "waiting" || (state === "working" && rail) ? null : clips.length ? "clips" : "plan";
  const download = fs.file_id && (
    <a className={buttonClass(noted ? "secondary" : "primary")} href={fileUrl(fs.file_id)} download={mp4(fs.title)}>
      <Download size={16} strokeWidth={1.75} aria-hidden />
      Download MP4
    </a>
  );
  const top = (
    <>
      {state === "waiting" && maker && <Button variant="ghost" dense className="text-muted! hover:text-text!" busy={actions.withdraw.isPending} onClick={() => actions.withdraw.mutate()}>Withdraw</Button>}
      {state === "working" && <Button variant="secondary" dense icon={Square} onClick={() => setStopping(true)}>Stop</Button>}
      {state === "change" && maker && <Button variant="ghost" dense className="text-muted! hover:text-text!" busy={actions.withdraw.isPending} onClick={() => actions.withdraw.mutate()}>Withdraw change</Button>}
      {owner && ["delivered", "stopped", "failed", "declined", "withdrawn"].includes(state) && (
        <Button variant={noted || !fs.file_id ? "primary" : "secondary"} dense busy={again.isPending} price={run?.run_price || undefined} charge="estimate" onClick={() => again.mutate()}>
          Make it again
        </Button>
      )}
      {state !== "working" && download}
    </>
  );
  const box =
    state === "waiting" ? (fromScript ? "Opens once the owner approves" : "You can change it once the owner approves it, or withdraw it now.")
    : state === "working" ? "The director will read this on its next move."
    : state === "change" ? "Another change waits for the owner too."
    : owner ? "Notes are saved. Make it again makes them."
    : "Each change goes to the owner first. Nothing is spent until they say yes.";
  const extra = (t: Said) =>
    t.id === delivered ? (
      <Cut fs={fs} p={p} note={items.find((i) => i.id === t.id)?.text ?? ""} seconds={seconds} spent={run?.credits ?? fs.credits} hasClips={clips.length > 0} />
    ) : t.id === heldMove && state === "waiting" ? (
      <Card title="Sent to the owner for approval" price={fs.up_to ?? 0} frames={clips.length || 6} foot={fromScript ? undefined : "Nothing is made until the owner says yes."} />
    ) : t.id === heldMove && state === "change" ? (
      <Card title="Change asked · waiting for the owner" price={run?.run_price ?? 0} foot="The cut above stays until the owner says yes." />
    ) : null;
  return (
    <div className="flex h-[calc(100dvh-var(--tabbar-h))] flex-col lg:h-screen">
      <VideoTop brandId={p.brand_id} fs={fs} title={title} stepsTo={stepsTo} actions={rail ? top : null} />
      <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto px-4 py-6 lg:px-8">
        <div className="mx-auto w-full max-w-[736px] space-y-6">
          {state === "working" && rail && (
            <div className="-mt-3 space-y-2">
              <p className="text-sm text-muted tabular-nums">{[phaseOf(run?.turns ?? [], clips, false), `${creditsLabel(wholeCredits(fs.credits))} spent so far`, "you can leave this page"].join(" · ")}</p>
              <div className="flex items-center gap-2 text-sm text-muted">
                Locked <LockChips projectId={p.id} />
              </div>
            </div>
          )}
          <Thread
            fs={fs}
            items={items.map((t) => (t.id === delivered ? { ...t, text: "Delivered." } : t))}
            tags={words(fs)}
            owner={owner}
            first={fromScript && <ScriptCard title={script.title} slot={slot?.slot ?? 0} seconds={slot?.seconds ?? 0} lines={(slot?.text ?? "").split("\n").filter((l) => l.trim()).length} to={`/b/${p.brand_id}/scripts/${script.id}`} />}
            extra={extra}
          />
          {noted && <p className="text-sm text-muted">Saved. Press Make it again to make this change.</p>}
          {again.isError && <p role="alert" className="text-sm text-danger">{again.error.message}</p>}
          {actions.withdraw.isError && <p role="alert" className="text-sm text-danger">{actions.withdraw.error.message}</p>}
        </div>
      </div>
      <div className="border-t border-border bg-bg px-4 py-3 lg:border-0 lg:px-8 lg:pb-6 lg:pt-0">
        <div className="mx-auto w-full max-w-[736px] space-y-3">
          <ChangeBox fs={fs} status={box} closed={state === "waiting" ? (fromScript ? box : null) : null} disabled={state === "waiting"} saveTo={owner && !running ? p.id : undefined} />
          {!rail && (state === "working" ? <Button variant="secondary" className="w-full" onClick={() => setStopping(true)}>Stop</Button> : state === "waiting" && maker ? <Button variant="secondary" className="w-full" busy={actions.withdraw.isPending} onClick={() => actions.withdraw.mutate()}>Withdraw</Button> : fs.file_id ? <div className="[&_a]:w-full">{download}</div> : null)}
        </div>
      </div>
      {stopping && (
        <Dialog title="Stop the director?" actionLabel="Stop" danger busy={actions.stop.isPending} onCancel={() => setStopping(false)} onConfirm={() => actions.stop.mutate(undefined, { onSettled: () => setStopping(false) })}>
          <p>It makes no more moves. What it already started still finishes, and nothing is undone. You can carry on in the steps.</p>
        </Dialog>
      )}
    </div>
  );
}

/** The cut where it was delivered (B_VideoDelivered): the player, the delivery note, the clips in it and what it cost. */
function Cut({ fs, p, note, seconds, spent, hasClips }: { fs: Freestyle; p: { id: number }; note: string; seconds: number; spent: number; hasClips: boolean }) {
  const clips = useProjectClips(p.id).data ?? [];
  return (
    <div className="flex flex-col gap-5 sm:flex-row">
      <video controls src={fileUrl(fs.file_id!)} aria-label="The cut" className="w-full shrink-0 rounded-md bg-surface-2 object-contain sm:w-[180px]" style={{ aspectRatio: fs.shape.replace(":", " / ") }} />
      <div className="min-w-0 flex-1 space-y-3">
        {note !== "Delivered." && <p className="break-words">{note}</p>}
        {hasClips && <InTheCut clips={clips} projectId={p.id} />}
        <p className="text-sm text-muted tabular-nums">{[seconds > 0 && `${seconds} s`, `spent ${creditsLabel(wholeCredits(spent))} on this run`].filter(Boolean).join(" · ")}</p>
      </div>
    </div>
  );
}

/** The director's card for what waits on the owner: its "up to" price and, before anything is made, the clips to come. */
function Card({ title, price, frames, foot }: { title: string; price: number; frames?: number; foot?: string }) {
  return (
    <div className="space-y-3 rounded-lg border border-border bg-surface px-4 py-3.5">
      <p className="flex items-center justify-between gap-3 text-sm">
        <span className="inline-flex items-center gap-2">
          <span aria-hidden className="size-2 rounded-full bg-warning" />
          {title}
        </span>
        <span className="text-muted tabular-nums">up to {creditsLabel(price)}</span>
      </p>
      {frames && (
        <ol aria-hidden className="grid grid-cols-6 gap-1.5">
          {Array.from({ length: frames }, (_, i) => (
            <li key={i} className="relative h-20 rounded-md bg-gradient-to-br from-surface-3 to-surface">
              {!foot ? null : <span className="absolute bottom-1 left-1 rounded-sm bg-black/50 px-1 text-xs text-muted">{i + 1}</span>}
            </li>
          ))}
        </ol>
      )}
      {foot && <p className="text-sm text-muted">{foot}</p>}
    </div>
  );
}

/** The script a video was made from (E_EditorSent), in place of pasted words. */
function ScriptCard({ title, slot, seconds, lines, to }: { title: string; slot: number; seconds: number; lines: number; to: string }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-surface px-4 py-3">
      <FileText size={16} strokeWidth={1.75} aria-hidden className="shrink-0 text-muted" />
      <div className="min-w-0 flex-1">
        <p className="font-medium">{`From script ${title} · version ${letterOf(slot)}`}</p>
        <p className="text-sm text-muted">{[seconds > 0 && mmss(seconds), `${lines} line${lines === 1 ? "" : "s"}`].filter(Boolean).join(" · ")}</p>
      </div>
      <Link to={to} className="text-sm text-muted hover:text-text">Open script</Link>
    </div>
  );
}
