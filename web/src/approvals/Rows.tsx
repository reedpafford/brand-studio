import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import { Button, buttonClass, creditsLabel, creditsText, Dialog, Field } from "../components";
import { Meter } from "../projects/Meter";
import { budgetUsed } from "../projects/budget";
import { useBrands } from "../shell/useBrands";
import { useToast } from "../toast";
import { useRail } from "../useMedia";
import { errorText as errorClass } from "../ui";
import { serverTime } from "../time";
import { typeName, type Kind } from "../freestyle/useFreestyle";
import { STEPS } from "./steps";
import { stepOf } from "./HeldRequests";
import { letterOf } from "../scripts/status";
import type { Job, Project } from "./useHeld";
import { refreshJobs } from "../jobs/refresh";

const lower = (s: string) => s.charAt(0).toLowerCase() + s.slice(1);
const whole = (n: number) => Math.round(n * 10) / 10;
export const dollars = (n: number) => `$${n.toFixed(2)}`;

/** How long ago, in words: "just now", "4 min ago", "3 h ago", "2 days ago". */
function ago(iso: string) {
  const s = Math.max(0, (Date.now() - serverTime(iso).getTime()) / 1000);
  const days = Math.floor(s / 86400);
  return s < 60 ? "just now" : s < 3600 ? `${Math.floor(s / 60)} min ago` : s < 86400 ? `${Math.floor(s / 3600)} h ago` : `${days} day${days === 1 ? "" : "s"} ago`;
}

const DOT = { accent: "bg-accent", warning: "bg-warning", danger: "bg-danger" } as const;

/** A row's status: a dot and words; on a phone, who asked and when follow it. */
function Status({ tone, children }: { tone: keyof typeof DOT; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted">
      <span aria-hidden className={`size-2 shrink-0 rounded-full ${DOT[tone]}`} />
      <span>{children}</span>
    </span>
  );
}

/** What the row is about, its brand's name first ("fomo · Market open · Another take"), then who asked (on a computer). */
function Where({ brandId, children, asked }: { brandId: number | null | undefined; children: ReactNode; asked?: string }) {
  const { data: brands } = useBrands();
  const brand = brands?.find((b) => b.id === brandId);
  const rail = useRail();
  return (
    <div className="flex flex-wrap items-baseline gap-x-2">
      <p className="flex flex-wrap items-baseline gap-x-1.5 font-medium">
        {brand && (
          <>
            <span>{brand.name}</span>
            <span aria-hidden className="text-muted">·</span>
          </>
        )}
        {children}
      </p>
      {rail && asked && <span className="text-xs text-muted">{asked}</span>}
    </div>
  );
}

/** One row of the inbox (v5 D_NeedsYou): on a computer the status, what it is and the presses side by side over a
 *  hairline; on a phone (D_PhoneNeedsYou) a card with the status and who asked on top and the presses below. */
function Row({ id, status, where, children, actions, ...rest }: { id?: string; status: ReactNode; where: ReactNode; children: ReactNode; actions: ReactNode; tabIndex?: number; "aria-current"?: boolean; className?: string }) {
  return (
    <li
      id={id}
      tabIndex={rest.tabIndex}
      aria-current={rest["aria-current"]}
      className={`space-y-2 rounded-lg border border-border bg-surface p-4 text-sm lg:grid lg:grid-cols-[120px_minmax(0,1fr)_auto] lg:items-start lg:gap-4 lg:space-y-0 lg:rounded-none lg:border-0 lg:border-b lg:bg-transparent lg:px-6 lg:py-4 ${rest.className ?? ""}`}
    >
      <div className="lg:pt-0.5">{status}</div>
      <div className="min-w-0 space-y-1.5">
        {where}
        {children}
      </div>
      <div className="grid grid-cols-2 gap-2 pt-1 lg:flex lg:items-center lg:pt-0">{actions}</div>
    </li>
  );
}

/** The script and version a held send was made from ("From Bo tries salmon › B"), linked by the script's own brand, all
 *  from the send itself (#1232): a pasted Dialogue's hidden script reads "Pasted text", with nothing to read. */
function FromScript({ fs }: { fs: NonNullable<Job["freestyle"]> }) {
  if (fs.hidden) return <p className="text-xs text-muted">Pasted text</p>;
  const label = `From ${fs.script_title}${fs.slot != null ? ` › ${letterOf(fs.slot)}` : ""}`;
  return fs.brand_id != null ? (
    <Link className="inline-flex min-h-11 items-center text-xs text-accent-text hover:underline lg:min-h-0" to={`/b/${fs.brand_id}/scripts/${fs.script_id}`}>{label}</Link>
  ) : (
    <p className="text-xs text-muted">{label}</p>
  );
}

export function useRefresh() {
  const queryClient = useQueryClient();
  return () => Promise.all([refreshJobs(queryClient), ...["held-jobs", "projects", "library"].map((k) => queryClient.invalidateQueries({ queryKey: [k] }))]);
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
  const fs = job.freestyle;
  const what = fs ? "Freestyle" : job.step ? (STEPS[job.step] ?? job.step) : "Quick clip";
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
  // A freestyle's price is its run's "up to"; its first turn's own credits against the video's budget (budget_credits)
  // would be a second, different figure (QA on #1194), so it has no budget line or meter.
  const after = !fs && project && project.budget_credits > 0 ? ((budgetUsed(project) + job.credits) / project.budget_credits) * 100 : null;
  const rail = useRail();
  const askedBy = `${who ? `asked by ${who}, ` : ""}${ago(job.created_at)}`;
  const where = (
    <Where brandId={job.brand_id ?? project?.brand_id} asked={askedBy}>
      {project && (
        <>
          <Link className="inline-flex min-h-11 items-center underline lg:min-h-0" to={`/b/${project.brand_id}/projects/${project.id}`}>{project.name}</Link>
          <span aria-hidden className="text-muted">·</span>
        </>
      )}
      <span>{fs ? `Freestyle · ${typeName(fs.type as Kind)} · ${fs.title}` : what}</span>
    </Where>
  );
  // Open goes where the request was made: the freestyle thread, the video at its step, or the script (a song take).
  const brandOf = job.brand_id ?? project?.brand_id;
  const step = stepOf(job);
  const open = fs
    ? { to: `/freestyle/${fs.id}`, label: `Open freestyle ${fs.title}` }
    : project
      ? { to: `/b/${project.brand_id}/videos/${project.id}${step ? `?step=${step}` : ""}`, label: `Open ${project.name}` }
      : job.script_id != null && brandOf != null
        ? { to: `/b/${brandOf}/scripts/${job.script_id}`, label: "Open its script" }
        : null;
  const actions = (
    <>
      <Button variant="secondary" className="lg:order-2" disabled={act.isPending} aria-label={`Decline ${lower(what)}`} onClick={() => setDeclining(true)}>
        Decline
      </Button>
      <Button variant="secondary" className="lg:order-3" busy={act.isPending && !declining} aria-label={`Approve ${lower(what)}`} onClick={() => act.mutate(true)}>
        Approve
      </Button>
      {open && (
        <Link className={`${buttonClass("ghost")} col-span-2 lg:order-1`} to={open.to} aria-label={open.label}>Open</Link>
      )}
    </>
  );
  return (
    <Row id={`job-${job.id}`} tabIndex={-1} aria-current={asked || undefined} className={asked ? "outline outline-2 -outline-offset-2 outline-accent" : ""} status={<Status tone="warning">Request{!rail && ` · ${askedBy}`}</Status>} where={where} actions={actions}>
      {fs ? (
        <>
          <p className="text-xs text-muted">{fs.change ? "Change asked" : "First send"}</p>
          {fs.script_id != null && <FromScript fs={fs} />}
          {fs.said && <p className="line-clamp-6 whitespace-pre-line font-mono text-xs leading-relaxed">"{fs.said}"</p>}
          {fs.up_to != null && <p className="tabular-nums">Up to {creditsLabel(fs.up_to)}{fs.change ? " for this change" : " · your OK covers the whole run"}</p>}
          {/* Only what's spent so far: "in all" read as a second price (QA-3 on #1213, as on the video page). */}
          {fs.change && <p className="tabular-nums text-muted">{fs.spent > 0 ? `${creditsLabel(fs.spent)} spent so far` : "Nothing spent yet"}</p>}
        </>
      ) : (
        // The editor's own words: a redo or change note as typed (#1232), or a Quick clip's prompt. A step's prompt is model
        // text, never quoted to the owner (QA-3 on #1213).
        (job.note || (!job.step && job.prompt_summary)) && <p className="whitespace-pre-line text-muted">"{job.note || job.prompt_summary}"</p>
      )}
      {/* A Freestyle shows its whole price above; its first charge beside it read as a second price (QA-3 on #1213). */}
      {!(fs && fs.up_to != null) && (
        <p className="tabular-nums">
          {creditsText(job.credits)}{usd !== undefined && !fs && ` (${dollars(usd)})`}{after !== null && ` · takes the video to ${Math.round(after)}% of its budget`}
        </p>
      )}
      {!project && !job.step && !fs && week && (
        <p className="text-muted tabular-nums">
          {who ? `${who}'s` : "The editor's"} quick clips this week: {whole(week.quick_clip_credits_used)} of {whole(week.quick_clip_credits_allowed)} credit{week.quick_clip_credits_allowed === 1 ? "" : "s"}
        </p>
      )}
      {project && after !== null && <Meter used={budgetUsed(project) + job.credits} budget={project.budget_credits} pct={after} />}
      {act.isError && <p role="alert" className={errorClass}>{act.error.message}</p>}
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
  const rail = useRail();
  const askedBy = project.created_by_name ? `asked by ${project.created_by_name}` : "";
  const where = (
    <Where brandId={project.brand_id} asked={askedBy}>
      <Link className="inline-flex min-h-11 items-center underline lg:min-h-0" to={`/b/${project.brand_id}/projects/${project.id}`}>{project.name}</Link>
      <span aria-hidden className="text-muted">·</span>
      <span>project</span>
    </Where>
  );
  const actions = (
    <Button variant="secondary" className="col-span-2" busy={approve.isPending} aria-label={`Approve ${project.name}`} onClick={() => approve.mutate()}>
      Approve
    </Button>
  );
  return (
    <Row status={<Status tone="warning">Request{!rail && askedBy && ` · ${askedBy}`}</Status>} where={where} actions={actions}>
      <p>
        Planned {project.planned_seconds} s · budget {Math.round(project.budget_credits)} credits
        {heldJobs > 0 && ` · ${heldJobs} step${heldJobs === 1 ? "" : "s"} held inside`}
      </p>
      <p className="text-muted">To decline, ask {project.created_by_name || "whoever planned it"} to shorten the plan.</p>
      {approve.isError && <p role="alert" className={errorClass}>{approve.error.message}</p>}
    </Row>
  );
}

/** A video that needs Reed without a request: stuck, failed or quiet (from In production), or finished with changes waiting. */
export function VideoRow({ tone, status, brandId, title, line, to }: { tone: keyof typeof DOT; status: string; brandId: number; title: string; line: string; to: string }) {
  const actions = <Link className={`${buttonClass("secondary")} col-span-2`} to={to} aria-label={`Open video ${title}`}>Open video</Link>;
  return (
    <Row status={<Status tone={tone}>{status}</Status>} where={<Where brandId={brandId}><span>{title}</span></Where>} actions={actions}>
      <p className="text-xs text-muted">{line}</p>
    </Row>
  );
}
