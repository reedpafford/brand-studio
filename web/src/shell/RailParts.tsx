import { useState, type ReactNode } from "react";
import { ChevronDown, ChevronRight, Plus } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { StatusDot, said, useIdeas } from "../folders/ideas";
import { WORDS_ID } from "../home/Words";

/** One row of the rail: a page, a folder, a video. */
export const railRow = "flex h-8 items-center gap-2 rounded-md px-2 text-sm transition-colors duration-(--dur-fast) ease-out";

const KEY = (id: string) => `bs.rail.${id}`;

/** A group of rail rows under a header that folds them away ("Assets", "Projects"): open until it is closed, and
 *  remembered on this computer. `action` sits at the right of the header (Projects' new folder). The icon rail has no
 *  headers, so its groups are a thin line and their rows always show. */
export function RailGroup({ id, label, wide, action, children }: { id: string; label: string; wide: boolean; action?: ReactNode; children: ReactNode }) {
  const [open, setOpen] = useState(() => localStorage.getItem(KEY(id)) !== "0");
  const toggle = () => {
    localStorage.setItem(KEY(id), open ? "0" : "1");
    setOpen(!open);
  };
  const Chevron = open ? ChevronDown : ChevronRight;
  return (
    <div role="group" aria-label={label} className="flex flex-col gap-0.5">
      {wide ? (
        <div className="mt-2.5 flex h-7 items-center gap-1.5 pl-1 pr-2 text-xs font-medium text-muted">
          <button type="button" aria-expanded={open} onClick={toggle} className="flex h-6 items-center gap-1 rounded-md px-1 hover:text-text">
            {label}
            <Chevron size={12} strokeWidth={1.75} aria-hidden />
          </button>
          <span className="flex-1" />
          {action}
        </div>
      ) : (
        <span aria-hidden className="mx-2 my-1.5 border-t border-border" />
      )}
      {(open || !wide) && children}
    </div>
  );
}

/** Projects › New video: Home, on its words box (already there: straight to the words). `folder`: the open folder, kept
 *  so the new idea lands in it. */
export function NewVideoRow({ brandId, folder, wide }: { brandId: number; folder?: string | null; wide: boolean }) {
  return (
    <Link
      to={`/b/${brandId}${folder ? `?folder=${folder}` : ""}`}
      onClick={() => document.getElementById(WORDS_ID)?.focus()}
      aria-label={wide ? undefined : "New video"}
      title={wide ? undefined : "New video"}
      className={`${railRow} font-medium text-muted hover:bg-surface-3/60 hover:text-text ${wide ? "" : "justify-center"}`}
    >
      <span aria-hidden className="grid size-5 shrink-0 place-items-center rounded-md border border-border-button bg-surface text-text">
        <Plus size={12} strokeWidth={2} />
      </span>
      {wide && <span>New video</span>}
    </Link>
  );
}

const SHOWN = 6;

/** Projects › Recent: the brand's six most recently active videos by title, each with its status dot. */
export function Recent({ brandId }: { brandId: number }) {
  const ideas = useIdeas(brandId, { folder: "all", tab: "all", q: "", sort: "newest", madeBy: null, archived: false }).data?.pages[0]?.ideas.slice(0, SHOWN) ?? [];
  const { pathname } = useLocation();
  if (!ideas.length) return null;
  return (
    <>
      <p id="rail-recent" className="flex h-6 items-end px-2 pb-0.5 text-xs text-muted">
        Recent
      </p>
      <ul aria-labelledby="rail-recent" className="flex flex-col gap-0.5">
        {ideas.map((i) => {
          const to = `/b/${brandId}/videos/${i.id}`;
          const on = pathname === to;
          return (
            <li key={i.id}>
              <Link to={to} title={`${i.title} · ${said(i.status)}`} aria-current={on ? "page" : undefined} className={`${railRow} text-text ${on ? "bg-surface-3" : "hover:bg-surface-3/60"}`}>
                <span className="grid w-5 shrink-0 place-items-center">
                  <StatusDot status={i.status} label />
                </span>
                <span className="truncate">{i.title}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </>
  );
}
