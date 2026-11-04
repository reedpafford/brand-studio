import { useEffect, useRef, useState } from "react";
import { Folder, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { StatusDot, flatten, useIdeas, useTree, type Branch } from "../folders/ideas";
import { useDebounced } from "../scripts/status";

type Hit = { key: string; to: string; label: string; where: string; dot?: Parameters<typeof StatusDot>[0]["status"] };
const count = (b: Branch) => `folder · ${b.count} idea${b.count === 1 ? "" : "s"}`;

/** The magnifier beside New video (S-gaps-04 R2): this brand's idea titles and folder names. Each idea shows its status dot
 *  and its folder; Enter opens the first, ↑↓ move, Esc closes. */
export function QuickSearch({ brandId, phone }: { brandId: number; phone?: boolean }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [at, setAt] = useState(0);
  const q = useDebounced(text.trim(), 200);
  const navigate = useNavigate();
  const box = useRef<HTMLDivElement>(null);
  const tree = useTree(brandId).data;
  const ideas = useIdeas(brandId, { folder: "all", tab: "all", q, sort: "newest", madeBy: null, archived: false }, open && !!q);
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open]);

  const folders = flatten(tree?.folders ?? []);
  const named = new Map(folders.map((f) => [f.id, f.name]));
  const branches = new Map<number, Branch>();
  const walk = (bs: Branch[]) => bs.forEach((b) => (branches.set(b.id!, b), walk(b.folders ?? [])));
  walk(tree?.folders ?? []);
  const hits: Hit[] = !q
    ? []
    : [
        ...(ideas.data?.pages[0]?.ideas ?? []).slice(0, 8).map((i) => ({ key: `i${i.id}`, to: `/b/${brandId}/videos/${i.id}`, label: i.title, where: i.folder_id ? (named.get(i.folder_id) ?? "") : "Unsorted", dot: i.status })),
        ...folders.filter((f) => f.name.toLowerCase().includes(q.toLowerCase())).slice(0, 4).map((f) => ({ key: `f${f.id}`, to: `/b/${brandId}/videos?folder=${f.id}`, label: f.name, where: count(branches.get(f.id)!) })),
      ];
  const go = (h: Hit | undefined) => {
    if (!h) return;
    setOpen(false);
    setText("");
    navigate(h.to);
  };
  return (
    <div ref={box} className="relative">
      <button type="button" aria-label="Quick search" aria-expanded={open} onClick={() => setOpen(!open)} className={phone ? "grid size-control place-items-center rounded-md text-text" : `grid size-8 place-items-center rounded-md border border-border-button text-muted hover:text-text ${open ? "bg-surface-3" : "bg-surface"}`}>
        <Search size={phone ? 22 : 14} strokeWidth={1.75} aria-hidden />
      </button>
      {open && (
        <div role="dialog" aria-label="Quick search" className={`absolute top-full z-40 mt-2 rounded-lg ${phone ? "-right-12 w-[calc(100vw-1.5rem)]" : "-left-[200px] w-[400px]"} border border-border bg-surface p-1 shadow-raised`}>
          <label className="relative m-0.5 mb-1.5 block">
            <span className="sr-only">Search ideas and folders</span>
            <Search size={14} strokeWidth={1.75} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input
              autoFocus
              type="search"
              value={text}
              placeholder="Search ideas and folders"
              onChange={(e) => (setText(e.target.value), setAt(0))}
              onKeyDown={(e) => {
                if (e.key === "Escape") setOpen(false);
                if (e.key === "ArrowDown" || e.key === "ArrowUp") {
                  e.preventDefault();
                  setAt(e.key === "ArrowDown" ? Math.min(at + 1, hits.length - 1) : Math.max(at - 1, 0));
                }
                if (e.key === "Enter") go(hits[at] ?? hits[0]);
              }}
              className={`w-full rounded-md border border-accent bg-surface pl-9 pr-3 text-text outline-none placeholder:text-muted ${phone ? "h-control text-base" : "h-8 text-sm"}`}
            />
          </label>
          <div role="listbox" aria-label="Results">
            {hits.map((h, n) => (
                <button key={h.key} type="button" role="option" aria-selected={n === at} onMouseEnter={() => setAt(n)} onClick={() => go(h)} className={`flex w-full items-center gap-2 rounded-[5px] px-2 text-left text-sm ${phone ? "min-h-control" : "h-[30px]"} ${n === at ? "bg-surface-2" : ""}`}>
                  {h.dot ? (
                    <span className="mx-1 grid place-items-center">
                      <StatusDot status={h.dot} label />
                    </span>
                  ) : (
                    <Folder size={14} strokeWidth={1.75} aria-hidden />
                  )}
                  <span className="min-w-0 flex-1 truncate">{h.label}</span>
                  <span className="shrink-0 text-xs text-muted">{h.where}</span>
                </button>
            ))}
          </div>
          {q && !ideas.isFetching && hits.length === 0 && <p className="px-2 py-1.5 text-sm text-muted">Nothing called “{q}” in this brand.</p>}
          <div className="my-1 border-t border-border" />
          <p className="px-2 py-1 text-xs text-muted">Enter opens the first · ↑↓ to move · Esc closes</p>
        </div>
      )}
    </div>
  );
}
