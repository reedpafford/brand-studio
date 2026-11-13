import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Archive, ArrowRightLeft, Folder, FolderPlus, Inbox, Pencil, Plus, Trash2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api, must } from "../api/client";
import { Dialog, Field, MenuItem, useToast } from "../components";
import { flatten, useRefreshIdeas, useTree, type Branch } from "./ideas";

type Asking = "new" | "rename" | "move" | "delete" | null;

/** The folder requests, as every screen sends them: a new folder (`parentId` null: at the top), a new name, a delete
 *  (its ideas move to Unsorted) and the Undo of one. */
export const folderWrites = {
  make: (brandId: number, name: string, parentId: number | null) => must(api.POST("/brands/{brand_id}/folders", { params: { path: { brand_id: brandId } }, body: { name: name.trim(), parent_id: parentId } })),
  rename: (id: number, name: string) => must(api.PATCH("/folders/{folder_id}", { params: { path: { folder_id: id } }, body: { name: name.trim() } })),
  remove: (id: number) => must(api.DELETE("/folders/{folder_id}", { params: { path: { folder_id: id } } })),
  restore: (id: number) => must(api.POST("/folders/{folder_id}/restore", { params: { path: { folder_id: id } } })),
};

/** The ideas and folders inside a folder, counted at any depth: "Its 3 ideas move to Unsorted". */
const plural = (n: number, one: string) => `${n} ${one}${n === 1 ? "" : "s"}`;

type Options = {
  onDeleted?: (parentId: number | null) => void;
  /** Where the Undo after a delete shows: the app's toast, or the rail's own (S0-01). */
  say?: (message: string, undo: () => void) => void;
  /** The tree renames in place (S0-01 "type, Enter to save"); elsewhere Rename opens a dialog. */
  renameInPlace?: () => void;
  /** The tree's menu starts with "New video here" (S0-01); the folder page has its own New video. */
  newVideoHere?: boolean;
};

/** A folder's actions (S0-01's menu; S-gaps-02 for the header's ⋯): New video here, New folder inside, Rename, Move to…,
 *  Delete folder…, each with its dialog, and Undo after a delete. `items` renders the menu rows; `dialogs` their dialogs. */
export function useFolderActions(brandId: number, folder: Branch | undefined, { onDeleted, say, renameInPlace, newVideoHere }: Options = {}) {
  const [asking, setAsking] = useState<Asking>(null);
  const [name, setName] = useState("");
  const [to, setTo] = useState<number | null>(null);
  const tree = useTree(brandId).data;
  const refresh = useRefreshIdeas();
  const toast = useToast();
  const navigate = useNavigate();
  const id = folder?.id ?? 0;
  const done = () => {
    setAsking(null);
    return refresh();
  };
  const make = useMutation({ mutationFn: () => folderWrites.make(brandId, name, folder?.id ?? null), onSuccess: done });
  const rename = useMutation({ mutationFn: () => folderWrites.rename(id, name), onSuccess: done });
  const move = useMutation({ mutationFn: () => must(api.PATCH("/folders/{folder_id}", { params: { path: { folder_id: id } }, body: { parent_id: to } })), onSuccess: done });
  const remove = useMutation({
    // What was deleted is kept with the answer: once the tree reloads, this folder is gone from it.
    mutationFn: async () => ({ ...(await folderWrites.remove(id)).data!, id, name: folder?.name ?? "", parent: folder?.parent_id ?? null }),
    onSuccess: ({ ideas: n, id: gone, name: was, parent }) => {
      onDeleted?.(parent); // off the folder that's gone: to the one it was in, or Unsorted
      void done();
      (say ?? toast)(`Deleted “${was}”. ${n ? `Its ${plural(n, "idea")} moved to Unsorted.` : "Nothing was in it."}`, async () => {
        await folderWrites.restore(gone).catch((e: Error) => toast(e.message, undefined, "error"));
        await refresh();
      });
    },
  });
  const open = (what: Asking) => {
    setName(what === "rename" ? (folder?.name ?? "") : "");
    setTo(folder?.parent_id ?? null);
    [make, rename, move, remove].forEach((m) => m.reset());
    setAsking(what);
  };
  // Never into itself or a folder inside it (the server says so too).
  const inside = new Set(folder ? flatten([folder]).map((f) => f.id) : []);
  const places = flatten(tree?.folders ?? []).filter((f) => !inside.has(f.id));
  const failed = (m: { error: Error | null }) => m.error?.message ?? null;

  const items = (close: () => void) =>
    folder?.id ? (
      <>
        {newVideoHere && (
          <MenuItem onClick={() => (close(), navigate(`/b/${brandId}/videos/new?folder=${folder.id}`))}>
            <Plus size={16} strokeWidth={1.75} aria-hidden /> New video here
          </MenuItem>
        )}
        <MenuItem onClick={() => (close(), open("new"))}>
          <FolderPlus size={16} strokeWidth={1.75} aria-hidden /> New folder inside
        </MenuItem>
        {folder.can_manage && (
          <>
            <MenuItem onClick={() => (close(), renameInPlace ? renameInPlace() : open("rename"))}>
              <Pencil size={16} strokeWidth={1.75} aria-hidden /> Rename
            </MenuItem>
            <MenuItem onClick={() => (close(), open("move"))}>
              <ArrowRightLeft size={16} strokeWidth={1.75} aria-hidden /> Move to…
            </MenuItem>
            <MenuItem danger onClick={() => (close(), open("delete"))}>
              <Trash2 size={16} strokeWidth={1.75} aria-hidden /> Delete folder…
            </MenuItem>
          </>
        )}
      </>
    ) : null;

  const dialogs = (
    <>
      {(asking === "new" || asking === "rename") && (
        <Dialog
          title={asking === "new" ? (folder?.id ? `New folder inside ${folder.name}` : "New folder") : `Rename ${folder?.name}`}
          cancelLabel="Not now"
          actionLabel={asking === "new" ? "Make the folder" : "Rename"}
          busy={make.isPending || rename.isPending}
          holdReason={!name.trim() ? "Give it a name" : failed(asking === "new" ? make : rename)}
          onCancel={() => setAsking(null)}
          onConfirm={() => (asking === "new" ? make : rename).mutate()}
        >
          <Field label="Name" value={name} maxLength={120} autoFocus onChange={(e) => (setName(e.target.value), make.reset(), rename.reset())} />
        </Dialog>
      )}
      {asking === "move" && folder && (
        <Dialog title={`Move ${folder.name} to…`} cancelLabel="Not now" actionLabel="Move" busy={move.isPending} holdReason={to === (folder.parent_id ?? null) ? "Pick another place" : failed(move)} onCancel={() => setAsking(null)} onConfirm={() => move.mutate()}>
          <div role="radiogroup" aria-label="Move to" className="-mx-2 max-h-80 overflow-y-auto">
            {[{ id: null as number | null, name: "The top level", depth: 0 }, ...places].map((p) => (
              <button key={p.id ?? "top"} type="button" role="radio" aria-checked={to === p.id} onClick={() => (setTo(p.id), move.reset())} style={{ paddingLeft: 8 + p.depth * 16 }} className={`flex min-h-control w-full items-center gap-2 rounded-md pr-2 text-left text-sm text-text lg:min-h-[30px] ${to === p.id ? "bg-surface-2 font-medium" : "hover:bg-surface-2"}`}>
                {p.id === null ? <Inbox size={14} strokeWidth={1.75} aria-hidden /> : <Folder size={14} strokeWidth={1.75} aria-hidden />}
                {p.name}
              </button>
            ))}
          </div>
        </Dialog>
      )}
      {asking === "delete" && folder && (
        <Dialog title={`Delete ${folder.name}?`} cancelLabel="Keep it" actionLabel="Delete folder" danger busy={remove.isPending} holdReason={failed(remove)} onCancel={() => setAsking(null)} onConfirm={() => remove.mutate()}>
          {folder.count ? `Its ${plural(folder.count, "idea")} move${folder.count === 1 ? "s" : ""} to Unsorted${folder.folders?.length ? ", with the folders inside it" : ""}. Nothing is deleted, and Undo brings it back.` : "Nothing is in it."}
        </Dialog>
      )}
    </>
  );
  return { items, dialogs, newInside: () => open("new"), rename: (to: string) => folderWrites.rename(id, to).then(() => refresh()) };
}

/** "Archived ideas · 2" under a folder's actions (S-gaps-02): hidden when there are none. */
export function ArchivedItem({ count, onClick }: { count: number; onClick: () => void }) {
  if (!count) return null;
  return (
    <MenuItem onClick={onClick}>
      <Archive size={16} strokeWidth={1.75} aria-hidden /> <span className="flex-1">Archived ideas</span>
      <span className="text-xs text-muted tabular-nums">{count}</span>
    </MenuItem>
  );
}
