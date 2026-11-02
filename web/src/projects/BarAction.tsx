import { useCostBarAction, type CostAction } from "./CostBar";

/** Registers a pane's press with the cost bar only while it has one. Two panes on one tab (Clips: the stills and the
 *  takes) each render this instead of calling the hook, so the one with nothing to press never clears the other's. */
export function BarAction({ action }: { action: CostAction }) {
  useCostBarAction(action);
  return null;
}
