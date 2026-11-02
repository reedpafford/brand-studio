import { useState } from "react";
import { useQueries } from "@tanstack/react-query";
import { Archive, Search } from "lucide-react";
import { api } from "../../api/client";
import { Button, Select, Sheet, Tabs } from "../../components";
import { useReferences } from "../../projects/BriefPickers";

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

/** The stage tabs are the Status filter: the server's status for each, and the words. */
const STAGES = [
  ["", "All"],
  ["draft", "Writing"],
  ["published", "Ready to make"],
  ["in_production", "In production"],
  ["done", "Finished"],
] as const;

/** The list's query without status or paging: what the stage counts are asked with. */
export type Ask = Record<string, string | number | boolean | undefined>;

/** All · Writing · Ready to make · In production · Finished, each with how many scripts the server has for it.
 *  `status` is the address's: "" is All for Reed; an editor's All is "any", since they start on Ready to make. */
export function StageTabs({ status, owner, ask, onPick }: { status: string; owner: boolean; ask: Ask; onPick: (status: string) => void }) {
  const counts = useQueries({
    queries: STAGES.map(([s]) => ({
      queryKey: ["scripts", "count", ask, s],
      queryFn: async () => {
        const { response } = await api.GET("/scripts", { params: { query: { ...ask, ...(s ? { status: s } : {}), limit: 1 } } });
        const n = Number(response.headers.get("X-Total-Count"));
        return response.headers.has("X-Total-Count") && Number.isFinite(n) ? n : null; // no count, no number
      },
    })),
  });
  const all = owner ? "" : "any";
  return (
    <Tabs
      label="Stage"
      value={status === all || status === "any" ? "all" : status}
      onChange={(id) => onPick(id === "all" ? all : id)}
      tabs={STAGES.map(([s, label], i) => ({ id: s || "all", label, count: counts[i].data ?? undefined }))}
    />
  );
}

type Filters = { len: string; ref: string; left: string; mine: boolean; removed: boolean; all: boolean; sort: string };

/** The search and the other filters: in a row on desktop, behind one Filters button on a phone. */
export function ScriptFilters({ rail, owner, text, onText, f, set, filtered, active, clear }: { rail: boolean; owner: boolean; text: string; onText: (t: string) => void; f: Filters; set: (key: string, value: string) => void; filtered: boolean; active: number; clear: () => void }) {
  const refs = useReferences();
  const [sheet, setSheet] = useState(false);
  const search = (
    <div className="w-full sm:w-[320px]">
      <label className="relative block">
        <span className="sr-only">Search scripts</span>
        <Search size={16} strokeWidth={1.75} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
        <input type="search" value={text} onChange={(e) => onText(e.target.value)} placeholder="Search titles, descriptions and scripts" className="min-h-control w-full rounded-md border border-border-strong bg-surface pl-9 pr-3 text-base text-text placeholder:text-muted" />
      </label>
    </div>
  );
  const clearButton = filtered && (
    <Button variant="ghost" onClick={clear}>
      Clear filters
    </Button>
  );
  const selects = (
    <>
      <div className="w-full lg:w-36">
        <Select label="Length" value={f.len} onChange={(e) => set("len", e.target.value)}>
          {LENGTH_FILTER.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </Select>
      </div>
      <div className="w-full lg:w-44">
        <Select label="Reference" value={f.ref} onChange={(e) => set("ref", e.target.value)}>
          <option value="">Any</option>
          <option value="none">No reference</option>
          {refs.data?.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </Select>
      </div>
      <div className="w-full lg:w-40">
        <Select label="Versions left" value={f.left} onChange={(e) => set("left", e.target.value)}>
          <option value="">Any</option>
          <option value="1">At least one</option>
          <option value="0">None</option>
        </Select>
      </div>
      <Button variant={f.mine ? "primary" : "secondary"} aria-pressed={f.mine} onClick={() => set("mine", f.mine ? "" : "1")}>
        Mine
      </Button>
      <Button variant={f.removed ? "primary" : "secondary"} icon={Archive} aria-pressed={f.removed} onClick={() => set("removed", f.removed ? "" : "1")}>
        Deleted and archived
      </Button>
      {owner && (
        <div className="w-full lg:w-36">
          <Select label="Brand" value={f.all ? "all" : ""} onChange={(e) => set("brand", e.target.value)}>
            <option value="">This brand</option>
            <option value="all">All brands</option>
          </Select>
        </div>
      )}
      <div className="w-full lg:w-40">
        <Select label="Sort" value={f.sort} onChange={(e) => set("sort", e.target.value)}>
          {SORTS.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </Select>
      </div>
    </>
  );
  if (rail)
    return (
      <div className="flex flex-wrap items-end gap-3">
        {search}
        {selects}
        {clearButton}
      </div>
    );
  return (
    <div className="flex items-center gap-3">
      {search}
      <Button variant={active > 0 ? "primary" : "secondary"} className="shrink-0 whitespace-nowrap" onClick={() => setSheet(true)}>
        Filters{active > 0 ? ` (${active})` : ""}
      </Button>
      {sheet && (
        <Sheet title="Filters" onClose={() => setSheet(false)}>
          <div className="space-y-3 pb-2">
            {selects}
            {clearButton}
          </div>
        </Sheet>
      )}
    </div>
  );
}
