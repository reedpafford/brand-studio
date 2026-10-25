import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import { Elapsed, useJobs } from "../clip/History";
import { Sparkles } from "lucide-react";
import { Badge, Banner, Button, Card, Skeleton } from "../components";
import { errorText as errorClass } from "../ui";

const GOING = ["queued", "running", "needs_owner_approval"];

/** No script yet: Claude writes a few drafts from the brief, and you pick one to start from. */
export function DraftsPanel({
  projectId,
  used,
  budget,
  children,
}: {
  projectId: number;
  used: number;
  budget: number;
  children?: ReactNode;
}) {
  const queryClient = useQueryClient();
  const path = { project_id: projectId };
  const jobs = useJobs();
  const mine = (jobs.data ?? [])
    .filter((j) => j.project_id === projectId && j.step === "script_draft")
    .sort((a, b) => b.id - a.id);
  const latest = mine[0];
  const writing = !!latest && GOING.includes(latest.status);
  const failed = latest?.status === "failed";
  const drafts = useQuery({
    queryKey: ["script-drafts", projectId, latest?.id, latest?.status],
    queryFn: async () =>
      (
        await api.GET("/projects/{project_id}/script/drafts", {
          params: { path },
        })
      ).data ?? [],
  });
  const rates = useQuery({
    queryKey: ["rates"],
    queryFn: async () => (await api.GET("/credits/rates")).data ?? [],
  });
  const cost = rates.data?.find(
    (r) => r.kind === "write-claude",
  )?.credits_per_unit;
  const over = cost !== undefined && used + cost > budget;

  const write = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST(
        "/projects/{project_id}/script/draft",
        { params: { path } },
      );
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });
  const use = useMutation({
    mutationFn: async (d: { job_id: number; n: number }) => {
      const { data, error } = await api.POST(
        "/projects/{project_id}/script/drafts/{job_id}/{n}/use",
        { params: { path: { ...path, job_id: d.job_id, n: d.n } } },
      );
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["script", projectId] }),
  });
  const err = write.error ?? use.error;
  const list = drafts.data ?? [];

  const price = cost === undefined ? undefined : Math.round(cost * 10) / 10;
  return (
    <section className="space-y-4" aria-label="Script drafts">
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="space-y-3">
          <h2 className="flex items-center gap-2 font-display text-md font-bold">
            <Sparkles size={20} strokeWidth={1.75} aria-hidden />
            Write it with Claude
          </h2>
          <p className="text-sm text-muted">
            Claude writes drafts from your brief. You pick one.
          </p>
          {writing && latest ? (
            <div className="space-y-3">
              <p className="text-sm text-muted" role="status">
                {latest.status === "needs_owner_approval" ? (
                  <Badge tone="warning">Waiting for Reed to approve</Badge>
                ) : (
                  <>
                    {latest.status === "queued"
                      ? "Queued "
                      : "Writing drafts… "}
                    <Elapsed since={latest.created_at} />
                  </>
                )}
              </p>
              <Skeleton className="h-10" />
            </div>
          ) : (
            <Button
              variant={list.length ? "secondary" : "primary"}
              ask={over}
              price={price}
              busy={write.isPending}
              onClick={() => write.mutate()}
            >
              {list.length ? "Write new drafts" : "Write drafts"}
            </Button>
          )}
        </Card>
        {children}
      </div>
      {failed && !writing && (
        <Banner
          title="The drafts didn't finish."
          action={
            <Button variant="secondary" onClick={() => write.mutate()}>
              Try again
            </Button>
          }
        >
          Nothing was charged.
        </Banner>
      )}
      {err && (
        <p role="alert" className={errorClass}>
          {err.message}
        </p>
      )}
      {writing && (
        <div className="grid gap-3 lg:grid-cols-3" aria-hidden>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-40" />
          ))}
        </div>
      )}
      {!writing && list.length > 0 && (
        <ul className="grid gap-3 lg:grid-cols-3">
          {list.map((d) => (
            <li key={`${d.job_id}-${d.n}`} aria-label={`Draft ${d.n}`}>
              <DraftCard d={d} busy={use.isPending} onUse={() => use.mutate(d)} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function DraftCard({ d, busy, onUse }: { d: { n: number; hook_idea?: string | null; script: string }; busy: boolean; onUse: () => void }) {
  const [all, setAll] = useState(false);
  return (
    <Card className="flex h-full flex-col gap-3 text-sm">
      <h3 className="font-display text-md font-bold">Draft {d.n}</h3>
      {d.hook_idea && <p className="text-muted">Hook idea: {d.hook_idea}</p>}
      <p className={`whitespace-pre-wrap font-script [overflow-wrap:anywhere] ${all ? "" : "line-clamp-6"}`}>{d.script}</p>
      <Button variant="ghost" dense aria-expanded={all} onClick={() => setAll(!all)}>
        {all ? "Show less" : "Show all"}
      </Button>
      <div className="mt-auto">
        <Button variant="secondary" busy={busy} onClick={onUse}>
          Use this draft
        </Button>
      </div>
    </Card>
  );
}
