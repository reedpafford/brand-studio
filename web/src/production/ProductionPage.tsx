import type { ReactNode } from "react";
import { Check, ChevronDown, CircleAlert, Clapperboard, Clock, Film, TriangleAlert } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { fileUrl } from "../api/upload";
import { useMe } from "../auth/useMe";
import { Badge, Banner, Button, EmptyState, PageTop, Skeleton, Tabs, wholeCredits, type Tone } from "../components";
import { useBrands } from "../shell/useBrands";
import { lastText } from "../usage/parts";
import { useRail } from "../useMedia";
import { useProduction, useProductionSummary, type Row, type Step } from "./useProduction";
import { serverTime } from "../time";
import { linkText } from "../ui";

export const STEPS: Record<Step, string> = { breakdown: "Plan", assets: "Cast", storyboard: "Storyboard", clips: "Clips", downloads: "Final cut" };
export const FLAGS: Record<NonNullable<Row["flag"]>, { label: string; tone: Tone; icon: typeof Clock }> = {
  failed: { label: "Didn't finish", tone: "danger", icon: CircleAlert },
  stuck: { label: "Stuck", tone: "warning", icon: TriangleAlert },
  idle: { label: "No activity", tone: "warning", icon: Clock },
};

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
const label = (r: Row) => `${r.script.title}, version ${r.letter}, ${who(r)}, at ${STEPS[r.step]}${r.flag ? `, ${FLAGS[r.flag].label.toLowerCase()}` : ""}`;

/** What a moving video is doing now, by its step (v5 D_Production's Now column). */
const NOW: Record<Step, string> = { breakdown: "Making the plan", assets: "Casting", storyboard: "Drawing the storyboard", clips: "Making clips", downloads: "Making the final cut" };
// D_Production's four bars: Plan · Cast · Clips · Final cut (the stills are drawn on Clips, so the storyboard counts as Clips).
const BARS = ["Plan", "Cast", "Clips", "Final cut"] as const;
const BAR: Record<Step, number> = { breakdown: 0, assets: 1, storyboard: 2, clips: 2, downloads: 3 };

/** A compact select for the page's bars on a computer ("Brand: All" on the board); `label` names it for screen readers. */
function BarSelect({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <span className="relative inline-flex">
      <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)} className="min-h-control appearance-none rounded-md lg:min-h-control-dense border border-border bg-transparent pl-3 pr-8 text-sm font-medium hover:bg-surface-2">
        {options.map(([v, name]) => (
          <option key={v} value={v}>{name}</option>
        ))}
      </select>
      <ChevronDown size={14} strokeWidth={1.75} aria-hidden className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-muted" />
    </span>
  );
}

/** The steps as four short bars: done in green, the current one in the accent; all green once delivered (D_Production). */
function StepDots({ r }: { r: Row }) {
  const at = r.finished_at ? BARS.length : BAR[r.step];
  return (
    <span className="inline-flex gap-[3px]" role="img" aria-label={r.finished_at ? "Delivered: all 4 steps done" : `${BARS[at]}: step ${at + 1} of ${BARS.length}`}>
      {BARS.map((b, i) => (
        <i key={b} className={`h-1 w-3.5 rounded-sm ${i < at ? "bg-success" : i === at ? "bg-accent" : "bg-surface-3"}`} />
      ))}
    </span>
  );
}

/** The Now column: a flagged video's badge colour and reason, or what a moving one is doing and when it last moved. */
function Now({ r }: { r: Row }) {
  const f = r.flag ? FLAGS[r.flag] : null;
  return (
    <span className="flex min-w-0 items-start gap-2 text-sm">
      <span aria-hidden className={`mt-1.5 size-2 shrink-0 rounded-full ${f ? (f.tone === "danger" ? "bg-danger" : "bg-warning") : r.finished_at ? "bg-success" : "bg-accent"}`} />
      <span className="min-w-0 break-words">
        {f ? (
          <>
            <span className="font-medium">{f.label}</span> <span className="text-muted">{reason(r)}</span>
          </>
        ) : r.finished_at ? (
          <>
            Delivered <span className="text-muted">· {ago(lastText(r.finished_at))}</span>
          </>
        ) : (
          <>
            {NOW[r.step]}
            {r.step === "clips" && (r.clips_total ?? 0) > 0 && `: ${r.clips_made} of ${r.clips_total}`} <span className="text-muted">· {ago(lastText(r.last_activity_at))}</span>
          </>
        )}
      </span>
    </span>
  );
}


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

/** A row's spend (the Producer, 3 Nov): "spent N" in whole credits, the director's time included; where the owner approved
 *  a run, "up to M approved" muted under it (rule 34). The director's split is on Usage only. */
function Spent({ r }: { r: Row & { approved_up_to?: number | null } }) {
  return (
    <>
      <span className="block">spent {wholeCredits(r.credits_used).toLocaleString("en-US")}</span>
      {r.approved_up_to != null && <span className="block text-xs text-muted">up to {wholeCredits(r.approved_up_to).toLocaleString("en-US")} approved</span>}
    </>
  );
}

/** The owner's list of every video being made, across all brands (v5 D_Production): the three tabs, Brand in the top
 *  bar, nothing else to filter. Rows come needing attention first, then by last activity. Filters live in the address. */
export function ProductionPage() {
  const { data: me, isPending } = useMe();
  const rail = useRail();
  const [params, setParams] = useSearchParams();
  const { data: brands } = useBrands();
  const brand = params.get("brand") ?? "";
  const attention = params.get("attention") === "1";
  const delivered = params.get("delivered") === "1"; // the Delivered today tab (#1232)
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
  const { query, rows } = useProduction({ brand, editor: "", attention, delivered, q: "", sort: delivered ? "activity" : "attention" });

  if (isPending) return null;
  if (!owner || summary.error?.message === "404" || query.error?.message === "404") return <p className="p-6">Page not found.</p>;

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
  const named = brands?.find((b) => String(b.id) === brand)?.name;
  // v5 D_Production: the same line on every tab.
  const count = summary.data && [named ?? "Every brand", `${all} video${all === 1 ? "" : "s"} making`, needs > 0 ? `${needs} need${needs === 1 ? "s" : ""} attention` : ""].filter(Boolean).join(" · ");

  const showTabs = (
    <Tabs label="Show" value={delivered ? "delivered" : attention ? "attention" : "making"} onChange={(t) => setParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("attention");
      next.delete("delivered");
      if (t !== "making") next.set(t, "1");
      return next;
    }, { replace: true })} tabs={[
      { id: "making", label: "Making", count: all },
      { id: "attention", label: rail ? "Needs attention" : "Attention", count: summary.data ? needs : undefined },
      { id: "delivered", label: rail ? "Delivered today" : "Delivered", count: summary.data?.delivered_today },
    ]} />
  );

  let empty: ReactNode = null;
  if (query.isSuccess && rows.length === 0) {
    if (delivered) empty = <EmptyState icon={Clapperboard} title="Nothing delivered today yet.">Videos show here on the day their final cut is made.</EmptyState>;
    else if (attention) empty = <EmptyState icon={Check} title="Nothing needs attention." action={<Button variant="ghost" onClick={() => set("attention", "")}>Show all</Button>}>Every video is moving.</EmptyState>;
    else if (brand) empty = <EmptyState icon={Clapperboard} title={`Nothing is being made in ${named ?? "this brand"} right now.`} action={<Button variant="ghost" onClick={() => set("brand", "")}>Every brand</Button>} />;
    else empty = <EmptyState icon={Clapperboard} title="Nothing is being made right now.">A video shows here while it's being made, from its first plan to its final cut.</EmptyState>;
  }

  return (
    <main className="mx-auto max-w-content space-y-4 p-4 sm:p-6">
      <PageTop title="In production" line={count && <>{count}{!delivered && !brand && waitingLink && <> · {waitingLink}</>}</>}>
        <BarSelect label="Brand" value={brand} onChange={(v) => set("brand", v)} options={[["", "Brand: All"], ...(brands ?? []).map((b): [string, string] => [String(b.id), b.name])]} />
      </PageTop>
      {/* v5 D_Production: only the three tabs, in a band; on a phone with shorter names (QA-3 on #1241). */}
      <div className="-mx-4 -mt-4 border-b border-border px-4 py-2 sm:-mx-6 sm:px-6">{showTabs}</div>
      {query.isError && <Banner title="Couldn't load the videos being made." action={<Button variant="secondary" onClick={() => void query.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      {query.isPending && (
        <div role="status" aria-label="Loading" className={rail ? "space-y-2" : "grid gap-3 sm:grid-cols-2"}>
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className={rail ? "h-16" : "h-40"} />
          ))}
        </div>
      )}
      {empty}
      {rows.length > 0 && (rail ? <Table rows={rows} showBrand={!brand} /> : <Cards rows={rows} />)}
      {query.hasNextPage && (
        <Button variant="secondary" busy={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()} className="w-full lg:w-auto">
          Show more
        </Button>
      )}
    </main>
  );
}

/** v5 D_Production: Video · Brand · Step · Now · Maker · Spent, one hairline row each across the page. */
function Table({ rows, showBrand }: { rows: Row[]; showBrand: boolean }) {
  const cols = showBrand ? "grid-cols-[minmax(0,1.6fr)_120px_96px_minmax(0,1.6fr)_100px_140px]" : "grid-cols-[minmax(0,1.6fr)_96px_minmax(0,1.6fr)_100px_140px]";
  return (
    <div className="-mx-6 -mt-4">
      <div aria-hidden className={`grid ${cols} gap-x-4 border-b border-border px-6 py-2 text-xs text-muted`}>
        <span>Video</span>
        {showBrand && <span>Brand</span>}
        <span>Step</span>
        <span>Now</span>
        <span>Maker</span>
        <span className="text-right">Spent</span>
      </div>
      <ul>
        {rows.map((r) => (
          <li key={r.project_id} className="relative border-b border-border">
            <Link to={`/b/${r.brand.id}/projects/${r.project_id}`} aria-label={label(r)} className={`grid ${cols} min-h-13 items-center gap-x-4 px-6 py-2 text-sm tabular-nums hover:bg-surface-2`}>
              <span className="min-w-0 break-words font-medium">{r.script.title} · {r.letter}</span>
              {showBrand && (
                <span className="min-w-0 break-words text-muted">{r.brand.name}</span>
              )}
              <StepDots r={r} />
              <Now r={r} />
              <span className="min-w-0 break-words text-muted">{who(r)}</span>
              <span className="text-right">
                <Spent r={r} />
              </span>
            </Link>
          </li>
        ))}
      </ul>
      <p className="px-6 py-3 text-xs text-muted">Steps: Plan · Cast · Clips · Final cut. A row opens its video on the director thread.</p>
    </div>
  );
}

function Cards({ rows }: { rows: Row[] }) {
  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {rows.map((r) => (
        <li key={r.project_id} className="relative">
          <Link to={`/b/${r.brand.id}/projects/${r.project_id}`} aria-label={label(r)} className="block space-y-3 rounded-lg border border-border bg-surface p-4 hover:bg-surface-2">
            <span className="flex gap-3">
              <Poster id={r.poster_file_id} size="h-22 w-14" />
              <span className="min-w-0 flex-1 space-y-1">
                <span className="block break-words font-display text-md font-bold">{r.script.title} · {r.letter}</span>
                <span className="block break-words text-sm text-muted">{r.brand.name} · {who(r)}</span>
                {/* Like the computer's Now (QA-3 on #1241); a flagged one keeps its step here and its flag below. */}
                {r.flag ? <span className="block text-sm text-muted">{STEPS[r.step]} · {ago(lastText(r.last_activity_at))}</span> : <span className="block text-muted"><Now r={r} /></span>}
                <span className="block text-sm text-muted tabular-nums">
                  <Spent r={r} />
                </span>
              </span>
            </span>
            <FlagLine r={r} />
          </Link>
        </li>
      ))}
    </ul>
  );
}
