import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Archive, ArrowRightLeft, Folder, FolderPlus, Inbox, Pencil, Trash2 } from "lucide-react";
import { api, must } from "../api/client";
import { Dialog, Field, MenuItem, useToast } from "../components";
import { flatten, useRefreshIdeas, useTree, type Branch } from "./ideas";

type Asking = "new" | "rename" | "move" | "delete" | null;

/** The ideas and folders inside a folder, counted at any depth: "Its 3 ideas move to Unsorted". */
const plural = (n: number, one: string) => `${n} ${one}${n === 1 ? "" : "s"}`;

/** A folder's actions (S0-01's menu; S-gaps-02 for the header's ⋯): New folder inside, Rename, Move to…, Delete folder…,
 *  each with its dialog, and the toast with Undo after a delete. `items` renders the menu rows; `dialogs` their dialogs. */
export function useFolderActions(brandId: number, folder: Branch | undefined, onDeleted?: (parentId: number | null) => void) {
  const [asking, setAsking] = useState<Asking>(null);
  const [name, setName] = useState("");
  const [to, setTo] = useState<number | null>(null);
  const tree = useTree(brandId).data;
  const refresh = useRefreshIdeas();
  const toast = useToast();
  const id = folder?.id ?? 0;
  const done = () => {
    setAsking(null);
    return refresh();
  };
  const make = useMutation({ mutationFn: () => must(api.POST("/brands/{brand_id}/folders", { params: { path: { brand_id: brandId } }, body: { name: name.trim(), parent_id: folder?.id ?? null } })), onSuccess: done });
  const rename = useMutation({ mutationFn: () => must(api.PATCH("/folders/{folder_id}", { params: { path: { folder_id: id } }, body: { name: name.trim() } })), onSuccess: done });
  const move = useMutation({ mutationFn: () => must(api.PATCH("/folders/{folder_id}", { params: { path: { folder_id: id } }, body: { parent_id: to } })), onSuccess: done });
  const remove = useMutation({
    // What was deleted is kept with the answer: once the tree reloads, this folder is gone from it.
    mutationFn: async () => ({ ...(await must(api.DELETE("/folders/{folder_id}", { params: { path: { folder_id: id } } }))).data!, id, name: folder?.name ?? "", parent: folder?.parent_id ?? null }),
    onSuccess: ({ ideas: n, id: gone, name: was, parent }) => {
      onDeleted?.(parent); // off the folder that's gone: to the one it was in, or Unsorted
      void done();
      toast(`Deleted “${was}”. ${n ? `Its ${plural(n, "idea")} moved to Unsorted.` : "Nothing was in it."}`, async () => {
        await must(api.POST("/folders/{folder_id}/restore", { params: { path: { folder_id: gone } } })).catch((e: Error) => toast(e.message, undefined, "error"));
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
        <MenuItem onClick={() => (close(), open("new"))}>
          <FolderPlus size={16} strokeWidth={1.75} aria-hidden /> New folder inside
        </MenuItem>
        {folder.can_manage && (
          <>
            <MenuItem onClick={() => (close(), open("rename"))}>
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
  return { items, dialogs, newInside: () => open("new") };
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
