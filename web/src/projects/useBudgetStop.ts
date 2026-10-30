import { useMe } from "../auth/useMe";

/** An editor is never asked to send a spend to the owner: past the video's budget the paid button is disabled with the reason.
 *  The owner is never stopped (pressing past a budget is their approval). Returns why a price is declined, or null. */
export function useBudgetStop(video?: { used: number; budget: number }) {
  const editor = useMe().data?.role === "editor";
  return (cost: number | undefined): string | null => (cost !== undefined && editor && video && video.used + cost > video.budget ? "That's more than this video's budget." : null);
}
