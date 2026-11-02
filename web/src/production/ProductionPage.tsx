import { useState, type ReactNode } from "react";
import { Check, ChevronDown, CircleAlert, Clapperboard, Clock, Film, Search, TriangleAlert } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { fileUrl } from "../api/upload";
import { useMe } from "../auth/useMe";
import { Badge, Banner, Button, EmptyState, PageTop, Select, Sheet, Skeleton, Tabs, creditsText, type Tone } from "../components";
import { useDebounced } from "../scripts/status";
import { VideoMenu, useVideoActions, type VideoTarget } from "../projects/ReleaseVideo";
import { useBrands } from "../shell/useBrands";
import { lastText, money } from "../usage/parts";
import { useRail } from "../useMedia";
import { useProduction, useProductionSummary, type Row, type Sort, type Step } from "./useProduction";
import { serverTime } from "../time";
import { budgetUsed } from "../projects/budget";
import { linkText } from "../ui";

export const STEPS: Record<Step, string> = { breakdown: "Plan", assets: "Cast", storyboard: "Storyboard", clips: "Clips", downloads: "Final cut" };
const SORTS: { id: Sort; label: string }[] = [
  { id: "attention", label: "Needs attention first" },
  { id: "activity", label: "Last activity" },
  { id: "credits", label: "Most credits used" },
  { id: "budget", label: "Closest to budget" },
];
const sortFrom = (s: string | null): Sort => SORTS.find((x) => x.id === s)?.id ?? "attention";
export const FLAGS: Record<NonNullable<Row["flag"]>, { label: string; tone: Tone; icon: typeof Clock }> = {
  failed: { label: "Didn't finish", tone: "danger", icon: CircleAlert },
  stuck: { label: "Stuck", tone: "warning", icon: TriangleAlert },
  idle: { label: "No activity", tone: "warning", icon: Clock },
};
const CLOSE = "Close to the budget. Going over needs your approval.";

const mins = (iso: string) => Math.max(1, Math.floor((Date.now() - serverTime(iso).getTime()) / 60_000));
const span = (iso: string) => (mins(iso) < 90 ? `${mins(iso)} min` : `${Math.floor(mins(iso) / 60)} h`);
/** "3 h" reads "3 h ago" on a card; "yesterday" and dates stand alone. */
const ago = (t: string) => (/ (min|h|days)$/.test(t) ? `${t} ago` : t);

/** What follows the badge, in plain words. */
export function reason(r: Row) {
  if (r.flag === "failed") return `${STEPS[r.step]}: ${r.flag_problem ?? "the last job didn't finish."}`;
  if (r.flag === "stuck") return `${r.flag_job ?? "Working"} for ${r.flag_since ? span(r.flag_since) : "a while"}`;
  return `Nothing for ${r.flag_since ? Math.max(2, Math.floor(mins(r.flag_since) / 1440)) : 2} days`;
}
/** Who started it; the server says nobody when that person is gone. */
export const who = (r: Row) => r.editor?.name ?? "Someone";
const target = (r: Row): VideoTarget => ({ id: r.project_id, name: `${r.script.title} · ${r.letter}`, letter: r.letter, creditsUsed: r.credits_used });
const label = (r: Row) => `${r.script.title}, version ${r.letter}, ${who(r)}, at ${STEPS[r.step]}${r.flag ? `, ${FLAGS[r.flag].label.toLowerCase()}` : ""}`;
const nearBudget = (r: Row) => r.budget_credits > 0 && budgetUsed(r) / r.budget_credits >= 0.9; // the director's own time never counts (DECISIONS #1066)

/** What a moving video is doing now, by its step (v5 D_Production's Now column). */
const NOW: Record<Step, string> = { breakdown: "Making the plan", assets: "Casting", storyboard: "Drawing the storyboard", clips: "Making clips", downloads: "Making the final cut" };
const ORDER: Step[] = ["breakdown", "assets", "storyboard", "clips", "downloads"];

/** A compact select for the page's bars on a computer ("Brand: All" on the board); `label` names it for screen readers. */
function BarSelect({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <span className="relative inline-flex">
      <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)} className="min-h-control-dense appearance-none rounded-md border border-border bg-transparent pl-3 pr-8 text-sm font-medium hover:bg-surface-2">
        {options.map(([v, name]) => (
          <option key={v} value={v}>{name}</option>
        ))}
      </select>
      <ChevronDown size={14} strokeWidth={1.75} aria-hidden className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-muted" />
    </span>
  );
}

/** The steps as short bars: done in green, the current one in the accent (D_Production's Step column). */
function StepDots({ step }: { step: Step }) {
  const at = ORDER.indexOf(step);
  return (
    <span className="inline-flex gap-[3px]" role="img" aria-label={`${STEPS[step]}: step ${at + 1} of ${ORDER.length}`}>
      {ORDER.map((s, i) => (
        <i key={s} className={`h-1 w-3.5 rounded-sm ${i < at ? "bg-success" : i === at ? "bg-accent" : "bg-surface-3"}`} />
      ))}
    </span>
  );
}

/** The Now column: a flagged video's badge colour and reason, or what a moving one is doing and when it last moved. */
function Now({ r }: { r: Row }) {
  const f = r.flag ? FLAGS[r.flag] : null;
  return (
    <span className="flex min-w-0 items-start gap-2 text-sm">
      <span aria-hidden className={`mt-1.5 size-2 shrink-0 rounded-full ${!f ? "bg-accent" : f.tone === "danger" ? "bg-danger" : "bg-warning"}`} />
      <span className="min-w-0 break-words">
        {f ? (
          <>
            <span className="font-medium">{f.label}</span> <span className="text-muted">{reason(r)}</span>
          </>
        ) : (
          <>
            {NOW[r.step]} <span className="text-muted">· {ago(lastText(r.last_activity_at))}</span>
          </>
        )}
      </span>
    </span>
  );
}

const Dot = ({ colour }: { colour?: string }) => <span aria-hidden className="size-3 shrink-0 rounded-full bg-brand" style={colour ? { background: colour } : undefined} />;

function Poster({ id, size }: { id: number | null; size: string }) {
  return (
    <span aria-hidden className={`grid shrink-0 place-items-center overflow-hidden rounded-md bg-surface-2 text-muted ${size}`}>
      {id ? <img src={fileUrl(id)} alt="" className="size-full object-cover" /> : <Film size={20} strokeWidth={1.75} />}
    </span>
  );
}

function FlagLine({ r }: { r: Row }) {
  if (!r.flag) return null;
  const f = FLAGS[r.flag];
  return (
    <span className="flex flex-col items-start gap-1 lg:flex-row lg:flex-wrap lg:items-center lg:gap-2">
      <Badge tone={f.tone} icon={f.icon}>{f.label}</Badge>
      <span className="text-sm text-muted">{reason(r)}</span>
    </span>
  );
}

function Credits({ r }: { r: Row }) {
  return (
    <>
      <span title={nearBudget(r) ? CLOSE : undefined} className={nearBudget(r) ? "text-warning" : undefined}>
        {Math.round(budgetUsed(r))} of {Math.round(r.budget_credits)}
      </span>
      {/* The director's own time, apart from the budget (#1216, QA-3 on #1218). */}
      {(r.director_credits ?? 0) > 0 && <span className="block text-xs text-muted">{creditsText(r.director_credits)} of director time</span>}
    </>
  );
}

/** Reed's list of every version being made, across all brands. Filters live in the address. */
export function ProductionPage() {
  const { data: me, isPending } = useMe();
  const rail = useRail();
  const [params, setParams] = useSearchParams();
  const { data: brands } = useBrands();
  const colour = (id: number) => brands?.find((b) => b.id === id)?.colours?.[0];
  const brand = params.get("brand") ?? "";
  const editor = params.get("editor") ?? "";
  const attention = params.get("attention") === "1";
  const sort = sortFrom(params.get("sort"));
  const [text, setText] = useState(params.get("q") ?? "");
  const q = useDebounced(text.trim());
  const [sheet, setSheet] = useState(false);
  const video = useVideoActions();
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
  const owner = me?.role === "owner";
  const summary = useProductionSummary(owner);
  const { query, rows, total } = useProduction({ brand, editor, attention, q, sort });
  // Everyone with a video in the list, kept as filters narrow it.
  const [people, setPeople] = useState(new Map<number, string>());
  const seen = rows.flatMap((r): [number, string][] => (r.editor ? [[r.editor.id, r.editor.name]] : []));
  if (seen.some(([id, name]) => people.get(id) !== name)) setPeople(new Map([...people, ...seen]));

  if (isPending) return null;
  if (!owner || summary.error?.message === "404" || query.error?.message === "404") return <p className="p-6">Page not found.</p>;

  const filtered = !!(brand || editor || attention || q);
  const clear = () => {
    setText("");
    setParams({}, { replace: true });
  };
  const all = summary.data?.in_production;
  const needs = summary.data?.needs_attention ?? 0;
  // Finished videos whose clips changed since are not being made, but they aren't done either (#749 LW2).
  const waiting = summary.data?.changes_waiting ?? 0;
  // They are listed, by brand, in Usage (this page is Reed's, and so is Usage).
  const waitingLink = waiting > 0 && (
    <Link to="/usage" className={`${linkText} inline-flex min-h-11 items-center sm:min-h-0`}>
      {waiting} finished video{waiting === 1 ? " has" : "s have"} changes waiting
    </Link>
  );
  const count = summary.data && (filtered ? `${total ?? 0} of ${all} video${all === 1 ? "" : "s"}` : [`${all} video${all === 1 ? "" : "s"} being made`, needs > 0 ? `${needs} need${needs === 1 ? "s" : ""} attention` : ""].filter(Boolean).join(" · "));

  const brandSelect = (
    <Select label="Brand" value={brand} onChange={(e) => set("brand", e.target.value)}>
      <option value="">All</option>
      {brands?.map((b) => (
        <option key={b.id} value={b.id}>{b.name}</option>
      ))}
    </Select>
  );
  const editorSelect = (
    <Select label="Editor" value={editor} onChange={(e) => set("editor", e.target.value)}>
      <option value="">Anyone</option>
      {[...people].map(([id, name]) => (
        <option key={id} value={id}>{name}</option>
      ))}
    </Select>
  );
  const sortSelect = (
    <Select label="Sort" value={sort} onChange={(e) => set("sort", e.target.value === "attention" ? "" : e.target.value)}>
      {SORTS.map((s) => (
        <option key={s.id} value={s.id}>{s.label}</option>
      ))}
    </Select>
  );
  const toggle = (
    <button type="button" aria-pressed={attention} onClick={() => set("attention", attention ? "" : "1")} className={`inline-flex min-h-control items-center whitespace-nowrap rounded-md border px-4 font-medium lg:min-h-control-dense ${attention ? "border-accent bg-accent-soft text-accent-text" : "border-border bg-surface hover:bg-surface-2"}`}>
      Needs attention
    </button>
  );
  const search = (
    <label className="relative block min-w-0 flex-1 lg:w-56 lg:flex-none">
      <span className="sr-only">Search scripts</span>
      <Search size={16} strokeWidth={1.75} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
      <input type="search" role="searchbox" placeholder="Search scripts" value={text} onChange={(e) => (setText(e.target.value), set("q", e.target.value.trim()))} className="min-h-control w-full rounded-md border border-border bg-surface pl-9 pr-3 lg:min-h-control-dense" />
    </label>
  );
  const clearButton = filtered && <Button variant="ghost" onClick={clear}>Clear filters</Button>;
  const active = [brand, editor, attention, sort !== "attention"].filter(Boolean).length;

  let empty: ReactNode = null;
  if (query.isSuccess && rows.length === 0) {
    if (!filtered) empty = <EmptyState icon={Clapperboard} title="Nothing is being made right now.">Videos show up here when someone starts a version from the library.</EmptyState>;
    else if (attention && !(brand || editor || q)) empty = <EmptyState icon={Check} title="Nothing needs attention." action={<Button variant="ghost" onClick={() => set("attention", "")}>Show all</Button>}>Every video is moving.</EmptyState>;
    else empty = <EmptyState icon={Search} title="Nothing matches these filters." action={clearButton || undefined} />;
  }

  return (
    <main className="mx-auto max-w-content space-y-4 p-4 sm:p-6">
      <PageTop title="In production" line={count && <>{count}{!filtered && waitingLink && <> · {waitingLink}</>}</>}>
        {rail && <BarSelect label="Brand" value={brand} onChange={(v) => set("brand", v)} options={[["", "Brand: All"], ...(brands ?? []).map((b): [string, string] => [String(b.id), b.name])]} />}
      </PageTop>
      {/* v5 D_Production: Making and Needs attention as tabs in a band, the other filters on its right. */}
      {rail && (
        <div className="-mx-6 -mt-4 flex flex-wrap items-center gap-3 border-b border-border px-6 py-2">
          <Tabs label="Show" value={attention ? "attention" : "making"} onChange={(t) => set("attention", t === "attention" ? "1" : "")} tabs={[
            { id: "making", label: "Making", count: all },
            { id: "attention", label: "Needs attention", count: summary.data ? needs : undefined },
          ]} />
          <span className="flex-1" />
          {clearButton}
          {search}
          <BarSelect label="Editor" value={editor} onChange={(v) => set("editor", v)} options={[["", "Editor: Anyone"], ...[...people].map(([id, name]): [string, string] => [String(id), name])]} />
          <BarSelect label="Sort" value={sort} onChange={(v) => set("sort", v === "attention" ? "" : v)} options={SORTS.map((x): [string, string] => [x.id, x.label])} />
        </div>
      )}
      {!rail && (
      <div className="flex flex-wrap items-end gap-3">
        {search}
        <Button variant={active > 0 ? "primary" : "secondary"} className="shrink-0 whitespace-nowrap" onClick={() => setSheet(true)}>
          {active > 0 ? `Filters (${active})` : "Filters"}
        </Button>
      </div>
      )}
      {query.isError && <Banner title="Couldn't load the videos being made." action={<Button variant="secondary" onClick={() => void query.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      {query.isPending && (
        <div role="status" aria-label="Loading" className={rail ? "space-y-2" : "grid gap-3 sm:grid-cols-2"}>
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className={rail ? "h-16" : "h-40"} />
          ))}
        </div>
      )}
      {empty}
      {rows.length > 0 && (rail ? <Table rows={rows} showBrand={!brand} colour={colour} onRelease={(r) => video.release(target(r))} /> : <Cards rows={rows} colour={colour} onRelease={(r) => video.release(target(r))} />)}
      {query.hasNextPage && (
        <Button variant="secondary" busy={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()} className="w-full lg:w-auto">
          Show more
        </Button>
      )}
      {video.dialog}
      {sheet && (
        <Sheet title="Filters" onClose={() => setSheet(false)}>
          <div className="space-y-3 pb-2">
            {brandSelect}
            {editorSelect}
            {toggle}
            {sortSelect}
            {clearButton}
          </div>
        </Sheet>
      )}
    </main>
  );
}

/** v5 D_Production: Video · Brand · Step · Now · Maker · Spent, one hairline row each across the page. */
function Table({ rows, showBrand, colour, onRelease }: { rows: Row[]; showBrand: boolean; colour: (id: number) => string | undefined; onRelease: (r: Row) => void }) {
  const cols = showBrand ? "grid-cols-[minmax(0,1.6fr)_120px_96px_minmax(0,1.6fr)_100px_140px_44px]" : "grid-cols-[minmax(0,1.6fr)_96px_minmax(0,1.6fr)_100px_140px_44px]";
  return (
    <div className="-mx-6 -mt-4">
      <div aria-hidden className={`grid ${cols} gap-x-4 border-b border-border px-6 py-2 text-xs text-muted`}>
        <span>Video</span>
        {showBrand && <span>Brand</span>}
        <span>Step</span>
        <span>Now</span>
        <span>Maker</span>
        <span className="text-right">Spent</span>
        <span />
      </div>
      <ul>
        {rows.map((r) => (
          <li key={r.project_id} className="relative border-b border-border">
            <Link to={`/b/${r.brand.id}/projects/${r.project_id}`} aria-label={label(r)} className={`grid ${cols} min-h-13 items-center gap-x-4 px-6 py-2 text-sm tabular-nums hover:bg-surface-2`}>
              <span className="min-w-0 break-words font-medium">{r.script.title} · {r.letter}</span>
              {showBrand && (
                <span className="flex min-w-0 items-center gap-2 text-muted">
                  <Dot colour={colour(r.brand.id)} />
                  <span className="min-w-0 break-words">{r.brand.name}</span>
                </span>
              )}
              <StepDots step={r.step} />
              <Now r={r} />
              <span className="min-w-0 break-words text-muted">{who(r)}</span>
              <span className="text-right">
                <Credits r={r} /> <span className="text-muted">{money(r.spent_usd)}</span>
              </span>
              <span aria-hidden />
            </Link>
            <div className="absolute right-4 top-1/2 flex -translate-y-1/2 items-center">
              <VideoMenu title={`${r.script.title} · ${r.letter}`} onRelease={() => onRelease(r)} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Cards({ rows, colour, onRelease }: { rows: Row[]; colour: (id: number) => string | undefined; onRelease: (r: Row) => void }) {
  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {rows.map((r) => (
        <li key={r.project_id} className="relative">
          <Link to={`/b/${r.brand.id}/projects/${r.project_id}`} aria-label={label(r)} className="block space-y-3 rounded-lg border border-border bg-surface p-4 hover:bg-surface-2">
            <span className="flex gap-3">
              <Poster id={r.poster_file_id} size="h-22 w-14" />
              <span className="min-w-0 flex-1 space-y-1">
                <span className="block break-words font-display text-md font-bold">{r.script.title} · {r.letter}</span>
                <span className="flex items-center gap-2 text-sm text-muted">
                  <Dot colour={colour(r.brand.id)} />
                  <span className="min-w-0 break-words">{r.brand.name} · {who(r)}</span>
                </span>
                <span className="block text-sm text-muted">{STEPS[r.step]} · {ago(lastText(r.last_activity_at))}</span>
                <span className="block text-sm text-muted tabular-nums">
                  <Credits r={r} /> credits · {money(r.spent_usd)}
                </span>
              </span>
              <span aria-hidden className="size-control shrink-0" />
            </span>
            <FlagLine r={r} />
          </Link>
          <div className="absolute right-1 top-1">
            <VideoMenu title={`${r.script.title} · ${r.letter}`} onRelease={() => onRelease(r)} />
          </div>
        </li>
      ))}
    </ul>
  );
}
