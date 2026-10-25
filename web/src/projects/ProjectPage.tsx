import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, FileText, Pencil } from "lucide-react";
import { Link, Navigate, useParams, useSearchParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import { Button, Card, Field, Skeleton, StepPicker } from "../components";
import { ActionBar } from "../shell/ActionBar";
import { useRail } from "../useMedia";
import { BreakdownPane } from "./BreakdownPane";
import { BriefEditor } from "./BriefEditor";
import { ClipsPane } from "./ClipsPane";
import { Notes, useEnhance } from "./Enhance";
import { EstimateNote } from "./EstimateNote";
import { FinalPane } from "./FinalPane";
import { Meter, WaitingBadge } from "./Meter";
import { ScriptPanel } from "./ScriptPanel";
import { ScriptTab } from "./ScriptTab";
import { StoryboardPane } from "./StoryboardPane";
import { STEPS, firstUnfinished, lockReason, nextOf, stepFromParams, stepStates, type StepId } from "./steps";
import { useProgress } from "./useProgress";

/** One video: header with the credits, six steps, the step's work, one Next button, and the Script on demand. */
export function ProjectPage() {
  const { brandId = "", projectId } = useParams();
  const id = Number(projectId);
  const [params, setParams] = useSearchParams();
  const step = stepFromParams(params);
  const rail = useRail();
  const queryClient = useQueryClient();
  const [panel, setPanel] = useState(false);
  const [highlight, setHighlight] = useState<number[]>([]);
  const [line, setLine] = useState<number | null>(null);
  const [dirty, setDirty] = useState(false); // unsaved edits in Shots
  const [editingBrief, setEditingBrief] = useState(false);
  const [renaming, setRenaming] = useState<string | null>(null);
  const project = useQuery({
    queryKey: ["project", id],
    queryFn: async () => (await api.GET("/projects/{project_id}", { params: { path: { project_id: id } } })).data ?? null,
  });
  const { progress, loading, script } = useProgress(id);
  const enhance = useEnhance(id, script.data?.version, script.data?.text);
  const rename = useMutation({
    mutationFn: async (name: string) => {
      const { error, response } = await api.PATCH("/projects/{project_id}", { params: { path: { project_id: id } }, body: { name } });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: async () => {
      await Promise.all([queryClient.invalidateQueries({ queryKey: ["project", id] }), queryClient.invalidateQueries({ queryKey: ["projects"] })]);
      setRenaming(null);
    },
  });

  if (project.isPending || loading)
    return (
      <div className="mx-auto max-w-content space-y-4 p-4 sm:p-8" role="status" aria-label="Loading">
        <Skeleton className="h-10 w-1/2" />
        <Skeleton className="h-12" />
        <Skeleton className="h-64" />
      </div>
    );
  const p = project.data;
  if (!p) return <p className="p-6">That video doesn't exist.</p>;
  // A link to a step that is locked lands on the first step that is not finished yet.
  if (lockReason(step, progress) !== null) return <Navigate to={`?stage=${firstUnfinished(progress)}`} replace />;

  const pick = (to: string) => {
    setParams(to === "brief" ? {} : { stage: to });
    setPanel(false);
  };
  const showLines = (lines: number[]) => {
    setHighlight(lines);
    setLine(null);
    setPanel(true);
  };
  const label = STEPS.find((s) => s.id === step)?.label;
  const next = nextOf(step);
  const nextReason = next ? (step === "shots" && dirty ? "Save your changes first." : lockReason(next.id, progress)) : null;
  // While directions are accepted but not added yet, "Add N directions" is the amber button, so Next steps aside.
  const adding = step === "script" && enhance.marks.some((m) => m.status === "accepted");
  const nextButton = next && !(step === "brief" && editingBrief) && !adding && (
    <Button disabled={nextReason !== null} reason={nextReason} onClick={() => pick(next.id)}>
      Next: {next.label}
    </Button>
  );
  const fromShotsOn = step !== "brief" && step !== "script";

  return (
    <main className={`mx-auto max-w-content space-y-4 p-4 sm:p-8 ${rail ? "" : "pb-28"}`}>
      {rail ? (
        <Link to={`/b/${brandId}/projects`} className="inline-flex min-h-control items-center gap-1 text-accent-text hover:underline sm:min-h-control-dense">
          <ChevronLeft size={20} strokeWidth={1.75} aria-hidden />
          Videos
        </Link>
      ) : (
        // On a phone the video's own line replaces the brand bar: back, name, how much is used, and a thin meter.
        <div className="sticky top-0 z-20 -mx-4 -mt-4 border-b border-border bg-bg">
          <div className="flex h-14 items-center gap-1 px-2">
            <Link to={`/b/${brandId}/projects`} aria-label="Videos" className="grid size-control shrink-0 place-items-center rounded-md text-accent-text hover:bg-surface-2">
              <ChevronLeft size={20} strokeWidth={1.75} aria-hidden />
            </Link>
            {renaming === null ? (
              <>
                <h1 className="min-w-0 flex-1 truncate type-card">{p.name}</h1>
                <span className={`shrink-0 text-sm font-medium tabular-nums ${p.budget_pct > 100 ? "text-danger" : p.budget_pct >= 75 ? "text-warning" : "text-accent-text"}`}>
                  {Math.round(p.budget_pct)}%<span className="sr-only"> of the budget used</span>
                </span>
                <button type="button" aria-label="Rename" onClick={() => setRenaming(p.name)} className="grid size-control shrink-0 place-items-center rounded-md text-muted hover:bg-surface-2">
                  <Pencil size={20} strokeWidth={1.75} aria-hidden />
                </button>
              </>
            ) : (
              <span className="flex-1 truncate type-card">Rename</span>
            )}
          </div>
          <div className="h-1 bg-surface-2" aria-hidden>
            <div className={`h-full ${p.budget_pct > 100 ? "bg-danger" : p.budget_pct >= 75 ? "bg-warning" : "bg-accent"}`} style={{ width: `${Math.min(100, Math.max(0, p.budget_pct))}%` }} />
          </div>
        </div>
      )}
      <div className="flex flex-wrap items-start justify-between gap-3">
        {renaming === null ? (
          rail && (
            <h1 className="flex min-w-0 items-center gap-2 type-page">
              <span className="min-w-0 break-words">{p.name}</span>
              <button type="button" aria-label="Rename" onClick={() => setRenaming(p.name)} className="grid size-control shrink-0 place-items-center rounded-md text-muted hover:bg-surface-2">
                <Pencil size={20} strokeWidth={1.75} aria-hidden />
              </button>
            </h1>
          )
        ) : (
          <form
            className="flex min-w-0 flex-1 flex-wrap items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (renaming.trim()) rename.mutate(renaming.trim());
            }}
          >
            <div className="min-w-0 flex-1">
              <Field label="Name" value={renaming} onChange={(e) => setRenaming(e.target.value)} error={rename.isError ? rename.error.message : null} maxLength={120} autoFocus />
            </div>
            <Button type="submit" busy={rename.isPending} disabled={!renaming.trim()}>
              Save
            </Button>
            <Button variant="ghost" onClick={() => setRenaming(null)}>
              Cancel
            </Button>
          </form>
        )}
        {rail && (
          <div className="flex w-auto items-start gap-3">
            <div className="min-w-0 w-72">
              <Meter used={p.credits_used} budget={p.budget_credits} pct={p.budget_pct} />
              <EstimateNote projectId={id} used={p.credits_used} budget={p.budget_credits} />
            </div>
          </div>
        )}
      </div>
      {p.status === "needs_owner_approval" && <WaitingBadge />}
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <StepPicker steps={stepStates(step, progress)} onPick={pick} />
        </div>
        {fromShotsOn && (
          <Button variant="secondary" dense icon={FileText} onClick={() => setPanel(true)} aria-label="Show script">
            {rail ? "Script" : ""}
          </Button>
        )}
      </div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h2 className="type-section">{label}</h2>
        {rail ? nextButton : nextButton && <ActionBar phone>{nextButton}</ActionBar>}
      </div>
      {step === "brief" && (
        <Card>
          <BriefEditor project={p} hasScript={progress.script} onEditing={setEditingBrief} />
        </Card>
      )}
      {step === "script" && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="min-w-0">
            <ScriptTab projectId={id} used={p.credits_used} budget={p.budget_credits} enhance={enhance} />
          </div>
          <div className="min-w-0">
            <Notes e={enhance} />
          </div>
        </div>
      )}
      {step === "shots" && <BreakdownPane projectId={id} brandId={p.brand_id} scriptVersion={script.data?.version ?? 0} plannedSeconds={p.planned_seconds} used={p.credits_used} budget={p.budget_credits} line={line} onShowLines={showLines} onDirty={setDirty} />}
      {step === "storyboard" && <StoryboardPane projectId={id} brandId={p.brand_id} aspect={p.aspect_ratio} used={p.credits_used} budget={p.budget_credits} />}
      {step === "clips" && <ClipsPane projectId={id} brandId={p.brand_id} aspect={p.aspect_ratio} projectName={p.name} used={p.credits_used} budget={p.budget_credits} />}
      {step === "final" && <FinalPane projectId={id} aspect={p.aspect_ratio} projectName={p.name} />}
      {!rail && (
        <Card>
          <Meter used={p.credits_used} budget={p.budget_credits} pct={p.budget_pct} />
          <EstimateNote projectId={id} used={p.credits_used} budget={p.budget_credits} />
        </Card>
      )}
      {panel && (
        <ScriptPanel
          projectId={id}
          rail={rail}
          highlight={highlight}
          onLineClick={
            step === "shots"
              ? (n) => {
                  setLine(n);
                  setHighlight([n]);
                  if (!rail) setPanel(false);
                }
              : undefined
          }
          onEdit={() => pick("script")}
          onClose={() => setPanel(false)}
        />
      )}
    </main>
  );
}

export type { StepId };
