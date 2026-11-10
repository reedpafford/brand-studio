import { ChartColumn, ChevronRight } from "lucide-react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, must } from "../api/client";
import type { components } from "../api/schema";
import { Badge, Banner, Button, buttonClass, EmptyState, wholeCredits, PageTop, Skeleton } from "../components";
import { useNeedsYou } from "../approvals/NeedsYouPage";
import { useRail } from "../useMedia";
import { useMe } from "../auth/useMe";
import { useRestoreBrand } from "../brand/ArchiveBrand";
import { ByFormat } from "./ByFormat";
import { ByVideo } from "./ByVideo";
import { Charges } from "./Charges";
import { Money, MonthPicker, Stat, money, useSpan } from "./parts";
import { useBrandRows, useSummary, type BrandRow, type Period } from "./useUsage";

type Person = components["schemas"]["PersonRow"];
type Part = components["schemas"]["Part"];

const count = (n: number) => wholeCredits(n).toLocaleString("en-US");

/** The owner's Usage (v5 D_Usage; Reed, 9 Nov: "track API usage per brand (from all api providers), and spend per
 *  video/project"): what was spent in the period and what waits for his OK; By brand, split by service, with the Freestyle
 *  and Other rows; By video; By person; By format and style; and every charge behind a link, with the month's CSV. */
export function UsagePage() {
  const [params, setParams] = useSearchParams();
  const rail = useRail();
  const span = useSpan();
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
  const { period = "month", month } = span.query;
  const summary = useSummary(period, month);
  const rows = useBrandRows({ period, month, q: "", archived, sort: "spend" });
  const owner = useMe().data?.role === "owner";
  const inbox = useNeedsYou(null, owner).data; // its Money cards: what waits for the owner's OK, as Needs you shows it
  const oks = inbox ? [...inbox.money.flatMap((r) => (r.ask.money ? [r.ask.money.up_to] : [])), ...inbox.sends.map((s) => s.up_to)] : [];
  const waitingUsd = oks.reduce((n, p) => n + (p.usd ?? 0), 0); // the owner's figures are dollars (rule 4)
  if (summary.error?.message === "404") return <Navigate to="/usage/mine" replace />; // an editor: their own credits (OR4)
  const items = rows.data?.pages.flatMap((p) => p.items) ?? [];
  const f = summary.data;
  const extra: Extra[] = [
    ...(f?.freestyle && (f.freestyle.credits > 0 || f.freestyle.spend_usd > 0 || f.freestyle.videos > 0) ? [{ name: "Freestyle", note: "(no brand picked)", spend_usd: f.freestyle.spend_usd, estimated: !!f.freestyle.spend_estimated, providers: f.freestyle.providers ?? [], videos: f.freestyle.videos }] : []),
    ...(f && (f.unassigned_credits > 0 || f.unassigned_spend_usd > 0) ? [{ name: "Other", note: "(no brand or video)", spend_usd: f.unassigned_spend_usd, estimated: !!f.unassigned_estimated, providers: f.unassigned_providers ?? [], videos: null }] : []),
  ];
  const services = (f?.providers ?? []).map((p) => p.name); // the period's services, most spent first: the columns

  return (
    <main className="mx-auto max-w-content space-y-5 p-4 sm:p-6">
      <PageTop title="Usage">
        <MonthPicker label="Period" value={span.value} options={span.options} onChange={span.set} />
        {/* A month's charges as a spreadsheet, one row per charge (#1247): the month picked, else this month's. */}
        <a href={`/api/usage/charges.csv?month=${span.csv}`} download className={buttonClass("secondary")}>Download CSV</a>
      </PageTop>
      {summary.isError && <Banner title="Couldn't load usage." action={<Button variant="secondary" onClick={() => void summary.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      <div role="group" aria-label="Totals" className="grid gap-3 sm:grid-cols-3 lg:max-w-[1100px]">
        {!f ? (
          [0, 1, 2].map((i) => <Skeleton key={i} className="h-28" />)
        ) : (
          <>
            <Stat label={`Spent ${span.words}`} link={<span className="text-muted">{count(f.spend_credits)} credits</span>}>
              <Money value={f.spend_usd} estimated={f.spend_estimated} />
            </Stat>
            <Stat label="Waiting for your OK" link={oks.length > 0 && <Link to="/approvals" className="inline-flex min-h-11 items-center text-accent-text hover:underline lg:min-h-0">{oks.length} in Needs you</Link>}>
              {oks.length === 0 ? "Nothing" : waitingUsd > 0 ? `up to $${waitingUsd.toFixed(2)}` : `${oks.length} waiting`}
            </Stat>
            <Stat label="The director's own time" link={<span className="text-muted">Its thinking and watching, part of what was spent</span>}>
              {money(f.director_spend_usd ?? 0)}
            </Stat>
          </>
        )}
      </div>

      <section aria-label="By brand" className="space-y-3 lg:max-w-[1100px]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="type-section">By brand</h2>
            <p className="text-sm text-muted">Spent {span.words}, by service. ≈ means some of it is at list price.</p>
          </div>
          <label className="inline-flex min-h-control items-center gap-2 text-sm text-muted lg:min-h-control-dense">
            <input type="checkbox" className="size-5 lg:size-4" checked={archived} onChange={(e) => set("archived", e.target.checked ? "1" : "")} />
            Show archived
          </label>
        </div>
        {rows.isError && <Banner title="Couldn't load usage." action={<Button variant="secondary" onClick={() => void rows.refetch()}>Try again</Button>}>Check your connection.</Banner>}
        {rows.isPending && <Skeleton className="h-32" />}
        {rows.data && items.length === 0 && <EmptyState icon={ChartColumn} title="No brands yet.">Add a brand from the brand menu. It shows up here by itself.</EmptyState>}
        {items.length > 0 && <BrandTable items={items} extra={extra} services={services} rail={rail} onRestore={(b) => void restoreBrand({ id: b.brand_id, name: b.name })} />}
        {rows.hasNextPage && (
          <Button variant="secondary" busy={rows.isFetchingNextPage} onClick={() => void rows.fetchNextPage()} className="w-full lg:w-auto">
            Show more
          </Button>
        )}
      </section>
      <ByVideo query={span.query} words={span.words} />
      <People query={span.query} words={span.words} />
      <ByFormat />
      <Charges />
    </main>
  );
}

/** v5 D_Usage's By person (#1232): each person's credits, dollars, videos and week, for the period. */
function People({ query, words }: { query: { period?: Period; month?: string }; words: string }) {
  const people = useQuery({
    queryKey: ["usage", "people", query],
    retry: false, // a failed read says so at once, with Try again
    queryFn: async () => (await must(api.GET("/usage/people", { params: { query } }))).data!,
  });
  const week = (p: Person) => (p.week_allowance === null ? "No limit" : `${count(p.week_used)} of ${count(p.week_allowance)} quick credits`);
  return (
    <section aria-label="By person" className="space-y-3 lg:max-w-[1100px]">
      <h2 className="type-section">By person</h2>
      {people.isError && <Banner title="Couldn't load usage by person." action={<Button variant="secondary" onClick={() => void people.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      {people.isPending && <Skeleton className="h-24" />}
      {people.data && people.data.length === 0 && <p className="text-sm text-muted">Nobody has used anything {words}.</p>}
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

type Extra = { name: string; note: string; spend_usd: number; estimated: boolean; providers: Part[]; videos: number | null };

/** "$4.00" for a service's part of a row, "≈ $4.00" when some is at list price, "—" for none. */
function Cell({ parts, name }: { parts: Part[]; name: string }) {
  const p = parts.find((x) => x.name === name);
  return p ? <Money value={p.usd} estimated={p.estimated} /> : <>—</>;
}

const line = (parts: Part[]) => parts.map((p) => `${p.name} ${p.estimated ? "≈ " : ""}${money(p.usd)}`).join(" · ");

/** By brand (Reed, 9 Nov): Brand | Spent | one column a service (Replicate, Claude, MiniMax, …) | Videos. Freestyle (no brand
 *  picked) and Other (no brand or video) follow as their own rows when they have anything, so the rows add up to what was
 *  spent. On a phone each brand is a card: what it spent, then each service's part. */
function BrandTable({ items, extra, services, rail, onRestore }: { items: BrandRow[]; extra: Extra[]; services: string[]; rail: boolean; onRestore: (b: BrandRow) => void }) {
  const restore = (b: BrandRow, full?: boolean) => (
    <Button variant="secondary" dense={!full} className={full ? "w-full" : undefined} aria-label={`Restore ${b.name}`} onClick={() => onRestore(b)}>
      Restore
    </Button>
  );
  const videos = (n: number) => `${n} video${n === 1 ? "" : "s"}`;
  if (!rail)
    return (
      <ul className="space-y-3">
        {items.map((b) => (
          <li key={b.brand_id} className="space-y-2">
            <Link to={`/usage/brands/${b.brand_id}`} className="block space-y-1 rounded-lg border border-border bg-surface p-4 hover:bg-surface-2">
              <span className="flex items-center gap-2 font-medium">
                <span className="min-w-0 flex-1 break-words">{b.name}</span>
                {b.archived && <Badge>Archived</Badge>}
                <ChevronRight size={20} strokeWidth={1.75} aria-hidden className="shrink-0 text-muted" />
              </span>
              <span className="block text-lg font-semibold tabular-nums"><Money value={b.spend_usd} estimated={b.spend_estimated} /> <span className="text-sm font-normal text-muted">spent · {videos(b.videos)}</span></span>
              {(b.providers ?? []).length > 0 && <span className="block text-sm tabular-nums text-muted">{line(b.providers ?? [])}</span>}
            </Link>
            {b.archived && restore(b, true)}
          </li>
        ))}
        {extra.map((x) => (
          <li key={x.name} className="space-y-1 rounded-lg border border-border bg-surface p-4">
            <span className="block font-medium">{x.name} <span className="font-normal text-muted">{x.note}</span></span>
            <span className="block text-lg font-semibold tabular-nums"><Money value={x.spend_usd} estimated={x.estimated} /> <span className="text-sm font-normal text-muted">spent{x.videos !== null && ` · ${videos(x.videos)}`}</span></span>
            {x.providers.length > 0 && <span className="block text-sm tabular-nums text-muted">{line(x.providers)}</span>}
          </li>
        ))}
      </ul>
    );
  return (
    <div className="overflow-x-auto">
      <table aria-label="By brand" className="w-full text-sm tabular-nums">
        <thead className="text-muted">
          <tr className="border-b border-border text-right">
            <th scope="col" className="px-4 py-3 text-left font-medium">Brand</th>
            <th scope="col" className="px-3 py-3 font-medium">Spent</th>
            {services.map((s) => (
              <th key={s} scope="col" className="px-3 py-3 font-medium">{s}</th>
            ))}
            <th scope="col" className="px-3 py-3 font-medium">Videos</th>
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
              <td className="px-3 py-3 font-medium"><Money value={b.spend_usd} estimated={b.spend_estimated} /></td>
              {services.map((s) => (
                <td key={s} className="px-3 py-3 text-muted"><Cell parts={b.providers ?? []} name={s} /></td>
              ))}
              <td className="px-3 py-3">{b.videos}</td>
              <td className="pr-3 text-muted">
                {b.archived && <span className="relative z-10 inline-flex">{restore(b)}</span>}
              </td>
            </tr>
          ))}
          {extra.map((x) => (
            <tr key={x.name} className="text-right">
              <th scope="row" className="px-4 py-3 text-left font-medium">{x.name} <span className="font-normal text-muted">{x.note}</span></th>
              <td className="px-3 py-3 font-medium"><Money value={x.spend_usd} estimated={x.estimated} /></td>
              {services.map((s) => (
                <td key={s} className="px-3 py-3 text-muted"><Cell parts={x.providers} name={s} /></td>
              ))}
              <td className="px-3 py-3">{x.videos ?? "—"}</td>
              <td />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
