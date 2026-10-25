import type { ReactNode } from "react";
import { Skeleton } from "../components";
import type { Period } from "./useUsage";

/** "$1,204.50": always two decimals. */
export const money = (n: number) => `${n < 0 ? "−" : ""}$${Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const signed = (n: number, text: string) => `${n < 0 ? "−" : "+"}${text}`;

const PERIODS: { id: Period; label: string }[] = [
  { id: "week", label: "This week" },
  { id: "month", label: "This month" },
  { id: "all", label: "All time" },
];
export const periodWord = (p: Period) => (p === "week" ? "this week" : p === "month" ? "this month" : "all time");

/** One period for the whole page, kept in the address. */
export function PeriodControl({ value, onChange }: { value: Period; onChange: (p: Period) => void }) {
  return (
    <div role="radiogroup" aria-label="Period" className="flex w-full rounded-lg border border-border bg-surface p-1 lg:w-auto">
      {PERIODS.map((p) => (
        <button key={p.id} type="button" role="radio" aria-checked={value === p.id} onClick={() => onChange(p.id)} className={`min-h-control flex-1 rounded-md px-4 font-medium lg:min-h-control-dense lg:flex-none ${value === p.id ? "bg-surface-2 text-text" : "text-muted hover:text-text"}`}>
          {p.label}
        </button>
      ))}
    </div>
  );
}

/** "Week of 20 Oct", "October 2026", "Everything so far". */
export function periodLine(period: Period, startsAt: string | null) {
  if (period === "all" || !startsAt) return "Everything so far";
  const d = new Date(startsAt);
  return period === "week" ? `Week of ${d.toLocaleDateString("en-GB", { day: "numeric", month: "short" })}` : d.toLocaleDateString(undefined, { month: "long", year: "numeric" });
}

export type Figures = { spend_usd: number; spend_estimated: boolean; finished: number; cost_per_finished_usd: number | null; in_progress: number; previous: { spend_usd: number; finished: number; cost_per_finished_usd: number | null } | null };

/** "≈ $30.62" when some of it is an estimate; the tooltip says so. */
export function Money({ value, estimated }: { value: number; estimated: boolean }) {
  return estimated ? (
    <span title="Some of this is an estimate: the provider didn't report the exact cost.">≈ {money(value)}</span>
  ) : (
    <>{money(value)}</>
  );
}

function Stat({ label, children, note }: { label: string; children: ReactNode; note?: string | null }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <p className="text-sm text-muted">{label}</p>
      <p className="text-lg font-bold tabular-nums lg:text-2xl">{children}</p>
      {note && <p className="hidden text-sm text-muted lg:block">{note}</p>}
    </div>
  );
}

/** Spent, Finished, Cost per finished video, In progress. The comparison with the period before is plain text. */
export function Stats({ figures: f, period }: { figures?: Figures; period: Period }) {
  const last = period === "week" ? "on last week" : "on last month";
  const p = f?.previous;
  const dollars = (now: number, before: number) => (now === before ? null : `${signed(now - before, money(Math.abs(now - before)))} ${last}`);
  return (
    <div role="group" aria-label="Totals" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {!f ? (
        [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24" />)
      ) : (
        <>
          <Stat label="Spent" note={p && dollars(f.spend_usd, p.spend_usd)}>
            <Money value={f.spend_usd} estimated={f.spend_estimated} />
          </Stat>
          <Stat label="Finished" note={p && f.finished !== p.finished ? `${signed(f.finished - p.finished, String(Math.abs(f.finished - p.finished)))} ${last}` : null}>
            {f.finished} {f.finished === 1 ? "video" : "videos"}
          </Stat>
          <Stat label="Cost per finished video" note={p && f.cost_per_finished_usd !== null && p.cost_per_finished_usd !== null ? dollars(f.cost_per_finished_usd, p.cost_per_finished_usd) : null}>
            {f.cost_per_finished_usd === null ? "—" : money(f.cost_per_finished_usd)}
          </Stat>
          <Stat label="In progress">
            {f.in_progress} {f.in_progress === 1 ? "video" : "videos"}
          </Stat>
        </>
      )}
    </div>
  );
}

/** "2 h", "yesterday", "12 Oct", or "—". */
export function lastText(iso: string | null, now = Date.now()) {
  if (!iso) return "—";
  const mins = Math.floor((now - new Date(iso).getTime()) / 60000);
  if (mins < 60) return `${Math.max(mins, 1)} min`;
  if (mins < 24 * 60) return `${Math.floor(mins / 60)} h`;
  const days = Math.floor(mins / (24 * 60));
  if (days < 2) return "yesterday";
  if (days < 7) return `${days} days`;
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}
