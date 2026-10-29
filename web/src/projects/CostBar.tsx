import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Button, creditsLabel, wholeCredits } from "../components";
import { ActionBar } from "../shell/ActionBar";
import { useRail } from "../useMedia";
import { Meter } from "./Meter";

/** The step's one amber, as the cost bar shows it: what runs, its price, and why it can't be pressed yet. */
export type CostAction = {
  label: string;
  /** Credits; null while the price isn't known yet (the press waits for it). Leave out for a free press. */
  price?: number | null;
  upTo?: boolean;
  usually?: number;
  reason?: string | null;
  busy?: boolean;
  onPress: () => void;
};

const Ctx = createContext<(a: CostAction | null) => void>(() => {});

/** A step registers its one amber here; the bar at the bottom of the video page shows it. Unregisters on unmount. */
export function useCostBarAction(action: CostAction | null) {
  const set = useContext(Ctx);
  const latest = useRef(action);
  useEffect(() => {
    latest.current = action;
  });
  // Re-registered only when what the bar shows changes; the press always runs the newest handler.
  const key = action && JSON.stringify({ ...action, onPress: undefined });
  useEffect(() => {
    set(action && { ...action, onPress: () => latest.current?.onPress() });
    return () => set(null);
  }, [key, set]); // eslint-disable-line react-hooks/exhaustive-deps
}

/** One cost bar per video: the budget, what finishing costs, and the step's amber with what it leaves. Credits only (rule 4). */
export function CostBarProvider(props: {
  projectId: number;
  used: number;
  budget: number;
  pct: number;
  /** An editor on their own script is billed to the week, not to a budget. */
  week: { used: number; allowed: number } | null;
  /** Set where the viewer may only look: the step's own press shows greyed out with this reason. */
  lookOnly?: string | null;
  /** The press when the step has none of its own (Next: …). */
  fallback: CostAction | null;
  children: ReactNode;
}) {
  const [action, setAction] = useState<CostAction | null>(null);
  const rail = useRail();
  const shown = action && props.lookOnly ? { ...action, reason: props.lookOnly } : (action ?? props.fallback);
  const estimate = useQuery({
    queryKey: ["project-estimate", props.projectId, props.used],
    queryFn: async () => (await api.GET("/projects/{project_id}/estimate", { params: { path: { project_id: props.projectId } } })).data ?? null,
  });
  const left = props.week ? props.week.allowed - props.week.used : props.budget - props.used;
  const after = shown?.price != null && !shown.reason ? left - shown.price : null;
  const value = useMemo(() => setAction, []);
  const press = shown && (
    <Button price={shown.price} upTo={shown.upTo} usually={shown.usually} reason={shown.reason} disabled={!!shown.reason} busy={shown.busy} onClick={shown.onPress}>
      {shown.label}
    </Button>
  );
  const bar = (
    <div role="region" aria-label="Cost" className={rail ? "sticky bottom-2 z-10 flex flex-wrap items-center gap-x-6 gap-y-2 rounded-md border border-border bg-surface p-3 shadow-md" : "space-y-2 text-left"}>
      <div className="min-w-48 flex-1">
        {props.week ? (
          <p className="text-sm tabular-nums text-muted">
            This week: {wholeCredits(props.week.used)} of {wholeCredits(props.week.allowed)} credits
          </p>
        ) : (
          <Meter used={props.used} budget={props.budget} pct={props.pct} />
        )}
      </div>
      {estimate.data && (
        <p className="text-sm tabular-nums text-muted">
          {estimate.data.remaining_credits === 0 ? "Nothing left to make." : `To finish: up to ${creditsLabel(estimate.data.remaining_credits)}`} · {wholeCredits(Math.max(0, left))} left
        </p>
      )}
      {press && (
        <div className="flex flex-col items-stretch gap-1 lg:items-end">
          {after !== null && <p className="text-xs tabular-nums text-muted">This press leaves {wholeCredits(Math.max(0, after))}</p>}
          {press}
        </div>
      )}
    </div>
  );
  return (
    <Ctx.Provider value={value}>
      {props.children}
      {rail ? bar : <ActionBar phone>{bar}</ActionBar>}
    </Ctx.Provider>
  );
}
