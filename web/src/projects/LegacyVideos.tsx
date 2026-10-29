import { useQuery } from "@tanstack/react-query";
import { Clapperboard } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { fileUrl } from "../api/upload";
import { useJobs } from "../clip/History";
import { Badge, MediaCard, buttonClass } from "../components";
import { STEPS, firstUnfinished, type StepId } from "./steps";
import { useProgress } from "./useProgress";

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
    p.status === "needs_owner_approval" ? <Badge>Waiting for the owner's OK</Badge>
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

/** The Script library's "Videos made before scripts": the earlier videos stay reachable, and the earlier way to start one for now. */
export function LegacyVideos({ brandId }: { brandId: number }) {
  const projects = useProjectList(brandId);
  // A video made from a library version lives with its script, not here.
  const list = (projects.data ?? []).filter((p) => !p.script_draft_id).sort((a, b) => b.id - a.id);
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
