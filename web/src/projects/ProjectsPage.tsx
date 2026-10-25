import { useState } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { Bell, Clapperboard, Plus } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { fileUrl } from "../api/upload";
import { useHeld } from "../approvals/useHeld";
import { useJobs } from "../clip/History";
import { Badge, Banner, Button, EmptyState, MediaCard, Skeleton, buttonClass } from "../components";
import { useBrands } from "../shell/useBrands";
import { ActionBar } from "../shell/ActionBar";
import { useMedia } from "../useMedia";
import { STEPS, firstUnfinished, type StepId } from "./steps";
import { useProgress, videoQuery } from "./useProgress";

type Project = NonNullable<ReturnType<typeof useProjectList>["data"]>[number];
type Job = NonNullable<ReturnType<typeof useJobs>["data"]>[number];

export function useProjectList(brandId: number) {
  return useQuery({
    queryKey: ["projects", brandId],
    queryFn: async () => {
      const { data } = await api.GET("/projects", { params: { query: { brand_id: brandId } } });
      if (!data) throw new Error("load");
      return data;
    },
  });
}

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
const FINISHED_SHOWN = 8;

/** Credits used against the budget: a thin bar always, the words on hover or focus on desktop (always on touch), and always when it matters. */
function CreditsBar({ used, budget, pct }: { used: number; budget: number; pct: number }) {
  const state = pct > 100 ? "Over budget" : pct >= 75 ? "Almost at budget" : "";
  const tone = pct > 100 ? "text-danger" : pct >= 75 ? "text-warning" : "text-muted";
  const bar = pct > 100 ? "bg-danger" : pct >= 75 ? "bg-warning" : "bg-accent";
  return (
    <span className="block space-y-1">
      <span className={`block text-sm tabular-nums ${tone} ${state ? "" : "lg:sr-only lg:group-focus-within:not-sr-only lg:group-hover:not-sr-only"}`}>
        {Math.round(used)} of {Math.round(budget)} credits{state && ` · ${state}`}
      </span>
      <span className="block h-1 overflow-hidden rounded-full bg-surface-2" aria-hidden>
        <span className={`block h-full rounded-full ${bar}`} style={{ width: `${Math.min(100, Math.max(0, pct))}%` }} />
      </span>
    </span>
  );
}

/** What a video is up to, said once: the step it is at and one plain line about it. */
function VideoCard({ p, brandId, job }: { p: Project; brandId: number; job?: Job }) {
  const { progress, script, breakdown, media } = useProgress(p.id);
  const shape = p.aspect_ratio || "9:16";
  const step: StepId = progress.video.made ? "final" : !progress.script ? "brief" : firstUnfinished(progress);
  const label = STEPS.find((s) => s.id === step)!.label;
  const f = progress.frames;
  const c = progress.clips;
  const line =
    step === "brief"
      ? "Brief written"
      : step === "script"
        ? script.data ? `${script.data.words} words` : "Draft ready to read"
        : step === "shots"
          ? progress.shots.problems > 0
            ? `${plural(progress.shots.problems, "problem")} to fix`
            : progress.shots.made ? `${plural(media.clips, "clip")} planned` : "Ready for shots"
          : step === "storyboard"
            ? f.total === 0 ? "Ready for the storyboard" : `${f.approved} of ${plural(f.total, "frame")} approved`
            : step === "clips"
              ? c.total === 0 ? "Ready for clips" : `${c.approved} of ${plural(c.total, "clip")} approved`
              : `Ready · ${media.seconds || p.planned_seconds} s · ${shape}`;
  const second =
    p.status === "needs_owner_approval" ? <Badge tone="warning">Waiting for Reed to approve</Badge>
    : job?.status === "failed" ? <Badge tone="danger">Didn't finish · credits returned</Badge>
    : step === "final" && progress.video.outOfDate ? <Badge>Out of date</Badge>
    : null;
  void breakdown;
  return (
    <div className="group">
      <MediaCard
        to={`/b/${brandId}/projects/${p.id}`}
        label={`${p.name}, ${label}, ${line}`}
        title={p.name}
        meta={line}
        aspect="9 / 14"
        icon={Clapperboard}
        image={media.image ? fileUrl(media.image) : null}
        video={media.video ? fileUrl(media.video) : null}
        playable={step === "final"}
        badge={
          <span className="flex flex-col items-start gap-1">
            <Badge tone="media">{label}</Badge>
            {second}
          </span>
        }
      >
        <CreditsBar used={p.credits_used} budget={p.budget_credits} pct={p.budget_pct} />
      </MediaCard>
    </div>
  );
}

export function ProjectsPage() {
  const brandId = Number(useParams().brandId);
  const { data: brands } = useBrands();
  const held = useHeld();
  const name = brands?.find((b) => b.id === brandId)?.name ?? "this brand";
  const projects = useProjectList(brandId);
  const jobs = useJobs();
  const [all, setAll] = useState(false);
  const list = projects.data;
  const videos = useQueries({ queries: (list ?? []).map((p) => videoQuery(p.id)) });
  const phone = !useMedia("(min-width: 1024px)");
  const newVideo = (
    <Link to={`/b/${brandId}/projects/new`} className={buttonClass("primary")}>
      <Plus size={20} strokeWidth={1.75} aria-hidden />
      New video
    </Link>
  );

  // Newest first. A video with a final video is finished (even when it is out of date); the rest are in progress.
  const newest = (list ?? []).map((p, i) => ({ p, made: !!videos[i]?.data })).sort((a, b) => b.p.id - a.p.id);
  const inProgress = newest.filter((x) => !x.made).map((x) => x.p);
  const finished = newest.filter((x) => x.made).map((x) => x.p);
  const lastJob = (id: number) => (jobs.data ?? []).filter((j) => j.project_id === id).sort((a, b) => b.id - a.id)[0];
  const grid = "grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3 xl:grid-cols-4";
  const cards = (ps: Project[]) => (
    <ul className={grid}>
      {ps.map((p) => (
        <li key={p.id}>
          <VideoCard p={p} brandId={brandId} job={lastJob(p.id)} />
        </li>
      ))}
    </ul>
  );
  const heldCredits = Math.round(held.allHeldJobs.reduce((n, j) => n + (j.credits ?? 0), 0));

  return (
    <main className="mx-auto max-w-content space-y-6 p-4 sm:p-6">
      {held.owner && held.count > 0 && (
        <Banner tone="info" title={`${held.count} ${held.count === 1 ? "request is" : "requests are"} waiting for you`} action={<Link to="/approvals" className={buttonClass("secondary")}><Bell size={20} strokeWidth={1.75} aria-hidden />Review</Link>}>
          {heldCredits > 0 && `${heldCredits} credits in all`}
        </Banner>
      )}
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="type-eyebrow text-muted">{name}</p>
          <h1 className="type-page">Videos</h1>
        </div>
        {list && list.length > 0 && !phone && newVideo}
        {list && list.length > 0 && phone && <p className="text-sm text-muted">{inProgress.length} in progress</p>}
      </div>
      {projects.isError && (
        <Banner title="Couldn't load your videos." action={<Button variant="secondary" onClick={() => void projects.refetch()}>Try again</Button>}>
          Check your connection.
        </Banner>
      )}
      {projects.isPending && (
        <div className={grid} aria-label="Loading">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="aspect-[9/14] rounded-lg" />
          ))}
        </div>
      )}
      {list?.length === 0 && (
        <EmptyState icon={Clapperboard} title={`No videos for ${name} yet`} action={newVideo}>
          Start from a brief: what it's for, who's in it and how long. Claude helps with the script.
        </EmptyState>
      )}
      {list && list.length > 0 && (
        <>
          <section aria-label="In progress" className="space-y-3">
            <div className="flex items-baseline justify-between gap-3">
              <h2 className="type-section">In progress</h2>
              {!phone && <p className="text-sm text-muted">{plural(inProgress.length, "video")}{finished.length > 0 && ` · ${finished.length} finished`}</p>}
            </div>
            {inProgress.length > 0 ? cards(inProgress) : <p className="text-sm text-muted">Nothing in progress. Start a new video.</p>}
          </section>
          {finished.length > 0 && (
            <section aria-label="Finished" className="space-y-3">
              <h2 className="type-section">Finished</h2>
              {cards(all ? finished : finished.slice(0, FINISHED_SHOWN))}
              {!all && finished.length > FINISHED_SHOWN && (
                <Button variant="secondary" onClick={() => setAll(true)}>
                  Show all {finished.length}
                </Button>
              )}
            </section>
          )}
          {phone && <ActionBar phone>{newVideo}</ActionBar>}
        </>
      )}
    </main>
  );
}

/** The Script library's "Videos made before scripts": the earlier videos stay reachable, and the earlier way to start one for now. */
export function LegacyVideos({ brandId }: { brandId: number }) {
  const projects = useProjectList(brandId);
  const list = (projects.data ?? []).slice().sort((a, b) => b.id - a.id);
  const jobs = useJobs();
  const lastJob = (id: number) => (jobs.data ?? []).filter((j) => j.project_id === id).sort((a, b) => b.id - a.id)[0];
  return (
    <section className="space-y-3 border-t border-border pt-4" aria-label="Videos made before scripts">
      {list.length > 0 && (
        <details>
          <summary className="flex min-h-control cursor-pointer items-center font-medium">Videos made before scripts ({list.length})</summary>
          <ul className="mt-3 grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3 xl:grid-cols-4">
            {list.map((p) => (
              <li key={p.id}>
                <VideoCard p={p} brandId={brandId} job={lastJob(p.id)} />
              </li>
            ))}
          </ul>
        </details>
      )}
      <Link to={`/b/${brandId}/projects/new`} className={buttonClass("secondary")}>
        New video (the earlier way)
      </Link>
    </section>
  );
}
