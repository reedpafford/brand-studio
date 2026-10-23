import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, Navigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { linkText, pageTitle } from "../ui";
import { useEnhance } from "./Enhance";
import { useBreakdown } from "./BreakdownPane";
import { Meter, WaitingBadge } from "./Meter";
import { ScriptTab, useLatestScript } from "./ScriptTab";
import { STAGES, StagePane, Stepper, firstUnfinished, lockReason, type Stage } from "./Workspace";

/** One video: the stage steps along the top, the script always on the left, what to do next on the right. */
export function ProjectPage() {
  const { brandId = "", projectId } = useParams();
  const id = Number(projectId);
  const [params, setParams] = useSearchParams();
  const asked = params.get("stage") ?? (params.get("tab") === "script" ? "script" : "brief");
  const stage = (STAGES.some((s) => s.id === asked) ? asked : "brief") as Stage;
  const [pane, setPane] = useState<"script" | "stage">("script");
  const [highlight, setHighlight] = useState<number[]>([]);
  const [line, setLine] = useState<number | null>(null);
  const project = useQuery({
    queryKey: ["project", id],
    queryFn: async () => (await api.GET("/projects/{project_id}", { params: { path: { project_id: id } } })).data ?? null,
  });
  const script = useLatestScript(id);
  const enhance = useEnhance(id, script.data?.version, script.data?.text);
  const breakdown = useBreakdown(id, script.data?.version ?? 0);
  if (project.isPending || script.isPending || breakdown.isPending) return <p className="p-6 text-muted">Loading…</p>;
  const p = project.data;
  if (!p) return <p className="p-6">That project doesn't exist.</p>;
  const hasScript = !!script.data;
  const ready = { script: hasScript, breakdown: !!breakdown.data, breakdownOk: !!breakdown.data && !breakdown.data.stale && breakdown.data.problems.length === 0 };
  // A link to a stage that is locked lands on the first stage that is not finished yet.
  if (lockReason(stage, ready) !== null) return <Navigate to={`?stage=${firstUnfinished(ready)}`} replace />;
  const pick = (s: Stage) => setParams(s === "brief" ? {} : { stage: s });
  const bd = breakdown.data;
  const done: Stage[] = ["brief", ...(script.data ? (["script"] as Stage[]) : []), ...(bd && !bd.stale && bd.problems.length === 0 ? (["breakdown"] as Stage[]) : [])];

  return (
    <main className="mx-auto max-w-7xl space-y-4 p-4 sm:p-6">
      <Link to={`/b/${brandId}/projects`} className={linkText}>
        ← Projects
      </Link>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className={pageTitle}>{p.name}</h1>
        <div className="w-full sm:w-72">
          <Meter used={p.credits_used} budget={p.budget_credits} pct={p.budget_pct} />
        </div>
      </div>
      {p.status === "needs_owner_approval" && <WaitingBadge />}
      <Stepper stage={stage} done={done} ready={ready} onPick={pick} />
      <div role="tablist" className="flex gap-1 text-sm lg:hidden">
        {(["script", "stage"] as const).map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={pane === t}
            className={`min-h-11 flex-1 rounded-sm px-3 ${pane === t ? "bg-accent-soft font-medium text-accent-text" : "text-muted"}`}
            onClick={() => setPane(t)}
          >
            {t === "script" ? "Script" : STAGES.find((s) => s.id === stage)?.label}
          </button>
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-[minmax(360px,3fr)_minmax(320px,2fr)]">
        <div className={pane === "script" ? "" : "hidden lg:block"}>
          <ScriptTab
            projectId={id}
            enhance={enhance}
            highlight={highlight}
            onLineClick={
              stage === "breakdown"
                ? (n) => {
                    setLine(n);
                    setHighlight([n]);
                    setPane("stage");
                  }
                : undefined
            }
          />
        </div>
        <div className={pane === "stage" ? "" : "hidden lg:block"}>
          <StagePane stage={stage} brief={p} hasScript={hasScript} enhance={enhance} version={script.data?.version ?? 0} projectId={id} brandId={p.brand_id} used={p.credits_used}
            budget={p.budget_credits}
            line={line}
            onShowLines={(lines) => {
              setHighlight(lines);
              setLine(null);
              setPane("script");
            }}
            onPick={pick}
          />
        </div>
      </div>
    </main>
  );
}
