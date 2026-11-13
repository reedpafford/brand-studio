import { useEffect, useRef, useState, type DragEvent, type ReactNode } from "react";
import { ChevronDown, ChevronRight, Ellipsis, Folder, FolderOpen, FolderPlus, Inbox } from "lucide-react";
import { Link, useLocation, useMatch, useNavigate, useSearchParams } from "react-router-dom";
import { api, must } from "../api/client";
import { useFolderActions } from "../folders/FolderActions";
import { StatusDot, UNSORTED, pathTo, useRefreshIdeas, useTree, type Branch } from "../folders/ideas";
import { useVideoProject } from "../videos/VideoChat";
import { NewVideoRow, RailGroup, Recent, railRow as row } from "./RailParts";

/** What a dragged idea carries (an idea card on the folder page, or an idea in the tree). */
export const IDEA = "application/x-brand-studio-idea";
export const dragIdea = (e: DragEvent, id: number, title: string) => {
  e.dataTransfer.setData(IDEA, JSON.stringify({ id, title }));
  e.dataTransfer.effectAllowed = "move";
};

const OPEN = (brandId: number) => `bs.tree.${brandId}`;
const readOpen = (brandId: number): number[] => {
  try {
    return JSON.parse(localStorage.getItem(OPEN(brandId)) ?? "[]");
  } catch {
    return [];
  }
};

type Said = { message: string; undo?: () => void; id: number } | null;

/** An idea dropped on a folder, or on Unsorted, is filed there, and Undo files it back where it was. `say`: where the
 *  words and the Undo show. */
export function useDropIdea(say: (message: string, undo?: () => void) => void) {
  const refresh = useRefreshIdeas();
  return async (e: DragEvent, to: Branch) => {
    e.preventDefault();
    const raw = e.dataTransfer.getData(IDEA);
    if (!raw) return;
    const { id, title } = JSON.parse(raw) as { id: number; title: string };
    try {
      const { data } = await must(api.POST("/folders/file", { body: { kind: "video", ids: [id], folder_id: to.id ?? null } }));
      const was = data!.was[0]?.folder_id ?? null;
      if (was === (to.id ?? null)) return;
      await refresh();
      say(`Moved “${title}” to ${to.name}.`, async () => {
        await must(api.POST("/folders/file", { body: { kind: "video", ids: [id], folder_id: was } }));
        await refresh();
      });
    } catch (err) {
      say((err as Error).message); // no Undo: nothing moved
    }
  };
}

/** The rail's Projects (v6 S0-01): a header that folds it away, with New folder; New video; the brand's recent videos; then
 *  the folder tree: folders inside folders with their counts, the open folder's newest ideas with their status dots, and
 *  Unsorted. Drag an idea onto a folder to move it; right-click or ⋯ for New video here, New folder inside, Rename (in
 *  place), Move to… and Delete folder…; Undo shows at the foot of the rail. */
export function FolderTree({ brandId }: { brandId: number }) {
  const tree = useTree(brandId).data;
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [params] = useSearchParams();
  const onVideos = pathname === `/b/${brandId}/videos`;
  const picked = onVideos ? params.get("folder") || UNSORTED : null;
  // On a video, its folder opens in the tree and its row is marked.
  const video = useMatch("/b/:brandId/videos/:projectId");
  const videoId = Number(video?.params.projectId) || 0;
  const project = useVideoProject(videoId).data;
  const here = picked ?? (videoId && project ? (project.folder_id == null ? UNSORTED : String(project.folder_id)) : null);

  const [open, setOpen] = useState<number[]>(() => readOpen(brandId));
  const toggle = (id: number) =>
    setOpen((was) => {
      const next = was.includes(id) ? was.filter((x) => x !== id) : [...was, id];
      localStorage.setItem(OPEN(brandId), JSON.stringify(next));
      return next;
    });
  const trail = here && here !== UNSORTED ? pathTo(tree?.folders ?? [], Number(here)).map((f) => f.id!) : [];
  const isOpen = (id: number) => open.includes(id) || trail.includes(id);

  // The rail's own Undo (S0-01: "Deleted “Black Friday”. Its 3 ideas moved to Unsorted. Undo").
  const [said, setSaid] = useState<Said>(null);
  const say = (message: string, undo?: () => void) => setSaid((was) => ({ message, undo, id: (was?.id ?? 0) + 1 }));
  useEffect(() => {
    if (!said) return;
    const t = setTimeout(() => setSaid(null), 8000);
    return () => clearTimeout(t);
  }, [said]);

  const [drop, setDrop] = useState<number | "none" | null>(null);
  const fileIdea = useDropIdea(say);
  const moveIdea = (e: DragEvent, to: Branch) => (setDrop(null), fileIdea(e, to));
  const dropTarget = (b: Branch) => ({
    onDragOver: (e: DragEvent) => {
      if (!e.dataTransfer.types.includes(IDEA)) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      setDrop(b.id ?? "none");
    },
    onDragLeave: (e: DragEvent) => !e.currentTarget.contains(e.relatedTarget as Node | null) && setDrop(null), // not when crossing its own rows
    onDrop: (e: DragEvent) => void moveIdea(e, b),
  });

  const top = useFolderActions(brandId, undefined, { say });

  const ideas = (b: Branch, depth: number) => (
    <>
      {b.ideas.map((i) => {
        const on = videoId === i.id;
        return (
          <Link
            key={i.id}
            to={`/b/${brandId}/videos/${i.id}`}
            draggable={i.can_manage}
            onDragStart={(e) => dragIdea(e, i.id, i.title)}
            aria-current={on ? "page" : undefined}
            style={{ paddingLeft: 12 + depth * 16 }}
            className={`${row} ${on ? "bg-surface-3 text-text" : "text-text hover:bg-surface-3/60"}`}
          >
            <span className="grid w-[11px] place-items-center">
              <StatusDot status={i.status} label />
            </span>
            <span className="truncate">{i.title}</span>
          </Link>
        );
      })}
      {b.more > 0 && (
        <Link to={`/b/${brandId}/videos?folder=${b.id ?? UNSORTED}`} style={{ paddingLeft: 12 + depth * 16 }} className={`${row} text-text hover:bg-surface-3/60`}>
          <span aria-hidden className="grid w-[11px] place-items-center">
            <span className="size-[7px] rounded-full bg-faint" />
          </span>
          + {b.more} more
        </Link>
      )}
    </>
  );

  const newFolder = (
    <button type="button" aria-label="New folder" title="New folder" onClick={top.newInside} className="grid size-6 place-items-center rounded-md hover:bg-surface-3 hover:text-text">
      <FolderPlus size={14} strokeWidth={1.75} aria-hidden />
    </button>
  );
  return (
    <div className="relative">
      <RailGroup id="projects" label="Projects" wide action={newFolder}>
        <NewVideoRow brandId={brandId} folder={picked === UNSORTED ? null : picked} wide />
        <Recent brandId={brandId} />
        {tree?.folders && (
          <>
            {tree.folders.map((b) => (
              <FolderRow key={b.id} brandId={brandId} b={b} depth={0} here={picked} isOpen={isOpen} toggle={toggle} drop={drop} dropTarget={dropTarget} ideas={ideas} say={say} onDeleted={(parent) => here === String(b.id) && navigate(`/b/${brandId}/videos${parent ? `?folder=${parent}` : ""}`)} />
            ))}
            <div {...dropTarget(tree.unsorted)}>
              <Link to={`/b/${brandId}/videos`} aria-current={picked === UNSORTED ? "page" : undefined} className={`${row} font-medium ${drop === "none" ? "bg-accent-soft text-accent-text outline-1 outline-dashed outline-[#9fa3ef]" : picked === UNSORTED ? "bg-surface-3 text-text" : "text-muted hover:bg-surface-3/60"}`}>
                <span className="w-3" />
                <Inbox size={14} strokeWidth={1.75} aria-hidden />
                <span className="flex-1 truncate">Unsorted</span>
                <span className="text-xs text-muted tabular-nums">{tree.unsorted.count}</span>
              </Link>
            </div>
            {here === UNSORTED && ideas(tree.unsorted, 1)}
          </>
        )}
      </RailGroup>
      {top.dialogs}
      {said && (
        <div role="status" className="fixed bottom-16 left-2 z-40 flex w-[232px] flex-wrap items-center gap-1.5 rounded-lg bg-ink px-3.5 py-2.5 text-sm text-white shadow-overlay">
          <span>{said.message}</span>
          {said.undo && (
            <button type="button" onClick={() => (said.undo?.(), setSaid(null))} className="font-semibold text-[#b9bdfa] hover:underline">
              Undo
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function FolderRow(props: {
  brandId: number;
  b: Branch;
  depth: number;
  here: string | null;
  isOpen: (id: number) => boolean;
  toggle: (id: number) => void;
  drop: number | "none" | null;
  dropTarget: (b: Branch) => object;
  ideas: (b: Branch, depth: number) => ReactNode;
  say: (message: string, undo?: () => void) => void;
  onDeleted: (parent: number | null) => void;
}) {
  const { brandId, b, depth, here, isOpen, toggle, drop, dropTarget, ideas, say, onDeleted } = props;
  const [renaming, setRenaming] = useState<string | null>(null);
  const ended = useRef(false); // Enter or Esc ended the rename: the blur that follows does nothing
  const [menu, setMenu] = useState(false);
  const actions = useFolderActions(brandId, b, { say, onDeleted, newVideoHere: true, renameInPlace: () => start() });
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!menu) return;
    const away = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setMenu(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setMenu(false);
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [menu]);
  const open = isOpen(b.id!);
  const on = here === String(b.id);
  const start = () => ((ended.current = false), setRenaming(b.name));
  const finish = async (keep: boolean) => {
    if (ended.current) return;
    ended.current = true;
    const to = renaming?.trim();
    setRenaming(null);
    if (keep && to && to !== b.name) await actions.rename(to).catch((e: Error) => say(e.message)); // an empty name keeps the old one
  };
  const pad = { paddingLeft: 8 + depth * 16 };
  const Icon = open ? FolderOpen : Folder;
  return (
    <>
      <div ref={box} className="group relative" {...dropTarget(b)} onContextMenu={(e) => (e.preventDefault(), setMenu(true))}>
        {renaming !== null ? (
          <div style={pad} className={`${row} border border-accent bg-surface text-text`}>
            <ChevronRight size={12} strokeWidth={1.75} aria-hidden className="text-muted" />
            <Folder size={14} strokeWidth={1.75} aria-hidden />
            <input
              aria-label={`Rename ${b.name}`}
              autoFocus
              value={renaming}
              maxLength={120}
              onChange={(e) => setRenaming(e.target.value)}
              onKeyDown={(e) => (e.key === "Enter" ? void finish(true) : e.key === "Escape" && void finish(false))}
              onBlur={() => void finish(true)}
              className="min-w-0 flex-1 bg-transparent text-sm font-medium outline-none"
            />
          </div>
        ) : (
          <div style={pad} className={`${row} font-medium ${drop === b.id ? "bg-accent-soft text-accent-text outline-1 outline-dashed outline-[#9fa3ef]" : on ? "bg-surface-3 text-text" : "text-muted hover:bg-surface-3/60"}`}>
            <button type="button" aria-label={open ? `Close ${b.name}` : `Open ${b.name}`} aria-expanded={open} onClick={() => toggle(b.id!)} className="grid size-3 place-items-center">
              {open ? <ChevronDown size={12} strokeWidth={1.75} aria-hidden /> : <ChevronRight size={12} strokeWidth={1.75} aria-hidden />}
            </button>
            <Link to={`/b/${brandId}/videos?folder=${b.id}`} aria-current={on ? "page" : undefined} onDoubleClick={() => b.can_manage && start()} className="flex min-w-0 flex-1 items-center gap-2">
              <Icon size={14} strokeWidth={1.75} aria-hidden className="shrink-0" />
              <span className="truncate">{b.name}</span>
            </Link>
            <span className="text-xs text-muted tabular-nums group-hover:hidden">{b.count}</span>
            <button type="button" aria-label={`More for ${b.name}`} aria-haspopup="menu" aria-expanded={menu} onClick={() => setMenu(!menu)} className="hidden size-5 place-items-center rounded-sm text-muted hover:text-text group-hover:grid focus-visible:grid">
              <Ellipsis size={14} strokeWidth={1.75} aria-hidden />
            </button>
          </div>
        )}
        {menu && (
          <div role="menu" aria-label={b.name} className="absolute left-14 top-full z-40 mt-1 w-52 rounded-lg border border-border bg-surface p-1 shadow-raised">
            {actions.items(() => setMenu(false))}
          </div>
        )}
      </div>
      {open && (
        <>
          {(b.folders ?? []).map((c) => (
            <FolderRow key={c.id} {...props} b={c} depth={depth + 1} />
          ))}
          {ideas(b, depth + 1)}
        </>
      )}
      {actions.dialogs}
    </>
  );
}
