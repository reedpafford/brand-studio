import { useState } from "react";
import { ChartColumn, ChevronRight, Search } from "lucide-react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, must } from "../api/client";
import type { components } from "../api/schema";
import { Badge, Banner, Button, creditsLabel, EmptyState, PageTop, Select, Sheet, Skeleton } from "../components";
import { useHeld } from "../approvals/useHeld";
import { linkText } from "../ui";
import { useRail } from "../useMedia";
import { useDebounced } from "../scripts/status";
import { useRestoreBrand } from "../brand/ArchiveBrand";
import { Charges } from "./Charges";
import { Money, PeriodControl, Stat, Stats, lastText, money, periodLine, periodWord } from "./parts";
import { periodFrom, useBrandRows, useSummary, type BrandRow, type Sort } from "./useUsage";

type Person = components["schemas"]["PersonRow"];

const SORTS: { id: Sort; label: string }[] = [
  { id: "spend", label: "Most spent" },
  { id: "finished", label: "Most finished" },
  { id: "cost", label: "Cost per video (high first)" },
  { id: "activity", label: "Last activity" },
  { id: "name", label: "Name A–Z" },
];
const sortFrom = (s: string | null): Sort => SORTS.find((x) => x.id === s)?.id ?? "spend";

const Dot = ({ colour }: { colour: string | null }) => <span aria-hidden className="size-3 shrink-0 rounded-full bg-faint" style={colour ? { background: colour } : undefined} />;

/** Reed's brand tracker: what each brand spent, how many videos it finished, and what a finished video costs. */
export function UsagePage() {
  const [params, setParams] = useSearchParams();
  const rail = useRail();
  const period = periodFrom(params.get("period"));
  const sort = sortFrom(params.get("sort"));
  const archived = params.get("archived") === "1";
  const [text, setText] = useState(params.get("q") ?? "");
  const q = useDebounced(text.trim());
  const [sheet, setSheet] = useState(false);
  const set = (key: string, value: string) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (value) next.set(key, value);
        else next.delete(key);
        return next;
      },
      { replace: true },
    );
  const restoreBrand = useRestoreBrand();
  const summary = useSummary(period);
  const rows = useBrandRows({ period, q, archived, sort });
  const held = useHeld();
  const waitingCredits = held.heldJobs.reduce((n, j) => n + (j.freestyle?.up_to ?? j.credits), 0); // as Needs you counts it
  if (summary.error?.message === "404") return <Navigate to="/usage/mine" replace />; // an editor: their own credits (OR4)
  const items = rows.data?.pages.flatMap((p) => p.items) ?? [];
  const total = rows.data?.pages[0]?.total;
  const nothingSpent = summary.data && summary.data.spend_usd === 0 && !summary.data.spend_estimated;

  const sortSelect = (
    <Select label="Sort" value={sort} onChange={(e) => set("sort", e.target.value === "spend" ? "" : e.target.value)}>
      {SORTS.map((s) => (
        <option key={s.id} value={s.id}>
          {s.label}
        </option>
      ))}
    </Select>
  );
  const archivedBox = (
    <label className="inline-flex min-h-control items-center gap-2 lg:min-h-control-dense">
      <input type="checkbox" className="size-5 lg:size-4" checked={archived} onChange={(e) => set("archived", e.target.checked ? "1" : "")} />
      Show archived
    </label>
  );
  const active = (sort !== "spend" ? 1 : 0) + (archived ? 1 : 0);

  return (
    <main className="mx-auto max-w-content space-y-5 p-4 sm:p-6">
      <PageTop title="Usage" line={summary.data ? periodLine(period, summary.data.starts_at) : undefined}>
        {rail && <PeriodControl value={period} onChange={(p) => set("period", p === "week" ? "" : p)} />}
      </PageTop>
      {!rail && <PeriodControl value={period} onChange={(p) => set("period", p === "week" ? "" : p)} />}
      {summary.isError && <Banner title="Couldn't load usage." action={<Button variant="secondary" onClick={() => void summary.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      <Stats figures={summary.data} period={period}>
        {/* v5 D_Usage: what's waiting for the owner's OK, with the way to it. */}
        <Stat label="Waiting for your OK" link={held.count > 0 && <Link to="/approvals" className={`${linkText} inline-flex min-h-11 items-center lg:min-h-0`}>{held.count} request{held.count === 1 ? "" : "s"} in Needs you</Link>}>
          {held.count === 0 ? "Nothing" : waitingCredits > 0 ? `up to ${creditsLabel(waitingCredits)}` : `${held.count} request${held.count === 1 ? "" : "s"}`}
        </Stat>
        {/* v5 D_Usage (#1208): the director's own time, in dollars, outside the credit budgets. */}
        {summary.data && (
          <Stat label="The director's own time" link={<span className="text-muted">Outside the credit budget</span>}>
            {money(summary.data.director_spend_usd ?? 0)}
          </Stat>
        )}
      </Stats>

      <section aria-label="Brands" className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 className="type-section">Brands</h2>
          <div className="flex w-full flex-wrap items-end gap-3 lg:w-auto">
            <label className="relative block min-w-0 flex-1 lg:w-64 lg:flex-none">
              <span className="sr-only">Search brands</span>
              <Search size={20} strokeWidth={1.75} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
              <input type="search" role="searchbox" placeholder="Search brands" value={text} onChange={(e) => (setText(e.target.value), set("q", e.target.value.trim()))} className="min-h-control w-full rounded-md border border-border bg-surface pl-10 pr-3 lg:min-h-control-dense" />
            </label>
            {rail ? (
              <>
                <div className="w-56">{sortSelect}</div>
                {archivedBox}
              </>
            ) : (
              <Button variant={active > 0 ? "primary" : "secondary"} onClick={() => setSheet(true)}>
                {active > 0 ? `Filters (${active})` : "Filters"}
              </Button>
            )}
          </div>
        </div>
        {nothingSpent && <p className="text-sm text-muted">Nothing was spent {periodWord(period)}.</p>}
        {rows.isError && <Banner title="Couldn't load usage." action={<Button variant="secondary" onClick={() => void rows.refetch()}>Try again</Button>}>Check your connection.</Banner>}
        {rows.isPending && (
          <div role="status" aria-label="Loading" className="space-y-2">
            {[0, 1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-14" />
            ))}
          </div>
        )}
        {total !== undefined && items.length > 0 && <p className="text-sm text-muted">{q ? `${items.length} of ${total} brands` : `${total} brand${total === 1 ? "" : "s"}`}</p>}
        {rows.data && items.length === 0 &&
          (q ? (
            <EmptyState icon={Search} title={`No brand matches "${q}".`} action={<Button variant="ghost" onClick={() => (setText(""), set("q", ""))}>Clear search</Button>}>
              Try another name.
            </EmptyState>
          ) : (
            <EmptyState icon={ChartColumn} title="No brands yet.">Add a brand from the brand menu. It shows up here by itself.</EmptyState>
          ))}
        {items.length > 0 && (rail ? <BrandTable items={items} period={period} spent={summary.data?.spend_usd ?? 0} onRestore={(b) => void restoreBrand({ id: b.brand_id, name: b.name })} /> : <BrandCards items={items} onRestore={(b) => void restoreBrand({ id: b.brand_id, name: b.name })} />)}
        {rows.hasNextPage && (
          <Button variant="secondary" busy={rows.isFetchingNextPage} onClick={() => void rows.fetchNextPage()} className="w-full lg:w-auto">
            Show more
          </Button>
        )}
        {summary.data && summary.data.unassigned_spend_usd > 0 && <p className="text-sm text-muted">Not tied to one brand: {money(summary.data.unassigned_spend_usd)} · character looks used by several brands</p>}
        {summary.data && summary.data.freestyle_spend_usd > 0 && <p className="text-sm text-muted">Freestyle: {money(summary.data.freestyle_spend_usd)} · sends with no brand picked (a brand's own are in its row)</p>}
      </section>
      <People period={period} />
      <Charges />
      {sheet && (
        <Sheet title="Filters" onClose={() => setSheet(false)}>
          <div className="space-y-3 pb-2">
            {sortSelect}
            {archivedBox}
          </div>
        </Sheet>
      )}
    </main>
  );
}

/** v5 D_Usage's By person (#1232): each person's credits, dollars, videos and week, for the period. */
function People({ period }: { period: ReturnType<typeof periodFrom> }) {
  const people = useQuery({
    queryKey: ["usage", "people", period],
    retry: false, // a failed read says so at once, with Try again
    queryFn: async () => (await must(api.GET("/usage/people", { params: { query: { period } } }))).data!,
  });
  const n = (x: number) => Math.ceil(x - 1e-9).toLocaleString("en-US"); // whole credits, as D_Usage shows them
  const week = (p: Person) => (p.week_allowance === null ? "No limit" : `${n(p.week_used)} of ${n(p.week_allowance)} credits this week`);
  return (
    <section aria-label="By person" className="space-y-3">
      <h2 className="type-section">By person</h2>
      {people.isError && <Banner title="Couldn't load usage by person." action={<Button variant="secondary" onClick={() => void people.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      {people.isPending && <Skeleton className="h-24" />}
      {people.data && people.data.length === 0 && <p className="text-sm text-muted">Nobody has used anything {periodWord(period)}.</p>}
      {people.data && people.data.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm tabular-nums">
            <thead className="text-muted">
              <tr className="border-b border-border text-right">
                <th scope="col" className="px-4 py-3 text-left font-medium">Person</th>
                <th scope="col" className="px-3 py-3 font-medium">Credits</th>
                <th scope="col" className="px-3 py-3 font-medium">Dollars</th>
                <th scope="col" className="px-3 py-3 font-medium">Videos</th>
                <th scope="col" className="px-3 py-3 text-left font-medium">Week allowance</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border border-b border-border">
              {people.data.map((p) => (
                <tr key={p.user_id} className="text-right">
                  <th scope="row" className="px-4 py-3 text-left font-medium">{p.name} <span className="font-normal text-muted">· {p.role === "owner" ? "Owner" : "Editor"}</span></th>
                  <td className="px-3 py-3">{Math.ceil(p.credits - 1e-9).toLocaleString("en-US")}</td>
                  <td className="px-3 py-3 text-muted">{money(p.spend_usd)}</td>
                  <td className="px-3 py-3">{p.videos}</td>
                  <td className="px-3 py-3 text-left text-muted">{week(p)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

const share = (part: number, whole: number) => (whole > 0 ? Math.round((part / whole) * 100) : 0);
const label = (b: BrandRow) => `${b.name}: ${money(b.spend_usd)} spent, ${b.finished} finished`;
const each = (b: BrandRow) => (b.cost_per_finished_usd === null ? "—" : money(b.cost_per_finished_usd));

function BrandTable({ items, period, spent, onRestore }: { items: BrandRow[]; period: ReturnType<typeof periodFrom>; spent: number; onRestore: (b: BrandRow) => void }) {
  const forPeriod = (name: string) => (
    <>
      {name}
      <span className="block text-xs font-normal">{periodWord(period)}</span>
    </>
  );
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm tabular-nums">
        <thead className="text-muted">
          <tr className="border-b border-border text-right align-bottom">
            <th scope="col" className="px-4 py-3 text-left font-medium">Brand</th>
            <th scope="col" className="px-3 py-3 font-medium">{forPeriod("Spent")}</th>
            <th scope="col" className="px-3 py-3 font-medium">{forPeriod("Finished")}</th>
            <th scope="col" className="px-3 py-3 font-medium">{forPeriod("Cost / video")}</th>
            <th scope="col" className="px-3 py-3 font-medium">In progress</th>
            <th scope="col" className="px-3 py-3 font-medium">Scripts</th>
            <th scope="col" className="px-3 py-3 font-medium">Versions left</th>
            <th scope="col" className="px-3 py-3 font-medium">Last</th>
            <th scope="col" className="w-32 px-3 py-3 text-left font-medium">{forPeriod("Share")}</th>
            <th scope="col" className="w-8" />
          </tr>
        </thead>
        <tbody className="divide-y divide-border border-b border-border">
          {items.map((b) => (
            <tr key={b.brand_id} className="relative text-right hover:bg-surface-2">
              <th scope="row" className="px-4 py-3 text-left font-medium">
                <Link to={`/usage/brands/${b.brand_id}`} aria-label={label(b)} className="flex items-center gap-2 after:absolute after:inset-0">
                  <Dot colour={b.colour} />
                  {b.name}
                  {b.archived && <Badge>Archived</Badge>}
                </Link>
              </th>
              <td className="px-3 py-3"><Money value={b.spend_usd} estimated={b.spend_estimated} /></td>
              <td className="px-3 py-3">{b.finished}</td>
              <td className="px-3 py-3">{each(b)}</td>
              <td className="px-3 py-3">{b.in_progress}</td>
              <td className="px-3 py-3">{b.scripts}</td>
              <td className="px-3 py-3">{b.versions_left}</td>
              <td className="px-3 py-3">{lastText(b.last_activity_at)}</td>
              {/* v5 D_Usage: the brand's part of what was spent, as a bar. */}
              <td className="px-3 py-3">
                <span role="img" aria-label={`${share(b.spend_usd, spent)}% of what was spent`} className="block h-1.5 overflow-hidden rounded-full bg-surface-3">
                  <i className="block h-full bg-accent" style={{ width: `${share(b.spend_usd, spent)}%` }} />
                </span>
              </td>
              <td className="pr-3 text-muted">
                {b.archived ? (
                  <span className="relative z-10 inline-flex">
                    <Button variant="secondary" dense aria-label={`Restore ${b.name}`} onClick={() => onRestore(b)}>
                      Restore
                    </Button>
                  </span>
                ) : (
                  <ChevronRight size={20} strokeWidth={1.75} aria-hidden />
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BrandCards({ items, onRestore }: { items: BrandRow[]; onRestore: (b: BrandRow) => void }) {
  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {items.map((b) => (
        <li key={b.brand_id} className="space-y-2">
          <Link to={`/usage/brands/${b.brand_id}`} aria-label={label(b)} className="block min-h-control space-y-1 rounded-lg border border-border bg-surface p-4 hover:bg-surface-2">
            <span className="flex items-center gap-2 font-display text-md font-bold">
              <Dot colour={b.colour} />
              <span className="min-w-0 flex-1 break-words">{b.name}</span>
              {b.archived && <Badge>Archived</Badge>}
              <ChevronRight size={20} strokeWidth={1.75} aria-hidden className="shrink-0 text-muted" />
            </span>
            <span className="block text-sm text-muted">
              <Money value={b.spend_usd} estimated={b.spend_estimated} /> spent · {b.finished} finished · {each(b)}
              {b.cost_per_finished_usd !== null && " each"}
            </span>
            <span className="block text-sm text-muted">
              {b.in_progress} in progress · {b.scripts} script{b.scripts === 1 ? "" : "s"} · {b.versions_left} version{b.versions_left === 1 ? "" : "s"} left
            </span>
          </Link>
          {b.archived && (
            <Button variant="secondary" className="w-full" aria-label={`Restore ${b.name}`} onClick={() => onRestore(b)}>
              Restore
            </Button>
          )}
        </li>
      ))}
    </ul>
  );
}
