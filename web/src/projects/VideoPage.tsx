import { useState } from "react";
import { ChevronLeft, FileText } from "lucide-react";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Banner, Button, Skeleton, ViewOnly, type Step } from "../components";
import { useRail } from "../useMedia";
import { useFreshProject } from "./useFreshProject";
import { AssetsPane, useAssets } from "./AssetsPane";
import { notInShots } from "./AssetCard";
import { BreakdownPane } from "./BreakdownPane";
import { PlanStep } from "./PlanStep";
import { CheckSummary } from "./Checks";
import { useBriefChoices } from "./BriefPickers";
import { ClipsStep } from "./ClipsStep";
import { DownloadsPane } from "./DownloadsPane";

import { WaitingBadge } from "./Meter";
import { CostBarProvider, type CostAction } from "./CostBar";
import { VideoMenu, useMayManageVideo, useVideoActions } from "./ReleaseVideo";
import { ScriptPanel } from "./ScriptPanel";
import { ShapeRow } from "./ShapeRow";
import { VideoSettings, useVideoSettings } from "./VideoSettings";
import { useUpdateAfter } from "./UpdateAfter";
import { SongStrip } from "../scripts/VideoSong";
import { isDone } from "./steps";
import { useProgress } from "./useProgress";
import { VIDEO_STEPS, isClips, videoBlocker, videoHold, videoLock, videoNext, videoStepFromParams, videoTabStates, type VideoProgress } from "./videoSteps";
import { VideoTabs } from "./VideoTabs";
import { HeldRequests, WaitingCount } from "../approvals/HeldRequests";
import { budgetPct, budgetUsed, directorTime } from "./budget";
import { DirectorPanel } from "./DirectorPanel";
import { useFreestyle } from "../freestyle/useFreestyle";
import { VideoTop } from "../videos/VideoTop";
import { useVideoProject } from "../videos/VideoTop";

/** A video made from a library version: Director · Plan · Cast · Clips · Final cut, one row of tabs (v4). */
export function VideoPage() {
  const { brandId = "", projectId } = useParams();
  const id = Number(projectId);
  const [params, setParams] = useSearchParams();
  const step = videoStepFromParams(params);
  const rail = useRail();
  const [panel, setPanel] = useState(false);
  const [highlight, setHighlight] = useState<number[]>([]);
  const [line, setLine] = useState<number | null>(null);
  const [dirty, setDirty] = useState(false); // unsaved edits in Plan's shots
  const navigate = useNavigate();
  const mayManage = useMayManageVideo();
  const video = useVideoActions((kind) => navigate(`/b/${brandId}/${kind === "release" ? "scripts" : "videos"}`)); // a released version is ready to make again in Scripts; an archived video is under Videos
  useFreshProject(id);
  const project = useVideoProject(id);
  const { progress, loading, script, media } = useProgress(id);
  const assets = useAssets(id);
  const p = project.data;
  const fs = useFreestyle(p?.freestyle_id ?? null).data; // a director-made video: its steps sit under its chat's top bar
  const flavours = useBriefChoices(p?.brand_id ?? 0, p?.product_variants ?? {});
  const settings = useVideoSettings(id); // the row has Shape once the server offers settings
  // The storyboard is out of date and the shots are current: one press brings it and the clip prompts up to date (audit M14 part 2).
  // An editor's over-budget press is held for the owner (#1068), never stopped here; only what blocks for everyone is.
  const stopFor = () => null;
  const updating = (step === "storyboard" || step === "clips") && !progress.shots.stale && (progress.frames.stale || progress.clips.stale);
  const update = useUpdateAfter(id, updating, stopFor, (to) => setParams({ step: to }));
  // When this step was opened, the Assets list as it was then: a read since then is this step's own.
  const [opened, setOpened] = useState(() => ({ step, at: assets.dataUpdatedAt }));
  if (opened.step !== step) setOpened({ step, at: assets.dataUpdatedAt });
  // Assets counts as looked at once opened here, or once the storyboard is started (it comes after).
  const [assetsSeen, setAssetsSeen] = useState(step === "cast");
  if (step === "cast" && !assetsSeen) setAssetsSeen(true);

  if (project.isPending || loading || assets.isPending)
    return (
      <div className="mx-auto max-w-content space-y-4 p-4 sm:p-8" role="status" aria-label="Loading">
        <Skeleton className="h-10 w-1/2" />
        <Skeleton className="h-12" />
        <Skeleton className="h-64" />
      </div>
    );
  if (!p) return <p className="p-6">That video doesn't exist.</p>;
  const list = (assets.data ?? []).filter((a) => !notInShots(a)); // a role no shot uses is not counted
  // Opening Assets reads its list again; until that read lands (and the brand's products are in) its counts and the flavour
  // check wait. Later reads (after an Approve, say) keep showing the counts.
  // A read that failed since then ends the wait too: the old counts show rather than "Loading assets…" for ever.
  const assetsLoading = (opened.at > 0 && assets.dataUpdatedAt <= opened.at && assets.errorUpdatedAt <= opened.at) || flavours.loading;
  const all: VideoProgress = { ...progress, assets: { total: list.length, ready: list.filter((a) => a.ready).length, seen: assetsSeen || progress.frames.total > 0 } };
  // A link to a step that is locked lands on the step that blocks it (Storyboard when its frames are out of date, say).
  // Old addresses move to their new place: Breakdown is Plan on its Shots view, Assets is Cast (flows 1b).
  const asked = params.get("step");
  if (asked === "breakdown") return <Navigate to="?step=plan&view=shots" replace />;
  if (asked === "assets") return <Navigate to="?step=cast" replace />;
  if (asked === "make") return <Navigate to={`?step=${videoTabStates(step, all)[2].id}`} replace />;
  if (videoLock(step, all) !== null) return <Navigate to={`?step=${videoBlocker(step, all)}`} replace />;

  const pick = (to: string) => {
    setParams({ step: to }); // no step is the Director view
    setPanel(false);
  };
  const showLines = (lines: number[]) => {
    setHighlight(lines);
    setLine(null);
    setPanel(true);
  };
  const label = isClips(step) ? "Clips" : VIDEO_STEPS.find((s) => s.id === step)?.label;
  const clipsLock = videoLock("clips", all);
  // Made work whose earlier step changed stays viewable; its paid presses wait, and the banner says where to go (audit M14).
  const held = videoHold(step, all);
  // While a look in the cast isn't ready, the update would be refused at its storyboard step: it waits with the same reason (Flow-QA on #936).
  const updateAction = update.action && held?.at === "cast" ? { ...update.action, reason: held.why } : update.action;
  const hold = held?.why ?? null;
  const fixAt = held ? VIDEO_STEPS.find((s) => s.id === held.at) : undefined;
  const next = videoNext(step === "storyboard" ? "clips" : step); // the stills and the takes are one tab: next is Final cut
  const reason = !next ? null : dirty && step === "plan" ? "Save your changes first." : step === "cast" && flavours.unchosen ? `Pick a ${flavours.unchosen} flavour first` : videoLock(next.id, all);
  // The cost bar's press when the step has none of its own. On a phone, unsaved shot edits take the bar's place.
  const nextAction: CostAction | null = next && !(step === "plan" && dirty && !rail) ? { label: `Next: ${next.id === "storyboard" ? "Clips" : next.label}`, reason, onPress: () => pick(next.id) } : null;
  // On the Director tab a made cut is the end, not Plan: the bar points at Final cut, quietly, beside Download MP4 (QA-11 on #1156).
  const cutAction: CostAction | null = progress.video.made ? { label: "Open Final cut", secondary: true, onPress: () => pick("downloads") } : nextAction;
  // Release while it is being made; Archive once it is done. An archived video is read-only until it is restored.
  const finished = isDone("final", progress);
  const target = { id, name: p.name, creditsUsed: p.credits_used, released: p.released };
  const menu = mayManage(p) && !p.archived_at && <VideoMenu title={p.name} onRelease={finished ? undefined : () => video.release(target)} onArchive={finished ? () => video.archive(target) : undefined} />;
  // Only its maker or the owner may change a video (the server refuses the rest): anyone else can look, with every press greyed out.
  const maker = p.created_by_name || "someone else";
  const lookOnly = !mayManage(p) && !p.archived_at ? `Only ${maker} or the owner can change this video.` : null;
  // The Director is the first tab (ux-audit §8.5, v4); any ?step= address opens a step. Only whoever may change the video directs it.
  const mayDirect = p.script_draft_id != null && !p.archived_at && !lookOnly; // made from a (published) script version
  const directing = mayDirect && !params.get("step");
  // Until Assets' own read lands, the step picker, the heading line and Next wait under one skeleton: no counts from an older read.
  const waiting = step === "cast" && assetsLoading;
  const count = (n: number, noun: string, ok: number) => `${n} ${noun}${n === 1 ? "" : "s"} · ${ok} approved`;
  // One row of tabs: the Director (when it can direct), then the steps. A locked step says why and doesn't open.
  const steps: Step[] = [
    ...(mayDirect ? [{ id: "director", label: "Director", state: directing ? "current" : "open" } as Step] : []),
    ...videoTabStates(step, all).map((s) => (directing && s.state === "current" ? { ...s, state: "open" as const } : s)),
  ];
  const approvedOf = all.clips.total > 0 ? `${all.clips.approved} of ${all.clips.total} approved` : all.frames.total > 0 ? `${all.frames.approved} of ${all.frames.total} stills approved` : null;
  const meta =
    step === "cast" ? (waiting ? null : `${all.assets.total} in the cast · ${all.assets.ready} approved`) : step === "storyboard" && all.frames.total > 0 ? count(all.frames.total, "still", all.frames.approved) : step === "clips" && all.clips.total > 0 ? count(all.clips.total, "clip", all.clips.approved) : null;

  return (
    // One cost bar at the bottom: the budget, what finishing costs, and the step's press (audit M1).
    <CostBarProvider projectId={id} used={budgetUsed(p)} budget={p.budget_credits} pct={budgetPct(p)} director={directorTime(p)} lookOnly={lookOnly} fallback={waiting ? null : directing ? cutAction : lookOnly ? nextAction : (updateAction ?? nextAction)}>
    {fs && <VideoTop brandId={p.brand_id} fs={fs} steps />}
    <main className={`mx-auto max-w-content space-y-4 p-4 sm:p-8 ${rail ? "" : "pb-28"}`}>
      {!fs && (
      <>
      <div className="flex items-center gap-1">
        {/* The back link names where it goes: this brand's videos. */}
        <Link to={`/b/${brandId}/videos`} className="inline-flex min-h-control items-center gap-1 text-accent-text hover:underline sm:min-h-control-dense">
          <ChevronLeft size={20} strokeWidth={1.75} aria-hidden />
          Videos
        </Link>
      </div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        {/* On a phone "Project: none" goes under the title rather than squeezing it (Next-Lead row 22). */}
        <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
          <div className="flex min-w-0 items-center gap-2">
            <h1 className="min-w-0 break-words type-page">{p.name}</h1>
            {menu}
          </div>
          <WaitingCount projectId={id} className="basis-full" />
        </div>
      </div>
      </>
      )}
      {video.dialog}
      {/* Every per-video choice in one row (flows VS1); an archived video is read only. Plan has its own song strip, with the player. */}
      {lookOnly && (
        <Banner tone="info" title={`This is ${p.created_by_name ? `${maker}'s` : "someone else's"} video. You can look, but only ${maker} or the owner can change it.`} />
      )}
      {!p.archived_at && !fs && ( // a director-made video's settings are the director's (B_VideoSteps)
        <ViewOnly on={!!lookOnly}>
          <VideoSettings project={p} finished={finished} song={step !== "plan"} />
        </ViewOnly>
      )}
      <HeldRequests where={{ projectId: id }} />
      {p.archived_at && (
        <Banner tone="info" title="Archived" action={mayManage(p) ? <Button variant="secondary" onClick={() => void video.restore(target)}>Restore</Button> : undefined}>
          It's out of the lists. Its clips and downloads are kept. Restore it to keep working.
        </Banner>
      )}
      {waiting ? (
        <Skeleton className="h-control" />
      ) : (
        <VideoTabs
          steps={steps}
          onPick={(to) => (to === "director" ? setParams({}) : pick(to))}
          end={
            // On Clips: how many are approved (v5; the list carries each clip's script line). Elsewhere: the script.
            isClips(step) && !directing ? (
              approvedOf && <span className="shrink-0 text-xs text-muted tabular-nums">{approvedOf}</span>
            ) : !directing && (
              <Button variant="ghost" dense icon={FileText} onClick={() => setPanel(true)} aria-label="Show script">
                {rail ? "Script" : ""}
              </Button>
            )
          }
        />
      )}
      {directing ? (
        <DirectorPanel projectId={id} aspect={p.aspect_ratio} name={p.name} onOpenClips={() => pick("clips")} />
      ) : (
      <>
      {p.status === "needs_owner_approval" && <WaitingBadge />}
      <div className="flex flex-wrap items-start justify-between gap-3 has-[>div:empty]:hidden">
        <div className="empty:hidden">
          {/* On Clips the list is the heading, and its count sits at the end of the tabs (v5). */}
          {!isClips(step) && <h2 className="type-section">{label}</h2>}
          {meta && !isClips(step) && <p className="text-sm text-muted tabular-nums">{meta}</p>}
          {/* While the takes are locked (the stills aren't approved), it says why. */}
          {isClips(step) && clipsLock && <p className="text-sm text-muted">Takes: {clipsLock}</p>}
          {(isClips(step) || step === "downloads") && <CheckSummary projectId={id} />}
        </div>
      </div>
      {hold && !update.stopped && ( // a stopped update says where, with that step's own press
        <Banner tone="warning" title={held?.at === "cast" ? "Waiting on the cast" : "Out of date"} action={fixAt && !(isClips(step) && isClips(fixAt.id)) && <Button variant="secondary" onClick={() => pick(fixAt.id)}>Open {fixAt.label}</Button>}>
          {hold}
        </Banner>
      )}
      {update.note}
      <ViewOnly on={!!lookOnly}>
      {step === "plan" && (
        <PlanStep
          project={p as typeof p & { plan_status?: "none" | "ready" | "approved" | null }}
          shots={
            <div className="space-y-4">
              <ShapeRow shape={!settings.data} projectId={id} aspect={p.aspect_ratio} platform={p.platform} />
              {p.song && <SongStrip project={p} hasShots={all.shots.made} hasClips={all.clips.total > 0} />}
              <BreakdownPane projectId={id} brandId={p.brand_id} scriptVersion={script.data?.version ?? 0} plannedSeconds={p.planned_seconds ?? p.breakdown_seconds ?? 0} used={p.credits_used} budget={p.budget_credits} line={line} onShowLines={showLines} onDirty={setDirty} />
            </div>
          }
        />
      )}
      {step === "cast" && <AssetsPane bar projectId={id} brandId={p.brand_id} variants={p.product_variants ?? {}} />}
      {isClips(step) && (
        <ClipsStep
          projectId={id}
          brandId={p.brand_id}
          aspect={p.aspect_ratio}
          projectName={p.name}
          used={p.credits_used}
          budget={p.budget_credits}
          scriptVersion={script.data?.version ?? 0}
          castRedraw={p.cast_redraw}
          clipCount={media.clips}
          clipsLock={clipsLock}
          stillsHold={videoHold("storyboard", all)?.why ?? null}
          clipsHold={videoHold("clips", all)}
          barTaken={!!update.action}
        />
      )}
      {step === "downloads" && <DownloadsPane projectId={id} aspect={p.aspect_ratio} projectName={p.name} />}
      </ViewOnly>
      </>
      )}
      {panel && (
        <ScriptPanel
          projectId={id}
          rail={rail}
          highlight={highlight}
          onLineClick={
            step === "plan"
              ? (n) => {
                  setLine(n);
                  setHighlight([n]);
                  if (!rail) setPanel(false);
                }
              : undefined
          }
          onClose={() => setPanel(false)}
        />
      )}
    </main>
    </CostBarProvider>
  );
}
