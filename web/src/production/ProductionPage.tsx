import { useState, type ReactNode } from "react";
import { Check, CircleAlert, Clapperboard, Clock, Film, Search, TriangleAlert } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { fileUrl } from "../api/upload";
import { useMe } from "../auth/useMe";
import { Badge, Banner, Button, Card, EmptyState, Select, Sheet, Skeleton, type Tone } from "../components";
import { useDebounced } from "../scripts/ScriptsPage";
import { VideoMenu, useVideoActions, type VideoTarget } from "../projects/ReleaseVideo";
import { useBrands } from "../shell/useBrands";
import { lastText, money } from "../usage/parts";
import { useRail } from "../useMedia";
import { useProduction, useProductionSummary, type Row, type Sort, type Step } from "./useProduction";
import { serverTime } from "../time";

const STEPS: Record<Step, string> = { breakdown: "Breakdown", assets: "Assets", storyboard: "Storyboard", clips: "Clips", downloads: "Downloads" };
const SORTS: { id: Sort; label: string }[] = [
  { id: "attention", label: "Needs attention first" },
  { id: "activity", label: "Last activity" },
  { id: "credits", label: "Most credits used" },
  { id: "budget", label: "Closest to budget" },
];
const sortFrom = (s: string | null): Sort => SORTS.find((x) => x.id === s)?.id ?? "attention";
const FLAGS: Record<NonNullable<Row["flag"]>, { label: string; tone: Tone; icon: typeof Clock }> = {
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
function reason(r: Row) {
  if (r.flag === "failed") return `${STEPS[r.step]}: ${r.flag_problem ?? "the last job didn't finish."}`;
  if (r.flag === "stuck") return `${r.flag_job ?? "Working"} for ${r.flag_since ? span(r.flag_since) : "a while"}`;
  return `Nothing for ${r.flag_since ? Math.max(2, Math.floor(mins(r.flag_since) / 1440)) : 2} days`;
}
/** Who started it; the server says nobody when that person is gone. */
const who = (r: Row) => r.editor?.name ?? "Someone";
const target = (r: Row): VideoTarget => ({ id: r.project_id, name: `${r.script.title} · ${r.letter}`, letter: r.letter, creditsUsed: r.credits_used });
const label = (r: Row) => `${r.script.title}, version ${r.letter}, ${who(r)}, at ${STEPS[r.step]}${r.flag ? `, ${FLAGS[r.flag].label.toLowerCase()}` : ""}`;
const nearBudget = (r: Row) => r.budget_credits > 0 && r.credits_used / r.budget_credits >= 0.9;

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
    <span title={nearBudget(r) ? CLOSE : undefined} className={nearBudget(r) ? "text-warning" : undefined}>
      {r.credits_used} of {r.budget_credits}
    </span>
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
  const waitingText = waiting > 0 ? `${waiting} finished video${waiting === 1 ? " has" : "s have"} changes waiting` : "";
  const count = summary.data && (filtered ? `${total ?? 0} of ${all} video${all === 1 ? "" : "s"}` : [`${all} video${all === 1 ? "" : "s"} being made`, needs > 0 ? `${needs} need${needs === 1 ? "s" : ""} attention` : "", waitingText].filter(Boolean).join(" · "));

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
  const clearButton = filtered && <Button variant="ghost" onClick={clear}>Clear filters</Button>;
  const active = [brand, editor, attention, sort !== "attention"].filter(Boolean).length;

  let empty: ReactNode = null;
  if (query.isSuccess && rows.length === 0) {
    if (!filtered) empty = <EmptyState icon={Clapperboard} title="Nothing is being made right now.">Videos show up here when someone starts a version from the library.</EmptyState>;
    else if (attention && !(brand || editor || q)) empty = <EmptyState icon={Check} title="Nothing needs attention." action={<Button variant="ghost" onClick={() => set("attention", "")}>Show all</Button>}>Every video is moving.</EmptyState>;
    else empty = <EmptyState icon={Search} title="Nothing matches these filters." action={clearButton || undefined} />;
  }

  return (
    <main className="mx-auto max-w-content space-y-5 p-4 sm:p-6">
      <div>
        <p className="hidden text-xs font-bold uppercase tracking-[0.12em] text-muted lg:block">Studio</p>
        <h1 className="type-page">In production</h1>
        <p className="text-sm text-muted">{count ?? " "}</p>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="relative block min-w-0 flex-1 lg:w-64 lg:flex-none">
          <span className="sr-only">Search scripts</span>
          <Search size={20} strokeWidth={1.75} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input type="search" role="searchbox" placeholder="Search scripts" value={text} onChange={(e) => (setText(e.target.value), set("q", e.target.value.trim()))} className="min-h-control w-full rounded-md border border-border bg-surface pl-10 pr-3 lg:min-h-control-dense" />
        </label>
        {rail ? (
          <>
            <div className="w-40">{brandSelect}</div>
            <div className="w-40">{editorSelect}</div>
            {toggle}
            {clearButton}
            <div className="ml-auto w-56">{sortSelect}</div>
          </>
        ) : (
          <Button variant={active > 0 ? "primary" : "secondary"} className="shrink-0 whitespace-nowrap" onClick={() => setSheet(true)}>
            {active > 0 ? `Filters (${active})` : "Filters"}
          </Button>
        )}
      </div>
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

function Table({ rows, showBrand, colour, onRelease }: { rows: Row[]; showBrand: boolean; colour: (id: number) => string | undefined; onRelease: (r: Row) => void }) {
  const cols = showBrand ? "grid-cols-[minmax(0,2.6fr)_minmax(0,1.2fr)_minmax(0,0.9fr)_minmax(0,1fr)_minmax(0,0.9fr)_minmax(0,1.5fr)_44px]" : "grid-cols-[minmax(0,2.6fr)_minmax(0,0.9fr)_minmax(0,1fr)_minmax(0,0.9fr)_minmax(0,1.5fr)_44px]";
  return (
    <Card className="p-0 sm:p-0">
      <div aria-hidden className={`grid ${cols} gap-x-4 border-b border-border px-4 py-3 text-sm font-medium text-muted`}>
        <span>Video</span>
        {showBrand && <span>Brand</span>}
        <span>Editor</span>
        <span>Step</span>
        <span className="text-right">Last activity</span>
        <span className="text-right">Credits</span>
        <span />
      </div>
      <ul className="divide-y divide-border">
        {rows.map((r) => (
          <li key={r.project_id} className="relative">
            <Link to={`/b/${r.brand.id}/projects/${r.project_id}`} aria-label={label(r)} className={`grid ${cols} items-center gap-x-4 gap-y-2 px-4 py-3 text-sm tabular-nums hover:bg-surface-2`}>
              <span className="flex min-w-0 items-center gap-3">
                <Poster id={r.poster_file_id} size="h-14 w-9" />
                <span className="min-w-0 break-words font-semibold">{r.script.title} · {r.letter}</span>
              </span>
              {showBrand && (
                <span className="flex min-w-0 items-center gap-2">
                  <Dot colour={colour(r.brand.id)} />
                  <span className="min-w-0 break-words">{r.brand.name}</span>
                </span>
              )}
              <span className="min-w-0 break-words">{who(r)}</span>
              <span>{STEPS[r.step]}</span>
              <span className="text-right">{lastText(r.last_activity_at)}</span>
              <span className="text-right">
                <Credits r={r} /> <span className="text-muted">{money(r.spent_usd)}</span>
              </span>
              <span aria-hidden />
              {r.flag && (
                <span className="col-span-full pl-12">
                  <FlagLine r={r} />
                </span>
              )}
            </Link>
            <div className="absolute right-2 top-3 flex items-center">
              <VideoMenu title={`${r.script.title} · ${r.letter}`} onRelease={() => onRelease(r)} />
            </div>
          </li>
        ))}
      </ul>
    </Card>
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
