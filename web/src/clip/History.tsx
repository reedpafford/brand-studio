import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { fileUrl } from "../api/upload";
import { Clapperboard, Download, Zap } from "lucide-react";
import { Badge, Banner, Button, EmptyState, MediaCard, Sheet, Skeleton, buttonClass, type Tone } from "../components";
import { useMedia } from "../useMedia";

const WORDS = {
  queued: "Queued",
  running: "Making",
  succeeded: "Ready",
  failed: "Didn't finish · credits returned",
  cancelled: "Cancelled",
  needs_owner_approval: "Waiting for Reed to approve",
} as const;
const TONES: Record<keyof typeof WORDS, Tone> = { queued: "media", running: "media", succeeded: "media", failed: "danger", cancelled: "neutral", needs_owner_approval: "warning" };
const FILTERS = { all: "All", ready: "Ready", making: "Making", failed: "Didn't finish" } as const;
type Filter = keyof typeof FILTERS;
const inFilter = (status: string, f: Filter) => f === "all" || (f === "ready" && status === "succeeded") || (f === "making" && ACTIVE.includes(status)) || (f === "failed" && status === "failed");
const ACTIVE = ["queued", "running", "needs_owner_approval"];

/** The caller's jobs. Polls while anything is still going. */
export function useJobs() {
  return useQuery({
    queryKey: ["jobs"],
    queryFn: async () => (await api.GET("/jobs")).data ?? [],
    refetchInterval: (q) => (q.state.data?.some((j) => ACTIVE.includes(j.status)) ? 3000 : false),
  });
}

export const isRendering = (jobs: { kind: string; status: string }[] = []) =>
  jobs.some((j) => j.kind.startsWith("video") && (j.status === "queued" || j.status === "running"));

/** "45s" or "1m 20s". */
export function elapsed(ms: number) {
  const total = Math.max(0, Math.floor(ms / 1000));
  return total < 60 ? `${total}s` : `${Math.floor(total / 60)}m ${total % 60}s`;
}

/** How long a clip has been going. Ticks every second while it is on screen. */
export function Elapsed({ since }: { since: string }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  return <span>{elapsed(now - new Date(since).getTime())}</span>;
}

type Job = NonNullable<ReturnType<typeof useJobs>["data"]>[number];
const fileOf = (j: Job) => (j.output as { file_ids?: number[] } | null)?.file_ids?.[0];

export function History({ brandName, onTryAgain, onStart }: { brandName: string; onTryAgain: (jobId: number) => void; onStart?: () => void }) {
  const queryClient = useQueryClient();
  const jobs = useJobs();
  const rail = useMedia("(min-width: 1024px)");
  const [filter, setFilter] = useState<Filter>("all");
  const [open, setOpen] = useState<Job | null>(null);
  const cancel = useMutation({
    mutationFn: (job_id: number) => api.POST("/jobs/{job_id}/cancel", { params: { path: { job_id } } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });
  // Clips made inside a video belong to that video and its own prompts, so they are not listed here.
  const clips = (jobs.data?.filter((j) => j.kind.startsWith("video") && !j.project_id) ?? []).slice().sort((a, b) => b.id - a.id);
  const shown = clips.filter((j) => inFilter(j.status, filter));

  if (jobs.isError)
    return (
      <Banner title="Couldn't load your clips." action={<Button variant="secondary" onClick={() => void jobs.refetch()}>Try again</Button>}>
        Check your connection.
      </Banner>
    );
  if (jobs.isPending)
    return (
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3 lg:gap-4" aria-label="Loading">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-24 lg:aspect-[9/14] lg:h-auto" />
        ))}
      </div>
    );
  if (clips.length === 0)
    return (
      <EmptyState icon={Zap} title={`Your first ${brandName} clip starts here.`} action={onStart && <Button variant="ghost" onClick={onStart}>Start describing</Button>}>
        Describe a moment, add a brand piece, press Generate.
      </EmptyState>
    );

  const card = (j: Job) => {
    const fileId = fileOf(j);
    const detail = [j.duration && `${j.duration} s`, j.aspect_ratio, j.resolution].filter(Boolean).join(" · ");
    const active = j.status === "queued" || j.status === "running";
    const badge = (
      <Badge tone={TONES[j.status]}>
        {WORDS[j.status]}
        {active && (
          <>
            {" "}
            <Elapsed since={j.created_at} />
          </>
        )}
      </Badge>
    );
    const actions = (
      <div className="space-y-2 text-sm">
        {j.status === "failed" && j.error && <p className="text-danger">{j.error}</p>}
        <div className="flex flex-wrap items-center gap-2">
          {j.status === "failed" && (
            <Button variant="secondary" dense price={j.credits} onClick={() => onTryAgain(j.id)}>
              Try again
            </Button>
          )}
          {ACTIVE.includes(j.status) && (
            <Button variant="ghost" dense aria-label={`Cancel clip ${j.id}`} onClick={() => cancel.mutate(j.id)}>
              Cancel
            </Button>
          )}
          {j.status === "succeeded" && fileId && (
            <a className={buttonClass("secondary")} href={fileUrl(fileId)} download aria-label={`Download clip ${j.id}`}>
              <Download size={20} strokeWidth={1.75} aria-hidden />
              Download
            </a>
          )}
        </div>
      </div>
    );
    const title = j.prompt_summary || `Clip ${j.id}`;
    if (rail)
      return (
        <li key={j.id}>
          <MediaCard title={title} meta={detail} badge={badge} video={fileId && j.status === "succeeded" ? fileUrl(fileId) : null} playable={j.status === "succeeded"} aspect={j.aspect_ratio ? j.aspect_ratio.replace(":", " / ") : "9 / 14"} icon={Clapperboard} onOpen={j.status === "succeeded" && fileId ? () => setOpen(j) : undefined}>
            {actions}
          </MediaCard>
        </li>
      );
    return (
      <li key={j.id} className="flex gap-3 rounded-lg border border-border bg-surface p-3">
        {j.status === "succeeded" && fileId ? (
          <button type="button" aria-label={`Open clip ${j.id}`} onClick={() => setOpen(j)} className="relative block w-16 shrink-0 overflow-hidden rounded-md bg-surface-2" style={{ aspectRatio: "9 / 14" }}>
            <video src={`${fileUrl(fileId)}#t=0.1`} muted playsInline preload="metadata" aria-hidden className="absolute inset-0 size-full object-cover" />
          </button>
        ) : (
          <span className="grid w-16 shrink-0 place-items-center rounded-md bg-surface-2 text-muted" style={{ aspectRatio: "9 / 14" }} aria-hidden>
            <Clapperboard size={20} strokeWidth={1.75} />
          </span>
        )}
        <div className="min-w-0 flex-1 space-y-2">
          {badge}
          <p className="line-clamp-2">{title}</p>
          {detail && <p className="text-sm text-muted">{detail} · {j.credits} credits</p>}
          {actions}
        </div>
      </li>
    );
  };

  return (
    <div className="space-y-3">
      <label className="flex items-center gap-2 text-sm">
        <span className="text-muted">Show</span>
        <select value={filter} onChange={(e) => setFilter(e.target.value as Filter)} className="min-h-control rounded-md border border-border bg-surface-2 px-3 lg:min-h-control-dense">
          {Object.entries(FILTERS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </label>
      {shown.length === 0 && <p className="text-sm text-muted">No clips like that yet.</p>}
      <ul className={rail ? "grid grid-cols-2 gap-4 xl:grid-cols-3" : "space-y-3"}>{shown.map(card)}</ul>
      {open && fileOf(open) && (
        <Sheet title="Your clip" onClose={() => setOpen(null)}>
          <video controls autoPlay src={fileUrl(fileOf(open)!)} className="max-h-[60dvh] w-full rounded-lg bg-surface-2" />
          {open.prompt_summary && <p>{open.prompt_summary}</p>}
          <p className="text-sm text-muted">{[open.duration && `${open.duration} s`, open.aspect_ratio, open.resolution].filter(Boolean).join(" · ")}</p>
          <a className={buttonClass("primary")} href={fileUrl(fileOf(open)!)} download>
            <Download size={20} strokeWidth={1.75} aria-hidden />
            Download
          </a>
        </Sheet>
      )}
    </div>
  );
}
