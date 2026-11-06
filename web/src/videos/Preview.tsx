import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, Lock, Scissors } from "lucide-react";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { Banner, Button, Skeleton, ViewOnly, buttonClass, useViewOnly } from "../components";
import { mmss } from "../freestyle/FromScript";
import { BreakdownPane } from "../projects/BreakdownPane";
import { PlanStep } from "../projects/PlanStep";
import { ShapeRow } from "../projects/ShapeRow";
import { VideoSettings, useVideoSettings } from "../projects/VideoSettings";
import { Scorecard } from "../projects/Scorecard";
import { ScriptText, useLatestScript } from "../projects/ScriptTab";
import { useCut, useMakeCut, useProgress, useProjectClips, useProjectVideo } from "../projects/useProgress";
import { videoHold, videoLock, type VideoProgress } from "../projects/videoSteps";
import { FinalSong, SongStrip, useSongChanged } from "../scripts/VideoSong";
import { CastPane } from "../cast/CastPane";
import { ClipsPane } from "../clips/ClipsPane";
import { notInShots, useAssets } from "../cast/useAssets";
import { Empty, SOON } from "./Empty";
import { PaneBoundary } from "./PaneBoundary";
import { mp4, type Head } from "./VideoHead";
import { Filmstrip, SceneRow, useSeen, type Progress } from "./RunCard";
import { useAsks } from "./AskCard";
import { serverTime } from "../time";
import { useRail } from "../useMedia";
import { CutEditor, fixLabel } from "../cut/CutEditor";
import { useCutEdits } from "../cut/useCutEdits";

type Project = components["schemas"]["ProjectOut"];

/** The preview panel's tabs (S3): the cut, the clips, the cast, the plan and the script. */
export const TABS = [
  { id: "cut", label: "Cut" },
  { id: "clips", label: "Clips" },
  { id: "cast", label: "Cast" },
  { id: "plan", label: "Plan" },
  { id: "script", label: "Script" },
] as const;
export type TabId = (typeof TABS)[number]["id"];

// Old addresses (?step=, from Needs you, the lists and the director's links) open their tab.
const OLD: Record<string, TabId> = { downloads: "cut", final: "cut", storyboard: "clips", clips: "clips", assets: "cast", cast: "cast", breakdown: "plan", plan: "plan", shots: "plan" };
export const tabFrom = (params: URLSearchParams): TabId | null => {
  const asked = params.get("tab") ?? "";
  return TABS.find((t) => t.id === asked)?.id ?? OLD[params.get("step") ?? ""] ?? null;
};

/** What a tab's pane gets. `go` opens another tab (a hold's "Open Cast"); `lines`/`line` tie the plan to the script. */
export type PaneProps = { p: Project; head: Head | undefined; run: Progress | null; lookOnly: string | null; progress: VideoProgress; go: (tab: TabId) => void; toChat?: () => void; lines: number[]; line: number | null; showLines: (lines: number[]) => void; pickLine: (n: number) => void; onEditor?: (on: boolean) => void };


/** The Cut tab (S3-09, S7): Watch (the delivered cut, its downloads and what changed) or Edit (the cut editor, screen 10).
 *  Before the first cut, and while it's made or if it failed, the editor shows where it is (S7-04, S7-06). */
function CutPane(props: PaneProps) {
  const { p, progress, onEditor } = props;
  const [mode, setMode] = useState<"watch" | "edit">("watch");
  const viewOnly = useViewOnly(); // someone else's video: Watch only (its editor would offer nothing)
  const cut = useProjectVideo(p.id);
  const live = useCut(p.id).data;
  const first = !cut.data || !!(live?.making && !live.number); // the first cut: the editor shows where it is
  const editing = !cut.isPending && (first ? !!cut.data || progress.clips.total > 0 : !viewOnly && mode === "edit");
  useEffect(() => onEditor?.(editing), [editing, onEditor]); // the chat narrows to the boards' 400px (S7)
  useEffect(() => () => onEditor?.(false), [onEditor]);
  if (cut.isPending) return <Skeleton className="h-[533px] w-[300px] max-w-full rounded-[10px]" />;
  if (!cut.data && progress.clips.total === 0) return <Empty title="The cut plays here when it’s ready">{SOON}</Empty>;
  // Every clip approved and no cut yet: the editor puts it together the first time this opens, for free.
  const editor = <CutEditor projectId={p.id} aspect={p.aspect_ratio} projectName={props.head?.title ?? p.name} auto={!viewOnly} />;
  if (first) return editor;
  if (viewOnly) return <CutWatch {...props} />;
  return (
    <div className="space-y-4">
      <div role="radiogroup" aria-label="Cut view" className="ml-auto flex w-fit gap-0.5 rounded-md bg-surface-2 p-0.5">
        {(["watch", "edit"] as const).map((m) => (
          <button key={m} type="button" role="radio" aria-checked={mode === m} onClick={() => setMode(m)} className={`flex min-h-control items-center gap-1 rounded-sm px-3 text-sm lg:min-h-control-dense ${mode === m ? "bg-surface text-text shadow-raised" : "text-muted"}`}>
            {m === "edit" && <Scissors size={14} strokeWidth={1.75} aria-hidden />}
            {m === "watch" ? "Watch" : "Edit"}
          </button>
        ))}
      </div>
      {mode === "edit" ? editor : <CutWatch {...props} />}
    </div>
  );
}

type Cut = components["schemas"]["CutOut"];
const and = (xs: string[]) => (xs.length < 2 ? xs.join("") : `${xs.slice(0, -1).join(", ")} and ${xs.at(-1)}`);

/** Cut 1 | Cut 2 · making (S3-12): the cuts made so far, each watchable, and the next while it's made. The cut before stays
 *  watchable until the new one is ready, and what the new one replaces shows as going out of date. */
/** The next cut while it's made; not the director making its own cut again before it delivers (same number). */
const nextCut = (cut: Cut) => (cut.making && !cut.versions.some((v) => v.number === cut.making?.number) ? cut.making : null);

function CutSwitch({ cut, picked, onPick }: { cut: Cut; picked: number | null; onPick: (n: number) => void }) {
  const making = nextCut(cut);
  if (cut.versions.length < 2 && !making) return null;
  const tab = "flex min-h-control items-center rounded-sm px-3 text-sm lg:min-h-control-dense";
  return (
    <div className="flex flex-col gap-3">
      <div role="radiogroup" aria-label="Which cut" className="flex w-fit flex-wrap gap-0.5 rounded-md bg-surface-2 p-0.5">
        {cut.versions.map((v) => (
          <button key={v.number} type="button" role="radio" aria-checked={v.number === picked} onClick={() => onPick(v.number)} className={`${tab} ${v.number === picked ? "bg-surface text-text shadow-raised" : "text-muted hover:text-text"}`}>
            {`Cut ${v.number}`}
          </button>
        ))}
        {making && (
          <span role="radio" aria-checked={false} aria-disabled className={`${tab} text-muted`}>
            {`Cut ${making.number} · making`}
          </span>
        )}
      </div>
      {making && cut.number != null && <p className="text-sm text-muted">{`Cut ${cut.number} stays watchable until Cut ${making.number} is ready.`}</p>}
      {making && cut.going.length > 0 && (
        <div className="flex flex-col gap-2 border-t border-border pt-3">
          <h3 className="text-xs font-semibold text-muted">Going out of date</h3>
          <ul className="flex flex-wrap gap-2">
            {cut.going.map((g) => (
              <li key={g.piece} className="relative h-[85px] w-12 overflow-hidden rounded-md bg-surface-2">
                {g.file_id != null && <video src={`${fileUrl(g.file_id)}#t=0.1`} muted preload="metadata" aria-hidden className="size-full object-cover" />}
                <span className="absolute inset-x-0 bottom-0 whitespace-nowrap bg-black/60 text-center text-[9px] leading-4 text-white">out of date</span>
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted">{and(cut.going.map((g) => g.label))}</p>
        </div>
      )}
    </div>
  );
}

/** Watch (S3-09): the cut, its downloads and what changed after watching. */
function CutWatch({ p, head, progress, run }: PaneProps) {
  const { media, progress: now } = useProgress(p.id);
  const cut = useProjectVideo(p.id);
  const video = cut.data;
  const phone = !useRail();
  const seen = useSeen(p.id);
  const player = useRef<HTMLVideoElement>(null);
  const changed = run?.changed ?? [];
  // A frame (or a changed clip) plays the cut from where that clip starts, and counts as watched (S3-09).
  const jump = (clipId: string, takeId: number | null) => {
    const order = (run?.scenes ?? []).flatMap((s) => s.clips);
    const index = order.findIndex((c) => c.clip_id === clipId);
    const at = order.slice(0, index).reduce((n, c) => n + c.seconds, 0); // the clips' planned lengths: close, not to the frame
    if (player.current && index >= 0) {
      player.current.currentTime = at;
      void player.current.play?.()?.catch?.(() => {});
    }
    if (takeId != null) seen.mutate([takeId]);
  };
  const clips = useProjectClips(p.id).data ?? [];
  const settings = useVideoSettings(p.id);
  const songChanged = useSongChanged(p.id, video?.song_take_id);
  const remake = useMakeCut(p.id); // made on the server; the cut before keeps playing
  const live = useCut(p.id).data;
  const fix = useCutEdits(p.id);
  const [picked, setPicked] = useState<number | null>(null); // an earlier cut to watch (S3-12); none: the one that plays
  if (!video) return null; // CutPane shows the editor until there's a cut
  const older = live?.versions.find((v) => v.number === picked && v.number !== live.number) ?? null;
  const file = older?.file_id ?? live?.file_id ?? video.file_id; // the switch's pick, else the cut that plays
  const base = mp4(head?.title ?? p.name);
  const name = older ? base.replace(/\.mp4$/, `-cut-${older.number}.mp4`) : base;
  const pick = (n: number) => setPicked(n === live?.number ? null : n); // the cut that plays isn't pinned: a new one replaces it
  const owner = head?.spent.usd != null;
  const s = settings.data;
  const model = s && (s.video_models.find((m) => m.id === s.video_model) ?? s.video_models.find((m) => m.default))?.name;
  // A take made from an older Cast & places look stays approved but is out of date too (N6), as the lists say. Making the
  // cut again only helps once each clip shows what it should.
  const olderLook = clips.filter((c) => c.take_stale).length;
  const left = clips.filter((c) => c.picked_take_id == null).length; // V6: no per-clip Approve, only a take for each clip
  const held = left > 0 ? `Make every clip’s take first (${left} left)` : olderLook > 0 ? `Make another take on Clips, or keep the older look (${olderLook} left)` : null;
  const rows: [string, string][] = [
    ["Style", head?.style ?? p.look],
    ...(head?.format ? [["Format", head.format] as [string, string]] : []),
    ...(model ? [["Clips made with", model] as [string, string]] : []),
    [owner ? "Spent" : "Credits used", owner ? `$${head!.spent.usd!.toFixed(2)}` : `${Math.round(head?.spent.credits ?? p.credits_used)} credits`],
  ];
  return (
    <div className="space-y-5">
      {remake.isError && <Banner title="The cut couldn’t be made again.">Nothing was charged. {remake.error.message}</Banner>}
      {live?.failed && ( // a failed cut says why with its way forward; the one before keeps playing (rule 22)
        <Banner
          title={live.failed.why}
          action={live.can_edit && live.failed.fixes.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {live.failed.fixes.map((f, i) => (
                <Button key={f} variant={i === 0 ? "primary" : "secondary"} busy={fix.fix.isPending && fix.fix.variables === f} disabled={fix.busy} onClick={() => fix.fix.mutate(f)}>
                  {fixLabel(f)}
                </Button>
              ))}
            </div>
          ) : undefined}
        />
      )}
      {now.video.outOfDate && !live?.making && ( // while the next cut is made it says so beside the switch (S3-12)
        <Banner tone="warning" title="Out of date." action={live?.failed ? undefined /* the failed cut's own fixes come first */ : <Button variant="secondary" busy={remake.isPending} disabled={!!held} reason={held} onClick={() => remake.mutate()}>Make it again</Button>}>
          {left === 0 && !video.out_of_date && olderLook > 0 ? `${olderLook === 1 ? "A clip's take shows" : `${olderLook} clips' takes show`} an older look from Cast & places.` : songChanged && left === 0 ? `The ${songChanged} changed since this video was made.` : "Clips changed since this video was made."} This MP4 still downloads.{live?.failed ? "" : " Making it again is free."}
        </Banner>
      )}
      <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
        <video ref={player} controls src={fileUrl(file)} aria-label="The cut" className="mx-auto w-full max-w-[240px] shrink-0 rounded-[10px] bg-black shadow-raised sm:mx-0 sm:w-[300px] sm:max-w-[300px]" style={{ aspectRatio: p.aspect_ratio.replace(":", " / ") }} />
        <div className="flex min-w-0 flex-1 flex-col gap-4">
          {live && <CutSwitch cut={live} picked={older?.number ?? live.number} onPick={pick} />}
          <div className="flex flex-col gap-1 max-sm:hidden">
            {!(live && (live.versions.length > 1 || nextCut(live))) && <h2 className="text-lg font-semibold">Final cut</h2>}
            <p className="text-sm tabular-nums text-muted">{older ? `Cut ${older.number} · made ${serverTime(older.made_at).toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23" })}` : [media.seconds > 0 && mmss(media.seconds), p.aspect_ratio, `${progress.clips.total} clip${progress.clips.total === 1 ? "" : "s"}`].filter(Boolean).join(" · ")}</p>
          </div>
          <div className="flex flex-col gap-2">
            <a className={`${buttonClass("primary")} justify-start`} href={fileUrl(file)} download={name}>
              <Download size={16} strokeWidth={1.75} aria-hidden />
              Download MP4
            </a>
            <a className={`${buttonClass("secondary")} justify-start lg:min-h-control`} href={`/api/projects/${p.id}/clips.zip`} download={base.replace(/\.mp4$/, "-clips.zip")}>
              Download every clip (.zip)
            </a>
          </div>
          {changed.length > 0 && !phone && (
            <>
              <div className="h-px bg-border" />
              <div className="flex flex-col gap-2">
                <h3 className="text-xs font-semibold text-muted">Changed after watching</h3>
                <ul className="flex flex-wrap gap-2">
                  {changed.map((c) => (
                    <li key={c.clip_id}>
                      <button type="button" aria-label={`Clip ${c.number}${c.watched ? "" : ", not watched yet"}`} onClick={() => jump(c.clip_id, c.take_id)}>
                        {c.frame_file_id != null ? <img src={fileUrl(c.frame_file_id)} alt="" className={`h-[71px] w-10 rounded-md object-cover ${c.watched ? "" : "outline outline-[1.5px] outline-offset-1 outline-accent"}`} /> : <span className="block h-[71px] w-10 rounded-md bg-surface-2" />}
                      </button>
                    </li>
                  ))}
                </ul>
                <p className="text-xs text-muted">Marked until you’ve watched them.</p>
              </div>
            </>
          )}
          <div className="h-px bg-border" />
          <dl className="flex flex-col gap-2 text-sm">
            {rows.map(([k, v]) => (
              <div key={k} className="flex justify-between gap-3">
                <dt className="text-muted">{k}</dt>
                <dd className="font-medium tabular-nums">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
      {run && run.scenes.length > 0 &&
        (phone ? (
          <div className="flex flex-col gap-2">
            <SceneRow scenes={run.scenes} />
            {changed.length > 0 && <p className="text-xs text-muted">{`${changed.length} clip${changed.length === 1 ? "" : "s"} changed after watching ${changed.length === 1 ? "is" : "are"} outlined`}</p>}
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            <p className="flex justify-between text-xs">
              <span className="font-semibold text-muted">The video, scene by scene</span>
              <span className="text-muted">Click a frame to jump there</span>
            </p>
            <Filmstrip scenes={run.scenes} big onPick={(c) => jump(c.clip_id, c.take_id)} />
          </div>
        ))}
      {/* The song or narration under the cut, and the owner's score: no board draws them, and nothing else carries them. */}
      <div className="space-y-3 border-t border-border pt-4 empty:hidden">
        <FinalSong projectId={p.id} madeWith={video.song_take_id} narration={video.narration} />
        <Scorecard projectId={p.id} />
      </div>
    </div>
  );
}

/** The clips (today's Clips step until screen 8): the stills and the takes, each clip's line, and their holds. */
function ClipsTab(props: PaneProps) {
  const { progress, go, toChat } = props;
  // Nothing drawn yet and the stills can't start: what fills in here, why it waits and the one press that gets it going.
  const waits = progress.frames.total === 0 && progress.clips.total === 0 ? videoLock("storyboard", progress) : null;
  if (waits)
    return (
      <Empty title="The clips fill in here" action={<Button variant="secondary" onClick={() => go(/cast/i.test(waits) ? "cast" : "plan")}>Open {/cast/i.test(waits) ? "Cast" : "Plan"}</Button>}>
        {waits}
      </Empty>
    );
  const held = videoHold("clips", progress) ?? videoHold("storyboard", progress);
  return (
    <>
      {held && (
        <Banner tone="warning" title={held.at === "cast" ? "Waiting on the cast" : "Out of date"} action={held.at !== "storyboard" && <Button variant="secondary" onClick={() => go(held.at === "cast" ? "cast" : "plan")}>Open {held.at === "cast" ? "Cast" : "Plan"}</Button>}>
          {held.why}
        </Banner>
      )}
      {(progress.frames.total === 0 || progress.clips.total === 0) && (
        // Rule 22: with the step presses gone, the way on is the director (screen 4). On a phone the chat is a press away.
        <p className="text-sm text-muted">
          The director makes the stills and the clips.{" "}
          {toChat ? (
            <button type="button" onClick={toChat} className="font-medium text-accent-text hover:underline max-lg:min-h-control">
              Start it or tell it what to do in the chat.
            </button>
          ) : (
            "Start it or tell it what to do in the chat."
          )}
        </p>
      )}
      <ClipsPane {...props} />
    </>
  );
}

/** The plan: the treatment and its scenes, then the shots (today's Plan step). Lines tie to the Script tab. */
function PlanTab({ p, head, progress, line, showLines }: PaneProps) {
  const { script } = useProgress(p.id);
  const settings = useVideoSettings(p.id);
  const clips = useProjectClips(p.id).data ?? [];
  // The video's own choices (shape, models, style), on every video; the director keeps what a person changed (Reed: "the
  // option to change models for each ad"). Its drawn place is coming from the design session.
  const choices = (
    <>
      <VideoSettings project={p} finished={progress.video.made} song={false} broll={p.kind === "narrated"} notMade={clips.filter((c) => !c.picked_take_id).length} />
      <ShapeRow shape={!settings.data} projectId={p.id} aspect={p.aspect_ratio} platform={p.platform} />
    </>
  );
  // While the director starts, before any plan: what fills in here (S3-01). With no run, today's Make the plan.
  if (head?.status.kind === "working" && !progress.shots.made && ((p as { plan_status?: string | null }).plan_status ?? "none") === "none")
    return (
      <>
        {choices}
        <Empty title="The plan shows here first">{SOON}</Empty>
      </>
    );
  return (
    <>
      <div className="space-y-4">{choices}</div>
      <PlanStep
        project={p as Project & { plan_status?: "none" | "ready" | "approved" | null }}
        shots={
          <div className="space-y-4">
            {p.song && <SongStrip project={p} hasShots={progress.shots.made} hasClips={progress.clips.total > 0} />}
            <BreakdownPane projectId={p.id} brandId={p.brand_id} scriptVersion={script.data?.version ?? 0} plannedSeconds={p.planned_seconds ?? p.breakdown_seconds ?? 0} used={p.credits_used} budget={p.budget_credits} line={line} onShowLines={showLines} onDirty={() => {}} />
          </div>
        }
      />
    </>
  );
}

/** The script the video is made from, read only. Lines the plan pointed at are marked; a press on one shows its shot. */
function ScriptTabPane({ p, lines, pickLine }: PaneProps) {
  const script = useLatestScript(p.id);
  // The words someone asked to change, marked where they're said (S3-14): the newest such ask's.
  const asked = (useAsks(p.id, false).data ?? []).filter((a) => a.kind === "instead").at(-1)?.subject;
  // The notes saved on the script (the old page's script panel showed them): kept here, read only, by line.
  const notes = useQuery({ queryKey: ["script-notes", p.id, script.data?.version], enabled: !!script.data, retry: false, queryFn: async () => (await api.GET("/projects/{project_id}/script/notes", { params: { path: { project_id: p.id } } })).data ?? [] });
  if (script.isPending) return <Skeleton className="h-64" />;
  if (!script.data) return <Empty title="No script yet">The words the director makes the video from show here.</Empty>;
  return (
    <div className="space-y-3">
      <div className="space-y-3 rounded-lg border border-border bg-surface p-4">
        {p.script_draft_id != null && (
          <p className="flex items-center gap-2 text-[13px] text-muted">
            <Lock size={14} strokeWidth={1.75} aria-hidden className="shrink-0" />
            Published script · the words are set
          </p>
        )}
        {lines.length > 0 && <p className="text-sm text-muted">Lines for this step are highlighted.</p>}
        <ScriptText text={script.data.text} highlight={lines} marks={asked ? [asked] : []} onLineClick={pickLine} />
      </div>
      {notes.isError && <p className="text-sm text-muted">Couldn’t load the notes saved on the script. They’re kept; open this tab again to see them.</p>}
      {(notes.data ?? []).length > 0 && (
        <section aria-label="Notes on the script" className="space-y-2 rounded-lg border border-border bg-surface p-4">
          <h3 className="text-sm font-semibold">Notes on the script</h3>
          <ul className="space-y-1.5 text-sm">
            {notes.data!.map((n) => (
              <li key={`${n.line}-${n.text}`}>
                <button type="button" onClick={() => pickLine(n.line)} className="text-accent-text hover:underline">
                  Line {n.line}
                </button>{" "}
                {n.text}
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted">To change the direction, tell the director in the chat.</p>
        </section>
      )}
    </div>
  );
}

/** Each tab's pane. One slot a tab: the cut editor (screen 10), Clips (screen 8) and Cast (screen 9) replace theirs here. */
export const PANES: Record<TabId, (props: PaneProps) => ReactNode> = { cut: CutPane, clips: ClipsTab, cast: CastPane, plan: PlanTab, script: ScriptTabPane };

/** The video's progress as the panes read it, with the cast's count. */
export function usePanelFacts(p: Project | null) {
  const id = p?.id ?? 0;
  const { progress, loading } = useProgress(id);
  const assets = useAssets(id);
  // The Cast tab's roles and places (S-gaps-07 A); a role no shot uses is not counted.
  const cast = (assets.data ?? []).filter((a) => !notInShots(a) && (a.kind === "character" || a.kind === "place"));
  const all: VideoProgress = { ...progress, assets: { total: cast.length, ready: cast.filter((a) => a.ready).length, seen: true } };
  return { progress: all, loading: loading || assets.isPending, cast, made: !!progress.video.made };
}

/** Which tab a video opens on: its cut once made, its clips while they're made, else its plan (S3-01, S3-03, S3-09). */
export const firstTab = (progress: VideoProgress): TabId => (progress.video.made ? "cut" : progress.frames.total > 0 || progress.clips.total > 0 ? "clips" : "plan");

/** The preview panel (S3): its tabs with counts, then the open tab's pane. On a phone the tabs are a segmented row
 *  (P-09, S-gaps-03). */
export function Preview({ p, head, run, tab, onTab, toChat, lookOnly, phone, facts, onEditor }: { p: Project | null; head: Head | undefined; run: Progress | null; tab: TabId; onTab: (t: TabId) => void; toChat?: () => void; lookOnly: string | null; phone: boolean; facts: ReturnType<typeof usePanelFacts>; onEditor?: (on: boolean) => void }) {
  const [lines, setLines] = useState<number[]>([]);
  const [line, setLine] = useState<number | null>(null);
  const count: Partial<Record<TabId, number>> = { clips: facts.progress.clips.total || facts.progress.frames.total, cast: facts.cast.length };
  const Pane = PANES[tab];
  const tabs = phone ? (
    <div className="border-b border-border px-2 py-1.5">
      <div role="tablist" aria-label="Preview" className="flex gap-0.5 overflow-x-auto rounded-md bg-surface-2 p-0.5">
        {TABS.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={tab === t.id} onClick={() => onTab(t.id)} className={`flex h-control shrink-0 items-center rounded-[5px] px-3 text-sm font-medium ${tab === t.id ? "bg-surface text-text shadow-[var(--shadow-soft,0_1px_2px_rgb(28_27_25/0.06))]" : "text-muted"}`}>
            {t.label}
          </button>
        ))}
      </div>
    </div>
  ) : (
    <div role="tablist" aria-label="Preview" className="flex h-10 shrink-0 items-stretch gap-0.5 border-b border-border bg-surface px-4">
      {TABS.map((t) => (
        <button key={t.id} type="button" role="tab" aria-selected={tab === t.id} onClick={() => onTab(t.id)} className={`-mb-px inline-flex items-center gap-1.5 border-b-2 px-2.5 text-sm font-medium ${tab === t.id ? "border-text text-text" : "border-transparent text-muted hover:text-text"}`}>
          {t.label}
          {!!count[t.id] && " "}
          {!!count[t.id] && <span className="inline-flex h-4 items-center rounded-lg bg-surface-2 px-1.5 text-[11px] text-muted tabular-nums">{count[t.id]}</span>}
        </button>
      ))}
    </div>
  );
  return (
    <section aria-label="Preview" className="flex min-h-0 min-w-0 flex-1 flex-col bg-bg">
      {tabs}
      <div role="tabpanel" aria-label={TABS.find((t) => t.id === tab)!.label} className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-5">
        {!p ? (
          <Empty title="Opens once the owner approves">The plan, the cast, the clips and the cut show here once the owner says yes.</Empty>
        ) : facts.loading ? (
          <PanelSkeleton />
        ) : (
          <ViewOnly on={!!lookOnly}>
            <PaneBoundary tab={tab}>
              <Pane
              p={p}
              head={head}
              run={run}
              lookOnly={lookOnly}
              progress={facts.progress}
              go={onTab}
              toChat={toChat}
              lines={lines}
              line={line}
              showLines={(ls) => (setLines(ls), setLine(null), onTab("script"))}
              pickLine={(n) => (setLine(n), setLines([n]), onTab("plan"))}
              onEditor={onEditor}
            />
            </PaneBoundary>
          </ViewOnly>
        )}
      </div>
    </section>
  );
}

/** The panel while the video loads (S3-15): the player's place and the side column. */
export function PanelSkeleton() {
  return (
    <div className="flex gap-5" role="status" aria-label="Loading">
      <Skeleton className="h-[533px] w-[300px] shrink-0 rounded-[10px]" />
      <div className="flex flex-col gap-3">
        <Skeleton className="h-[18px] w-40" />
        <Skeleton className="h-3 w-[200px]" />
        <Skeleton className="h-9 w-[220px]" />
        <Skeleton className="h-9 w-[220px]" />
      </div>
    </div>
  );
}
