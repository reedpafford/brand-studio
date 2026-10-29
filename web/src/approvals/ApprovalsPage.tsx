import { useState } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Check, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { api, errorText } from "../api/client";
import { useMe } from "../auth/useMe";
import { Banner, Button, Card, Dialog, EmptyState, Skeleton } from "../components";
import { Meter } from "../projects/Meter";
import { ActionBar } from "../shell/ActionBar";
import { useBrands } from "../shell/useBrands";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { useRail } from "../useMedia";
import { useHeld, type Job, type Project } from "./useHeld";
import { serverTime } from "../time";

const lower = (s: string) => s.charAt(0).toLowerCase() + s.slice(1);
// What a request makes, in plain words (the card names the video beside it).
const STEPS: Record<string, string> = {
  enhance: "Script suggestions",
  script_draft: "A script draft",
  breakdown: "The breakdown",
  storyboard: "The storyboard",
  frame: "A new still",
  clip_prompts: "The clip prompts",
  clip_take: "A new take",
  sheet: "A character's look",
  improve: "A better prompt",
};

/** How long ago, in words: "just now", "2m", "3h", "4d". */
function ago(iso: string) {
  const s = Math.max(0, (Date.now() - serverTime(iso).getTime()) / 1000);
  return s < 60 ? "just now" : s < 3600 ? `${Math.floor(s / 60)}m` : s < 86400 ? `${Math.floor(s / 3600)}h` : `${Math.floor(s / 86400)}d`;
}

const whole = (n: number) => Math.round(n * 10) / 10;
const dollars = (n: number) => `$${n.toFixed(2)}`;

/** Owner only: one place to decide on everything that's waiting. */
export function ApprovalsPage() {
  const { data: me } = useMe();
  const held = useHeld();
  const toast = useToast();
  const refresh = useRefresh();
  const rail = useRail();
  const [asking, setAsking] = useState(false);
  // Dollars are for the owner only, so they come from the owner-only detail of each job.
  const details = useQueries({
    queries: held.heldJobs.map((j) => ({
      enabled: me?.role === "owner",
      queryKey: ["job-detail", j.id],
      queryFn: async () => (await api.GET("/jobs/{job_id}/detail", { params: { path: { job_id: j.id } } })).data ?? null,
    })),
  });
  const usd = new Map(held.heldJobs.map((j, i) => [j.id, details[i]?.data?.cost_usd]));
  const approveAll = useMutation({
    mutationFn: async () => {
      let done = 0;
      const total = held.heldJobs.length + held.heldProjects.length;
      const stop = (error: unknown) => new Error(`${done} of ${total} went through. ${errorText(error)}`);
      for (const j of held.heldJobs) {
        const { error, response } = await api.POST("/jobs/{job_id}/approve", { params: { path: { job_id: j.id } } });
        if (!response.ok) throw stop(error);
        done += 1;
      }
      for (const p of held.heldProjects) {
        const { error, response } = await api.POST("/projects/{project_id}/approve", { params: { path: { project_id: p.id } } });
        if (!response.ok) throw stop(error);
        done += 1;
      }
    },
    onSuccess: async () => {
      setAsking(false);
      await refresh();
      toast("All done.");
    },
    onError: async () => {
      setAsking(false);
      await refresh(); // what did go through leaves the list
    },
  });
  if (me && me.role !== "owner") return <p className="p-6">Page not found.</p>;
  if (!me || held.isPending)
    return (
      <main className="mx-auto max-w-4xl space-y-4 p-4 sm:p-6" aria-label="Loading">
        <Skeleton className="h-10 w-1/3" />
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
      </main>
    );
  if (held.isError)
    return (
      <main className="mx-auto max-w-4xl p-4 sm:p-6">
        <Banner title="Couldn't load approvals." action={<Button variant="secondary" onClick={() => void refresh()}>Try again</Button>}>
          Check your connection.
        </Banner>
      </main>
    );
  const credits = held.heldJobs.reduce((n, j) => n + j.credits, 0);
  const known = held.heldJobs.every((j) => usd.get(j.id) !== undefined);
  const totalUsd = held.heldJobs.reduce((n, j) => n + (usd.get(j.id) ?? 0), 0);
  const money = known && held.heldJobs.length > 0 ? ` (${dollars(totalUsd)})` : "";
  const count = `${held.count} waiting${credits > 0 ? ` · ${whole(credits)} credits${money}` : ""}`;
  const all = (
    <Button disabled={held.count === 0} busy={approveAll.isPending} onClick={() => setAsking(true)}>
      Approve all{credits > 0 ? ` · ${whole(credits)} credits` : ""}
    </Button>
  );
  return (
    <main className="mx-auto max-w-4xl space-y-4 p-4 sm:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="type-page">Approvals</h1>
          {held.count > 0 && <p className="text-sm tabular-nums text-muted">{count}</p>}
        </div>
        {held.count > 0 && rail && all}
      </div>
      {held.count > 0 && !rail && <ActionBar phone>{all}</ActionBar>}
      {approveAll.isError && <p role="alert" className={errorClass}>{approveAll.error.message}</p>}
      {held.count === 0 ? (
        <EmptyState icon={Bell} title="Nothing waiting.">
          Editors are never sent here any more: past a budget or their week, their button gives the reason. Requests from before 26 Oct show here until they're handled.
        </EmptyState>
      ) : (
        <Card className="p-0 sm:p-0">
          <ul className="divide-y divide-border">
            {held.heldJobs.map((j) => (
              <JobRow key={`job-${j.id}`} job={j} projects={held.projects} usd={usd.get(j.id)} />
            ))}
            {held.heldProjects.map((p) => (
              <ProjectRow key={`project-${p.id}`} project={p} heldJobs={held.allHeldJobs.filter((j) => j.project_id === p.id).length} />
            ))}
          </ul>
        </Card>
      )}
      {asking && (
        <Dialog title={`Approve ${held.count} request${held.count === 1 ? "" : "s"} for ${whole(credits)} credits${money}?`} cancelLabel="Keep them" actionLabel="Approve all" busy={approveAll.isPending} onCancel={() => setAsking(false)} onConfirm={() => approveAll.mutate()}>
          Everything waiting starts now.
        </Dialog>
      )}
    </main>
  );
}

function Where({ brandId, children }: { brandId: number | null | undefined; children: React.ReactNode }) {
  const { data: brands } = useBrands();
  const brand = brands?.find((b) => b.id === brandId);
  return (
    <div className="flex flex-wrap items-center gap-2 font-medium">
      {brand && (
        <>
          <span aria-hidden className="size-2.5 rounded-full" style={{ background: brand.colours?.[0] || "var(--accent)" }} />
          <span>{brand.name}</span>
          <span aria-hidden className="text-muted">·</span>
        </>
      )}
      {children}
    </div>
  );
}

function useRefresh() {
  const queryClient = useQueryClient();
  return () => Promise.all([queryClient.invalidateQueries({ queryKey: ["held-jobs"] }), queryClient.invalidateQueries({ queryKey: ["projects"] }), queryClient.invalidateQueries({ queryKey: ["jobs"] }), queryClient.invalidateQueries({ queryKey: ["library"] })]);
}

/** The picture a request is about. There is no thumbnail to show yet, so it is the kind of work on a quiet tile. */
function Preview() {
  return (
    <span className="grid size-14 shrink-0 place-items-center rounded-lg bg-surface-2 text-muted" aria-hidden>
      <Sparkles size={20} strokeWidth={1.75} />
    </span>
  );
}

function JobRow({ job, projects, usd }: { job: Job; projects: Project[]; usd?: number }) {
  const toast = useToast();
  const refresh = useRefresh();
  const [declining, setDeclining] = useState(false);
  const project = projects.find((p) => p.id === job.project_id);
  const what = job.step ? (STEPS[job.step] ?? job.step) : "Quick clip";
  const who = job.created_by_name;
  const brandId = job.brand_id ?? project?.brand_id;
  const act = useMutation({
    mutationFn: async (yes: boolean) => {
      const { error, response } = yes
        ? await api.POST("/jobs/{job_id}/approve", { params: { path: { job_id: job.id } } })
        : await api.POST("/jobs/{job_id}/cancel", { params: { path: { job_id: job.id } } });
      if (!response.ok) throw new Error(errorText(error));
      return yes;
    },
    onSuccess: async (yes) => {
      setDeclining(false);
      await refresh();
      toast(yes ? `Approved. ${what}${who ? ` for ${who}` : ""} is being made.` : "Declined. Nothing was charged.");
    },
    onError: () => setDeclining(false),
  });
  // Each editor's own week, from the owner-only allowances.
  const allowances = useQuery({ queryKey: ["allowances"], queryFn: async () => (await api.GET("/credits/allowances")).data ?? [] });
  const week = allowances.data?.find((a) => a.user_id === job.created_by_id);
  const after = project && project.budget_credits > 0 ? ((project.credits_used + job.credits) / project.budget_credits) * 100 : null;
  return (
    <li className="flex gap-3 p-4 text-sm sm:p-5">
      <Preview />
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <Where brandId={brandId}>
            {project ? (
              <>
                <Link className="underline" to={`/b/${project.brand_id}/projects/${project.id}`}>{project.name}</Link>
                <span aria-hidden className="text-muted">·</span>
                <span>{what}</span>
              </>
            ) : (
              <span>{what}</span>
            )}
          </Where>
          <span className="text-muted">{who ? `asked by ${who}, ` : ""}{ago(job.created_at)}</span>
        </div>
        {job.prompt_summary && <p className="text-muted">"{job.prompt_summary}"</p>}
        <p className="tabular-nums">
          {whole(job.credits)} credits{usd !== undefined && ` (${dollars(usd)})`}{after !== null && ` · takes the project to ${Math.round(after)}% of its budget`}
        </p>
        {!project && !job.step && week && (
          <p className="text-muted tabular-nums">
            {who ? `${who}'s` : "The editor's"} quick clips this week: {whole(week.quick_clip_credits_used)} of {whole(week.quick_clip_credits_allowed)} credit{week.quick_clip_credits_allowed === 1 ? "" : "s"}
          </p>
        )}
        {project && after !== null && <Meter used={project.credits_used + job.credits} budget={project.budget_credits} pct={after} />}
        {act.isError && <p role="alert" className={errorClass}>{act.error.message}</p>}
        <div className="flex gap-2 pt-1">
          <Button variant="ghost" className="flex-1 sm:flex-none" disabled={act.isPending} aria-label={`Decline ${lower(what)}`} onClick={() => setDeclining(true)}>
            Decline
          </Button>
          <Button variant="secondary" icon={Check} className="flex-1 sm:flex-none" busy={act.isPending && !declining} aria-label={`Approve ${lower(what)}`} onClick={() => act.mutate(true)}>
            Approve
          </Button>
        </div>
      </div>
      {declining && (
        <Dialog title={`Decline ${lower(what)}${who ? ` for ${who}` : ""}?`} cancelLabel="Keep it" actionLabel="Decline" danger busy={act.isPending} onCancel={() => setDeclining(false)} onConfirm={() => act.mutate(false)}>
          Nothing is charged.{who && ` ${who} can ask again.`}
        </Dialog>
      )}
    </li>
  );
}

function ProjectRow({ project, heldJobs }: { project: Project; heldJobs: number }) {
  const toast = useToast();
  const refresh = useRefresh();
  const approve = useMutation({
    mutationFn: async () => {
      const { error, response } = await api.POST("/projects/{project_id}/approve", { params: { path: { project_id: project.id } } });
      if (!response.ok) throw new Error(errorText(error));
      // What was held inside it and is still held afterwards needs a separate decision.
      const left = (await api.GET("/jobs", { params: { query: { status: "needs_owner_approval" } } })).data?.filter((j) => j.project_id === project.id).length ?? 0;
      return left;
    },
    onSuccess: async (left) => {
      await refresh();
      const started = Math.max(0, heldJobs - left);
      toast(heldJobs === 0 ? "Approved." : `Approved. ${started} held step${started === 1 ? "" : "s"} started${left ? `; ${left} still need${left === 1 ? "s" : ""} you` : ""}.`);
    },
  });
  return (
    <li className="flex gap-3 p-4 text-sm sm:p-5">
      <Preview />
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <Where brandId={project.brand_id}>
            <Link className="underline" to={`/b/${project.brand_id}/projects/${project.id}`}>{project.name}</Link>
            <span aria-hidden className="text-muted">·</span>
            <span>project</span>
          </Where>
          {project.created_by_name && <span className="text-muted">asked by {project.created_by_name}</span>}
        </div>
        <p>
          Planned {project.planned_seconds} s · budget {Math.round(project.budget_credits)} credits
          {heldJobs > 0 && ` · ${heldJobs} step${heldJobs === 1 ? "" : "s"} held inside`}
        </p>
        <p className="text-muted">To decline, ask {project.created_by_name || "whoever planned it"} to shorten the plan.</p>
        {approve.isError && <p role="alert" className={errorClass}>{approve.error.message}</p>}
        <div className="pt-1">
          <Button variant="secondary" icon={Check} busy={approve.isPending} aria-label={`Approve ${project.name}`} onClick={() => approve.mutate()}>
            Approve
          </Button>
        </div>
      </div>
    </li>
  );
}
