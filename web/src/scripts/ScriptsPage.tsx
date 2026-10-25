import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, CircleAlert, Clock, FileText, Pencil, Plus, Search } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { Badge, Banner, Button, Card, EmptyState, Select, Sheet, Skeleton, buttonClass, type Tone } from "../components";
import { useMe } from "../auth/useMe";
import { useReferences } from "../projects/BriefPickers";
import { useBrands } from "../shell/useBrands";
import { ActionBar } from "../shell/ActionBar";
import { useRail } from "../useMedia";
import { LegacyVideos } from "../projects/ProjectsPage";

type Row = components["schemas"]["ScriptRow"];
type Version = Row["versions"][number];

const PAGE = 30;
const LETTER = ["A", "B", "C"];

/** A version's status in words, with a tone as the second signal. Never an internal word. */
const STATUS: Record<string, { label: string; tone: Tone; icon?: typeof Check }> = {
  draft: { label: "Writing", tone: "neutral", icon: Pencil },
  approved: { label: "Ready to make", tone: "accent" },
  in_production: { label: "In production", tone: "warning", icon: Clock },
  clips_ready: { label: "In production", tone: "warning", icon: Clock },
  done: { label: "Video done", tone: "success", icon: Check },
  failed: { label: "Didn't finish", tone: "danger", icon: CircleAlert },
};

const STATUS_FILTER = [
  ["", "Any"],
  ["draft", "Writing"],
  ["published", "Ready to make"],
  ["in_production", "In production"],
  ["done", "Video done"],
] as const;
const LENGTH_FILTER = [
  ["", "Any"],
  ["0-15", "Under 15 s"],
  ["15-30", "15–30 s"],
  ["30-60", "30–60 s"],
  ["60-", "Over 60 s"],
] as const;
const SORTS = [
  ["", "Recently changed"],
  ["newest", "Newest"],
  ["title", "Title A–Z"],
] as const;

/** "just now", "5 min ago", "3 h ago", "yesterday", "2 days ago", then the date. */
export function age(iso: string, now = Date.now()) {
  const mins = Math.max(0, Math.floor((now - new Date(iso).getTime()) / 60_000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "yesterday";
  if (days < 7) return `${days} days ago`;
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

const lengthText = (versions: Version[]) => {
  const s = versions.map((v) => v.seconds).filter((n) => n > 0);
  if (s.length === 0) return "Length set at Breakdown";
  const lo = Math.round(Math.min(...s));
  const hi = Math.round(Math.max(...s));
  return lo === hi ? `${lo} s` : `${lo}–${hi} s`;
};

function useDebounced<T>(value: T, ms = 300) {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return settled;
}

/** The brand's home: every script, with its versions as chips. Filters live in the address so a view can be shared. */
export function ScriptsPage() {
  const brandId = Number(useParams().brandId);
  const { data: brands } = useBrands();
  const { data: me } = useMe();
  const rail = useRail();
  const [params, setParams] = useSearchParams();
  const brand = brands?.find((b) => b.id === brandId);
  const owner = me?.role === "owner";
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
  // An editor starts on what is ready to make; Reed on everything.
  const status = params.get("status") ?? (owner ? "" : "published");
  const apiStatus = status === "any" ? "" : status;
  const len = params.get("len") ?? "";
  const ref = params.get("ref") ?? "";
  const left = params.get("left") ?? "";
  const mine = params.get("mine") === "1";
  const all = owner && params.get("brand") === "all";
  const sort = params.get("sort") ?? "";
  const [text, setText] = useState(params.get("q") ?? "");
  const q = useDebounced(text.trim());
  const [shown, setShown] = useState(PAGE);
  const [sheet, setSheet] = useState(false);
  useEffect(() => set("q", q), [q]); // eslint-disable-line react-hooks/exhaustive-deps
  const [lo, hi] = len ? len.split("-") : ["", ""];
  const refs = useReferences();

  const scripts = useQuery({
    queryKey: ["scripts", { brandId: all ? null : brandId, status: apiStatus, q, ref, left, lo, hi }],
    queryFn: async () => {
      const { data } = await api.GET("/scripts", {
        params: {
          query: {
            ...(all ? {} : { brand_id: brandId }),
            ...(apiStatus ? { status: apiStatus } : {}),
            ...(q ? { q } : {}),
            ...(ref ? { reference: ref === "with" } : {}),
            ...(left === "1" ? { versions_left: 1 } : {}),
            ...(lo ? { min_seconds: Number(lo) } : {}),
            ...(hi ? { max_seconds: Number(hi) } : {}),
          },
        },
      });
      if (!data) throw new Error("load");
      return data;
    },
  });

  // An editor's own unpublished scripts, whatever the filters say: the main list asks for Ready to make, which leaves them out.
  const myDraftRows = useQuery({
    enabled: !owner && me !== undefined,
    queryKey: ["scripts", "my-drafts", all ? null : brandId],
    queryFn: async () => (await api.GET("/scripts", { params: { query: { ...(all ? {} : { brand_id: brandId }), status: "draft" } } })).data ?? [],
  });

  // Filters the server doesn't take are applied here.
  let rows = scripts.data ?? [];
  if (mine) rows = rows.filter((r) => r.created_by_id === me?.id);
  if (left === "0") rows = rows.filter((r) => r.versions_left === 0);
  if (sort === "title") rows = [...rows].sort((a, b) => a.title.localeCompare(b.title));
  if (sort === "newest") rows = [...rows].sort((a, b) => b.created_at.localeCompare(a.created_at));
  const filtered = status !== (owner ? "" : "published") || !!(q || len || ref || left || mine || all);
  const clear = () => {
    setText("");
    setParams({}, { replace: true });
  };
  const refName = (id: string | null) => refs.data?.find((r) => r.id === id)?.name;
  const search = (
      <div className="w-full sm:w-[360px]">
        <label className="relative block">
          <span className="sr-only">Search scripts</span>
          <Search size={20} strokeWidth={1.75} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input
            type="search"
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setShown(PAGE);
            }}
            placeholder="Search titles, descriptions and scripts"
            className="min-h-control w-full rounded-md border border-border-strong bg-surface pl-10 pr-3 text-base text-text placeholder:text-muted"
          />
        </label>
      </div>
  );
  const selects = (
    <>
      <div className="w-full lg:w-40">
        <Select label="Status" value={status} onChange={(e) => (e.target.value === (owner ? "" : "published") ? set("status", "") : set("status", e.target.value))}>
          {STATUS_FILTER.map(([v, l]) => (
            <option key={v} value={v || (owner ? "" : "any")}>
              {l}
            </option>
          ))}
        </Select>
      </div>
      <div className="w-full lg:w-36">
        <Select label="Length" value={len} onChange={(e) => set("len", e.target.value)}>
          {LENGTH_FILTER.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </Select>
      </div>
      <div className="w-full lg:w-44">
        <Select label="Reference" value={ref} onChange={(e) => set("ref", e.target.value)}>
          <option value="">Any</option>
          <option value="none">No reference</option>
          <option value="with">With a reference</option>
        </Select>
      </div>
      <div className="w-full lg:w-44">
        <Select label="Versions left" value={left} onChange={(e) => set("left", e.target.value)}>
          <option value="">Any</option>
          <option value="1">At least one</option>
          <option value="0">None</option>
        </Select>
      </div>
      <Button variant={mine ? "primary" : "secondary"} aria-pressed={mine} onClick={() => set("mine", mine ? "" : "1")}>
        Mine
      </Button>
      {owner && (
        <div className="w-full lg:w-40">
          <Select label="Brand" value={all ? "all" : ""} onChange={(e) => set("brand", e.target.value)}>
            <option value="">This brand</option>
            <option value="all">All brands</option>
          </Select>
        </div>
      )}
      <div className="w-full lg:w-44">
        <Select label="Sort" value={sort} onChange={(e) => set("sort", e.target.value)}>
          {SORTS.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </Select>
      </div>
      {filtered && (
        <Button variant="ghost" onClick={clear}>
          Clear filters
        </Button>
      )}
    </>
  );
  const active = [status !== (owner ? "" : "published"), !!len, !!ref, !!left, mine, all, !!sort].filter(Boolean).length;
  const filters = rail ? (
    <div className="flex flex-wrap items-end gap-3">
      {search}
      {selects}
    </div>
  ) : (
    <div className="flex items-center gap-3">
      {search}
      <Button variant={active > 0 ? "primary" : "secondary"} onClick={() => setSheet(true)}>
        Filters{active > 0 ? ` (${active})` : ""}
      </Button>
    </div>
  );

  const list = (items: Row[]) => (
    <Card className="p-0 sm:p-0">
      <ul className="divide-y divide-border">
        {items.slice(0, shown).map((r) => (
          <ScriptItem key={r.id} mayOpen={r.status === "draft" && (owner || r.created_by_id === me?.id)} row={r} brandName={all ? brands?.find((b) => b.id === r.brand_id)?.name : undefined} refName={refName(r.reference_id)} narrow={!rail} />
        ))}
      </ul>
    </Card>
  );
  const newScript = (
    <Link to={`/b/${brandId}/scripts/new`} className={buttonClass("primary")}>
      <Plus size={20} strokeWidth={1.75} aria-hidden />
      New script
    </Link>
  );
  const myDrafts = (myDraftRows.data ?? []).filter((r) => r.created_by_id === me?.id);

  return (
    <main className="mx-auto max-w-content space-y-5 p-4 sm:p-6">
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="type-eyebrow text-muted">{brand?.name}</p>
          <h1 className="type-page">Scripts</h1>
        </div>
        {rail && newScript}
      </div>
      {!rail && <ActionBar phone>{newScript}</ActionBar>}
      {filters}
      {sheet && (
        <Sheet title="Filters" onClose={() => setSheet(false)}>
          <div className="space-y-3 pb-2">
            {selects}
            {filtered && (
              <Button variant="ghost" onClick={clear}>
                Clear filters
              </Button>
            )}
          </div>
        </Sheet>
      )}
      {scripts.isError && (
        <Banner title="Couldn't load your scripts." action={<Button variant="secondary" onClick={() => void scripts.refetch()}>Try again</Button>}>
          Check your connection.
        </Banner>
      )}
      {scripts.isPending && (
        <div className="space-y-3" aria-label="Loading">
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      )}
      {scripts.data && (
        <>
          {myDrafts.length > 0 && (
            <section aria-label="Your drafts" className="space-y-3">
              <h2 className="type-section">Your drafts</h2>
              {list(myDrafts)}
            </section>
          )}
          {rows.length === 0 && !filtered && (
            <EmptyState icon={FileText} title={owner ? `No scripts for ${brand?.name ?? "this brand"} yet.` : "No scripts ready to make yet."}>
              {owner ? "Write a script once and make up to three videos from it." : "Reed publishes scripts here. You can also write your own."}
            </EmptyState>
          )}
          {rows.length === 0 && filtered && (
            <div className="flex items-center gap-3">
              <p className="text-muted">Nothing matches these filters.</p>
              <Button variant="ghost" onClick={clear}>
                Clear filters
              </Button>
            </div>
          )}
          {rows.length > 0 && (
            <>
              <p className="text-sm text-muted">{filtered && scripts.data.length !== rows.length ? `${rows.length} of ${scripts.data.length} scripts` : `${rows.length} script${rows.length === 1 ? "" : "s"}`}</p>
              {list(rows)}
              {rows.length > shown && (
                <Button variant="secondary" onClick={() => setShown(shown + PAGE)}>
                  Show more
                </Button>
              )}
            </>
          )}
        </>
      )}
      <LegacyVideos brandId={brandId} />
    </main>
  );
}

function ScriptItem({ row: r, brandName, refName, narrow, mayOpen }: { row: Row; brandName?: string; refName?: string; narrow: boolean; mayOpen: boolean }) {
  const brandId = r.brand_id;
  const meta = [brandName, r.created_by_name && `${r.created_by_name} · ${age(r.created_at)}`, refName && `Ref: ${refName}`, lengthText(r.versions), r.published && r.versions_left > 0 && `${r.versions_left} version${r.versions_left === 1 ? "" : "s"} left to make`].filter(Boolean).join(" · ");
  return (
    <li className="flex gap-3 p-4 sm:p-5">
      <span aria-hidden className="grid h-[88px] w-14 shrink-0 place-items-center rounded-lg bg-surface-2 text-muted sm:h-[100px] sm:w-16">
        <FileText size={20} strokeWidth={1.75} />
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        <h3 className="font-display text-md font-bold">
          {mayOpen ? (
            <Link to={`/b/${brandId}/scripts/${r.id}`} className="hover:underline">
              {r.title}
            </Link>
          ) : (
            r.title
          )}
        </h3>
        {r.description && <p className="truncate text-sm text-muted">{r.description}</p>}
        <p className="text-sm text-muted">{meta}</p>
        <ul className="flex flex-wrap gap-2 pt-1" aria-label="Versions">
          {r.versions.map((v) => {
            const s = STATUS[v.status] ?? { label: v.status, tone: "neutral" as Tone };
            const letter = LETTER[v.slot] ?? String(v.slot + 1);
            const label = `${letter} · ${s.label}`;
            const chip = (
              <Badge tone={s.tone} icon={s.icon}>
                {label}
              </Badge>
            );
            return (
              <li key={v.slot}>
                {v.project_id || (v.status === "draft" && mayOpen) ? (
                  <Link to={v.project_id ? `/b/${brandId}/projects/${v.project_id}` : `/b/${brandId}/scripts/${r.id}`} aria-label={`Version ${letter}, ${s.label.toLowerCase()}`} className={`inline-flex items-center ${narrow ? "min-h-control" : "min-h-9"} rounded-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent`}>
                    {chip}
                  </Link>
                ) : (
                  <span aria-label={`Version ${letter}, ${s.label.toLowerCase()}`} className="inline-flex">
                    {chip}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </li>
  );
}
