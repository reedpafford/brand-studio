import { useLayoutEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Archive, Check, ChevronDown, Ellipsis, Film, Folder, FolderPlus, Inbox, RotateCcw, X } from "lucide-react";
import { Link } from "react-router-dom";
import { api, must } from "../api/client";
import { fileUrl } from "../api/upload";
import { Button, Dialog, Field, Menu, MenuItem, useToast } from "../components";
import { costText, day, flatten, StatusLine, useRefreshIdeas, useTree, type Idea } from "../folders/ideas";
import { age } from "../scripts/status";
import { dragIdea } from "../shell/FolderTree";

const to = (brandId: number, i: Idea) => (i.from_script ? `/b/${brandId}/videos/${i.id}${i.status.kind === "delivered" ? "?step=downloads" : ""}` : `/b/${brandId}/projects/${i.id}`);
const length = (i: Idea) => (i.seconds ? `${i.seconds} s` : "—");
const ideas = (n: number) => `${n} idea${n === 1 ? "" : "s"}`;

/** The idea's still, or a blank frame before it has one. */
function Still({ i, className }: { i: Idea; className: string }) {
  return (
    <span aria-hidden className={`grid place-items-center overflow-hidden bg-surface-2 text-faint ${className}`}>
      {i.still_file_id ? <img src={fileUrl(i.still_file_id)} alt="" className="size-full object-cover" /> : <Film size={20} strokeWidth={1.75} />}
    </span>
  );
}

/** A tick box: S1-07's on a card, S1-05's on a row. */
function Tick({ on, label, onChange, className = "" }: { on: boolean; label: string; onChange: () => void; className?: string }) {
  return (
    <button type="button" role="checkbox" aria-checked={on} aria-label={label} onClick={(e) => (e.preventDefault(), e.stopPropagation(), onChange())} className={`grid size-4 shrink-0 place-items-center rounded-sm border ${on ? "border-accent bg-accent text-on-accent" : "border-border-strong bg-surface"} ${className}`}>
      {on && <Check size={12} strokeWidth={2.5} aria-hidden />}
    </button>
  );
}

/** One idea as a card (S1-04, S1-08, P-02): its still (a bar while working), title, status and reason, style · length · who
 *  · when, and its cost ("up to $16.86"; an editor's in credits). Ticks show on hover, and on every card once one is ticked. */
export function IdeaCard({ brandId, i, phone, picked, picking, onPick }: { brandId: number; i: Idea; phone: boolean; picked: boolean; picking: boolean; onPick?: () => void }) {
  const { made, total } = i.status;
  // A phone selects by press and hold, then taps add or remove (S-gaps-06, 12).
  const hold = useRef<ReturnType<typeof setTimeout> | null>(null);
  const held = useRef(false);
  const letGo = () => hold.current && clearTimeout(hold.current);
  const press = phone && onPick
    ? {
        onPointerDown: () => {
          held.current = false;
          hold.current = setTimeout(() => ((held.current = true), onPick()), 500);
        },
        onPointerUp: letGo,
        onPointerLeave: letGo,
        onPointerMove: letGo,
        onContextMenu: (e: React.MouseEvent) => e.preventDefault(),
        onClick: (e: React.MouseEvent) => {
          if (held.current || picking) e.preventDefault();
          if (!held.current && picking) onPick();
          held.current = false;
        },
      }
    : {};
  const meta = phone ? [i.style, costText(i.cost)] : [i.style, i.seconds ? `${i.seconds} s` : "", i.made_by?.name, age(i.updated_at)];
  return (
    <div className="group relative min-w-0">
      <Link to={to(brandId, i)} draggable={!phone && i.can_manage} onDragStart={(e) => dragIdea(e, i.id, i.title)} {...press} className="flex min-w-0 flex-col gap-2 select-none lg:select-auto">
        <span className="relative block">
          <Still i={i} className={`${phone ? "aspect-[175/230]" : "aspect-[212/290]"} w-full rounded-md ${picked ? "outline-2 outline-offset-2 outline-accent" : ""}`} />
          {i.status.kind === "working" && total > 0 && (
            <span aria-hidden className="absolute inset-x-2 bottom-2 h-1 overflow-hidden rounded-sm bg-surface-3">
              <span className="block h-full rounded-sm bg-accent" style={{ width: `${Math.round((made / total) * 100)}%` }} />
            </span>
          )}
        </span>
        <span className="flex min-w-0 flex-col gap-1">
          <span className={`truncate font-semibold ${phone ? "text-md" : "text-base leading-[19px]"}`}>{i.title}</span>
          <StatusLine status={i.status} />
          <span className="truncate text-xs text-muted">{meta.filter(Boolean).join(" · ")}</span>
          {!phone && <span className="text-xs text-muted tabular-nums">{costText(i.cost)}</span>}
        </span>
      </Link>
      {onPick && (!phone || picking) && <Tick on={picked} label={`Select ${i.title}`} onChange={onPick} className={`absolute right-2 top-2 ${picking || picked ? "" : "opacity-0 group-hover:opacity-100 focus-visible:opacity-100"}`} />}
    </div>
  );
}

/** An archived idea (S1-06): faded, "Archived 28 Oct", style · who, and Restore. */
export function ArchivedCard({ brandId, i }: { brandId: number; i: Idea }) {
  const refresh = useRefreshIdeas();
  const toast = useToast();
  const restore = useMutation({ mutationFn: () => must(api.POST("/projects/{project_id}/restore", { params: { path: { project_id: i.id } } })), onSuccess: () => refresh(), onError: (e: Error) => toast(e.message, undefined, "error") });
  return (
    <div className="flex min-w-0 flex-col gap-2 opacity-75">
      <Link to={to(brandId, i)}>
        <Still i={i} className="aspect-[212/290] w-full rounded-md" />
      </Link>
      <span className="flex min-w-0 flex-col gap-1">
        <span className="truncate text-base font-semibold leading-[19px]">{i.title}</span>
        <StatusLine status={i.status} />
        <span className="truncate text-xs text-muted">{[i.style, i.made_by?.name].filter(Boolean).join(" · ")}</span>
        {i.can_manage && (
          <span className="mt-1">
            <Button variant="secondary" icon={RotateCcw} busy={restore.isPending} onClick={() => restore.mutate()}>
              Restore
            </Button>
          </span>
        )}
      </span>
    </div>
  );
}

const COLS = "grid grid-cols-[16px_22px_minmax(0,1fr)_230px_70px_90px_80px_110px_24px] items-center gap-3"; // Status is wider than S1-05 drew it: it carries the reason (S-gaps-01)

/** The list view for a big folder (S1-05): a row an idea, loading the next page as you scroll. */
export function IdeaRows({ brandId, rows, owner, picked, onPick, onAll, onMove, onArchive }: { brandId: number; rows: Idea[]; owner: boolean; picked: Set<number>; onPick: (i: Idea) => void; onAll: () => void; onMove: (i: Idea) => void; onArchive: (i: Idea) => void }) {
  const mine = rows.filter((r) => r.can_manage);
  const all = mine.length > 0 && mine.every((r) => picked.has(r.id));
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      <div className={`${COLS} bg-surface-2 px-3 py-2 text-xs font-medium text-muted`}>
        <Tick on={all} label="Select every idea shown" onChange={onAll} />
        <span />
        <span className="pl-2.5">Idea</span>
        <span>Status</span>
        <span>Length</span>
        <span>Made by</span>
        <span className="inline-flex items-center gap-1">
          Updated <ChevronDown size={12} strokeWidth={1.75} aria-hidden />
        </span>
        <span className="text-right">{owner ? "Cost" : "Credits"}</span>
        <span />
      </div>
      <ul>
        {rows.map((i) => (
          <li key={i.id} className={`${COLS} min-h-14 border-t border-border px-3 py-2 text-sm ${picked.has(i.id) ? "bg-accent-soft" : ""}`}>
            {i.can_manage ? <Tick on={picked.has(i.id)} label={`Select ${i.title}`} onChange={() => onPick(i)} /> : <span />}
            <Still i={i} className="h-[39px] w-[22px] rounded-sm" />
            <Link to={to(brandId, i)} className="truncate pl-2.5 font-medium hover:underline">
              {i.title}
            </Link>
            <StatusLine status={i.status} />
            <span className="text-muted tabular-nums">{length(i)}</span>
            <span className="truncate text-muted">{i.made_by?.name ?? ""}</span>
            <span className="text-muted">{day(i.updated_at)}</span>
            <span className="text-right tabular-nums">{costText(i.cost)}</span>
            {i.can_manage ? (
              <Menu
                title={i.title}
                align="right"
                trigger={(p) => (
                  <button type="button" {...p} aria-label={`More for ${i.title}`} className="grid size-6 place-items-center rounded-md text-muted hover:bg-surface-2">
                    <Ellipsis size={14} strokeWidth={1.75} aria-hidden />
                  </button>
                )}
              >
                {(close) => (
                  <>
                    <MenuItem onClick={() => (close(), onMove(i))}>Move to…</MenuItem>
                    <MenuItem onClick={() => (close(), onArchive(i))}>Archive</MenuItem>
                  </>
                )}
              </Menu>
            ) : (
              <span />
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Several selected (S1-07): the dark bar with Move to… and Archive, each with Undo. Move lists the brand's folders as the
 *  tree nests them, then Unsorted and New folder…. */
export function SelectBar({ brandId, picked, here, moveOpen, setMoveOpen, onClear }: { brandId: number; picked: Idea[]; here: number | null; moveOpen: boolean; setMoveOpen: (open: boolean) => void; onClear: () => void }) {
  const tree = useTree(brandId).data;
  const refresh = useRefreshIdeas();
  const toast = useToast();
  const [naming, setNaming] = useState<string | null>(null);
  const n = picked.length;
  const menuBox = useRef<HTMLDivElement>(null);
  const [shift, setShift] = useState(0);
  useLayoutEffect(() => {
    if (!moveOpen || !menuBox.current) return setShift(0);
    const box = menuBox.current.getBoundingClientRect();
    const over = box.right - shift - (window.innerWidth - 8);
    setShift(over > 0 ? -over : 0);
  }, [moveOpen]); // eslint-disable-line react-hooks/exhaustive-deps
  const file = (ids: number[], folder: number | null) => must(api.POST("/folders/file", { body: { kind: "video", ids, folder_id: folder } })).then((r) => r.data!);
  const move = useMutation({
    mutationFn: async ({ folder, name }: { folder: number | null; name: string }) => ({ ...(await file(picked.map((i) => i.id), folder)), name }),
    onSuccess: async ({ was, name }) => {
      onClear();
      await refresh();
      toast(`Moved ${ideas(n)} to ${name}.`, async () => {
        const from = [...new Set(was.map((w) => w.folder_id))];
        await Promise.all(from.map((f) => file(was.filter((w) => w.folder_id === f).map((w) => w.id), f))).catch((e: Error) => toast(e.message, undefined, "error"));
        await refresh();
      });
    },
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  const make = useMutation({
    mutationFn: (name: string) => must(api.POST("/brands/{brand_id}/folders", { params: { path: { brand_id: brandId } }, body: { name } })).then((r) => r.data!),
    onSuccess: (made) => (setNaming(null), move.mutate({ folder: made.id, name: made.name })),
  });
  const archive = useMutation({
    mutationFn: () => Promise.all(picked.map((i) => must(api.POST("/projects/{project_id}/archive", { params: { path: { project_id: i.id } } })))),
    onSuccess: async () => {
      const ids = picked.map((i) => i.id);
      onClear();
      await refresh();
      toast(`Archived ${ideas(n)}.`, async () => {
        await Promise.all(ids.map((id) => must(api.POST("/projects/{project_id}/restore", { params: { path: { project_id: id } } })))).catch((e: Error) => toast(e.message, undefined, "error"));
        await refresh();
      });
    },
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  const dark = "inline-flex min-h-control items-center gap-1.5 rounded-md border border-white/15 bg-white/10 px-3 text-sm font-medium text-white hover:bg-white/15 lg:min-h-8";
  const place = "flex min-h-control w-full items-center gap-2 rounded-md px-2 text-left text-sm text-text hover:bg-surface-2 lg:min-h-[30px]";
  if (!n) return null;
  return (
    <div role="region" aria-label="Selected ideas" className="fixed inset-x-0 bottom-0 z-40 lg:inset-x-auto lg:bottom-6 lg:left-[calc(50%+var(--rail-w)/2)] lg:-translate-x-1/2">
      {/* On a phone the bar takes the tabs' place (S-gaps-06, 12). */}
      <div className="flex min-h-[calc(var(--tabbar-h)+env(safe-area-inset-bottom))] items-center gap-2.5 bg-ink py-2 pb-[calc(0.5rem+env(safe-area-inset-bottom))] pl-4 pr-2 text-white shadow-overlay lg:min-h-0 lg:rounded-[10px] lg:pb-2">
        <span className="whitespace-nowrap text-sm font-medium">{n} selected</span>
        <span className="flex-1 lg:hidden" />
        {/* S-gaps-06 (8): the menu opens straight up from Move to…, its left edge on the button, kept on screen. */}
        <span className="relative">
          {moveOpen && (
          <div role="menu" aria-label={`Move ${ideas(n)} to`} ref={menuBox} style={{ transform: `translateX(${shift}px)` }} className="absolute bottom-full left-0 mb-3 max-h-[60vh] w-60 overflow-y-auto rounded-lg border border-border bg-surface p-1 shadow-raised">
            <p className="px-2 py-1.5 text-xs text-muted">Move {ideas(n)} to</p>
            {flatten(tree?.folders ?? []).filter((f) => f.id !== here).map((f) => (
              <button key={f.id} type="button" role="menuitem" disabled={move.isPending} onClick={() => move.mutate({ folder: f.id, name: f.name })} style={{ paddingLeft: 8 + f.depth * 16 }} className={`${place} disabled:text-faint`}>
                <Folder size={14} strokeWidth={1.75} aria-hidden /> {f.name}
              </button>
            ))}
            {here !== null && (
              <button type="button" role="menuitem" disabled={move.isPending} onClick={() => move.mutate({ folder: null, name: "Unsorted" })} className={place}>
                <Inbox size={14} strokeWidth={1.75} aria-hidden /> Unsorted
              </button>
            )}
            <div className="my-1 border-t border-border" />
            <button type="button" role="menuitem" onClick={() => (setMoveOpen(false), setNaming(""))} className={place}>
              <FolderPlus size={14} strokeWidth={1.75} aria-hidden /> New folder…
            </button>
          </div>
        )}
          <button type="button" aria-expanded={moveOpen} onClick={() => setMoveOpen(!moveOpen)} className={dark}>
            <Folder size={14} strokeWidth={1.75} aria-hidden /> Move to…
          </button>
        </span>
        <button type="button" disabled={archive.isPending} onClick={() => archive.mutate()} className={dark}>
          <Archive size={14} strokeWidth={1.75} aria-hidden /> Archive
        </button>
        <button type="button" aria-label="Clear the selection" onClick={onClear} className="grid size-control place-items-center rounded-md text-white hover:bg-white/10 lg:size-8">
          <X size={14} strokeWidth={1.75} aria-hidden />
        </button>
      </div>
      {naming !== null && (
        <Dialog title="New folder" cancelLabel="Not now" actionLabel={`Make it and move ${ideas(n)}`} busy={make.isPending || move.isPending} holdReason={!naming.trim() ? "Give it a name" : (make.error?.message ?? null)} onCancel={() => setNaming(null)} onConfirm={() => make.mutate(naming.trim())}>
          <Field label="Name" value={naming} maxLength={120} autoFocus onChange={(e) => (setNaming(e.target.value), make.reset())} />
        </Dialog>
      )}
    </div>
  );
}
