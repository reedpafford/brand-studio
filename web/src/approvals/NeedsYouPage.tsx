import { useState } from "react";
import { useMutation, useQueries } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { Navigate, useSearchParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import { useMe } from "../auth/useMe";
import { Banner, Button, creditsLabel, Dialog, EmptyState, PageTop, Skeleton, Tabs } from "../components";
import { FLAGS, reason, STEPS as AT, who } from "../production/ProductionPage";
import { ActionBar } from "../shell/ActionBar";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { useRail } from "../useMedia";
import { dollars, JobRow, ProjectRow, useRefresh, VideoRow } from "./Rows";
import { useChangesWaiting, useHeld, useStuck } from "./useHeld";

const TABS = ["all", "requests", "stuck", "changes"] as const;
type TabId = (typeof TABS)[number];
const NONE: Record<TabId, [string, string]> = {
  all: ["Nothing needs you.", "When an editor's press goes past a video's budget or their week, or they make songs, narration or music on a script, it waits here for you to approve or decline. Stuck videos and finished videos with changes show here too."],
  requests: ["No requests waiting.", "Editors' presses that need your OK show here."],
  stuck: ["Nothing is stuck.", "Every video being made is moving."],
  changes: ["No changes waiting.", "Finished videos whose clips changed since show here."],
};
const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

/** The owner's one inbox, across brands: requests to approve, stuck videos, and finished videos with changes waiting. */
export function NeedsYouPage() {
  const { data: me } = useMe();
  const owner = me?.role === "owner";
  const held = useHeld();
  const stuck = useStuck(owner);
  const changes = useChangesWaiting(owner);
  const toast = useToast();
  const refresh = useRefresh();
  const rail = useRail();
  const [params, setParams] = useSearchParams();
  const tab: TabId = TABS.find((t) => t === params.get("tab")) ?? "all";
  const [asking, setAsking] = useState(false);
  // Dollars are for the owner only, so they come from the owner-only detail of each job.
  const details = useQueries({
    queries: held.heldJobs.map((j) => ({
      enabled: owner,
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
  if (me && !owner) return <Navigate to="/" replace />; // the inbox is the owner's: an editor lands on Home
  if (!me || held.isPending || stuck.isPending || changes.isPending)
    return (
      <main className="mx-auto max-w-content space-y-4 p-4 sm:p-6" aria-label="Loading">
        <Skeleton className="h-10 w-1/3" />
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
      </main>
    );
  if (held.isError)
    return (
      <main className="mx-auto max-w-content p-4 sm:p-6">
        <Banner title="Couldn't load what needs you." action={<Button variant="secondary" onClick={() => void refresh()}>Try again</Button>}>
          Check your connection.
        </Banner>
      </main>
    );
  const stuckRows = stuck.data ?? [];
  const counts: Record<TabId, number> = { all: held.count + stuckRows.length + changes.rows.length, requests: held.count, stuck: stuckRows.length, changes: changes.rows.length };
  const credits = held.heldJobs.reduce((n, j) => n + (j.freestyle?.up_to ?? j.credits), 0); // what approving commits to: a Freestyle run its cap (rules 34, 36)
  const known = held.heldJobs.every((j) => usd.get(j.id) !== undefined);
  // A held Freestyle's dollars are its first turn's; scale them to its up to at the same rate, so the owner's total matches the credits.
  const totalUsd = held.heldJobs.reduce((n, j) => n + (usd.get(j.id) ?? 0) * (j.freestyle?.up_to != null && j.credits > 0 ? j.freestyle.up_to / j.credits : 1), 0);
  const money = known && held.heldJobs.length > 0 ? ` (${dollars(totalUsd)})` : "";
  const worth = held.count > 0 ? ` · ${plural(held.count, "request")}${credits > 0 ? ` worth ${creditsLabel(credits)}${money}` : ""}` : "";
  const all = (
    <Button charge="estimate" price={credits > 0 ? credits : undefined} disabled={held.count === 0} busy={approveAll.isPending} onClick={() => setAsking(true)}>
      Approve all
    </Button>
  );
  const show = (t: TabId) => tab === "all" || tab === t;
  const rows = [
    ...(show("requests") ? held.heldJobs.map((j) => <JobRow key={`job-${j.id}`} job={j} projects={held.projects} usd={usd.get(j.id)} />) : []),
    ...(show("requests") ? held.heldProjects.map((p) => <ProjectRow key={`project-${p.id}`} project={p} heldJobs={held.allHeldJobs.filter((j) => j.project_id === p.id).length} />) : []),
    ...(show("stuck")
      ? stuckRows.map((r) => (
          <VideoRow key={`stuck-${r.project_id}`} tone={r.flag === "failed" ? "danger" : "warning"} status={r.flag ? FLAGS[r.flag].label : "Stuck"} brandId={r.brand.id} title={`${r.script.title} · ${r.letter}`}
            line={[r.flag === "failed" ? "" : `At ${AT[r.step]}`, reason(r), who(r)].filter(Boolean).join(" · ")} to={`/b/${r.brand.id}/videos/${r.project_id}`} />
        ))
      : []),
    ...(show("changes")
      ? changes.rows.map((v) => (
          <VideoRow key={`changes-${v.project_id}`} tone="warning" status="Changes waiting" brandId={v.brand_id} title={v.title}
            line={["Finished, then its clips changed. Make the final cut again to use them.", v.person?.name].filter(Boolean).join(" · ")} to={`/b/${v.brand_id}/videos/${v.project_id}?step=final`} />
        ))
      : []),
  ];
  const [title, hint] = NONE[tab];
  return (
    <main className="mx-auto max-w-content space-y-4 p-4 sm:p-6">
      <PageTop title="Needs you" line={`Every brand · ${plural(counts.all, "thing")}${worth}`}>
        {held.count > 0 && rail && all}
      </PageTop>
      {held.count > 0 && !rail && <ActionBar phone>{all}</ActionBar>}
      {/* On a phone "Changes waiting" is "Changes", so the four tabs fit across 390 px. */}
      <div className="-mx-4 border-b border-border -mt-4 px-4 py-2 sm:-mx-6 sm:px-6">
        <Tabs label="Show" value={tab} onChange={(t) => setParams(t === "all" ? {} : { tab: t }, { replace: true })} tabs={[
          { id: "all", label: "All", count: counts.all },
          { id: "requests", label: "Requests", count: counts.requests },
          { id: "stuck", label: "Stuck", count: counts.stuck },
          { id: "changes", label: rail ? "Changes waiting" : "Changes", count: counts.changes },
        ]} />
      </div>
      {approveAll.isError && <p role="alert" className={errorClass}>{approveAll.error.message}</p>}
      {(stuck.isError || changes.isError) && (
        <Banner title="Couldn't load every video that needs you." action={<Button variant="secondary" onClick={() => void Promise.all([stuck.refetch(), changes.refetch()])}>Try again</Button>}>
          Requests are all here. Check your connection.
        </Banner>
      )}
      {rows.length === 0 ? (
        <EmptyState icon={Bell} title={title}>{hint}</EmptyState>
      ) : (
        <ul className="space-y-3 lg:-mx-6 lg:-mt-4 lg:space-y-0">{rows}</ul>
      )}
      {asking && (
        <Dialog title={`Approve ${plural(held.count, "request")} for ${creditsLabel(credits)}${money}?`} cancelLabel="Keep them" actionLabel="Approve all" busy={approveAll.isPending} onCancel={() => setAsking(false)} onConfirm={() => approveAll.mutate()}>
          Everything waiting starts now.
        </Dialog>
      )}
    </main>
  );
}
