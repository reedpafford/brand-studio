import { useEffect, useRef, type ReactNode } from "react";
import { ChevronRight, Plus, Search } from "lucide-react";
import { Link, NavLink, useSearchParams } from "react-router-dom";
import { useBrands } from "../shell/useBrands";
import { useRail } from "../useMedia";
import { useFootage } from "./FootageTab";
import { useVoices } from "./Voices";
import { useCounts, type TabSlug } from "./kinds";

const TABS: { slug: TabSlug; title: string; phone?: string }[] = [
  { slug: "characters", title: "Characters" },
  { slug: "places", title: "Places" },
  { slug: "products", title: "Products" },
  { slug: "footage", title: "Footage" },
  { slug: "presenters", title: "Presenters & voices", phone: "Presenters" },
  { slug: "kit", title: "Brand kit" },
];
export const tabPath = (brandId: number, slug: TabSlug) => (slug === "kit" ? `/b/${brandId}/brand` : `/b/${brandId}/library/${slug}`);

/** The search box's words, kept in the address (?q=) so a tab change keeps them. */
export function useSearch() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const set = (v: string) => setParams((p) => (v ? (p.set("q", v), p) : (p.delete("q"), p)), { replace: true });
  return [q, set] as const;
}

/** The brand library's frame (v6 S8, P-13): Brand › Library with its line and the tab's one press, then the tabs with
 *  their counts and the search box. On a phone: the brand, "Library", a + for the press, and the tabs as a strip. */
export function LibraryFrame({ brandId, tab, action, onAdd, addLabel, children }: { brandId: number; tab: TabSlug; action?: ReactNode; onAdd?: () => void; addLabel?: string; children: ReactNode }) {
  const brand = useBrands().data?.find((b) => b.id === brandId);
  const counts = useCounts(brandId);
  const voices = useVoices(brandId).length; // the brand's own voices (L4); the app's are everyone's
  const footage = useFootage(brandId).data?.length;
  const rail = useRail();
  const [q, setQ] = useSearch();
  const name = brand?.name ?? "";
  const strip = useRef<HTMLElement>(null);
  // On a phone the tabs scroll sideways: the open one is brought into view (Brand kit sits past the edge).
  useEffect(() => {
    void strip.current?.querySelector<HTMLElement>("[aria-current=page]")?.scrollIntoView?.({ block: "nearest", inline: "nearest" }); // it may return a promise
  }, [tab, rail]);
  const count = (slug: TabSlug) =>
    slug === "kit" ? undefined : slug === "footage" ? footage : slug === "presenters" ? (counts.presenters === undefined ? undefined : counts.presenters + voices) : counts[slug];
  if (!rail) {
    return (
      <main className="min-h-screen pb-24">
        <header className="flex min-h-14 items-center gap-2.5 border-b border-border bg-surface px-4">
          <span aria-hidden className="grid size-6 shrink-0 place-items-center rounded-sm text-xs font-semibold text-white" style={{ background: brand?.colours?.[0] || "var(--accent)" }}>
            {name.slice(0, 1).toUpperCase()}
          </span>
          <h1 className="text-md font-semibold">Library</h1>
          <span className="flex-1" />
          {onAdd ? (
            <button type="button" aria-label={addLabel} onClick={onAdd} className="grid size-control place-items-center rounded-md text-text">
              <Plus size={20} strokeWidth={1.75} aria-hidden />
            </button>
          ) : (
            action
          )}
        </header>
        <nav ref={strip} aria-label="Library" className="overflow-x-auto px-3.5 py-2">
          <div className="inline-flex gap-0.5 rounded-md bg-surface-2 p-0.5 whitespace-nowrap">
            {TABS.map((t) => (
              <NavLink key={t.slug} to={tabPath(brandId, t.slug)} aria-current={t.slug === tab ? "page" : undefined} className={`inline-flex min-h-control items-center rounded-[5px] px-3 text-base ${t.slug === tab ? "bg-surface font-medium text-text shadow-sm" : "text-muted"}`}>
                {t.phone ?? t.title}
              </NavLink>
            ))}
          </div>
        </nav>
        <div className="px-3.5 py-1.5">{children}</div>
      </main>
    );
  }
  return (
    <main className="flex min-h-screen flex-col">
      <header className="flex h-14 shrink-0 items-center gap-2.5 border-b border-border bg-surface px-5">
        <p className="flex items-center gap-1.5 whitespace-nowrap text-sm text-muted">
          <span>{name}</span>
          <ChevronRight size={12} strokeWidth={1.75} aria-hidden />
          <span className="font-semibold text-text">Library</span>
        </p>
        <span className="truncate text-sm text-muted">Only {name} sees these. They fill in each video’s cast.</span>
        <span className="flex-1" />
        {action}
      </header>
      <div className="flex shrink-0 items-center gap-0.5 border-b border-border bg-surface px-6">
        <nav aria-label="Library" className="flex gap-0.5">
          {TABS.map((t) => {
            const on = t.slug === tab;
            const n = count(t.slug);
            return (
              <Link key={t.slug} to={tabPath(brandId, t.slug)} aria-current={on ? "page" : undefined} className={`-mb-px inline-flex h-10 items-center gap-1.5 border-b-2 px-2.5 text-sm font-medium ${on ? "border-text text-text" : "border-transparent text-muted hover:text-text"}`}>
                {t.title}
                {n !== undefined && <span className="inline-flex h-4 items-center rounded-lg bg-surface-2 px-1.5 text-[11px] tabular-nums text-muted">{n}</span>}
              </Link>
            );
          })}
        </nav>
        <span className="flex-1" />
        {tab !== "kit" && (
          <label className="relative block w-[220px]">
            <span className="sr-only">Search the library</span>
            <Search size={14} strokeWidth={1.75} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search" className="h-[30px] w-full rounded-md border border-border-strong bg-surface pl-8 pr-3 text-sm text-text placeholder:text-muted" />
          </label>
        )}
      </div>
      <div className="flex-1 px-6 py-5">{children}</div>
    </main>
  );
}
