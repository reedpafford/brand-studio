import { useState } from "react";
import { Search } from "lucide-react";
import { useReferences } from "../projects/BriefPickers";
import { TextArea } from "../components";

/** The reference reels as compact rows: a 96px picture, the name, a two-line logline and the length. Tap a row again to clear it. */
export function ReferenceList({ value, replace, onChange }: { value: string | null; replace: string; onChange: (id: string | null, replace: string) => void }) {
  const refs = useReferences();
  const [q, setQ] = useState("");
  if (!refs.data || refs.data.length === 0) return null;
  const many = refs.data.length > 6;
  const shown = refs.data.filter((r) => !q.trim() || `${r.name} ${r.logline}`.toLowerCase().includes(q.trim().toLowerCase()));
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium">Reference reel (optional)</legend>
      {many && (
        <label className="relative block">
          <span className="sr-only">Search the reels</span>
          <Search size={20} strokeWidth={1.75} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search the reels" className="min-h-control w-full rounded-md border border-border-strong bg-surface pl-10 pr-3 text-base text-text placeholder:text-muted" />
        </label>
      )}
      <ul className="divide-y divide-border overflow-hidden rounded-lg border border-border">
        {shown.map((r) => {
          const on = value === r.id;
          // The logline is shown unless it only repeats the name.
          const line = r.logline.trim().toLowerCase().startsWith(r.name.trim().toLowerCase()) ? "" : r.logline;
          return (
            <li key={r.id}>
              <button type="button" aria-pressed={on} onClick={() => onChange(on ? null : r.id, on ? "" : replace)} className={`flex min-h-control w-full items-start gap-3 p-2 text-left ${on ? "bg-accent-soft" : "hover:bg-surface-2"}`}>
                {r.has_thumbnail ? <img src={`/api/references/${r.id}/thumbnail`} alt="" className="aspect-video w-24 shrink-0 rounded-md object-cover" /> : <span aria-hidden className="grid aspect-video w-24 shrink-0 place-items-center rounded-md bg-surface-2 text-xs text-muted">No picture</span>}
                <span className="min-w-0 flex-1">
                  <span className="block font-medium">{r.name}</span>
                  {line && <span className="line-clamp-2 text-sm text-muted">{line}</span>}
                  <span className="block text-sm tabular-nums text-muted">{Math.round(r.seconds)} s</span>
                </span>
              </button>
            </li>
          );
        })}
        {shown.length === 0 && <li className="p-3 text-sm text-muted">No reel matches.</li>}
      </ul>
      {value && (
        <TextArea label="What to change" rows={3} hint="For example: the altar becomes a car showroom. Claude keeps the rest of the reel's story." value={replace} onChange={(e) => onChange(value, e.target.value)} />
      )}
    </fieldset>
  );
}
