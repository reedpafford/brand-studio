/** "412 / 660 credits · 62%" with a thin bar. The state is said in words, not only colour. Credits only, never dollars. */
export function Meter({ used, budget, pct }: { used: number; budget: number; pct: number }) {
  const state = pct > 100 ? "Over budget" : pct >= 75 ? "Almost at budget" : "";
  const tone = pct > 100 ? "text-danger" : pct >= 75 ? "text-warning" : "text-accent-text";
  const bar = pct > 100 ? "bg-danger" : pct >= 75 ? "bg-warning" : "bg-accent";
  return (
    <span className="block space-y-1">
      <span className={`block text-sm tabular-nums ${tone}`}>
        {Math.round(used)} / {Math.round(budget)} credits · {Math.round(pct)}%{state && ` · ${state}`}
      </span>
      <span className="block h-2 overflow-hidden rounded-full bg-surface-2" aria-hidden>
        <span className={`block h-full rounded-full ${bar}`} style={{ width: `${Math.min(100, Math.max(0, pct))}%` }} />
      </span>
    </span>
  );
}

/** Work held for the owner says what it waits for and why, never a bare "Not started". */
export function WaitingBadge() {
  return (
    <span className="block space-y-0.5">
      <span className="inline-block rounded-sm bg-surface-3 px-2 py-0.5 text-xs font-medium text-muted">Waiting for the owner's OK</span>
      <span className="block text-sm text-muted">This would go past the video's budget.</span>
    </span>
  );
}
