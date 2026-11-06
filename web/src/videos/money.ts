import { wholeCredits } from "../components";
import type { Head } from "./VideoHead";

/** A press's price in the preview panel, as the boards write it: the owner sees dollars, an editor credits (rule 4), and
 *  every price before a charge says "up to", rounded up so it's never below what it can charge (rule 36). */
export function upTo(head: Head | undefined, credits: number) {
  const rate = head?.usd_per_credit;
  if (rate != null) return `up to $${(Math.ceil(credits * rate * 100 - 1e-9) / 100).toFixed(2)}`;
  if (credits > 0 && credits < 1) return "under 1 credit"; // S6-06: Add sound effects
  const n = wholeCredits(credits);
  return `up to ${n} credit${n === 1 ? "" : "s"}`;
}

/** What was spent, in the owner's dollars or the editor's credits ("$0.64", "6 credits"). */
export function spent(head: Head | undefined, credits: number) {
  const rate = head?.usd_per_credit;
  if (rate != null) return `$${(Math.ceil(credits * rate * 100 - 1e-9) / 100).toFixed(2)}`;
  if (credits <= 0) return "nothing yet";
  const n = wholeCredits(credits);
  return n <= 1 && credits < 1 ? "under 1 credit" : `${n} credit${n === 1 ? "" : "s"}`;
}

/** What the video has spent, exactly as its header says it (the server's own figure: the owner's dollars, an editor's
 *  whole credits), so the two always agree on one screen; else from `credits`. */
export function spentAsHeader(head: Head | undefined, credits: number) {
  const m = head?.spent;
  if (m?.usd != null) return `$${m.usd.toFixed(2)}`;
  const n = Math.round(m ? m.credits : credits);
  return `${n} credit${n === 1 ? "" : "s"}`;
}

/** "N credit" or "N credits". */
export const credits = (n: number) => `${n} credit${n === 1 ? "" : "s"}`;
