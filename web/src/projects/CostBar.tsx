import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useMe } from "../auth/useMe";
import { Button } from "../components";

/** The step's one amber, as the cost bar shows it: what runs, its price, and why it can't be pressed yet. */
export type CostAction = {
  label: string;
  /** Credits; null while the price isn't known yet (the press waits for it). Leave out for a free press. */
  price?: number | null;
  upTo?: boolean;
  usually?: number;
  reason?: string | null;
  busy?: boolean;
  /** A press that isn't the screen's one primary (the Director tab's Final cut, once its cut is made). */
  secondary?: boolean;
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

/** A step's one press, kept at the foot of its preview tab until the director does that step (v6: screen 4 removes it).
 *  The money is in the video's header now, so this is the press only. An editor's press past the budget is sent to the
 *  owner, never refused (Hold requests, #1068; never "Ask the owner"). Credits only (rule 4). */
export function CostBarProvider(props: {
  used: number;
  budget: number;
  /** Set where the viewer may only look: the step's own press shows greyed out with this reason. */
  lookOnly?: string | null;
  /** The press when the step has none of its own. */
  fallback: CostAction | null;
  children: ReactNode;
}) {
  const [action, setAction] = useState<CostAction | null>(null);
  const shown = action && props.lookOnly ? { ...action, reason: props.lookOnly } : (action ?? props.fallback);
  const editor = useMe().data?.role === "editor";
  const sends = editor && shown?.price != null && !shown.reason && shown.price > props.budget - props.used;
  const value = useMemo(() => setAction, []);
  return (
    <Ctx.Provider value={value}>
      {props.children}
      {shown && (
        <div role="region" aria-label="Step press" className="sticky bottom-0 z-10 -mx-5 mt-4 flex flex-col items-end gap-1 border-t border-border bg-bg/95 px-5 py-3">
          <Button variant={shown.secondary ? "secondary" : "primary"} price={shown.price} charge={shown.upTo ? "estimate" : "fixed"} usually={shown.usually} reason={shown.reason} disabled={!!shown.reason} busy={shown.busy} onClick={shown.onPress}>
            {sends ? "Send for approval" : shown.label}
          </Button>
          {sends && <p className="text-xs text-muted">Goes past the video's budget. Nothing is charged until the owner says yes.</p>}
        </div>
      )}
    </Ctx.Provider>
  );
}
