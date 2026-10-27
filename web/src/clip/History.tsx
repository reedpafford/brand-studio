import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import { useMe } from "../auth/useMe";
import { fileUrl } from "../api/upload";
import { Clapperboard, Download, Ellipsis, Search, Trash2, Zap } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { Badge, Banner, Button, EmptyState, MediaCard, Menu, MenuItem, Sheet, Skeleton, buttonClass, type Tone } from "../components";
import { useDebounced } from "../scripts/ScriptsPage";
import { useToast } from "../toast";
import { useMedia } from "../useMedia";
import { serverTime } from "../time";

const WORDS = {
  queued: "Queued",
  running: "Making",
  succeeded: "Ready",
  failed: "Didn't finish · credits returned",
  cancelled: "Cancelled",
  needs_owner_approval: "Not started",
} as const;
const TONES: Record<keyof typeof WORDS, Tone> = { queued: "media", running: "media", succeeded: "media", failed: "danger", cancelled: "neutral", needs_owner_approval: "neutral" };
const FILTERS = { all: "All", ready: "Ready", making: "Making", failed: "Didn't finish", removed: "Removed" } as const;
type Filter = keyof typeof FILTERS;
const FINISHED = ["succeeded", "failed", "cancelled"];
const inFilter = (status: string, f: Filter) => f === "all" || f === "removed" || (f === "ready" && status === "succeeded") || (f === "making" && ACTIVE.includes(status)) || (f === "failed" && status === "failed");
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
  return <span>{elapsed(now - serverTime(since).getTime())}</span>;
}

/** The clips list, with what was typed in Search and, for Removed, the clips taken off the history. */
function useHistoryJobs(q: string, removed: boolean) {
  return useQuery({
    queryKey: ["jobs", "history", { q, removed }],
    queryFn: async () => (await api.GET("/jobs", { params: { query: { ...(q ? { q } : {}), ...(removed ? { removed: true } : {}) } } })).data ?? [],
    refetchInterval: (query) => (query.state.data?.some((j) => ACTIVE.includes(j.status)) ? 3000 : false),
  });
}

type Job = NonNullable<ReturnType<typeof useJobs>["data"]>[number];
const fileOf = (j: Job) => (j.output as { file_ids?: number[] } | null)?.file_ids?.[0];

export function History({ brandName, onTryAgain, onStart }: { brandName: string; onTryAgain: (jobId: number) => void; onStart?: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const { data: me } = useMe();
  const [params, setParams] = useSearchParams();
  const [text, setText] = useState(params.get("q") ?? "");
  const q = useDebounced(text.trim());
  useEffect(() => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      if (q) next.set("q", q);
      else next.delete("q");
      return next;
    }, { replace: true });
  }, [q]); // eslint-disable-line react-hooks/exhaustive-deps
  const rail = useMedia("(min-width: 1024px)");
  const [filter, setFilter] = useState<Filter>("all");
  const jobs = useHistoryJobs(q, filter === "removed");
  const [gone, setGone] = useState<number[]>([]); // taken off at once, before the list has caught up
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["jobs"] });
  const restore = async (j: Job, message: string) => {
    const { error, response } = await api.POST("/jobs/{job_id}/restore", { params: { path: { job_id: j.id } } });
    if (!response.ok) return toast(errorText(error), undefined, "error");
    setGone((g) => g.filter((id) => id !== j.id));
    await refresh();
    toast(message);
  };
  // No dialog, because it can be undone. The credits stay used either way.
  const remove = async (j: Job) => {
    setGone((g) => [...g, j.id]);
    const { error, response } = await api.DELETE("/jobs/{job_id}", { params: { path: { job_id: j.id } } });
    if (!response.ok) {
      setGone((g) => g.filter((id) => id !== j.id));
      return toast(errorText(error), undefined, "error");
    }
    await refresh();
    setGone((g) => g.filter((id) => id !== j.id)); // the list has caught up; the Removed view must show it
    toast("Removed from your history. Its credits stay used.", () => void restore(j, "Clip back in your history."));
  };
  const [open, setOpen] = useState<Job | null>(null);
  const cancel = useMutation({
    mutationFn: (job_id: number) => api.POST("/jobs/{job_id}/cancel", { params: { path: { job_id } } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });
  // Clips made inside a video belong to that video and its own prompts, so they are not listed here.
  const clips = (jobs.data?.filter((j) => j.kind.startsWith("video") && !j.project_id && !gone.includes(j.id)) ?? []).slice().sort((a, b) => b.id - a.id);
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
  if (clips.length === 0 && !q && filter !== "removed")
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
    const mine = j.created_by_id === me?.id || me?.role === "owner";
    const menu = filter !== "removed" && FINISHED.includes(j.status) && mine && (
      <Menu
        title={`More for clip ${j.id}`}
        align="right"
        trigger={(t) => (
          <button type="button" {...t} aria-label={`More for clip ${j.id}`} className="grid size-control place-items-center rounded-md text-muted hover:bg-surface-2 lg:size-9">
            <Ellipsis size={20} strokeWidth={1.75} aria-hidden />
          </button>
        )}
      >
        {(close) => (
          <MenuItem
            onClick={() => {
              close();
              void remove(j);
            }}
          >
            <Trash2 size={20} strokeWidth={1.75} aria-hidden />
            Remove from history
          </MenuItem>
        )}
      </Menu>
    );
    const actions = filter === "removed" ? (
      <div className="space-y-2 text-sm text-muted">
        <p>Removed</p>
        <Button variant="secondary" dense aria-label={`Restore clip ${j.id}`} onClick={() => void restore(j, "Clip back in your history.")}>
          Restore
        </Button>
      </div>
    ) : (
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
          {menu && <span className="ml-auto">{menu}</span>}
        </div>
      </div>
    );
    const title = j.prompt_summary || `Clip ${j.id}`;
    if (rail)
      return (
        <li key={j.id} className={filter === "removed" ? "opacity-60" : undefined}>
          <MediaCard title={title} meta={detail} badge={badge} video={fileId && j.status === "succeeded" ? fileUrl(fileId) : null} playable={j.status === "succeeded"} aspect={j.aspect_ratio ? j.aspect_ratio.replace(":", " / ") : "9 / 14"} icon={Clapperboard} onOpen={j.status === "succeeded" && fileId ? () => setOpen(j) : undefined}>
            {actions}
          </MediaCard>
        </li>
      );
    return (
      <li key={j.id} className={`flex gap-3 rounded-lg border border-border bg-surface p-3 ${filter === "removed" ? "opacity-60" : ""}`}>
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
      <label className="relative block">
        <span className="sr-only">Search your clips</span>
        <Search size={20} strokeWidth={1.75} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
        <input type="search" role="searchbox" placeholder="Search your clips" value={text} onChange={(e) => setText(e.target.value)} className="min-h-control w-full rounded-md border border-border bg-surface pl-10 pr-3 lg:min-h-control-dense" />
      </label>
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
      {shown.length === 0 &&
        (q ? (
          <div className="flex items-center gap-3">
            <p className="text-muted">No clips match "{q}".</p>
            <Button variant="ghost" onClick={() => setText("")}>
              Clear search
            </Button>
          </div>
        ) : filter === "removed" ? (
          <div className="flex items-center gap-3">
            <p className="text-sm text-muted">Nothing removed.</p>
            <Button variant="ghost" onClick={() => setFilter("all")}>
              Show all
            </Button>
          </div>
        ) : (
          <p className="text-sm text-muted">No clips like that yet.</p>
        ))}
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
