import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { fileUrl } from "../api/upload";
import { btnSecondary, card } from "../ui";

const WORDS = {
  queued: "Queued",
  running: "Rendering",
  succeeded: "Ready",
  failed: "Failed · credits returned",
  cancelled: "Cancelled",
  needs_owner_approval: "Waiting for Reed to approve",
} as const;
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
  return <span className="text-muted">{elapsed(now - new Date(since).getTime())}</span>;
}

export function History({ brandName, onTryAgain }: { brandName: string; onTryAgain: (jobId: number) => void }) {
  const queryClient = useQueryClient();
  const jobs = useJobs();
  const cancel = useMutation({
    mutationFn: (job_id: number) => api.POST("/jobs/{job_id}/cancel", { params: { path: { job_id } } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });
  const clips = jobs.data?.filter((j) => j.kind.startsWith("video")) ?? [];

  if (jobs.isError) return <p role="alert" className="text-danger">Could not load your clips. Try again.</p>;
  if (jobs.data && clips.length === 0)
    return (
      <div className={card}>
        <p className="text-[length:var(--text-xl)] font-semibold">Your first {brandName} clip starts here.</p>
        <p className="text-muted">Describe a moment, add a brand piece, press Generate.</p>
      </div>
    );
  return (
    <ul className="space-y-3">
      {clips.map((j) => {
        const fileId = (j.output as { file_ids?: number[] } | null)?.file_ids?.[0];
        const detail = [j.duration && `${j.duration}s`, j.resolution, j.aspect_ratio].filter(Boolean).join(" · ");
        return (
          <li key={j.id} className={`${card} space-y-1 text-sm`}>
            <div className="flex items-center gap-2">
              <span className={`rounded-sm px-2 py-0.5 text-xs ${j.status === "succeeded" ? "bg-success-soft text-success" : j.status === "failed" ? "bg-danger-soft text-danger" : "bg-surface-2"}`}>
                {WORDS[j.status]}
              </span>
              {(j.status === "queued" || j.status === "running") && <Elapsed since={j.created_at} />}
              <span className="text-muted">{j.credits} credits</span>
              {ACTIVE.includes(j.status) && (
                <button className={`${btnSecondary} ml-auto`} aria-label={`Cancel clip ${j.id}`} onClick={() => cancel.mutate(j.id)}>
                  Cancel
                </button>
              )}
            </div>
            {j.prompt_summary && <p className="line-clamp-2">{j.prompt_summary}</p>}
            {detail && <p className="text-muted">{detail}</p>}
            {j.status === "failed" && j.error && <p className="text-danger">{j.error}</p>}
            {j.status === "failed" && (
              <button className={btnSecondary} onClick={() => onTryAgain(j.id)}>
                Try again
              </button>
            )}
            {j.status === "succeeded" && fileId && (
              <>
                <video controls src={fileUrl(fileId)} className="max-h-72 rounded-sm" />
                <a className="underline" href={fileUrl(fileId)} download>
                  Download
                </a>
              </>
            )}
          </li>
        );
      })}
    </ul>
  );
}
