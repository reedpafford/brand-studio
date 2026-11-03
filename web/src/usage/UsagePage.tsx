import { ChartColumn, ChevronRight } from "lucide-react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, must } from "../api/client";
import type { components } from "../api/schema";
import { Badge, Banner, Button, buttonClass, creditsLabel, EmptyState, wholeCredits, PageTop, Skeleton } from "../components";
import { useHeld } from "../approvals/useHeld";
import { linkText } from "../ui";
import { useRail } from "../useMedia";
import { useRestoreBrand } from "../brand/ArchiveBrand";
import { Charges } from "./Charges";
import { Money, MonthPicker, Stat, money, useMonth } from "./parts";
import { useBrandRows, useSummary, type BrandRow } from "./useUsage";

type Person = components["schemas"]["PersonRow"];


const count = (n: number) => wholeCredits(n).toLocaleString("en-US");

/** The owner's month (v5 D_Usage, Reed 3 Nov): Spent this month, Waiting for your OK and the director's own time; By brand
 *  with the Freestyle row; By person; and every charge behind a link. One month at a time, with its CSV. */
export function UsagePage() {
  const [params, setParams] = useSearchParams();
  const rail = useRail();
  const { month, label, thisMonth, options, set: setMonth } = useMonth();
  const archived = params.get("archived") === "1";
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
  const summary = useSummary("month", month);
  const rows = useBrandRows({ period: "month", month, q: "", archived, sort: "spend" });
  const held = useHeld();
  const waitingCredits = held.heldJobs.reduce((n, j) => n + (j.freestyle?.up_to ?? j.credits), 0); // as Needs you counts it
  if (summary.error?.message === "404") return <Navigate to="/usage/mine" replace />; // an editor: their own credits (OR4)
  const items = rows.data?.pages.flatMap((p) => p.items) ?? [];
  const f = summary.data;

  return (
    <main className="mx-auto max-w-content space-y-5 p-4 sm:p-6">
      <PageTop title="Usage">
        <MonthPicker value={month} options={options} onChange={setMonth} />
        {/* The month's charges as a spreadsheet, one row per charge (#1247). */}
        <a href={`/api/usage/charges.csv?month=${month}`} download className={buttonClass("secondary")}>Download CSV</a>
      </PageTop>
      {summary.isError && <Banner title="Couldn't load usage." action={<Button variant="secondary" onClick={() => void summary.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      <div role="group" aria-label="Totals" className="grid gap-3 sm:grid-cols-3 lg:max-w-[1100px]">
        {!f ? (
          [0, 1, 2].map((i) => <Skeleton key={i} className="h-28" />)
        ) : (
          <>
            <Stat label={thisMonth ? "Spent this month" : `Spent in ${label}`} link={<span className="text-muted"><Money value={f.spend_usd} estimated={f.spend_estimated} /></span>}>
              {count(f.spend_credits)} credits
            </Stat>
            <Stat label="Waiting for your OK" link={held.count > 0 && <Link to="/approvals" className={`${linkText} inline-flex min-h-11 items-center lg:min-h-0`}>{held.count} request{held.count === 1 ? "" : "s"} in Needs you</Link>}>
              {held.count === 0 ? "Nothing" : waitingCredits > 0 ? `up to ${creditsLabel(waitingCredits)}` : `${held.count} request${held.count === 1 ? "" : "s"}`}
            </Stat>
            <Stat label="The director's own time" link={<span className="text-muted">Outside the credit budget</span>}>
              {money(f.director_spend_usd ?? 0)}
            </Stat>
          </>
        )}
      </div>

      <section aria-label="By brand" className="space-y-3 lg:max-w-[1100px]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="type-section">By brand</h2>
          <label className="inline-flex min-h-control items-center gap-2 text-sm text-muted lg:min-h-control-dense">
            <input type="checkbox" className="size-5 lg:size-4" checked={archived} onChange={(e) => set("archived", e.target.checked ? "1" : "")} />
            Show archived
          </label>
        </div>
        {rows.isError && <Banner title="Couldn't load usage." action={<Button variant="secondary" onClick={() => void rows.refetch()}>Try again</Button>}>Check your connection.</Banner>}
        {rows.isPending && <Skeleton className="h-32" />}
        {rows.data && items.length === 0 && <EmptyState icon={ChartColumn} title="No brands yet.">Add a brand from the brand menu. It shows up here by itself.</EmptyState>}
        {items.length > 0 && <BrandTable items={items} freestyle={f?.freestyle} spent={f?.spend_credits ?? 0} rail={rail} onRestore={(b) => void restoreBrand({ id: b.brand_id, name: b.name })} />}
        {rows.hasNextPage && (
          <Button variant="secondary" busy={rows.isFetchingNextPage} onClick={() => void rows.fetchNextPage()} className="w-full lg:w-auto">
            Show more
          </Button>
        )}
        {f && f.unassigned_spend_usd > 0 && <p className="text-sm text-muted">Not tied to one brand: {count(f.unassigned_credits)} credits · {money(f.unassigned_spend_usd)} · character looks used by several brands</p>}
      </section>
      <People month={month} />
      <Charges />
    </main>
  );
}

/** v5 D_Usage's By person (#1232): each person's credits, dollars, videos and week, for the month. */
function People({ month }: { month: string }) {
  const people = useQuery({
    queryKey: ["usage", "people", month],
    retry: false, // a failed read says so at once, with Try again
    queryFn: async () => (await must(api.GET("/usage/people", { params: { query: { month } } }))).data!,
  });
  const week = (p: Person) => (p.week_allowance === null ? "No limit" : `${count(p.week_used)} of ${count(p.week_allowance)} quick credits`);
  return (
    <section aria-label="By person" className="space-y-3 lg:max-w-[1100px]">
      <h2 className="type-section">By person</h2>
      {people.isError && <Banner title="Couldn't load usage by person." action={<Button variant="secondary" onClick={() => void people.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      {people.isPending && <Skeleton className="h-24" />}
      {people.data && people.data.length === 0 && <p className="text-sm text-muted">Nobody has used anything this month.</p>}
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
                  <td className="px-3 py-3">{count(p.credits)}</td>
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
type Freestyle = components["schemas"]["FreestyleUsage"];

function ShareBar({ part, spent }: { part: number; spent: number }) {
  const pct = share(part, spent);
  return (
    <span role="img" aria-label={`${pct}% of the month's credits`} className="block h-1.5 overflow-hidden rounded-full bg-surface-3">
      <i className="block h-full bg-accent" style={{ width: `${pct}%` }} />
    </span>
  );
}

/** v5 D_Usage's By brand: Brand | Credits | Dollars | Videos | Share, with Freestyle (no brand picked) as its own row.
 *  On a phone each brand is a card with the same numbers. */
function BrandTable({ items, freestyle, spent, rail, onRestore }: { items: BrandRow[]; freestyle?: Freestyle; spent: number; rail: boolean; onRestore: (b: BrandRow) => void }) {
  const fs = freestyle && (freestyle.credits > 0 || freestyle.videos > 0) ? freestyle : null;
  const restore = (b: BrandRow, full?: boolean) => (
    <Button variant="secondary" dense={!full} className={full ? "w-full" : undefined} aria-label={`Restore ${b.name}`} onClick={() => onRestore(b)}>
      Restore
    </Button>
  );
  if (!rail)
    return (
      <ul className="space-y-3">
        {items.map((b) => (
          <li key={b.brand_id} className="space-y-2">
            <Link to={`/usage/brands/${b.brand_id}`} className="block space-y-2 rounded-lg border border-border bg-surface p-4 hover:bg-surface-2">
              <span className="flex items-center gap-2 font-medium">
                <span className="min-w-0 flex-1 break-words">{b.name}</span>
                {b.archived && <Badge>Archived</Badge>}
                <ChevronRight size={20} strokeWidth={1.75} aria-hidden className="shrink-0 text-muted" />
              </span>
              <span className="block text-sm tabular-nums text-muted">{count(b.credits)} credits · <Money value={b.spend_usd} estimated={b.spend_estimated} /> · {b.videos} video{b.videos === 1 ? "" : "s"}</span>
              <ShareBar part={b.credits} spent={spent} />
            </Link>
            {b.archived && restore(b, true)}
          </li>
        ))}
        {fs && (
          <li className="space-y-2 rounded-lg border border-border bg-surface p-4">
            <span className="block font-medium">Freestyle <span className="font-normal text-muted">(no brand picked)</span></span>
            <span className="block text-sm tabular-nums text-muted">{count(fs.credits)} credits · {money(fs.spend_usd)} · {fs.videos} video{fs.videos === 1 ? "" : "s"}</span>
            <ShareBar part={fs.credits} spent={spent} />
          </li>
        )}
      </ul>
    );
  return (
    <div className="overflow-x-auto">
      <table aria-label="By brand" className="w-full text-sm tabular-nums">
        <thead className="text-muted">
          <tr className="border-b border-border text-right">
            <th scope="col" className="px-4 py-3 text-left font-medium">Brand</th>
            <th scope="col" className="px-3 py-3 font-medium">Credits</th>
            <th scope="col" className="px-3 py-3 font-medium">Dollars</th>
            <th scope="col" className="px-3 py-3 font-medium">Videos</th>
            <th scope="col" className="w-48 px-3 py-3 text-left font-medium">Share</th>
            <th scope="col" className="w-8"><span className="sr-only">Restore</span></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border border-b border-border">
          {items.map((b) => (
            <tr key={b.brand_id} className="relative text-right hover:bg-surface-2">
              <th scope="row" className="px-4 py-3 text-left font-medium">
                <Link to={`/usage/brands/${b.brand_id}`} className="flex items-center gap-2 after:absolute after:inset-0">
                  {b.name}
                  {b.archived && <Badge>Archived</Badge>}
                </Link>
              </th>
              <td className="px-3 py-3">{count(b.credits)}</td>
              <td className="px-3 py-3 text-muted"><Money value={b.spend_usd} estimated={b.spend_estimated} /></td>
              <td className="px-3 py-3">{b.videos}</td>
              <td className="px-3 py-3"><ShareBar part={b.credits} spent={spent} /></td>
              <td className="pr-3 text-muted">
                {b.archived && <span className="relative z-10 inline-flex">{restore(b)}</span>}
              </td>
            </tr>
          ))}
          {fs && (
            <tr className="text-right">
              <th scope="row" className="px-4 py-3 text-left font-medium">Freestyle <span className="font-normal text-muted">(no brand picked)</span></th>
              <td className="px-3 py-3">{count(fs.credits)}</td>
              <td className="px-3 py-3 text-muted">{money(fs.spend_usd)}</td>
              <td className="px-3 py-3">{fs.videos}</td>
              <td className="px-3 py-3"><ShareBar part={fs.credits} spent={spent} /></td>
              <td />
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
