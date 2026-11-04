import { Film, Folder, FolderOpen, FolderPlus, Inbox, Plus } from "lucide-react";
import { Link } from "react-router-dom";
import { buttonClass } from "../components";
import { useFolderActions } from "../folders/FolderActions";
import { StatusDot, UNSORTED, useTree, type Branch } from "../folders/ideas";
import { BrandMenu } from "../shell/Shell";
import { QuickSearch } from "../shell/QuickSearch";

const LAST = (brandId: number) => `bs.lastFolder.${brandId}`;
/** The folder a phone opened last: P-01 shows its newest ideas under it. */
export const rememberFolder = (brandId: number, folder: string) => {
  try {
    localStorage.setItem(LAST(brandId), folder);
  } catch {
    /* not remembering is fine */
  }
};
const lastFolder = (brandId: number) => {
  try {
    return localStorage.getItem(LAST(brandId));
  } catch {
    return null;
  }
};

const row = "flex min-h-12 items-center gap-3 border-b border-border px-4";

/** A brand and its folders on a phone (v6 P-01): each folder with its count, the one opened last with its newest ideas
 *  and their dots, Unsorted, and New video. A folder opens as P-02. */
export function PhoneFolders({ brandId }: { brandId: number }) {
  const tree = useTree(brandId).data;
  const top = useFolderActions(brandId, undefined);
  const last = lastFolder(brandId);
  const shown = tree?.folders.find((f) => String(f.id) === last) ?? tree?.folders[0];
  const folder = (b: Branch) => {
    const open = b === shown;
    const Icon = open ? FolderOpen : Folder;
    return (
      <li key={b.id}>
        <Link to={`/b/${brandId}/videos?folder=${b.id}`} className={`${row} text-md font-medium`}>
          <Icon size={20} strokeWidth={1.75} aria-hidden className="shrink-0 text-muted" />
          <span className="min-w-0 flex-1 truncate">{b.name}</span>
          <span className="tabular-nums">{b.count}</span>
        </Link>
        {open && (
          <ul>
            {b.ideas.slice(0, 3).map((i) => (
              <li key={i.id}>
                <Link to={`/b/${brandId}/videos/${i.id}`} className={`${row} pl-[52px] text-md`}>
                  <Film size={20} strokeWidth={1.75} aria-hidden className="shrink-0 text-muted" />
                  <span className="min-w-0 flex-1 truncate">{i.title}</span>
                  <StatusDot status={i.status} label />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </li>
    );
  };
  return (
    <main className="min-h-screen">
      <header className="flex h-14 items-center gap-2 border-b border-border bg-surface px-3">
        <BrandMenu />
        <span className="flex-1" />
        <QuickSearch brandId={brandId} phone />
        <button type="button" aria-label="New folder" onClick={top.newInside} className="grid size-control place-items-center rounded-md text-text">
          <FolderPlus size={22} strokeWidth={1.75} aria-hidden />
        </button>
      </header>
      <ul className="bg-surface">
        {(tree?.folders ?? []).map(folder)}
        {tree && (
          <li>
            <Link to={`/b/${brandId}/videos?folder=${UNSORTED}`} className={`${row} text-md font-medium`}>
              <Inbox size={20} strokeWidth={1.75} aria-hidden className="shrink-0 text-muted" />
              <span className="flex-1">Unsorted</span>
              <span className="tabular-nums">{tree.unsorted.count}</span>
            </Link>
          </li>
        )}
      </ul>
      <div className="p-4">
        <Link to={`/b/${brandId}/videos/new`} className={`${buttonClass("primary")} inline-flex`}>
          <Plus size={16} strokeWidth={1.75} aria-hidden /> New video
        </Link>
      </div>
      {top.dialogs}
    </main>
  );
}
