import type { ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { Skeleton } from "../components";
import type { Period } from "./useUsage";
import { serverTime } from "../time";

/** "$1,204.50": always two decimals. */
export const money = (n: number) => `${n < 0 ? "−" : ""}$${Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const signed = (n: number, text: string) => `${n < 0 ? "−" : "+"}${text}`;

const PERIODS: { id: Period; label: string }[] = [
  { id: "week", label: "This week" },
  { id: "month", label: "This month" },
  { id: "all", label: "All time" },
];
export const periodWord = (p: Period) => (p === "week" ? "this week" : p === "month" ? "this month" : "all time");

/** "2026-11" for this month, and the eleven before it, newest first (v5 D_Usage and D_MyCredits' month picker). */
export function months(now = new Date()) {
  return Array.from({ length: 12 }, (_, i) => {
    const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - i, 1));
    return { id: d.toISOString().slice(0, 7), label: d.toLocaleDateString("en-GB", { month: "long", year: d.getUTCFullYear() === now.getUTCFullYear() ? undefined : "numeric", timeZone: "UTC" }) };
  });
}

/** The page's month, kept in the address (?month=2026-10; none for this month). */
export function useMonth() {
  const [params, setParams] = useSearchParams();
  const options = months();
  const picked = options.find((m) => m.id === params.get("month")) ?? options[0];
  const set = (id: string) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (id === options[0].id) next.delete("month");
        else next.set("month", id);
        return next;
      },
      { replace: true },
    );
  return { month: picked.id, label: picked.label, thisMonth: picked === options[0], options, set };
}

/** The owner's Usage period (Reed, 9 Nov: this week, this month, all time), or an earlier month, kept in the address
 *  (?period=week|all or ?month=2026-10; none for this month). `query` is what the server is asked; `csv` the month to download. */
export function useSpan() {
  const [params, setParams] = useSearchParams();
  const [now, ...before] = months();
  const earlier = before.find((m) => m.id === params.get("month"));
  const asked = params.get("period");
  const value = earlier?.id ?? (asked === "week" || asked === "all" ? asked : "month");
  const set = (id: string) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("period");
        next.delete("month");
        if (id === "week" || id === "all") next.set("period", id);
        else if (id !== "month") next.set("month", id);
        return next;
      },
      { replace: true },
    );
  const words = earlier ? `in ${earlier.label}` : value === "all" ? "so far" : periodWord(value as Period);
  const query: { period?: Period; month?: string } = earlier ? { month: earlier.id } : { period: value as Period };
  return { value, options: [...PERIODS, ...before], set, words, query, csv: earlier?.id ?? now.id };
}

export function MonthPicker({ value, options, onChange, label = "Month" }: { value: string; options: { id: string; label: string }[]; onChange: (id: string) => void; label?: string }) {
  return (
    <span className="relative inline-flex">
      <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)} className="min-h-control appearance-none rounded-md border border-border bg-transparent pl-3 pr-8 text-sm font-medium hover:bg-surface-2 lg:min-h-control-dense">
        {options.map((m) => (
          <option key={m.id} value={m.id}>{m.label}</option>
        ))}
      </select>
      <ChevronDown size={14} strokeWidth={1.75} aria-hidden className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-muted" />
    </span>
  );
}

/** One period for the whole page, kept in the address. */
export function PeriodControl({ value, onChange }: { value: Period; onChange: (p: Period) => void }) {
  return (
    <div role="radiogroup" aria-label="Period" className="grid w-full grid-cols-3 rounded-lg border border-border bg-surface p-1 lg:flex lg:w-auto">
      {PERIODS.map((p) => (
        <button key={p.id} type="button" role="radio" aria-checked={value === p.id} onClick={() => onChange(p.id)} className={`min-h-control whitespace-nowrap rounded-md px-2 font-medium sm:px-4 lg:min-h-control-dense ${value === p.id ? "bg-surface-2 text-text" : "text-muted hover:text-text"}`}>
          {p.label}
        </button>
      ))}
    </div>
  );
}

/** "Week of 20 Oct", "October 2026", "Everything so far". */
export function periodLine(period: Period, startsAt: string | null) {
  if (period === "all" || !startsAt) return "Everything so far";
  const d = serverTime(startsAt);
  return period === "week" ? `Week of ${d.toLocaleDateString("en-GB", { day: "numeric", month: "short" })}` : d.toLocaleDateString(undefined, { month: "long", year: "numeric" });
}

type Figures = { spend_usd: number; spend_estimated: boolean; finished: number; cost_per_finished_usd: number | null; in_progress: number; previous: { spend_usd: number; finished: number; cost_per_finished_usd: number | null } | null };

/** "≈ $30.62" when some of it is an estimate; the tooltip says so. */
export function Money({ value, estimated }: { value: number; estimated: boolean }) {
  return estimated ? (
    <span title="Some of this is an estimate: the provider didn't report the exact cost.">≈ {money(value)}</span>
  ) : (
    <>{money(value)}</>
  );
}

export function Stat({ label, children, note, link }: { label: string; children: ReactNode; note?: string | null; /** Shown on phones too, unlike the note. */ link?: ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <p className="text-sm text-muted">{label}</p>
      <p className="text-lg font-bold tabular-nums lg:text-2xl">{children}</p>
      {note && <p className="hidden text-sm text-muted lg:block">{note}</p>}
      {link && <p className="text-sm">{link}</p>}
    </div>
  );
}

/** Spent, Finished, Cost per finished video, In progress. The comparison with the period before is plain text. */
export function Stats({ figures: f, period }: { figures?: Figures; period: Period }) {
  const last = period === "week" ? "on last week" : "on last month";
  const p = f?.previous;
  const dollars = (now: number, before: number) => (now === before ? null : `${signed(now - before, money(Math.abs(now - before)))} ${last}`);
  return (
    <div role="group" aria-label="Totals" className="grid grid-cols-2 gap-3 lg:grid-cols-[repeat(auto-fit,minmax(10rem,1fr))]">
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
  const mins = Math.floor((now - serverTime(iso).getTime()) / 60000);
  if (mins < 60) return `${Math.max(mins, 1)} min`;
  if (mins < 24 * 60) return `${Math.floor(mins / 60)} h`;
  const days = Math.floor(mins / (24 * 60));
  if (days < 2) return "yesterday";
  if (days < 7) return `${days} days`;
  return serverTime(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}
