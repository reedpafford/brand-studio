import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ChevronLeft, ChevronRight, Ellipsis, Layers, ListFilter, Plus, Search, FolderPlus } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { api, must } from "../api/client";
import { useMe } from "../auth/useMe";
import { Banner, Button, Menu, MenuItem, Skeleton, buttonClass, useToast } from "../components";
import { ArchivedItem, useFolderActions } from "../folders/FolderActions";
import { GONE, UNSORTED, pathTo, useIdeas, useRefreshIdeas, useTree, type Idea, type Sort, type Tab } from "../folders/ideas";
import { useDebounced } from "../scripts/status";
import { useBrands } from "../shell/useBrands";
import { useRail } from "../useMedia";
import { ArchivedCard, IdeaCard, IdeaRows, SelectBar } from "./IdeaCards";
import { BrandMenu } from "../shell/Shell";
import { PhoneFolders, rememberFolder } from "./PhoneFolders";
import { SetUp } from "./SetUp";

const TABS: [Tab, string][] = [
  ["all", "All"],
  ["needs_you", "Needs you"],
  ["working", "Working"],
  ["delivered", "Delivered"],
];
const SORTS: [Sort, string, string?][] = [
  ["newest", "Newest", "latest activity"],
  ["oldest", "Oldest"],
  ["name", "Name A–Z"],
];
const BIG = 100; // a folder this big opens as a list (S1-05)
const n = (count: number, one: string, many = `${one}s`) => `${count} ${count === 1 ? one : many}`;
const seg = "inline-flex shrink-0 gap-0.5 rounded-md bg-surface-2 p-0.5";
const segItem = (on: boolean) => `inline-flex h-control items-center gap-1.5 whitespace-nowrap rounded-sm px-3 text-sm font-medium transition-colors duration-(--dur-fast) lg:h-7 ${on ? "bg-surface text-text shadow-soft" : "text-muted hover:text-text"}`;
const chip = "inline-flex h-control items-center gap-1.5 whitespace-nowrap rounded-full bg-surface-2 px-3 text-xs font-medium text-text lg:h-[26px]";

/** Brand home: an open folder (v6 S1-01 to S1-08, P-02; S-gaps-01 and -02). Its ideas as cards, or a list for a big folder,
 *  with tabs, search, sort and Made by; several selected move or archive; the folder's ⋯ holds its actions and Archived.
 *  ?folder= is a folder's id or "none" (Unsorted, also where no folder is picked). A brand with no ideas and no folders
 *  shows its set-up list. */
export function FolderPage() {
  const brandId = Number(useParams().brandId);
  const owner = useMe().data?.role === "owner";
  const rail = useRail();
  const brands = useBrands().data;
  const brand = brands?.find((b) => b.id === brandId);
  const [params, setParams] = useSearchParams();
  const set = (changes: Record<string, string>) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        for (const [k, v] of Object.entries(changes)) {
          if (v) next.set(k, v);
          else next.delete(k);
        }
        return next;
      },
      { replace: true },
    );
  const folder = params.get("folder") || UNSORTED;
  const tab = (TABS.find(([t]) => t === params.get("tab"))?.[0] ?? "all") as Tab;
  const sort = (SORTS.find(([s]) => s === params.get("sort"))?.[0] ?? "newest") as Sort;
  const archived = params.get("archived") === "1";
  const madeBy = Number(params.get("made_by")) || null;
  const [text, setText] = useState(params.get("q") ?? "");
  const [searching, setSearching] = useState(!!text);
  const q = useDebounced(text.trim());
  useEffect(() => set({ q }), [q]); // eslint-disable-line react-hooks/exhaustive-deps

  const tree = useTree(brandId);
  useEffect(() => {
    if (params.get("folder")) rememberFolder(brandId, params.get("folder")!);
  }, [brandId, params]);
  const ideas = useIdeas(brandId, { folder, tab, q, sort, madeBy, archived });
  const first = ideas.data?.pages[0];
  const rows = ideas.data?.pages.flatMap((p) => p.ideas) ?? [];
  const path = folder === UNSORTED ? [] : pathTo(tree.data?.folders ?? [], Number(folder));
  const open = folder === UNSORTED ? tree.data?.unsorted : path.at(-1);
  const name = folder === UNSORTED ? "Unsorted" : (open?.name ?? "");
  const view = params.get("view") === "list" || (params.get("view") !== "cards" && (first?.counts.all ?? 0) >= BIG) ? "list" : "cards";
  const list = rail && view === "list";
  // A phone renames in the top bar (S-gaps-06, 19); a computer in a dialog.
  const [renaming, setRenaming] = useState<string | null>(null);
  const actions = useFolderActions(brandId, folder === UNSORTED ? undefined : open, { onDeleted: (parent) => set({ folder: parent ? String(parent) : "", archived: "", tab: "" }), renameInPlace: rail ? undefined : () => setRenaming(open?.name ?? "") });
  const endRename = useRef(false);
  const saveName = async (keep: boolean) => {
    if (endRename.current) return;
    endRename.current = true;
    const to = renaming?.trim();
    setRenaming(null);
    if (keep && to && to !== open?.name) await actions.rename(to).catch((e: Error) => toast(e.message, undefined, "error"));
  };

  // Several selected (S1-07): ticks on hover, on every card once one is ticked; Esc or × clears them.
  // A selection belongs to the view it was made in: another folder, tab or Archived starts with none.
  const scope = `${folder}|${tab}|${archived}|${q}|${madeBy}`;
  const [selection, setSelection] = useState<{ scope: string; ideas: Map<number, Idea> }>({ scope, ideas: new Map() });
  const picked = selection.scope === scope ? selection.ideas : new Map<number, Idea>();
  const setPicked = (next: (was: Map<number, Idea>) => Map<number, Idea>) => setSelection((s) => ({ scope, ideas: next(s.scope === scope ? s.ideas : new Map()) }));
  const [moveOpen, setMoveOpen] = useState(false);
  const clear = () => (setSelection({ scope, ideas: new Map() }), setMoveOpen(false));
  const pick = (i: Idea) =>
    setPicked((was) => {
      const next = new Map(was);
      if (next.has(i.id)) next.delete(i.id);
      else next.set(i.id, i);
      return next;
    });
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && !document.querySelector("[aria-modal]") && (setSelection((s) => ({ ...s, ideas: new Map() })), setMoveOpen(false));
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, []);
  const toast = useToast();
  const refresh = useRefreshIdeas();
  const archiveOne = useMutation({
    mutationFn: (i: Idea) => must(api.POST("/projects/{project_id}/archive", { params: { path: { project_id: i.id } } })).then(() => i),
    onSuccess: async (i) => {
      await refresh();
      toast(`Archived ${i.title}.`, async () => {
        await must(api.POST("/projects/{project_id}/restore", { params: { path: { project_id: i.id } } })).catch((e: Error) => toast(e.message, undefined, "error"));
        await refresh();
      });
    },
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });

  // The next page loads as the end of the list comes into view.
  const end = useRef<HTMLDivElement>(null);
  const { hasNextPage, isFetchingNextPage, fetchNextPage } = ideas;
  useEffect(() => {
    const el = end.current;
    if (!el || !hasNextPage || typeof IntersectionObserver === "undefined") return;
    const seen = new IntersectionObserver(([e]) => e.isIntersecting && !isFetchingNextPage && fetchNextPage(), { rootMargin: "400px" });
    seen.observe(el);
    return () => seen.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage, rows.length]);

  const newVideo = `/b/${brandId}/videos/new${folder === UNSORTED ? "" : `?folder=${folder}`}`;
  if (brand && tree.data && !tree.data.folders.length && !tree.data.unsorted.count && first && !first.archived && !q && !archived)
    return (
      <main>
        <header className="flex h-[52px] items-center gap-2.5 border-b border-border bg-surface px-5">
          <span className="text-sm font-semibold">{brand.name}</span>
          <span className="text-sm text-muted">New brand</span>
          <span className="flex-1" />
          {!rail && <BrandMenu />}
        </header>
        <SetUp brand={brand} others={(brands ?? []).filter((b) => b.id !== brandId).map((b) => b.name)} owner={owner} newVideo={newVideo} />
      </main>
    );

  if (!rail && !params.get("folder")) return <PhoneFolders brandId={brandId} />; // P-01: a phone opens on the folder list (G5)
  const loading = ideas.isPending;
  const counts = first?.counts;
  const filtered = !!(q || madeBy || tab !== "all");
  const empty = !loading && !archived && !filtered && counts?.all === 0;
  const sub = loading
    ? "Loading…"
    : empty
      ? "Empty"
      : [n(counts?.all ?? 0, rail ? "video idea" : "idea"), first?.folders_inside ? n(first.folders_inside, "folder inside", "folders inside") : counts?.needs_you ? n(counts.needs_you, "video needs you", "videos need you") : ""].filter(Boolean).join(" · ");
  const more = (
    <Menu
      title={name}
      align="right"
      popover
      trigger={(p) => (
        <button type="button" {...p} aria-label={`More for ${name}`} className="grid size-control shrink-0 place-items-center rounded-md text-muted hover:bg-surface-2 lg:size-8">
          <Ellipsis size={16} strokeWidth={1.75} aria-hidden />
        </button>
      )}
    >
      {(close) => (
        <>
          {actions.items(close)}
          {folder !== UNSORTED && !!first?.archived && <div className="my-1 border-t border-border" />}
          <ArchivedItem count={first?.archived ?? 0} onClick={() => (close(), set({ archived: "1", tab: "", q: "", made_by: "" }), setText(""))} />
        </>
      )}
    </Menu>
  );
  const searchBox = (
    <label className={`relative block ${rail ? (list ? "w-[200px]" : "w-[260px]") : "w-full"}`}>
      <span className="sr-only">Search this folder</span>
      <Search size={14} strokeWidth={1.75} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
      <input type="search" value={text} onChange={(e) => setText(e.target.value)} placeholder={list ? `Search ${n(counts?.all ?? 0, "idea")}` : "Search this folder"} className="h-control w-full rounded-md border border-border-strong bg-surface pl-9 pr-3 text-base text-text placeholder:text-muted lg:h-8 lg:text-sm" />
    </label>
  );

  return (
    <main className="mx-auto min-h-screen max-w-content pb-24 lg:min-h-full">
      {/* S1-04's top: Brand › folder, its counts, ⋯ and New video (P-02: the folder's name over its counts). */}
      <header className="flex min-h-14 items-center gap-2.5 border-b border-border bg-surface px-4 lg:px-5">
        {rail ? (
          <p className="flex min-w-0 items-center gap-1.5 text-sm text-muted">
            <span className="shrink-0">{brand?.name}</span>
            {path.slice(0, -1).map((f) => (
              <span key={f.id} className="contents">
                <ChevronRight size={12} strokeWidth={1.75} aria-hidden className="shrink-0" />
                <Link to={`/b/${brandId}/videos?folder=${f.id}`} className="truncate hover:text-text">
                  {f.name}
                </Link>
              </span>
            ))}
            <ChevronRight size={12} strokeWidth={1.75} aria-hidden className="shrink-0" />
            <span className="truncate font-semibold text-text">{name}</span>
            <span className="ml-1 shrink-0">{sub}</span>
          </p>
        ) : (
          <>
            <Link to={`/b/${brandId}/videos`} aria-label="All folders" className="-ml-2 grid size-control shrink-0 place-items-center rounded-md text-text">
              <ChevronLeft size={22} strokeWidth={1.75} aria-hidden />
            </Link>
            <div className="min-w-0">
              {renaming !== null ? (
                <input
                  aria-label={`Rename ${name}`}
                  autoFocus
                  value={renaming}
                  maxLength={120}
                  onFocus={() => (endRename.current = false)}
                  onChange={(e) => setRenaming(e.target.value)}
                  onKeyDown={(e) => (e.key === "Enter" ? void saveName(true) : e.key === "Escape" && void saveName(false))}
                  onBlur={() => void saveName(true)}
                  className="h-8 w-full rounded-md border border-accent bg-surface px-2 text-lg font-semibold outline-none"
                />
              ) : (
                <h1 className="truncate text-lg font-semibold">{name}</h1>
              )}
              <p className="truncate text-sm text-muted">{[brand?.name, sub].filter(Boolean).join(" · ")}</p>
            </div>
          </>
        )}
        <span className="flex-1" />
        {!rail && (
          <button type="button" aria-label="Search this folder" aria-pressed={searching} onClick={() => setSearching(!searching)} className="grid size-control place-items-center rounded-md text-text">
            <Search size={20} strokeWidth={1.75} aria-hidden />
          </button>
        )}
        {(folder !== UNSORTED || !!first?.archived) && more}
        {rail && (
          <Link to={newVideo} className={`${buttonClass(empty ? "secondary" : "primary")} lg:min-h-9 lg:px-3.5`}>
            <Plus size={16} strokeWidth={1.75} aria-hidden /> New video
          </Link>
        )}
      </header>

      {archived ? (
        <div className="flex flex-wrap items-center gap-3 px-4 pt-4 lg:px-6">
          <Button variant="secondary" icon={ArrowLeft} onClick={() => set({ archived: "" })}>
            Back to the folder
          </Button>
          <h2 className="text-lg font-semibold">Archived</h2>
          <span className="text-sm text-muted">{n(first?.archived ?? rows.length, "idea")} · kept, not shown in the folder · their files stay downloadable</span>
        </div>
      ) : (
        !empty && (
          <div className="flex flex-col gap-3 px-4 pt-4 lg:flex-row lg:items-center lg:px-6">
            {!rail && searching && searchBox}
            <div className="-mx-4 overflow-x-auto px-4 lg:mx-0 lg:px-0">
              <div role="tablist" aria-label="Status" className={seg}>
                {TABS.map(([t, label]) => (
                  <button key={t} type="button" role="tab" aria-selected={tab === t} onClick={() => set({ tab: t === "all" ? "" : t })} className={segItem(tab === t)}>
                    {label}
                    {counts && (rail || t !== "all") && " "}
                    {counts && (rail || t !== "all") && <span className="font-normal text-faint tabular-nums">{counts[t]}</span>}
                  </button>
                ))}
              </div>
            </div>
            {rail && searchBox}
            <span className="hidden flex-1 lg:block" />
            {list && first && (
              <Menu title="Made by" align="right" trigger={(p) => <button type="button" {...p} className={chip}><span className="font-normal text-muted">Made by</span> {first.makers.find((m) => m.id === madeBy)?.name ?? "Anyone"}</button>}>
                {(close) => [{ id: 0, name: "Anyone" }, ...first.makers].map((m) => (
                  <MenuItem key={m.id} checked={(madeBy ?? 0) === m.id} onClick={() => (close(), set({ made_by: m.id ? String(m.id) : "" }))}>
                    {m.name}
                  </MenuItem>
                ))}
              </Menu>
            )}
            {rail && (
              <>
                <Menu title="Sort" align="right" trigger={(p) => <button type="button" {...p} className={chip}><ListFilter size={14} strokeWidth={1.75} aria-hidden /><span className="font-normal text-muted">Sort</span> {SORTS.find(([s]) => s === sort)?.[1]}</button>}>
                  {(close) => SORTS.map(([s, label, note]) => (
                    <MenuItem key={s} checked={sort === s} onClick={() => (close(), set({ sort: s === "newest" ? "" : s }))}>
                      <span className="flex-1">{label}</span>
                      {note && <span className="text-xs text-muted">{note}</span>}
                    </MenuItem>
                  ))}
                </Menu>
                <div role="radiogroup" aria-label="View" className={seg}>
                  <button type="button" role="radio" aria-checked={!list} aria-label="Cards" onClick={() => set({ view: "cards" })} className={segItem(!list)}>
                    <Layers size={14} strokeWidth={1.75} aria-hidden />
                  </button>
                  <button type="button" role="radio" aria-checked={list} aria-label="List" onClick={() => set({ view: "list" })} className={segItem(list)}>
                    <ListFilter size={14} strokeWidth={1.75} aria-hidden />
                  </button>
                </div>
              </>
            )}
          </div>
        )
      )}

      {ideas.isError && (
        <div className="px-4 pt-4 lg:px-6">
          {ideas.error.message === GONE ? (
            <Banner tone="warning" title="This folder isn't here any more. It may have been deleted." action={<Link to={`/b/${brandId}/videos`} className={buttonClass("secondary")}>Open Unsorted</Link>} />
          ) : (
            <Banner tone="danger" title="Couldn't load this folder. Check your connection." action={<Button variant="secondary" onClick={() => ideas.refetch()}>Try again</Button>} />
          )}
        </div>
      )}

      {loading ? (
        <div role="status" aria-label="Loading" className="grid grid-cols-2 gap-3 px-4 py-5 lg:grid-cols-[repeat(auto-fill,minmax(200px,1fr))] lg:gap-x-4 lg:gap-y-5 lg:px-6">
          {Array.from({ length: 10 }, (_, k) => (
            <div key={k} className="flex flex-col gap-2">
              <Skeleton className="aspect-[212/290] w-full rounded-lg" />
              <Skeleton className="h-3 w-40 max-w-full" />
              <Skeleton className="h-3 w-28" />
            </div>
          ))}
        </div>
      ) : empty ? (
        <div className="flex min-h-[70vh] flex-col items-center justify-center gap-3 px-4 text-center">
          <div aria-hidden className="flex gap-2 opacity-90">
            {[0, 1, 2].map((k) => (
              <span key={k} className="h-32 w-[72px] rounded-md border border-dashed border-border-strong bg-surface-2" />
            ))}
          </div>
          <h2 className="mt-2 text-xl font-semibold">{folder === UNSORTED ? "Nothing in Unsorted" : `Nothing in ${name} yet`}</h2>
          <p className="max-w-[420px] text-md text-muted">{folder === UNSORTED ? "New ideas land here until you put them in a folder." : rail ? "Start a video here, or drag ideas in from another folder in the list on the left." : "Start a video here, or move ideas in from another folder."}</p>
          <div className="flex flex-wrap justify-center gap-2">
            <Link to={newVideo} className={`${buttonClass("primary")} lg:min-h-9`}>
              <Plus size={16} strokeWidth={1.75} aria-hidden /> {folder === UNSORTED ? "New video" : `New video in ${name}`}
            </Link>
            {folder !== UNSORTED && (
              <Button variant="secondary" icon={FolderPlus} className="lg:min-h-9" onClick={actions.newInside}>
                New folder inside
              </Button>
            )}
          </div>
        </div>
      ) : rows.length === 0 && !ideas.isError ? (
        <p className="px-4 py-10 text-center text-muted lg:px-6">{archived ? "Nothing archived here." : "Nothing matches. Try another tab or search."}</p>
      ) : list && !archived ? (
        <div className="px-6 py-4">
          <IdeaRows
            brandId={brandId}
            rows={rows}
            owner={owner}
            picked={new Set(picked.keys())}
            onPick={pick}
            onAll={() => setPicked((was) => (rows.filter((r) => r.can_manage).every((r) => was.has(r.id)) ? new Map() : new Map(rows.filter((r) => r.can_manage).map((r) => [r.id, r]))))}
            onMove={(i) => (setPicked(() => new Map([[i.id, i]])), setMoveOpen(true))}
            onArchive={(i) => archiveOne.mutate(i)}
          />
          <div className="flex justify-between px-1 py-2.5 text-sm text-muted">
            <span>
              Showing 1–{rows.length} of {first?.total}
            </span>
            {hasNextPage && <span>Scroll for more · the list loads as you go</span>}
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-x-3 gap-y-5 px-4 py-5 lg:grid-cols-[repeat(auto-fill,minmax(200px,1fr))] lg:gap-x-4 lg:px-6">
          {rows.map((i) => (archived ? <ArchivedCard key={i.id} brandId={brandId} i={i} /> : <IdeaCard key={i.id} brandId={brandId} i={i} phone={!rail} picked={picked.has(i.id)} picking={picked.size > 0} onPick={i.can_manage ? () => pick(i) : undefined} />))}
        </div>
      )}
      <div ref={end} aria-hidden />
      {actions.dialogs}
      <SelectBar brandId={brandId} picked={[...picked.values()]} here={folder === UNSORTED ? null : Number(folder)} moveOpen={moveOpen} setMoveOpen={setMoveOpen} onClear={clear} />
    </main>
  );
}
