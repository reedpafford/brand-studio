import type { ReactNode } from "react";
import { useIsFetching, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Download, Receipt, RefreshCw } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import type { components } from "../api/schema";
import { day } from "../library/kinds";
import { useBrands } from "../shell/useBrands";
import { Money, money, months } from "../usage/parts";
import { useBrandRows, useBrandUsage, useBrandVideos, useSummary, useVideoSpends, type Period } from "../usage/useUsage";
import { Choice, Popover } from "./Popover";
import "./spend.css";

type Brand = components["schemas"]["BrandOut"];
/** What the server says of a time, for every brand or for one: the same fields on both answers. */
type Figures = Pick<components["schemas"]["UsageBrandOut"], "spend_usd" | "spend_estimated" | "finished" | "cost_per_finished_usd" | "in_progress" | "providers">;
type Bar = { key: string | number; name: string; colour?: string; note?: string; usd: number; estimated: boolean; onPick?: () => void };
type Row = { id: number; brandId: number; title: string; brand?: string; when: string | null; usd: number; estimated: boolean };
type Time = (typeof TIMES)[number];

const ICON = { size: 16, strokeWidth: 1.75, "aria-hidden": true } as const;
/** The times the server keeps figures for (it has no rolling 7 or 30 days). */
const TIMES: { id: Period; label: string; words: string }[] = [
  { id: "week", label: "This week", words: "this week" },
  { id: "month", label: "This month", words: "this month" },
  { id: "all", label: "All time", words: "all time" },
];
const count = (n: number, one: string) => `${n} ${one}${n === 1 ? "" : "s"}`;
const square = (colour?: string | null) => <i aria-hidden className="sq" style={{ background: colour || "var(--accent)" }} />;

/** Spend in the new look (the redesign, stage 6): one large figure for the time picked, where it went by service, each
 *  brand as a row that filters on a press, and every video with what it has cost. Every figure is the server's own, read
 *  through the current Usage page's hooks; nothing is added up here, and the page only reads. The brand and the time are
 *  kept in the address. */
export function Spend() {
  const [params, setParams] = useSearchParams();
  const brands = useBrands().data ?? [];
  const time = TIMES.find((t) => t.id === params.get("period")) ?? TIMES[1];
  const brand = brands.find((b) => b.id === Number(params.get("brand")));
  const set = (key: "brand" | "period", value: string) =>
    setParams(
      (was) => {
        const next = new URLSearchParams(was);
        if (value) next.set(key, value);
        else next.delete(key);
        return next;
      },
      { replace: true },
    );
  const pickBrand = (id?: number) => set("brand", id ? String(id) : "");
  const filters = (
    <>
      {brands.length > 1 && (
        <Popover
          label="Brand"
          button={(p) => (
            <button type="button" className="btn soft" {...p}>
              {brand && square(brand.colours[0])}
              {brand?.name ?? "All brands"}
              <ChevronDown size={14} strokeWidth={1.75} aria-hidden />
            </button>
          )}
        >
          {(close) => (
            <>
              <Choice checked={!brand} onPick={() => (pickBrand(), close())}>
                All brands
              </Choice>
              {brands.map((b) => (
                <Choice key={b.id} checked={b.id === brand?.id} lead={square(b.colours[0])} onPick={() => (pickBrand(b.id), close())}>
                  {b.name}
                </Choice>
              ))}
            </>
          )}
        </Popover>
      )}
      <div className="seg" role="group" aria-label="Time">
        {TIMES.map((t) => (
          <button key={t.id} type="button" aria-pressed={t === time} onClick={() => set("period", t.id === "month" ? "" : t.id)}>
            {t.label}
          </button>
        ))}
      </div>
      {(brand || time.id !== "month") && (
        <button type="button" className="btn ghost" onClick={() => setParams({}, { replace: true })}>
          Clear
        </button>
      )}
    </>
  );
  return brand ? <OneBrand key={brand.id} brand={brand} time={time} filters={filters} /> : <AllBrands time={time} filters={filters} onBrand={pickBrand} />;
}

/** Every brand together: the studio's total, each brand's part (and what belongs to no brand, so the rows add up to the
 *  total), then each video with a charge in that time. The server does not say here which of them are finished. */
function AllBrands({ time, filters, onBrand }: { time: Time; filters: ReactNode; onBrand: (id: number) => void }) {
  const summary = useSummary(time.id);
  const brands = useBrandRows({ period: time.id, q: "", archived: false, sort: "spend" });
  const videos = useVideoSpends({ period: time.id }, "recent");
  const f = summary.data;
  const bars: Bar[] = [
    ...(brands.data?.pages.flatMap((p) => p.items) ?? []).map((b) => ({ key: b.brand_id, name: b.name, colour: b.colour || "var(--accent)", note: count(b.videos, "video"), usd: b.spend_usd, estimated: b.spend_estimated, onPick: () => onBrand(b.brand_id) })),
    ...(f && (f.freestyle.spend_usd > 0 || f.freestyle.videos > 0) ? [{ key: "freestyle", name: "No brand picked", colour: "var(--hover)", note: count(f.freestyle.videos, "video"), usd: f.freestyle.spend_usd, estimated: f.freestyle.spend_estimated }] : []),
    ...(f && f.unassigned_spend_usd > 0 ? [{ key: "other", name: "No brand or video", colour: "var(--hover)", usd: f.unassigned_spend_usd, estimated: f.unassigned_estimated }] : []),
  ];
  const rows = (videos.data?.pages.flatMap((p) => p.items) ?? []).map((v): Row => ({ id: v.project_id, brandId: v.brand_id, title: v.title, brand: v.brand, when: v.last_at, usd: v.spend_usd, estimated: v.spend_estimated }));
  return (
    <Frame figures={summary} title={`Spent on all brands, ${time.words}`} filters={filters} note={f && f.director_spend_usd > 0 && `Of this, ${money(f.director_spend_usd)} was the director’s own thinking and watching.`} empty={<Empty title={time.id === "all" ? "Nothing spent yet" : `Nothing spent ${time.words}`} hint={time.id === "all" ? "What a video costs shows here as soon as one is made." : "Try a longer time."} />}>
      {bars.length > 1 && (
        <section aria-labelledby="spend-brands">
          <h2 id="spend-brands">By brand</h2>
          <Bars label="By brand" rows={bars} />
          {brands.hasNextPage && <More onClick={() => void brands.fetchNextPage()}>Show more brands</More>}
        </section>
      )}
      <Videos title={`Videos, ${time.words}`} why="Each video with a charge in that time, with everything it has cost so far." when="Last charge" cost="Cost so far" rows={rows} />
      {videos.hasNextPage && <More onClick={() => void videos.fetchNextPage()}>Show more videos</More>}
    </Frame>
  );
}

/** One brand: its total, then its videos by where they stand, as the server says: still being made (what each has cost
 *  so far), finished, and the ones that did not finish. */
function OneBrand({ brand, time, filters }: { brand: Brand; time: Time; filters: ReactNode }) {
  const usage = useBrandUsage(brand.id, time.id);
  const videos = useBrandVideos(brand.id, { period: time.id, status: "any", person: null, q: "", sort: "activity" });
  const items = videos.data?.pages.flatMap((p) => p.items) ?? [];
  const rows = (status: (typeof items)[number]["status"]) => items.filter((v) => v.status === status).map((v): Row => ({ id: v.project_id, brandId: brand.id, title: v.title, when: status === "done" ? v.finished_at : v.last_activity_at, usd: v.spend_usd, estimated: v.spend_estimated }));
  const empty = (
    <Empty title={time.id === "all" ? `Nothing spent on ${brand.name} yet` : `Nothing spent on ${brand.name} ${time.words}`} hint={time.id === "all" ? "What a video costs shows here as soon as one is made." : "Try a longer time."}>
      {time.id === "all" && (
        <Link className="btn go" to={`/s/b/${brand.id}`}>
          Make its first video
        </Link>
      )}
    </Empty>
  );
  return (
    <Frame figures={usage} title={`Spent on ${brand.name}, ${time.words}`} filters={filters} empty={empty}>
      <Videos title="Still being made" when="Last worked on" cost="Cost so far" rows={rows("in_production")} />
      <Videos title={`Finished, ${time.words}`} when="Finished" cost="Cost" rows={rows("done")} />
      <Videos title="Did not finish" when="Last worked on" cost="Cost" rows={rows("failed")} />
      {videos.hasNextPage && <More onClick={() => void videos.fetchNextPage()}>Show more videos</More>}
    </Frame>
  );
}

/** The page around either view: the filters, when the figures were read and a press that reads them all again, the
 *  large figure with what the server counts beside it, and where it went by service. */
function Frame({ figures: q, title, note, filters, empty, children }: { figures: { data?: Figures; error: Error | null; isError: boolean; dataUpdatedAt: number }; title: string; note?: ReactNode; filters: ReactNode; empty: ReactNode; children: ReactNode }) {
  const queryClient = useQueryClient();
  const reading = useIsFetching({ queryKey: ["usage"] }) > 0;
  const f = q.data;
  return (
    <>
      <header className="head">
        <h1>Spend</h1>
        <span className="grow" />
        {f && (
          <a className="btn soft" href={`/api/usage/charges.csv?month=${months()[0].id}`} download title="Every charge this month, as a spreadsheet">
            <Download {...ICON} />
            This month’s charges
          </a>
        )}
      </header>
      <div className="view">
        <div className="page spendpage">
          <div className="filters">
            {filters}
            <span className="grow" />
            {q.dataUpdatedAt > 0 && <span className="asof">Updated {new Date(q.dataUpdatedAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</span>}
            <button type="button" className="btn ghost square" aria-label="Update now" title="Update now" onClick={() => void queryClient.invalidateQueries({ queryKey: ["usage"] })}>
              <RefreshCw {...ICON} className={reading ? "spin" : undefined} />
            </button>
          </div>
          {q.error?.message === "404" ? (
            <p className="quiet">
              Only the owner sees what the studio spends. <Link to="/usage/mine">Your own credits are on the current site</Link>.
            </p>
          ) : q.isError ? (
            <p role="alert" className="none">
              Could not load what was spent. Press Update now to try again.
            </p>
          ) : !f ? (
            <p role="status" className="none">
              Loading…
            </p>
          ) : f.spend_usd === 0 && f.finished === 0 && f.in_progress === 0 ? (
            empty
          ) : (
            <>
              <section className="top">
                <div className="hero">
                  <span className="lab">{title}</span>
                  <b>
                    <Money value={f.spend_usd} estimated={f.spend_estimated} />
                  </b>
                  <span className="lab">
                    {count(f.finished, "finished video")}
                    {f.cost_per_finished_usd !== null && ` · ${money(f.cost_per_finished_usd)} a finished video`}
                  </span>
                  {note && <span className="lab">{note}</span>}
                  {f.in_progress > 0 && (
                    <span className="lab live">
                      <i aria-hidden className="dot" />
                      {count(f.in_progress, "video")} still being made
                    </span>
                  )}
                </div>
                {f.providers.length > 0 && (
                  <div>
                    <span className="lab">Where it went, by service</span>
                    <Bars label="Where it went, by service" rows={f.providers.map((p) => ({ key: p.name, name: p.name, usd: p.usd, estimated: p.estimated }))} />
                  </div>
                )}
              </section>
              {children}
              <p className="quiet why">
                Earlier months, each single charge and cost by look are on the current site: <Link to="/usage">open Usage</Link>.
              </p>
            </>
          )}
        </div>
      </div>
    </>
  );
}

/** Rows of dollars against the largest of them: a name (a brand with its colour), a bar, a count, the dollars. A row
 *  with `onPick` is a press. */
function Bars({ label, rows }: { label: string; rows: Bar[] }) {
  const top = Math.max(...rows.map((r) => r.usd), 0.01);
  return (
    <ul className="bars" aria-label={label}>
      {rows.map((r) => {
        const inner = (
          <>
            <span className="nm">
              {r.colour && square(r.colour)}
              <span className="clip">{r.name}</span>
            </span>
            <span aria-hidden className="bbar">
              <i style={{ width: `${(r.usd / top) * 100}%` }} />
            </span>
            <span className="n">{r.note}</span>
            <b>
              <Money value={r.usd} estimated={r.estimated} />
            </b>
          </>
        );
        return (
          <li key={r.key}>
            {r.onPick ? (
              <button type="button" className="bb" aria-label={[r.name, r.note, `${r.estimated ? "about " : ""}${money(r.usd)}`].filter(Boolean).join(", ")} onClick={r.onPick}>
                {inner}
              </button>
            ) : (
              <div className="bb">{inner}</div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/** A table of videos, each opening on its page in the new look: its name, its brand when several are shown, a date and
 *  its dollars, every column named. Nothing is drawn when there are none. */
function Videos({ title, why, when, cost, rows }: { title: string; why?: string; when: string; cost: string; rows: Row[] }) {
  if (rows.length === 0) return null;
  const brands = rows.some((v) => v.brand);
  return (
    <section aria-label={title}>
      <h2>{title}</h2>
      {why && <p className="why">{why}</p>}
      <table>
        <thead>
          <tr>
            <th scope="col">Video</th>
            {brands && <th scope="col" className="hp cbrand">Brand</th>}
            <th scope="col" className="hp cwhen">{when}</th>
            <th scope="col" className="r">{cost}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((v) => (
            <tr key={v.id}>
              <th scope="row">
                <Link to={`/s/b/${v.brandId}/videos/${v.id}`}>{v.title}</Link>
              </th>
              {brands && <td className="q hp">{v.brand}</td>}
              <td className="q hp">{v.when ? day(v.when) : "—"}</td>
              <td className="r">
                <Money value={v.usd} estimated={v.estimated} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function More({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button type="button" className="btn soft showmore" onClick={onClick}>
      {children}
    </button>
  );
}

function Empty({ title, hint, children }: { title: string; hint: string; children?: ReactNode }) {
  return (
    <div className="hold bare">
      <Receipt size={20} strokeWidth={1.75} aria-hidden />
      <b>{title}</b>
      <p>{hint}</p>
      {children}
    </div>
  );
}
