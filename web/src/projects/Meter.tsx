/** "412 / 660 credits · 62%". Calm under 75%, warning from 75%, danger over 100%. Credits only, never dollars. */
export function Meter({ used, budget, pct }: { used: number; budget: number; pct: number }) {
  const tone = pct > 100 ? "bg-danger-soft text-danger" : pct >= 75 ? "bg-warning-soft text-warning" : "bg-accent-soft text-accent-text";
  return (
    <span className={`inline-block rounded-full px-3 py-1 text-sm tabular-nums ${tone}`}>
      {Math.round(used)} / {Math.round(budget)} credits · {Math.round(pct)}%
    </span>
  );
}
