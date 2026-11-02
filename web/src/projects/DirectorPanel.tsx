import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Square, Wand2 } from "lucide-react";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { useMe } from "../auth/useMe";
import { Badge, Banner, Button, Dialog, buttonClass, creditsText } from "../components";
import { linkText } from "../ui";
import { useToast } from "../toast";
import { ReviewChip } from "./Checks";
import { useProjectClips, useProjectVideo } from "./useProgress";
import { useFrames } from "./StoryboardPane";
import { LockChips } from "./LockChips";
import { DirectorChat } from "./DirectorChat";
import { refreshJobs } from "../jobs/refresh";

type Run = components["schemas"]["DirectorOut"];
type Clip = components["schemas"]["ProjectClipOut"];

// Never on screen: tool names, codes, ids, JSON or model names (the Producer's condition). A line with any left is dropped
// for the plain step it belongs to.
export const NOT_PLAIN = /\b[a-z]+_[a-z_]+\b|[{}[\]<>]|"\w+"\s*:|\b[a-z]\d+\b|\bid\b|\b(claude|gpt|opus|sonnet|haiku)\b/i;

/** The server's words for a move, made plain: "c3" is clip 3 and "take 12" is that clip's take number. */
export function plain(line: string, clips: Clip[]): string {
  const out = line
    .replace(/\btake (\d+) for c(\d+)\b/g, (_all, id: string, n: string) => {
      const t = clips.find((c) => c.clip_id === `c${n}`)?.takes.find((k) => k.id === Number(id));
      return t ? `take ${t.number} for clip ${n}` : `a take for clip ${n}`;
    })
    .replace(/\bc(\d+)\b/g, "clip $1");
  return NOT_PLAIN.test(out) ? "" : out;
}

// What it's doing, from its newest move (ux-audit §8.5's progress line).
const DOING: Record<string, string> = {
  plan: "Making the plan",
  make_looks: "Making the looks",
  storyboard: "Making the storyboard",
  stills: "Drawing the stills",
  clip_prompts: "Writing the clip prompts",
  make_take: "Making clips",
  pick_take: "Making clips",
  final_cut: "Making the cut",
  deliver: "Making the cut",
};

/** The Director tab (ux-audit §8.5, v4): the cut and the delivery note with what it redid and why, Make it and Stop, the
 *  clips in the cut; on the right the locks it builds around and every move it made. Talking to it comes later. */
export function DirectorPanel({ projectId, aspect, name, onOpenClips }: { projectId: number; aspect: string; name: string; onOpenClips: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const owner = useMe().data?.role === "owner";
  const [stopping, setStopping] = useState(false);
  const run = useQuery({
    queryKey: ["director", projectId],
    queryFn: async () => (await api.GET("/projects/{project_id}/director", { params: { path: { project_id: projectId } } })).data ?? null,
    refetchInterval: (q) => (q.state.data?.status === "running" ? 5_000 : false),
  });
  const clips = useProjectClips(projectId);
  const video = useProjectVideo(projectId);
  const r = run.data;
  const status = r?.status ?? "none";
  // When a move finishes, the steps have new work: refresh them, and the waiting banner for a held move.
  const moves = r?.turns.length ?? 0;
  useEffect(() => {
    if (!moves) return;
    void queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "director" && q.queryKey.includes(projectId) });
    void refreshJobs(queryClient);
  }, [moves, status, projectId, queryClient]);
  const after = (data: Run) => {
    queryClient.setQueryData(["director", projectId], data);
    return refreshJobs(queryClient);
  };
  const start = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/projects/{project_id}/director", { params: { path: { project_id: projectId } } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: after,
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  const stop = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/projects/{project_id}/director/stop", { params: { path: { project_id: projectId } } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data) => {
      setStopping(false);
      toast("Stopped. What it already started still finishes.");
      return after(data);
    },
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  if (run.isPending) return null;
  if (run.isError) return <Banner tone="warning" title="Couldn't load the director." action={<Button variant="secondary" onClick={() => void run.refetch()}>Try again</Button>} />;

  const turns = r?.turns ?? [];
  const running = status === "running";
  const held = running && turns.some((t) => t.status === "needs_owner_approval");
  const blocked = r?.start_blocked || null;
  const cut = video.data;
  const list = clips.data ?? [];
  // A note waits: the newest in the thread is a person's message and nothing runs. A message never starts a run by itself
  // (the Producer, 2 Nov): the press does, through the holds as ever.
  const noted = status !== "running" && status !== "none" && (r?.unread ?? 0) > 0; // notes waiting for the press
  // The conversation; a server without it yet still shows this run's moves (each with its reason).
  type Said = { said?: string };
  const thread = r?.thread?.length
    ? r.thread
    : turns.map((t) => ({ id: `t${t.turn}`, kind: "move" as const, at: t.created_at, who: "Director", text: plain((t as Said).said || t.result, list) || (t.status === "needs_owner_approval" ? "Waiting for the owner's OK." : t.tool && DOING[t.tool] ? `${DOING[t.tool]}.` : ""), status: t.status === "needs_owner_approval" ? ("held" as const) : null, why: t.why }));
  const doing = [...turns].reverse().find((t) => t.tool && DOING[t.tool])?.tool;
  const made = list.filter((c) => c.takes.length > 0).length;
  const phase = held ? "Waiting for the owner's OK" : !doing ? "Starting" : DOING[doing] === "Making clips" && list.length ? `Making clips: ${made} of ${list.length}` : DOING[doing];
  const credits = r ? creditsText(r.credits) : null;
  const dollars = owner && r?.spent_usd != null ? `the director's own time $${r.spent_usd.toFixed(2)}` : null; // rule 4: the owner only
  const note = plain([...turns].reverse().find((t) => t.tool === "deliver")?.why ?? "", list);
  const firstTake = turns.findIndex((t) => t.tool === "make_take");
  const redid = turns.filter((t, i) => t.tool === "make_take" && i > firstTake && plain(t.why, list));
  const seconds = Math.round(list.reduce((n, c) => n + c.seconds, 0));
  const line =
    status === "none" ? (blocked ?? "It makes every step from the script, checks each take, and delivers the finished cut. You can stop it any time.")
    : running ? [phase, credits && `up to ${credits} so far`, dollars, "you can leave this page"].filter(Boolean).join(" · ")
    : [status === "ended" && (plain(r!.ended, list) || "It stopped."), cut && seconds > 0 && `${seconds} s`, credits && `up to ${credits} for this run`, dollars].filter(Boolean).join(" · ");
  const badge = running ? <Badge tone={held ? "warning" : "neutral"}>{held ? "Waiting for approval" : "Working…"}</Badge> : status === "delivered" ? <Badge tone="success">Delivered</Badge> : status === "ended" ? <Badge tone="warning">Stopped</Badge> : null;

  const ratio = aspect.replace(":", " / ");
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <section className="min-w-0 space-y-6" aria-label="The director">
        <div className="flex flex-col gap-6 sm:flex-row">
          {cut ? (
            <video controls src={fileUrl(cut.file_id)} className="w-full shrink-0 rounded-md bg-surface-2 object-contain sm:w-56" style={{ aspectRatio: ratio }} aria-label="The finished video" />
          ) : (
            <div className="grid w-full shrink-0 place-items-center rounded-md bg-surface-2 p-4 text-center text-sm text-muted sm:w-56" style={{ aspectRatio: ratio }}>
              {running ? `${phase}…` : "The cut shows here once it's made."}
            </div>
          )}
          <div className="min-w-0 flex-1 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="type-section">{status === "none" && !cut ? "Let the director make it" : status === "delivered" ? "Delivery note" : "The director's cut"}</h2>
              {badge}
            </div>
            {line && <p className="break-words text-sm text-muted tabular-nums">{line}</p>}
            {status !== "none" && !running && blocked && <p className="text-sm text-muted">{blocked}</p>}
            {note && <p className="max-w-prose break-words">{note}</p>}
            {redid.length > 0 && (
              <div className="space-y-2 border-t border-border pt-3">
                <p className="text-sm text-muted">What it redid on its own ({redid.length})</p>
                <ul className="space-y-1 text-sm">
                  {redid.map((t) => (
                    <li key={t.turn} className="grid grid-cols-[4.5rem_minmax(0,1fr)] gap-3">
                      <span className="text-muted">Redid</span>
                      <span className="break-words">{plain(t.why, list)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {status === "delivered" && <ReviewChip projectId={projectId} />}
            <div className="flex flex-wrap items-center gap-2">
              {running ? (
                <Button variant="secondary" icon={Square} onClick={() => setStopping(true)}>
                  Stop
                </Button>
              ) : (
                <Button variant={cut && !noted ? "secondary" : "primary"} icon={Wand2} busy={start.isPending} disabled={!!blocked} onClick={() => start.mutate()}>
                  {status === "none" ? "Make it" : status === "ended" && noted ? "Start again with this note" : "Make it again"}
                </Button>
              )}
              {cut && !running && (
                <a className={buttonClass(noted ? "secondary" : "primary")} href={fileUrl(cut.file_id)} download={`${name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "video"}.mp4`}>
                  <Download aria-hidden className="size-4" />
                  Download MP4
                </a>
              )}
            </div>
          </div>
        </div>
        {list.length > 0 && <InTheCut clips={list} projectId={projectId} onOpenClips={onOpenClips} />}
        {status === "delivered" && <p className="text-sm text-muted">Advice it leaves stays on Review.</p>}
      </section>
      <aside className="min-w-0 space-y-4 lg:border-l lg:border-border lg:pl-6" aria-label="Locks and conversation">
        <div className="space-y-2">
          <p className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="font-medium">Locked</span>
            <span className="text-sm text-muted">It builds around these</span>
          </p>
          <LockChips projectId={projectId} />
        </div>
        <div className="space-y-2 border-t border-border pt-4">
          <h3 className="font-medium">Talk to the director</h3>
          <DirectorChat projectId={projectId} thread={thread} plain={(t) => plain(t, list)} canAsk={status !== "none"} owner={owner} waiting={noted ? (status === "ended" ? "Saved. Press Start again with this note to make it." : "Saved. Press Make it again to make this change.") : running && thread.at(-1)?.kind === "message" ? "The director will read this on its next move." : null} />
        </div>
      </aside>
      {stopping && (
        <Dialog title="Stop the director?" actionLabel="Stop" danger busy={stop.isPending} onCancel={() => setStopping(false)} onConfirm={() => stop.mutate()}>
          <p>It makes no more moves. What it already started still finishes, and nothing is undone. You can carry on in the other tabs.</p>
        </Dialog>
      )}
    </div>
  );
}

/** The clips in the cut, as a strip: each as wide as it is long, its still as the picture. "All clips" opens the Clips tab. */
function InTheCut({ clips, projectId, onOpenClips }: { clips: Clip[]; projectId: number; onOpenClips: () => void }) {
  const frames = useFrames(projectId);
  return (
    <div className="space-y-2">
      <p className="flex items-baseline justify-between gap-2 text-sm">
        <span className="text-muted">In the cut</span>
        <button type="button" className={`${linkText} min-h-11 sm:min-h-9`} onClick={onOpenClips}>
          All clips
        </button>
      </p>
      <ol className="flex h-20 gap-0.5" aria-label="In the cut">
        {clips.map((c) => {
          const still = frames.data?.find((f) => f.clip_id === c.clip_id)?.file_id;
          return (
            <li key={c.id} className="relative min-w-0 overflow-hidden rounded-sm bg-surface-2" style={{ flex: Math.max(1, c.seconds) }} aria-label={`Clip ${c.clip_id.replace(/^c/, "")}, ${c.seconds} s`}>
              {still != null && <img src={fileUrl(still)} alt="" className="h-full w-full object-cover" />}
              <span aria-hidden className="absolute bottom-1 left-1 rounded-sm bg-surface/80 px-1 text-xs tabular-nums">{c.clip_id.replace(/^c/, "")}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
