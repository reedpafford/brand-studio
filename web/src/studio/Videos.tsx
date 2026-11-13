import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Archive, Clapperboard, Ellipsis, Folder, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { folderWrites } from "../folders/FolderActions";
import { GONE, UNSORTED, flatten, pathTo, useIdeas, useRefreshIdeas, useTree, type Branch, type Idea } from "../folders/ideas";
import { useVideoActions } from "../projects/ReleaseVideo";
import { useDebounced } from "../scripts/status";
import { useBrands } from "../shell/useBrands";
import { serverTime } from "../time";
import { useToast } from "../toast";
import { Dialog } from "./Dialog";
import { Popover } from "./Popover";
import { NewFolder } from "./RailFolders";
import { MAKING } from "./StudioShell";
import { VideoCard } from "./VideoCard";
import { ArchiveAsk } from "./VideoMenu";
import "./video.css"; // the crumb, the empty box and the dialogs' words are the video page's
import "./videos.css";

const ICON = { size: 16, strokeWidth: 1.75, "aria-hidden": true } as const;
const SHOWS = [["all", "All"], ["making", "Being made"], ["delivered", "Delivered"]] as const;
type Show = (typeof SHOWS)[number][0] | "archived";
const GROUPS = [["date", "Date"], ["look", "Look"]] as const;
type Group = (typeof GROUPS)[number][0];
const GROUP = "bs.videos.group"; // how the cards were last grouped, kept on this computer
const videos = (n: number) => `${n} video${n === 1 ? "" : "s"}`;

/** By date: what is still on its way first, then by the day each last changed. */
function byDate(list: Idea[]): [string, Idea[]][] {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  const of = (i: Idea) => {
    if (MAKING.includes(i.status.kind)) return "Being made";
    const at = serverTime(i.updated_at);
    return at >= today ? "Today" : at >= yesterday ? "Yesterday" : "Earlier";
  };
  return ["Being made", "Today", "Yesterday", "Earlier"].map((name): [string, Idea[]] => [name, list.filter((i) => of(i) === name)]).filter(([, x]) => x.length);
}
/** By look: every Movie video together, every Pixar video together, the look used most recently first. */
const byLook = (list: Idea[]) => [...new Set(list.map((i) => i.style))].map((style): [string, Idea[]] => [style, list.filter((i) => i.style === style)]);

/** Rename this folder: one field. The server's own words show if it refuses (a name already taken). */
function RenameFolder({ folder, onClose }: { folder: Branch; onClose: () => void }) {
  const [name, setName] = useState(folder.name);
  const refresh = useRefreshIdeas();
  const rename = useMutation({ mutationFn: () => folderWrites.rename(folder.id!, name), onSuccess: () => refresh().then(onClose) });
  return (
    <Dialog title="Rename this folder" confirm="Rename" busy={rename.isPending} onClose={onClose} onConfirm={() => (name.trim() && name.trim() !== folder.name ? rename.mutate() : onClose())}>
      <input data-autofocus aria-label="Name" value={name} maxLength={120} onChange={(e) => (setName(e.target.value), rename.reset())} />
      {rename.error && (
        <p className="dsub" role="alert">
          {rename.error.message}
        </p>
      )}
    </Dialog>
  );
}

/** /s/b/:brandId/videos: the brand's videos in the new look (the redesign, stage 4). */
export function Videos() {
  const brandId = Number(useParams().brandId);
  return <Page key={brandId} brandId={brandId} />; // another brand starts clean: no search carried over
}

/** The brand's videos as poster cards, or one folder's (?folder=, picked in the rail; on a phone, in the row of pills).
 *  Shown All, Being made or Delivered, with Archived behind one quiet press; searched by title; grouped by date or by
 *  look. The whole list is read, a page after a page through the current site's own hook, because the groups are made
 *  from all of it. A folder's "…" renames or deletes it. Nothing is sent until something is pressed or dropped. */
function Page({ brandId }: { brandId: number }) {
  const base = `/s/b/${brandId}`;
  const brand = useBrands().data?.find((b) => b.id === brandId);
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
  const folder = params.get("folder"); // a folder's id, "none" for Unsorted, or nothing: every video in the brand
  const show: Show = params.get("show") === "archived" ? "archived" : (SHOWS.find(([s]) => s === params.get("show"))?.[0] ?? "all");
  const archived = show === "archived";
  const [group, setGroup] = useState<Group>(() => (localStorage.getItem(GROUP) === "look" ? "look" : "date"));
  const [text, setText] = useState(params.get("q") ?? "");
  const q = useDebounced(text.trim());
  useEffect(() => set({ q }), [q, folder]); // eslint-disable-line react-hooks/exhaustive-deps

  const tree = useTree(brandId).data;
  const open = folder === null ? undefined : folder === UNSORTED ? tree?.unsorted : pathTo(tree?.folders ?? [], Number(folder)).at(-1);
  const ideas = useIdeas(brandId, { folder: folder ?? "all", tab: "all", q, sort: "newest", madeBy: null, archived });
  const { hasNextPage, isFetching, isFetchNextPageError, isPlaceholderData, fetchNextPage } = ideas;
  useEffect(() => {
    if (hasNextPage && !isFetching && !isFetchNextPageError && !isPlaceholderData) void fetchNextPage();
  }, [hasNextPage, isFetching, isFetchNextPageError, isPlaceholderData, fetchNextPage]);
  const first = ideas.data?.pages[0];
  const [facts, setFacts] = useState(first); // the counts last read: the row of filters stays put while another view loads
  if (first && first !== facts) setFacts(first);
  const rows = ideas.data?.pages.flatMap((p) => p.ideas) ?? [];
  const shown = show === "making" ? rows.filter((i) => MAKING.includes(i.status.kind)) : show === "delivered" ? rows.filter((i) => i.status.kind === "delivered") : rows;
  const groups: [string, Idea[]][] = archived ? [["Archived", shown]] : group === "look" ? byLook(shown) : byDate(shown);

  const toast = useToast();
  const refresh = useRefreshIdeas();
  const video = useVideoActions(undefined, refresh);
  const [renaming, setRenaming] = useState(false);
  const [adding, setAdding] = useState(false);
  const remove = useMutation({
    mutationFn: async (b: Branch) => ({ ...(await folderWrites.remove(b.id!)).data!, b }),
    onSuccess: async ({ ideas: moved, b }) => {
      set({ folder: "", show: "" });
      await refresh();
      toast(`“${b.name}” is gone. ${moved ? `Its ${videos(moved)} moved to Unsorted.` : "Nothing was in it."}`, async () => {
        await folderWrites.restore(b.id!).catch((e: Error) => toast(e.message, undefined, "error"));
        await refresh();
      });
    },
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });

  const nothing = !!first && !q && !archived && first.counts.all === 0;
  const fresh = nothing && folder === null; // a brand with no videos: one next step, and nothing else to press
  const waiting = (
    <div className="vgrid" role="status" aria-label="Loading">
      {Array.from({ length: 6 }, (_, k) => (
        <span key={k} className="pic" />
      ))}
    </div>
  );
  return (
    <>
      <header className="head vids-head">
        {folder === null ? (
          <h1>Videos</h1>
        ) : (
          <>
            <Link className="crumb" to={`${base}/videos`}>
              Videos
            </Link>
            <span className="slash" aria-hidden>
              /
            </span>
            <h1 className="clip">{open?.name}</h1>
            {open?.id != null && open.can_manage && (
              <Popover
                label={`More for ${open.name}`}
                button={(b) => (
                  <button type="button" className="btn ghost square" aria-label="More for this folder" title="Rename or delete" {...b}>
                    <Ellipsis {...ICON} />
                  </button>
                )}
              >
                {(close) => (
                  <>
                    <button type="button" role="menuitem" onClick={() => (close(), setRenaming(true))}>
                      <Pencil {...ICON} /> Rename…
                    </button>
                    <button type="button" role="menuitem" disabled={remove.isPending} onClick={() => (close(), remove.mutate(open))}>
                      <Trash2 {...ICON} />
                      <span className="ol">
                        <b>Delete folder</b>
                        <small>Its videos go to Unsorted</small>
                      </span>
                    </button>
                  </>
                )}
              </Popover>
            )}
          </>
        )}
        <span className="grow" />
        {!fresh && (
          <>
            <label className="field">
              <Search size={14} strokeWidth={1.75} aria-hidden />
              <input type="search" aria-label={folder === null ? "Search videos" : "Search this folder"} placeholder="Search" value={text} onChange={(e) => setText(e.target.value)} />
            </label>
            <div className="seg" role="group" aria-label="Group by">
              {GROUPS.map(([g, words]) => (
                <button key={g} type="button" aria-pressed={group === g} onClick={() => (localStorage.setItem(GROUP, g), setGroup(g))}>
                  {words}
                </button>
              ))}
            </div>
            <Link className="btn go" to={base}>
              <Plus {...ICON} />
              New video
            </Link>
          </>
        )}
      </header>
      <div className="view">
        <div className="page vids">
          {tree && (
            <nav className="fpills" aria-label="Folders">
              {[{ id: "", name: "All" }, ...flatten(tree.folders), { id: UNSORTED, name: "Unsorted" }].map((f) => {
                const on = (folder ?? "") === String(f.id);
                return (
                  <Link key={f.id} className={on ? "pill on" : "pill"} aria-current={on ? "page" : undefined} to={`${base}/videos${f.id ? `?folder=${f.id}` : ""}`}>
                    {f.name}
                  </Link>
                );
              })}
              {adding ? (
                <NewFolder brandId={brandId} onDone={() => setAdding(false)} />
              ) : (
                <button type="button" className="pill" aria-label="New folder" onClick={() => setAdding(true)}>
                  <Plus {...ICON} />
                </button>
              )}
            </nav>
          )}
          {facts && (facts.counts.all > 0 || facts.archived > 0 || archived) && (
            <div className="vbar">
              {facts.counts.all > 0 && (
                <div className="seg" role="group" aria-label="Show">
                  {SHOWS.map(([s, words]) => (
                    <button key={s} type="button" aria-pressed={show === s} onClick={() => set({ show: s === "all" ? "" : s })}>
                      {words}
                    </button>
                  ))}
                </div>
              )}
              <span className="grow" />
              {(facts.archived > 0 || archived) && (
                <button type="button" className="btn ghost" aria-pressed={archived} onClick={() => set({ show: archived ? "" : "archived" })}>
                  <Archive {...ICON} />
                  Archived <span className="n">{facts.archived}</span>
                </button>
              )}
            </div>
          )}
          {ideas.isError && !rows.length ? (
            ideas.error.message === GONE ? (
              <p className="quiet" role="alert">
                This folder isn’t here any more. It may have been deleted. <Link to={`${base}/videos`}>Open all videos</Link>
              </p>
            ) : (
              <p className="quiet" role="alert">
                Couldn’t load the videos. Check your connection.{" "}
                <button type="button" className="btn soft" onClick={() => void ideas.refetch()}>
                  Try again
                </button>
              </p>
            )
          ) : !first ? (
            waiting
          ) : fresh ? (
            <div className="hold bare">
              <Clapperboard size={24} strokeWidth={1.5} aria-hidden />
              <b>No videos in {brand?.name ?? "this brand"} yet</b>
              <p>Paste a script and pick a look. The director does the rest.</p>
              <Link className="btn go" to={base}>
                <Plus {...ICON} />
                Make the first video
              </Link>
            </div>
          ) : nothing ? (
            <div className="hold bare">
              <Folder size={24} strokeWidth={1.5} aria-hidden />
              <b>Nothing in {open?.name ?? "this folder"} yet</b>
              {folder === UNSORTED ? (
                <p>New videos land here until you put them in a folder.</p>
              ) : (
                <p>
                  Pick it under “Move to” in a video’s menu<span className="wide">, or drag a video onto the folder on the left</span>. When you make a video, choose it under “Save in”.
                </p>
              )}
            </div>
          ) : !shown.length && hasNextPage ? (
            waiting
          ) : !shown.length ? (
            <p className="quiet">
              {archived ? "Nothing archived here." : q ? `Nothing matches “${q}”.` : show === "making" ? "Nothing is being made right now." : "Nothing delivered yet."}{" "}
              {q && (
                <button type="button" className="btn soft" onClick={() => setText("")}>
                  Clear the search
                </button>
              )}
            </p>
          ) : (
            <>
              {archived && <p className="quiet">Archived videos are out of the lists. Their clips and downloads are kept, and Restore brings one back.</p>}
              {groups.map(([name, list]) => (
                <section key={name} className="grp" aria-label={name}>
                  {!archived && (
                    <h2>
                      {name}
                      {!hasNextPage && <span>{videos(list.length)}</span>}
                    </h2>
                  )}
                  <div className="vgrid">
                    {list.map((i) => (
                      <VideoCard key={i.id} i={i} brandId={brandId} video={video} />
                    ))}
                  </div>
                </section>
              ))}
              {hasNextPage &&
                (isFetchNextPageError ? (
                  <p className="quiet" role="alert">
                    Couldn’t load the rest of the videos.{" "}
                    <button type="button" className="btn soft" onClick={() => void fetchNextPage()}>
                      Try again
                    </button>
                  </p>
                ) : (
                  <p className="none" role="status">
                    Loading the rest…
                  </p>
                ))}
            </>
          )}
        </div>
      </div>
      {renaming && open && <RenameFolder folder={open} onClose={() => setRenaming(false)} />}
      <ArchiveAsk asking={video.asking} />
    </>
  );
}
