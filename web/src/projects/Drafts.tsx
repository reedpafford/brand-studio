import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import { Elapsed, useJobs } from "../clip/History";
import { btnPrimary, btnSecondary, card, errorText as errorClass } from "../ui";

const GOING = ["queued", "running", "needs_owner_approval"];

/** No script yet: Claude writes a few drafts from the brief, and you pick one to start from. */
export function DraftsPanel({ projectId, used, budget }: { projectId: number; used: number; budget: number }) {
  const queryClient = useQueryClient();
  const path = { project_id: projectId };
  const jobs = useJobs();
  const mine = (jobs.data ?? []).filter((j) => j.project_id === projectId && j.step === "script_draft").sort((a, b) => b.id - a.id);
  const latest = mine[0];
  const writing = !!latest && GOING.includes(latest.status);
  const failed = latest?.status === "failed";
  const drafts = useQuery({
    queryKey: ["script-drafts", projectId, latest?.id, latest?.status],
    queryFn: async () => (await api.GET("/projects/{project_id}/script/drafts", { params: { path } })).data ?? [],
  });
  const rates = useQuery({ queryKey: ["rates"], queryFn: async () => (await api.GET("/credits/rates")).data ?? [] });
  const cost = rates.data?.find((r) => r.kind === "write-claude")?.credits_per_unit;
  const over = cost !== undefined && used + cost > budget;

  const write = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/projects/{project_id}/script/draft", { params: { path } });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });
  const use = useMutation({
    mutationFn: async (d: { job_id: number; n: number }) => {
      const { data, error } = await api.POST("/projects/{project_id}/script/drafts/{job_id}/{n}/use", { params: { path: { ...path, job_id: d.job_id, n: d.n } } });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["script", projectId] }),
  });
  const err = write.error ?? use.error;
  const list = drafts.data ?? [];

  return (
    <section className={`${card} space-y-3`} aria-label="Script drafts">
      <p className="text-[length:var(--text-md)] font-semibold">Or let Claude write it</p>
      <p className="text-sm text-muted">Claude reads your brief and writes a few drafts. You pick one to start from, then change anything you like.</p>
      <button className={`${btnSecondary} min-h-11 sm:min-h-9`} disabled={writing || write.isPending} onClick={() => write.mutate()}>
        {writing ? "Claude is writing drafts…" : over ? "Ask Reed to approve" : list.length ? "Write new drafts" : "Write drafts from the brief"}
        {!writing && cost !== undefined ? ` · ${Math.round(cost * 10) / 10} credits` : ""}
      </button>
      {writing && latest && (
        <p className="text-sm text-muted">
          {latest.status === "needs_owner_approval" ? "Waiting for Reed to approve" : latest.status === "queued" ? "Queued " : "Writing "}
          {latest.status !== "needs_owner_approval" && <Elapsed since={latest.created_at} />}
        </p>
      )}
      {failed && !writing && <p className="text-sm text-danger">Didn't finish · credits returned</p>}
      {err && <p role="alert" className={errorClass}>{err.message}</p>}
      {!writing && list.length > 0 && (
        <ul className="space-y-3">
          {list.map((d) => (
            <li key={`${d.job_id}-${d.n}`} className="space-y-2 rounded-md border border-border bg-surface p-3 text-sm" aria-label={`Draft ${d.n}`}>
              <div className="font-medium">Draft {d.n}</div>
              {d.hook_idea && <p className="text-muted">Hook idea: {d.hook_idea}</p>}
              <details>
                <summary className="min-h-11 cursor-pointer py-2 sm:min-h-0 sm:py-0">Read the script</summary>
                <p className="mt-1 whitespace-pre-wrap font-script [overflow-wrap:anywhere]">{d.script}</p>
              </details>
              <button className={`${btnPrimary} min-h-11 sm:min-h-9`} disabled={use.isPending} onClick={() => use.mutate(d)}>
                Use this draft
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
