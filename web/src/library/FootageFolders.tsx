import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRightLeft, ChevronRight, Ellipsis, Folder, FolderPlus, Inbox, Pencil, Trash2 } from "lucide-react";
import { api, must } from "../api/client";
import type { components } from "../api/schema";
import { Button, Dialog, Field, Menu, MenuItem, useToast } from "../components";
import type { Footage } from "./FootageTab";

/** The Footage tab's folders (Reed, 10 Nov): the app's folders, in a tree of the footage's own, nested as in his Drive. */
export type FootageFolder = components["schemas"]["FolderOut"];
type Place = { id: number | null; name: string; depth: number };

export function useFootageFolders(brandId: number) {
  return useQuery({
    queryKey: ["footage", brandId, "folders"],
    queryFn: async () => (await must(api.GET("/brands/{brand_id}/folders", { params: { path: { brand_id: brandId }, query: { footage: true } } }))).data!,
    enabled: brandId > 0,
  });
}

/** Where a folder is, from the top: its folders in order. */
export function trail(rows: FootageFolder[], id: number | null): FootageFolder[] {
  const found = rows.find((f) => f.id === id);
  return found ? [...trail(rows, found.parent_id ?? null), found] : [];
}

/** Every place under `parent`, each folder followed by the folders inside it. */
function places(rows: FootageFolder[], parent: number | null = null, depth = 1): Place[] {
  return rows.filter((f) => (f.parent_id ?? null) === parent).flatMap((f) => [{ id: f.id, name: f.name, depth }, ...places(rows, f.id, depth + 1)]);
}

/** The folder and every folder inside it. */
const inside = (rows: FootageFolder[], id: number) => new Set([id, ...places(rows, id).map((p) => p.id!)]);
const clips = (n: number) => `${n} clip${n === 1 ? "" : "s"}`;
const countIn = (footage: Footage[], ids: Set<number>) => footage.filter((c) => c.folder_id != null && ids.has(c.folder_id)).length;
const useRefresh = (brandId: number) => {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["footage", brandId] });
};

/** All footage › Product shots › Close-ups: each a press back up. */
export function Crumbs({ rows, at, open }: { rows: FootageFolder[]; at: number | null; open: (id: number | null) => void }) {
  const path = trail(rows, at);
  const crumb = "inline-flex min-h-control items-center rounded-md px-2 text-sm hover:bg-surface-2 lg:min-h-control-dense";
  return (
    <nav aria-label="Folders" className="flex min-w-0 flex-wrap items-center gap-0.5">
      <button type="button" onClick={() => open(null)} aria-current={at === null ? "page" : undefined} className={`${crumb} ${at === null ? "font-semibold text-text" : "text-muted"}`}>
        All footage
      </button>
      {path.map((f, i) => (
        <span key={f.id} className="inline-flex min-w-0 items-center gap-0.5">
          <ChevronRight size={14} strokeWidth={1.75} aria-hidden className="shrink-0 text-muted" />
          <button type="button" onClick={() => open(f.id)} aria-current={i === path.length - 1 ? "page" : undefined} className={`${crumb} min-w-0 ${i === path.length - 1 ? "font-semibold text-text" : "text-muted"}`}>
            <span className="truncate">{f.name}</span>
          </button>
        </span>
      ))}
    </nav>
  );
}

/** The folders inside the open one, each with its clips counted at any depth. */
export function SubFolders({ rows, footage, at, open }: { rows: FootageFolder[]; footage: Footage[]; at: number | null; open: (id: number) => void }) {
  const here = rows.filter((f) => (f.parent_id ?? null) === at);
  if (!here.length) return null;
  return (
    <ul aria-label="Folders here" className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
      {here.map((f) => (
        <li key={f.id}>
          <button type="button" onClick={() => open(f.id)} className="flex min-h-control w-full items-center gap-2.5 rounded-lg border border-border bg-surface px-3 py-2.5 text-left transition-colors duration-(--dur-fast) hover:bg-surface-2">
            <Folder size={16} strokeWidth={1.75} aria-hidden className="shrink-0 text-muted" />
            <span className="min-w-0 flex-1 truncate text-sm font-medium">{f.name}</span>
            <span className="shrink-0 text-xs tabular-nums text-muted">{clips(countIn(footage, inside(rows, f.id)))}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

/** Pick a place: the top, or a folder (never one of `not`). */
function Picker({ rows, value, not, onPick }: { rows: FootageFolder[]; value: number | null; not?: Set<number>; onPick: (id: number | null) => void }) {
  const all = [{ id: null, name: "All footage (the top)", depth: 0 } as Place, ...places(rows)].filter((p) => p.id === null || !not?.has(p.id));
  return (
    <div role="radiogroup" aria-label="Move to" className="-mx-2 max-h-80 overflow-y-auto">
      {all.map((p) => (
        <button key={p.id ?? "top"} type="button" role="radio" aria-checked={value === p.id} onClick={() => onPick(p.id)} style={{ paddingLeft: 8 + p.depth * 16 }} className={`flex min-h-control w-full items-center gap-2 rounded-md pr-2 text-left text-sm text-text lg:min-h-control-dense ${value === p.id ? "bg-surface-2 font-medium" : "hover:bg-surface-2"}`}>
          {p.id === null ? <Inbox size={14} strokeWidth={1.75} aria-hidden /> : <Folder size={14} strokeWidth={1.75} aria-hidden />}
          <span className="truncate">{p.name}</span>
        </button>
      ))}
    </div>
  );
}

/** A clip's "Move to…": into another folder, with Undo. */
export function MoveClip({ brandId, clip, rows, onClose }: { brandId: number; clip: Footage; rows: FootageFolder[]; onClose: () => void }) {
  const [to, setTo] = useState<number | null>(clip.folder_id ?? null);
  const refresh = useRefresh(brandId);
  const toast = useToast();
  const file = (folder: number | null) => must(api.POST("/folders/file", { body: { kind: "footage", ids: [clip.id], folder_id: folder } })).then((r) => r.data!);
  const move = useMutation({
    mutationFn: () => file(to),
    onSuccess: ({ was }) => {
      onClose();
      void refresh();
      const where = trail(rows, to).map((f) => f.name).join("/") || "All footage";
      toast(`Moved to ${where}.`, () => void file(was[0]?.folder_id ?? null).then(refresh, (e: Error) => toast(e.message, undefined, "error")));
    },
  });
  return (
    <Dialog title="Move the clip to…" cancelLabel="Not now" actionLabel="Move" busy={move.isPending} holdReason={to === (clip.folder_id ?? null) ? "Pick another folder" : (move.error?.message ?? null)} onCancel={onClose} onConfirm={() => move.mutate()}>
      <Picker rows={rows} value={to} onPick={(id) => (setTo(id), move.reset())} />
    </Dialog>
  );
}

type Asking = "new" | "rename" | "move" | "delete" | null;

/** New folder (inside the open one), and the open folder's Rename, Move to… and Delete folder…, with Undo after a delete.
 *  A deleted folder's clips go up a level; the folders inside it go with it until Undo. */
export function FolderActions({ brandId, rows, footage, at, open }: { brandId: number; rows: FootageFolder[]; footage: Footage[]; at: number | null; open: (id: number | null) => void }) {
  const [asking, setAsking] = useState<Asking>(null);
  const [name, setName] = useState("");
  const [to, setTo] = useState<number | null>(null);
  const folder = rows.find((f) => f.id === at);
  const refresh = useRefresh(brandId);
  const toast = useToast();
  const id = { params: { path: { folder_id: at ?? 0 } } };
  const done = () => (setAsking(null), refresh());
  const make = useMutation({ mutationFn: () => must(api.POST("/brands/{brand_id}/folders", { params: { path: { brand_id: brandId } }, body: { name: name.trim(), parent_id: at, footage: true } })), onSuccess: done });
  const rename = useMutation({ mutationFn: () => must(api.PATCH("/folders/{folder_id}", { ...id, body: { name: name.trim() } })), onSuccess: done });
  const move = useMutation({ mutationFn: () => must(api.PATCH("/folders/{folder_id}", { ...id, body: { parent_id: to } })), onSuccess: done });
  const gone = folder ? inside(rows, folder.id) : new Set<number>();
  const count = countIn(footage, gone);
  const up = folder ? (trail(rows, folder.parent_id ?? null).at(-1)?.name ?? "All footage") : "";
  const remove = useMutation({
    mutationFn: () => must(api.DELETE("/folders/{folder_id}", id)),
    onSuccess: () => {
      const was = folder!;
      open(was.parent_id ?? null);
      void done();
      const undo = () => void must(api.POST("/folders/{folder_id}/restore", { params: { path: { folder_id: was.id } } })).then(refresh, (e: Error) => toast(e.message, undefined, "error"));
      toast(`Deleted “${was.name}”. ${count ? `Its ${clips(count)} moved up to ${up}.` : "Nothing was in it."}`, undo);
    },
  });
  const ask = (what: Asking) => {
    setName(what === "rename" ? (folder?.name ?? "") : "");
    setTo(folder?.parent_id ?? null);
    [make, rename, move, remove].forEach((m) => m.reset());
    setAsking(what);
  };
  return (
    <div className="flex shrink-0 items-center gap-1">
      <Button variant="secondary" icon={FolderPlus} onClick={() => ask("new")}>
        New folder
      </Button>
      {folder?.can_manage && (
        <Menu
          title={folder.name}
          align="right"
          popover
          trigger={(p) => (
            <button type="button" {...p} aria-label={`More for ${folder.name}`} className="grid size-control shrink-0 place-items-center rounded-md text-muted hover:bg-surface-2 lg:size-8">
              <Ellipsis size={16} strokeWidth={1.75} aria-hidden />
            </button>
          )}
        >
          {(close) => (
            <>
              <MenuItem onClick={() => (close(), ask("rename"))}>
                <Pencil size={16} strokeWidth={1.75} aria-hidden /> Rename
              </MenuItem>
              <MenuItem onClick={() => (close(), ask("move"))}>
                <ArrowRightLeft size={16} strokeWidth={1.75} aria-hidden /> Move to…
              </MenuItem>
              <MenuItem danger onClick={() => (close(), ask("delete"))}>
                <Trash2 size={16} strokeWidth={1.75} aria-hidden /> Delete folder…
              </MenuItem>
            </>
          )}
        </Menu>
      )}
      {(asking === "new" || asking === "rename") && (
        <Dialog
          title={asking === "new" ? (folder ? `New folder inside ${folder.name}` : "New folder") : `Rename ${folder?.name}`}
          cancelLabel="Not now"
          actionLabel={asking === "new" ? "Make the folder" : "Rename"}
          busy={make.isPending || rename.isPending}
          holdReason={!name.trim() ? "Give it a name" : ((asking === "new" ? make : rename).error?.message ?? null)}
          onCancel={() => setAsking(null)}
          onConfirm={() => (asking === "new" ? make : rename).mutate()}
        >
          <Field label="Name" value={name} maxLength={120} autoFocus placeholder="Product shots" onChange={(e) => (setName(e.target.value), make.reset(), rename.reset())} />
        </Dialog>
      )}
      {asking === "move" && folder && (
        <Dialog title={`Move ${folder.name} to…`} cancelLabel="Not now" actionLabel="Move" busy={move.isPending} holdReason={to === (folder.parent_id ?? null) ? "Pick another place" : (move.error?.message ?? null)} onCancel={() => setAsking(null)} onConfirm={() => move.mutate()}>
          <Picker rows={rows} value={to} not={gone} onPick={(p) => (setTo(p), move.reset())} />
        </Dialog>
      )}
      {asking === "delete" && folder && (
        <Dialog title={`Delete ${folder.name}?`} cancelLabel="Keep it" actionLabel="Delete folder" danger busy={remove.isPending} holdReason={remove.error?.message ?? null} onCancel={() => setAsking(null)} onConfirm={() => remove.mutate()}>
          {count ? `Its ${clips(count)} move up to ${up}${gone.size > 1 ? ", and the folders inside it go with it" : ""}. No clip is deleted, and Undo brings it all back.` : "Nothing is in it."}
        </Dialog>
      )}
    </div>
  );
}
