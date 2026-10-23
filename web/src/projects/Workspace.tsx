import { btnPrimary, card } from "../ui";
import { BreakdownPane } from "./BreakdownPane";
import { Notes, type EnhanceState } from "./Enhance";

export const STAGES = [
  { id: "brief", label: "Brief" },
  { id: "script", label: "Script" },
  { id: "enhance", label: "Enhance" },
  { id: "breakdown", label: "Breakdown" },
  { id: "storyboard", label: "Storyboard" },
  { id: "clips", label: "Clips" },
] as const;
export type Stage = (typeof STAGES)[number]["id"];
const BUILT: Stage[] = ["brief", "script", "enhance", "breakdown"];

/** Why a stage can't be opened right now, or null when it can. */
export function lockReason(stage: Stage, hasScript: boolean): string | null {
  if (!BUILT.includes(stage)) return "Coming soon";
  if ((stage === "enhance" || stage === "breakdown") && !hasScript) return "Finish the script first";
  return null;
}

/** Where a link to a locked stage should land: the first stage not finished yet. */
export const firstUnfinished = (hasScript: boolean): Stage => (hasScript ? "enhance" : "script");

/** Done steps get a tick, the current one is filled, the ones not built yet say why they can't be opened. */
export function Stepper(props: { stage: Stage; done: Stage[]; hasScript: boolean; onPick: (s: Stage) => void }) {
  return (
    <>
      <ol className="hidden flex-wrap items-center gap-x-2 gap-y-1 text-sm lg:flex" aria-label="Stages">
        {STAGES.map((s, i) => {
          const why = lockReason(s.id, props.hasScript);
          const open = why === null;
          const current = s.id === props.stage;
          const done = props.done.includes(s.id);
          return (
            <li key={s.id} className="flex items-center gap-2">
              {i > 0 && <span aria-hidden className="text-faint">─</span>}
              <button
                type="button"
                disabled={!open}
                aria-current={current ? "step" : undefined}
                title={why ?? undefined}
                className={`rounded-sm px-2 py-1 ${current ? "bg-accent-soft font-medium text-accent-text" : open ? "text-text" : "text-faint"}`}
                onClick={() => props.onPick(s.id)}
              >
                {done && !current ? "✓ " : current ? "● " : ""}
                {s.label}
              </button>
            </li>
          );
        })}
      </ol>
      <label className="block text-sm lg:hidden">
        <span className="sr-only">Stage</span>
        <select
          aria-label="Stage"
          className="min-h-11 w-full rounded-sm border border-border-strong bg-surface px-2 text-base"
          value={props.stage}
          onChange={(e) => props.onPick(e.target.value as Stage)}
        >
          {STAGES.map((s) => {
            const why = lockReason(s.id, props.hasScript);
            return (
              <option key={s.id} value={s.id} disabled={why !== null}>
                {s.label}
                {why ? ` (${why.toLowerCase()})` : ""}
              </option>
            );
          })}
        </select>
      </label>
    </>
  );
}

export type BriefInfo = { goal: string; platform: string; aspect_ratio: string; format: string; planned_seconds: number };

/** The right-hand pane: what to do at the current stage. The script stays on the left. */
export function StagePane(props: { stage: Stage; brief: BriefInfo; hasScript: boolean; enhance: EnhanceState; version: number; projectId: number; brandId: number; used: number; budget: number; onPick: (s: Stage) => void }) {
  const { stage, brief } = props;
  if (stage === "brief")
    return (
      <section className={`${card} space-y-2 text-sm`} aria-label="Brief">
        <h2 className="text-[length:var(--text-md)] font-semibold">Brief</h2>
        {brief.goal ? <p>{brief.goal}</p> : <p className="text-muted">What's this video for? A few lines is enough. Claude turns it into a script.</p>}
        <p className="text-muted">{[brief.platform, brief.aspect_ratio, brief.format, `${brief.planned_seconds}s planned`].filter(Boolean).join(" · ")}</p>
        <button className={btnPrimary} onClick={() => props.onPick("script")}>
          Next: Script →
        </button>
      </section>
    );
  if (stage === "script")
    return (
      <section className={`${card} space-y-2 text-sm`} aria-label="Script stage">
        <h2 className="text-[length:var(--text-md)] font-semibold">Script</h2>
        <p className="text-muted">Paste your script or upload a document in the script pane. Every save is kept as a version, and you can come back to any of them from History.</p>
        <button className={btnPrimary} disabled={!props.hasScript} onClick={() => props.onPick("enhance")}>
          Next: Enhance →
        </button>
        {!props.hasScript && <p className="text-muted">Finish the script first.</p>}
      </section>
    );
  if (stage === "enhance")
    return (
      <div className="space-y-4">
        <section className={`${card} space-y-2 text-sm`} aria-label="Enhance stage">
          <h2 className="text-[length:var(--text-md)] font-semibold">Enhance</h2>
          <p className="text-muted">Claude suggests camera, movement, reactions and where brand screens show. It never changes your words. Nothing happens until you press Enhance in the script pane.</p>
        </section>
        <Notes e={props.enhance} />
      </div>
    );
  if (stage === "breakdown")
    return <BreakdownPane projectId={props.projectId} brandId={props.brandId} scriptVersion={props.version} plannedSeconds={brief.planned_seconds} used={props.used} budget={props.budget} />;
  return (
    <section className={`${card} text-sm`} aria-label="Coming soon">
      <h2 className="text-[length:var(--text-md)] font-semibold">Coming soon</h2>
      <p className="text-muted">This stage arrives with the next server release.</p>
    </section>
  );
}
