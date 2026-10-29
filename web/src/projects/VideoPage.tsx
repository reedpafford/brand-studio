import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, FileText } from "lucide-react";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { useMe } from "../auth/useMe";
import { Banner, Button, Skeleton, StepPicker } from "../components";
import { useRail } from "../useMedia";
import { useFreshProject } from "./useFreshProject";
import { AssetsPane, useAssets } from "./AssetsPane";
import { notInShots } from "./AssetCard";
import { BreakdownPane } from "./BreakdownPane";
import { PlanStep } from "./PlanStep";
import { useBriefChoices } from "./BriefPickers";
import { ClipsPane } from "./ClipsPane";
import { DownloadsPane } from "./DownloadsPane";

import { WaitingBadge } from "./Meter";
import { CostBarProvider, type CostAction } from "./CostBar";
import { VideoMenu, useMayManageVideo, useVideoActions } from "./ReleaseVideo";
import { ScriptPanel } from "./ScriptPanel";
import { ShapeRow } from "./ShapeRow";
import { StoryboardPane } from "./StoryboardPane";
import { SongStrip } from "../scripts/VideoSong";
import { isDone } from "./steps";
import { useProgress } from "./useProgress";
import { VIDEO_STEPS, videoBlocker, videoHold, videoLock, videoNext, videoStepFromParams, videoStepStates, type VideoProgress } from "./videoSteps";

/** A video made from a library version: Plan · Cast · Storyboard · Clips · Final cut. */
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
  const video = useVideoActions((kind) => navigate(`/b/${brandId}/${kind === "release" ? "scripts" : "videos"}`)) // a released version is ready to make again in Scripts; an archived video is under Videos;
  useFreshProject(id);
  const project = useQuery({
    queryKey: ["project", id],
    queryFn: async () => (await api.GET("/projects/{project_id}", { params: { path: { project_id: id } } })).data ?? null,
  });
  const { progress, loading, script, media } = useProgress(id);
  const assets = useAssets(id);
  const p = project.data;
  const { data: me } = useMe();
  const allowance = useQuery({ enabled: !!p?.own_script && me?.role === "editor", queryKey: ["allowance"], queryFn: async () => (await api.GET("/credits/me")).data ?? null });
  // An editor on their own script is billed to the week, not to a budget.
  const week = p?.own_script && allowance.data ? { used: allowance.data.quick_clip_credits_used, allowed: allowance.data.quick_clip_credits_allowed } : null;
  const flavours = useBriefChoices(p?.brand_id ?? 0, p?.product_variants ?? {});
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
  if (videoLock(step, all) !== null) return <Navigate to={`?step=${videoBlocker(step, all)}`} replace />;

  const pick = (to: string) => {
    setParams(to === "plan" ? {} : { step: to });
    setPanel(false);
  };
  const showLines = (lines: number[]) => {
    setHighlight(lines);
    setLine(null);
    setPanel(true);
  };
  const label = VIDEO_STEPS.find((s) => s.id === step)?.label;
  // Made work whose earlier step changed stays viewable; its paid presses wait, and the banner says where to go (audit M14).
  const hold = videoHold(step, all);
  const fixAt = hold ? VIDEO_STEPS.find((s) => s.id === videoBlocker(step, all)) : undefined;
  const next = videoNext(step);
  const reason = !next ? null : dirty && step === "plan" ? "Save your changes first." : step === "cast" && flavours.unchosen ? `Pick a ${flavours.unchosen} flavour first` : videoLock(next.id, all);
  // The cost bar's press when the step has none of its own. On a phone, unsaved shot edits take the bar's place.
  const nextAction: CostAction | null = next && !(step === "plan" && dirty && !rail) ? { label: `Next: ${next.label}`, reason, onPress: () => pick(next.id) } : null;
  // Release while it is being made; Archive once it is done. An archived video is read-only until it is restored.
  const finished = isDone("final", progress);
  const target = { id, name: p.name, creditsUsed: p.credits_used };
  const menu = mayManage(p) && !p.archived_at && <VideoMenu title={p.name} onRelease={finished ? undefined : () => video.release(target)} onArchive={finished ? () => video.archive(target) : undefined} />;
  // Until Assets' own read lands, the step picker, the heading line and Next wait under one skeleton: no counts from an older read.
  const waiting = step === "cast" && assetsLoading;
  const count = (n: number, noun: string, ok: number) => `${n} ${noun}${n === 1 ? "" : "s"} · ${ok} approved`;
  const meta =
    step === "cast" ? (waiting ? null : `${all.assets.total} in the cast · ${all.assets.ready} approved`) : step === "storyboard" && all.frames.total > 0 ? count(all.frames.total, "frame", all.frames.approved) : step === "clips" && all.clips.total > 0 ? count(all.clips.total, "clip", all.clips.approved) : null;

  return (
    // One cost bar at the bottom: the budget (or the editor's week), what finishing costs, and the step's press (audit M1).
    <CostBarProvider projectId={id} used={p.credits_used} budget={p.budget_credits} pct={p.budget_pct} week={week} fallback={waiting ? null : nextAction}>
    <main className={`mx-auto max-w-content space-y-4 p-4 sm:p-8 ${rail ? "" : "pb-28"}`}>
      <div className="flex items-center gap-1">
        {/* The back link names where it goes: this brand's videos. */}
        <Link to={`/b/${brandId}/videos`} className="inline-flex min-h-control items-center gap-1 text-accent-text hover:underline sm:min-h-control-dense">
          <ChevronLeft size={20} strokeWidth={1.75} aria-hidden />
          Videos
        </Link>
      </div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <h1 className="min-w-0 break-words type-page">{p.name}</h1>
          {menu}
        </div>
      </div>
      {video.dialog}
      {p.archived_at && (
        <Banner tone="info" title="Archived" action={mayManage(p) ? <Button variant="secondary" onClick={() => void video.restore(target)}>Restore</Button> : undefined}>
          It's out of the lists. Its clips and downloads are kept. Restore it to keep working.
        </Banner>
      )}
      {p.status === "needs_owner_approval" && <WaitingBadge />}
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          {waiting ? <Skeleton className="h-control" /> : <StepPicker steps={videoStepStates(step, all)} onPick={pick} />}
        </div>
        <Button variant="secondary" dense icon={FileText} onClick={() => setPanel(true)} aria-label="Show script">
          {rail ? "Script" : ""}
        </Button>
      </div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="type-section">{label}</h2>
          {meta && <p className="text-sm text-muted tabular-nums">{meta}</p>}
        </div>
      </div>
      {hold && (
        <Banner tone="warning" title="Out of date" action={fixAt && <Button variant="secondary" onClick={() => pick(fixAt.id)}>Open {fixAt.label}</Button>}>
          {hold}
        </Banner>
      )}
      {step === "plan" && (
        <PlanStep
          project={p as typeof p & { plan_status?: "none" | "ready" | "approved" | null }}
          shots={
            <div className="space-y-4">
              <ShapeRow projectId={id} aspect={p.aspect_ratio} platform={p.platform} />
              {p.song && <SongStrip project={p} hasShots={all.shots.made} hasClips={all.clips.total > 0} />}
              <BreakdownPane ownScript={p.own_script} projectId={id} brandId={p.brand_id} scriptVersion={script.data?.version ?? 0} plannedSeconds={p.planned_seconds ?? p.breakdown_seconds ?? 0} used={p.credits_used} budget={p.budget_credits} line={line} onShowLines={showLines} onDirty={setDirty} />
            </div>
          }
        />
      )}
      {step === "cast" && <AssetsPane projectId={id} brandId={p.brand_id} variants={p.product_variants ?? {}} ownScript={p.own_script} used={p.credits_used} budget={p.budget_credits} />}
      {step === "storyboard" && <StoryboardPane hold={hold} castRedraw={p.cast_redraw} ownScript={p.own_script} oneStep clips={media.clips} projectId={id} brandId={p.brand_id} aspect={p.aspect_ratio} used={p.credits_used} budget={p.budget_credits} />}
      {step === "clips" && <ClipsPane hold={hold} ownScript={p.own_script} review projectId={id} brandId={p.brand_id} aspect={p.aspect_ratio} projectName={p.name} used={p.credits_used} budget={p.budget_credits} />}
      {step === "downloads" && <DownloadsPane projectId={id} aspect={p.aspect_ratio} projectName={p.name} />}
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
