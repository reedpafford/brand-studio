import { useState } from "react";
import { ChartColumn, ChevronRight, Search } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { Badge, Banner, Button, Card, EmptyState, Select, Sheet, Skeleton } from "../components";
import { useRail } from "../useMedia";
import { useDebounced } from "../scripts/ScriptsPage";
import { Charges } from "./Charges";
import { Money, PeriodControl, Stats, lastText, money, periodLine, periodWord } from "./parts";
import { periodFrom, useBrandRows, useSummary, type BrandRow, type Sort } from "./useUsage";

const SORTS: { id: Sort; label: string }[] = [
  { id: "spend", label: "Most spent" },
  { id: "finished", label: "Most finished" },
  { id: "cost", label: "Cost per video (high first)" },
  { id: "activity", label: "Last activity" },
  { id: "name", label: "Name A–Z" },
];
const sortFrom = (s: string | null): Sort => SORTS.find((x) => x.id === s)?.id ?? "spend";

const Dot = ({ colour }: { colour: string | null }) => <span aria-hidden className="size-3 shrink-0 rounded-full bg-brand" style={colour ? { background: colour } : undefined} />;

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
  const summary = useSummary(period);
  const rows = useBrandRows({ period, q, archived, sort });
  if (summary.error?.message === "404") return <p className="p-6">Page not found.</p>;
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
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="type-page">Usage</h1>
          <p className="text-sm text-muted">{summary.data ? periodLine(period, summary.data.starts_at) : " "}</p>
        </div>
        <PeriodControl value={period} onChange={(p) => set("period", p === "week" ? "" : p)} />
      </div>
      {summary.isError && <Banner title="Couldn't load usage." action={<Button variant="secondary" onClick={() => void summary.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      <Stats figures={summary.data} period={period} />

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
        {items.length > 0 && (rail ? <BrandTable items={items} period={period} /> : <BrandCards items={items} />)}
        {rows.hasNextPage && (
          <Button variant="secondary" busy={rows.isFetchingNextPage} onClick={() => void rows.fetchNextPage()} className="w-full lg:w-auto">
            Show more
          </Button>
        )}
        {summary.data && summary.data.unassigned_spend_usd > 0 && <p className="text-sm text-muted">Not tied to one brand: {money(summary.data.unassigned_spend_usd)} · character looks used by several brands</p>}
      </section>
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

const label = (b: BrandRow) => `${b.name}: ${money(b.spend_usd)} spent, ${b.finished} finished`;
const each = (b: BrandRow) => (b.cost_per_finished_usd === null ? "—" : money(b.cost_per_finished_usd));

function BrandTable({ items, period }: { items: BrandRow[]; period: ReturnType<typeof periodFrom> }) {
  const forPeriod = (name: string) => (
    <>
      {name}
      <span className="block text-xs font-normal">{periodWord(period)}</span>
    </>
  );
  return (
    <Card className="overflow-x-auto p-0 sm:p-0">
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
            <th scope="col" className="w-8" />
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
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
              <td className="pr-3 text-muted"><ChevronRight size={20} strokeWidth={1.75} aria-hidden /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function BrandCards({ items }: { items: BrandRow[] }) {
  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {items.map((b) => (
        <li key={b.brand_id}>
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
              {b.in_progress} in progress · {b.scripts} scripts · {b.versions_left} versions left
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
