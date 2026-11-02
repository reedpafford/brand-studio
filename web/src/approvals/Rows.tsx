import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Film } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import { fileUrl } from "../api/upload";
import { Button, buttonClass, creditsText, Dialog, Field } from "../components";
import { Meter } from "../projects/Meter";
import { budgetUsed } from "../projects/budget";
import { useBrands } from "../shell/useBrands";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { serverTime } from "../time";
import { STEPS } from "./steps";
import type { Job, Project } from "./useHeld";

const lower = (s: string) => s.charAt(0).toLowerCase() + s.slice(1);
const whole = (n: number) => Math.round(n * 10) / 10;
export const dollars = (n: number) => `$${n.toFixed(2)}`;

/** How long ago, in words: "just now", "2m", "3h", "4d". */
function ago(iso: string) {
  const s = Math.max(0, (Date.now() - serverTime(iso).getTime()) / 1000);
  return s < 60 ? "just now" : s < 3600 ? `${Math.floor(s / 60)}m` : s < 86400 ? `${Math.floor(s / 3600)}h` : `${Math.floor(s / 86400)}d`;
}

const DOT = { accent: "bg-accent", warning: "bg-warning", danger: "bg-danger" } as const;

/** A row's status: a dot and words. */
function Status({ tone, children }: { tone: keyof typeof DOT; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted">
      <span aria-hidden className={`size-1.5 rounded-full ${DOT[tone]}`} />
      {children}
    </span>
  );
}

/** The brand (its colour and name), then what the row is about. */
function Where({ brandId, children }: { brandId: number | null | undefined; children: ReactNode }) {
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

/** The picture a row is about: the video's poster, or the kind of work on a quiet tile. */
function Preview({ fileId }: { fileId?: number | null }) {
  return (
    <span className="grid size-14 shrink-0 place-items-center overflow-hidden rounded-lg bg-surface-2 text-muted" aria-hidden>
      {fileId ? <img src={fileUrl(fileId)} alt="" className="size-full object-cover" /> : <Film size={20} strokeWidth={1.75} />}
    </span>
  );
}

/** One row of the inbox: picture, status, where, then the lines and actions. */
function Row({ id, status, where, children, ...rest }: { id?: string; status: ReactNode; where: ReactNode; children: ReactNode; poster?: number | null; tabIndex?: number; "aria-current"?: boolean; className?: string }) {
  return (
    <li id={id} tabIndex={rest.tabIndex} aria-current={rest["aria-current"]} className={`flex gap-3 p-4 text-sm sm:p-5 ${rest.className ?? ""}`}>
      <Preview fileId={rest.poster} />
      <div className="min-w-0 flex-1 space-y-2">
        {status}
        {where}
        {children}
      </div>
    </li>
  );
}

export function useRefresh() {
  const queryClient = useQueryClient();
  return () => Promise.all(["held-jobs", "projects", "jobs", "library"].map((k) => queryClient.invalidateQueries({ queryKey: [k] })));
}

export function JobRow({ job, projects, usd }: { job: Job; projects: Project[]; usd?: number }) {
  // A link from the request's own page (?job=ID, e.g. the director's held move) lands on its row.
  const [params] = useSearchParams();
  const asked = params.get("job") === String(job.id);
  useEffect(() => {
    if (!asked) return;
    const row = document.getElementById(`job-${job.id}`);
    row?.scrollIntoView?.({ block: "center" });
    row?.focus();
  }, [asked, job.id]);
  const toast = useToast();
  const refresh = useRefresh();
  const [declining, setDeclining] = useState(false);
  const [why, setWhy] = useState("");
  const project = projects.find((p) => p.id === job.project_id);
  const what = job.step ? (STEPS[job.step] ?? job.step) : "Quick clip";
  const who = job.created_by_name;
  const act = useMutation({
    mutationFn: async (yes: boolean) => {
      const { error, response } = yes
        ? await api.POST("/jobs/{job_id}/approve", { params: { path: { job_id: job.id } } })
        : await api.POST("/jobs/{job_id}/decline", { params: { path: { job_id: job.id } }, body: { reason: why.trim() } });
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
  const after = project && project.budget_credits > 0 ? ((budgetUsed(project) + job.credits) / project.budget_credits) * 100 : null;
  const where = (
    <div className="flex flex-wrap items-baseline justify-between gap-2">
      <Where brandId={job.brand_id ?? project?.brand_id}>
        {project && (
          <>
            <Link className="inline-flex min-h-11 items-center underline sm:min-h-0" to={`/b/${project.brand_id}/projects/${project.id}`}>{project.name}</Link>
            <span aria-hidden className="text-muted">·</span>
          </>
        )}
        <span>{what}</span>
      </Where>
      <span className="text-muted">{who ? `asked by ${who}, ` : ""}{ago(job.created_at)}</span>
    </div>
  );
  return (
    <Row id={`job-${job.id}`} tabIndex={-1} aria-current={asked || undefined} className={asked ? "outline outline-2 -outline-offset-2 outline-accent" : ""} status={<Status tone="accent">Request</Status>} where={where}>
      {job.prompt_summary && <p className="text-muted">"{job.prompt_summary}"</p>}
      <p className="tabular-nums">
        {creditsText(job.credits)}{usd !== undefined && ` (${dollars(usd)})`}{after !== null && ` · takes the video to ${Math.round(after)}% of its budget`}
      </p>
      {!project && !job.step && week && (
        <p className="text-muted tabular-nums">
          {who ? `${who}'s` : "The editor's"} quick clips this week: {whole(week.quick_clip_credits_used)} of {whole(week.quick_clip_credits_allowed)} credit{week.quick_clip_credits_allowed === 1 ? "" : "s"}
        </p>
      )}
      {project && after !== null && <Meter used={budgetUsed(project) + job.credits} budget={project.budget_credits} pct={after} />}
      {act.isError && <p role="alert" className={errorClass}>{act.error.message}</p>}
      <div className="flex gap-2 pt-1">
        <Button variant="ghost" className="flex-1 sm:flex-none" disabled={act.isPending} aria-label={`Decline ${lower(what)}`} onClick={() => setDeclining(true)}>
          Decline
        </Button>
        <Button variant="secondary" icon={Check} className="flex-1 sm:flex-none" busy={act.isPending && !declining} aria-label={`Approve ${lower(what)}`} onClick={() => act.mutate(true)}>
          Approve
        </Button>
      </div>
      {declining && (
        <Dialog title={`Decline ${lower(what)}${who ? ` for ${who}` : ""}?`} cancelLabel="Keep it" actionLabel="Decline" danger busy={act.isPending} onCancel={() => setDeclining(false)} onConfirm={() => act.mutate(false)}>
          <p>Nothing is charged.{who && ` ${who} sees your reason and can ask again.`}</p>
          <Field label="Reason (optional)" value={why} maxLength={300} placeholder="Let's keep this video under budget" onChange={(e) => setWhy(e.target.value)} />
        </Dialog>
      )}
    </Row>
  );
}

export function ProjectRow({ project, heldJobs }: { project: Project; heldJobs: number }) {
  const toast = useToast();
  const refresh = useRefresh();
  const approve = useMutation({
    mutationFn: async () => {
      const { error, response } = await api.POST("/projects/{project_id}/approve", { params: { path: { project_id: project.id } } });
      if (!response.ok) throw new Error(errorText(error));
      // What was held inside it and is still held afterwards needs a separate decision.
      return (await api.GET("/jobs", { params: { query: { status: "needs_owner_approval" } } })).data?.filter((j) => j.project_id === project.id).length ?? 0;
    },
    onSuccess: async (left) => {
      await refresh();
      const started = Math.max(0, heldJobs - left);
      toast(heldJobs === 0 ? "Approved." : `Approved. ${started} held step${started === 1 ? "" : "s"} started${left ? `; ${left} still need${left === 1 ? "s" : ""} you` : ""}.`);
    },
  });
  const where = (
    <div className="flex flex-wrap items-baseline justify-between gap-2">
      <Where brandId={project.brand_id}>
        <Link className="inline-flex min-h-11 items-center underline sm:min-h-0" to={`/b/${project.brand_id}/projects/${project.id}`}>{project.name}</Link>
        <span aria-hidden className="text-muted">·</span>
        <span>project</span>
      </Where>
      {project.created_by_name && <span className="text-muted">asked by {project.created_by_name}</span>}
    </div>
  );
  return (
    <Row status={<Status tone="accent">Request</Status>} where={where}>
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
    </Row>
  );
}

/** A video that needs Reed without a request: stuck, failed or quiet (from In production), or finished with changes waiting. */
export function VideoRow({ tone, status, brandId, title, line, poster, to }: { tone: keyof typeof DOT; status: string; brandId: number; title: string; line: string; poster?: number | null; to: string }) {
  return (
    <Row poster={poster} status={<Status tone={tone}>{status}</Status>} where={<Where brandId={brandId}><span>{title}</span></Where>}>
      <p className="text-muted">{line}</p>
      <div className="pt-1">
        <Link className={buttonClass("secondary")} to={to} aria-label={`Open video ${title}`}>Open video</Link>
      </div>
    </Row>
  );
}
