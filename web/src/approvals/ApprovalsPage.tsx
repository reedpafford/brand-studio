import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, errorText } from "../api/client";
import { useMe } from "../auth/useMe";
import { Meter } from "../projects/Meter";
import { useBrands } from "../shell/useBrands";
import { useToast } from "../toast";
import { btnPrimary, btnSecondary, card, errorText as errorClass, pageTitle } from "../ui";
import { useHeld, type Job, type Project } from "./useHeld";

const STEPS: Record<string, string> = {
  enhance: "Enhance",
  script_draft: "Script draft",
  breakdown: "Breakdown",
  storyboard: "Storyboard frames",
  frame: "Frame still",
  clip_prompts: "Clip prompts",
  clip_take: "Clip take",
  sheet: "House-style sheet",
  improve: "Improve prompt",
};

/** How long ago, in words: "just now", "2m", "3h", "4d". */
function ago(iso: string) {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  return s < 60 ? "just now" : s < 3600 ? `${Math.floor(s / 60)}m` : s < 86400 ? `${Math.floor(s / 3600)}h` : `${Math.floor(s / 86400)}d`;
}

/** Owner only: one place to decide on everything that's waiting. */
export function ApprovalsPage() {
  const { data: me } = useMe();
  const held = useHeld();
  if (me && me.role !== "owner") return <p className="p-6">Page not found.</p>;
  if (!me || held.isPending) return <p className="p-6 text-muted">Loading…</p>;
  if (held.isError) return <p role="alert" className={`p-6 ${errorClass}`}>Could not load what's waiting. Try again.</p>;
  return (
    <main className="mx-auto max-w-3xl space-y-4 p-4 sm:p-6">
      <h1 className={pageTitle}>
        Approvals <span className="font-normal text-muted">· {held.count} waiting</span>
      </h1>
      {held.count === 0 ? (
        <div className={`${card} space-y-1`}>
          <p className="font-semibold">Nothing waiting.</p>
          <p className="text-muted">Editors will see "Waiting for Reed to approve" when something needs you.</p>
        </div>
      ) : (
        <ul className="space-y-3">
          {held.heldJobs.map((j) => (
            <JobRow key={`job-${j.id}`} job={j} projects={held.projects} />
          ))}
          {held.heldProjects.map((p) => (
            <ProjectRow key={`project-${p.id}`} project={p} heldJobs={held.allHeldJobs.filter((j) => j.project_id === p.id).length} />
          ))}
        </ul>
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

function JobRow({ job, projects }: { job: Job; projects: Project[] }) {
  const toast = useToast();
  const refresh = useRefresh();
  const project = projects.find((p) => p.id === job.project_id);
  const what = job.step ? (STEPS[job.step] ?? job.step) : "Quick clip";
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
      await refresh();
      toast(yes ? `Approved. ${what} is starting.` : "Declined. Nothing was charged.");
    },
  });
  const after = project && project.budget_credits > 0 ? ((project.credits_used + job.credits) / project.budget_credits) * 100 : null;
  return (
    <li className={`${card} space-y-2 text-sm`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <Where brandId={brandId}>
          {project ? <Link className="underline" to={`/b/${project.brand_id}/projects/${project.id}`}>{project.name}</Link> : <span>Quick clip</span>}
          <span aria-hidden className="text-muted">·</span>
          <span>{what}</span>
        </Where>
        <span className="text-muted">{ago(job.created_at)}</span>
      </div>
      {job.prompt_summary && <p className="text-muted">"{job.prompt_summary}"</p>}
      <p>
        {Math.round(job.credits * 10) / 10} credits{after !== null && ` · takes the project to ${Math.round(after)}% of its budget`}
      </p>
      {project && after !== null && <Meter used={project.credits_used + job.credits} budget={project.budget_credits} pct={after} />}
      {act.isError && <p role="alert" className={errorClass}>{act.error.message}</p>}
      <div className="flex gap-2">
        <button
          className={`${btnSecondary} min-h-11 flex-1 sm:min-h-9 sm:flex-none`}
          disabled={act.isPending}
          aria-label={`Decline ${what}`}
          onClick={() => window.confirm(`Decline ${what.toLowerCase()}?`) && act.mutate(false)}
        >
          Decline
        </button>
        <button className={`${btnPrimary} min-h-11 flex-1 sm:min-h-9 sm:flex-none`} disabled={act.isPending} aria-label={`Approve ${what}`} onClick={() => act.mutate(true)}>
          Approve
        </button>
      </div>
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
    <li className={`${card} space-y-2 text-sm`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <Where brandId={project.brand_id}>
          <Link className="underline" to={`/b/${project.brand_id}/projects/${project.id}`}>{project.name}</Link>
          <span aria-hidden className="text-muted">·</span>
          <span>project</span>
        </Where>
      </div>
      <p>
        Planned {project.planned_seconds} s · budget {Math.round(project.budget_credits)} credits
        {heldJobs > 0 && ` · ${heldJobs} step${heldJobs === 1 ? "" : "s"} held inside`}
      </p>
      <p className="text-muted">To decline, ask whoever planned it to shorten the plan.</p>
      {approve.isError && <p role="alert" className={errorClass}>{approve.error.message}</p>}
      <div className="flex gap-2">
        <button className={`${btnPrimary} min-h-11 flex-1 sm:min-h-9 sm:flex-none`} disabled={approve.isPending} aria-label={`Approve ${project.name}`} onClick={() => approve.mutate()}>
          Approve
        </button>
      </div>
    </li>
  );
}
