// The director's own turns never count toward a video's budget (DECISIONS #1066); the hold check leaves them out, so every
// budget figure on screen does too. `director_credits` is the server's sum of those turns (0 until it sends it).
type Spend = { credits_used: number; budget_credits: number; director_credits?: number | null };

/** What counts against the video's budget: its spend without the director's own time. */
export const budgetUsed = (p: Spend) => Math.max(0, p.credits_used - (p.director_credits ?? 0));
/** The same as a share of the budget, as the server rounds budget_pct. */
export const budgetPct = (p: Spend) => (p.budget_credits > 0 ? Math.round((budgetUsed(p) / p.budget_credits) * 1000) / 10 : 0);
/** The director's own time on this video, shown apart from the budget; 0 when it never ran. */
export const directorTime = (p: Spend) => p.director_credits ?? 0;
