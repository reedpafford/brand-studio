import { useState, type ReactNode } from "react";
import { pickClass } from "../scripts/ScriptFrame";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Ellipsis, Folder, Plus } from "lucide-react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { api, must } from "../api/client";
import type { components } from "../api/schema";
import { Button, Dialog, Field, Menu, MenuItem, Panel, useToast } from "../components";
import { errorText as errorClass } from "../ui";

/** A brand's folder (flows OR1; v5 called it a project). The same folders as the v6 tree, so people see "Folder" and "Unsorted". */
export type FolderOut = components["schemas"]["FolderOut"];
export type FolderKind = "script" | "video" | "clip";

/** The brand's projects, by name, with what's in each; null where the server doesn't offer them yet (then nothing shows). */
export function useFolders(brandId: number) {
  return useQuery({
    enabled: brandId > 0,
    queryKey: ["folders", brandId],
    queryFn: async () => (await api.GET("/brands/{brand_id}/folders", { params: { path: { brand_id: brandId } } })).data ?? null, // none where the server doesn't offer them
    retry: false,
  });
}

/** The ?folder= filter a list asks the server for: a project's id, "none" for No project, or nothing for all. */
export function useFolderFilter(): string | null {
  const [params] = useSearchParams();
  return params.get("folder");
}
/** Spread into a list's query (/scripts, /projects, /jobs take ?folder=<id>|none). */
export const folderQuery = (folder: string | null) => (folder ? { folder } : {});

const count = (f: FolderOut) => f.items.scripts + f.items.videos + f.items.clips;
const LISTS = ["scripts"]; // the list a project filters (a brand's videos are its folders now, v6 S1)
/** The folders as the tree nests them, each with its depth: the lists indent the ones inside (v6). */
export function nested(folders: FolderOut[], parent: number | null = null, depth = 0): { f: FolderOut; depth: number }[] {
  return folders.filter((f) => (f.parent_id ?? null) === parent).flatMap((f) => [{ f, depth }, ...nested(folders, f.id, depth + 1)]);
}

function useRefresh(brandId: number) {
  const queryClient = useQueryClient();
  return () => Promise.all(["folders", "scripts", "videos", "jobs", "project", "script-lib"].map((k) => queryClient.invalidateQueries({ queryKey: k === "folders" ? [k, brandId] : [k] })));
}

/** One project's Rename and Delete (the owner, or whoever made it): Delete moves its items to Unsorted, with Undo. */
function ProjectMenu({ folder, brandId }: { folder: FolderOut; brandId: number }) {
  const toast = useToast();
  const refresh = useRefresh(brandId);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const rename = useMutation({ mutationFn: (name: string) => must(api.PATCH("/folders/{folder_id}", { params: { path: { folder_id: folder.id } }, body: { name } })), onSuccess: () => { setRenaming(null); return refresh(); } });
  const remove = useMutation({
    mutationFn: () => must(api.DELETE("/folders/{folder_id}", { params: { path: { folder_id: folder.id } } })),
    onSuccess: async () => {
      setDeleting(false);
      await refresh();
      toast(`Deleted ${folder.name}.`, async () => {
        await must(api.POST("/folders/{folder_id}/restore", { params: { path: { folder_id: folder.id } } })).catch((e: Error) => toast(e.message, undefined, "error")); // a live project took the name meanwhile
        await refresh();
      });
    },
  });
  const n = count(folder);
  return (
    <>
      <Menu
        title={folder.name}
        align="right"
        trigger={(p) => (
          <button type="button" {...p} aria-label={`More for ${folder.name}`} className="grid size-control shrink-0 place-items-center rounded-md text-muted hover:bg-surface-2">
            <Ellipsis size={20} strokeWidth={1.75} aria-hidden />
          </button>
        )}
      >
        {(close) => (
          <>
            <MenuItem onClick={() => { close(); setRenaming(folder.name); }}>Rename</MenuItem>
            <MenuItem danger onClick={() => { close(); setDeleting(true); }}>Delete</MenuItem>
          </>
        )}
      </Menu>
      {renaming !== null && (
        <Dialog title={`Rename ${folder.name}`} cancelLabel="Not now" actionLabel="Rename" busy={rename.isPending} holdReason={!renaming.trim() ? "Give it a name" : rename.isError ? rename.error.message : null} onCancel={() => { setRenaming(null); rename.reset(); }} onConfirm={() => rename.mutate(renaming.trim())}>
          <Field label="Name" value={renaming} maxLength={80} onChange={(e) => { setRenaming(e.target.value); rename.reset(); }} />
        </Dialog>
      )}
      {deleting && (
        <Dialog title={`Delete ${folder.name}?`} cancelLabel="Keep it" actionLabel="Delete" danger busy={remove.isPending} holdReason={remove.isError ? remove.error.message : null} onCancel={() => setDeleting(false)} onConfirm={() => remove.mutate()}>
          {n > 0 ? `Its ${n} item${n === 1 ? " moves" : "s move"} to Unsorted. Nothing inside is deleted.` : "Nothing is in it."}
        </Dialog>
      )}
    </>
  );
}

/** The brand's projects as a list (the left tab on desktop, a sheet on a phone): All, each project with its count, No project, New project.
 *  Picking one filters Scripts, Videos and Media (?folder=); off those lists it opens Videos. */
export function ProjectsList({ brandId, onPicked }: { brandId: number; onPicked?: () => void }) {
  const folders = useFolders(brandId);
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [params] = useSearchParams();
  const refresh = useRefresh(brandId);
  const [naming, setNaming] = useState<string | null>(null);
  const make = useMutation({ mutationFn: (name: string) => must(api.POST("/brands/{brand_id}/folders", { params: { path: { brand_id: brandId } }, body: { name } })), onSuccess: () => { setNaming(null); return refresh(); } });
  if (!folders.data) return null; // the server doesn't offer projects yet
  const current = params.get("folder");
  const section = /^\/b\/\d+\/([^/]+)$/.exec(pathname)?.[1];
  const go = (folder: string | null) => {
    const to = LISTS.includes(section ?? "") ? pathname : `/b/${brandId}/scripts`;
    const next = new URLSearchParams(LISTS.includes(section ?? "") ? params : undefined);
    if (folder) next.set("folder", folder);
    else next.delete("folder");
    navigate(`${to}${next.size ? `?${next}` : ""}`);
    onPicked?.();
  };
  const row = (key: string, label: string, n: number | null, folder: string | null, menu?: ReactNode, depth = 0) => {
    const on = LISTS.includes(section ?? "") && current === folder;
    return (
      <li key={key} className="flex items-center gap-1">
        <button type="button" aria-current={on ? "true" : undefined} aria-label={n !== null ? `${label} · ${n} item${n === 1 ? "" : "s"}` : undefined} onClick={() => go(folder)} style={depth ? { paddingLeft: 12 + depth * 16 } : undefined} className={`flex min-h-control min-w-0 flex-1 items-center gap-2 rounded-md px-3 text-left ${on ? "bg-surface-2 text-text" : "text-muted hover:bg-surface-2 hover:text-text"}`}>
          <span className="min-w-0 flex-1 truncate">{label}</span>
          {n !== null && <span className="text-xs tabular-nums">{n}</span>}
        </button>
        {menu}
      </li>
    );
  };
  return (
    <section aria-label="Folders" className="space-y-1">
      <ul className="space-y-0.5">
        {row("all", "All", null, null)}
        {nested(folders.data).map(({ f, depth }) => row(String(f.id), f.name, count(f), String(f.id), f.can_manage ? <ProjectMenu folder={f} brandId={brandId} /> : undefined, depth))}
        {row("none", "Unsorted", null, "none")}
      </ul>
      {folders.data.length === 0 && <p className="px-3 text-sm text-muted">No folders yet. Everything works without one.</p>}
      <Button variant="ghost" dense icon={Plus} onClick={() => setNaming("")}>
        New folder
      </Button>
      {naming !== null && (
        <Dialog title="New folder" cancelLabel="Not now" actionLabel="Make the folder" busy={make.isPending} holdReason={!naming.trim() ? "Give it a name" : make.isError ? make.error.message : null} onCancel={() => { setNaming(null); make.reset(); }} onConfirm={() => make.mutate(naming.trim())}>
          <Field label="Name" value={naming} maxLength={80} placeholder="November launch" onChange={(e) => { setNaming(e.target.value); make.reset(); }} />
        </Dialog>
      )}
    </section>
  );
}

/** On a list page: "Folder: All ▾", opening the brand's folders (pick, New folder, Rename, Delete) in a panel.
 *  At every width since the rail lost its Projects list (Reed, 2 Nov: nav A). */
export function ProjectsChip({ brandId, plain }: { brandId: number; /** The Scripts band's quiet text press, "Folder ▾", like Group and Sort (v5 C_Scripts). */ plain?: boolean }) {
  const folders = useFolders(brandId);
  const folder = useFolderFilter();
  const [open, setOpen] = useState(false);
  if (!folders.data) return null;
  const name = folder === "none" ? "Unsorted" : folder ? (folders.data.find((f) => String(f.id) === folder)?.name ?? "All") : "All";
  return (
    <>
      {plain ? (
        <Button variant="ghost" dense aria-haspopup="dialog" aria-label={`Folder: ${name}`} className="text-muted!" onClick={() => setOpen(true)}>
          {folder ? `Folder: ${name}` : "Folder"} ▾
        </Button>
      ) : (
        <Button variant="secondary" dense icon={Folder} trailing={ChevronDown} aria-haspopup="dialog" onClick={() => setOpen(true)}>
          Folder: {name}
        </Button>
      )}
      {open && (
        <Panel title="Folders" onClose={() => setOpen(false)}>
          <ProjectsList brandId={brandId} onPicked={() => setOpen(false)} />
        </Panel>
      )}
    </>
  );
}

/** "Folder: Unsorted ▾" on a script, video or quick clip: pick a folder and it moves there, with Undo. */
export function ProjectPicker({ brandId, kind, id, folderId, pick }: { brandId: number; kind: FolderKind; id: number; folderId: number | null | undefined; /** v5's settings row: "Project None ▾" */ pick?: boolean }) {
  const folders = useFolders(brandId);
  const toast = useToast();
  const refresh = useRefresh(brandId);
  const file = useMutation({ mutationFn: (to: number | null) => must(api.POST("/folders/file", { body: { kind, ids: [id], folder_id: to } })).then((r) => r.data!) });
  const [naming, setNaming] = useState<string | null>(null);
  // New project… here makes the project and files this item into it, so nobody has to leave the page for the Projects list.
  const make = useMutation({
    mutationFn: (name: string) => must(api.POST("/brands/{brand_id}/folders", { params: { path: { brand_id: brandId } }, body: { name } })).then((r) => r.data!),
    onSuccess: (made) => { setNaming(null); move(made.id, made); },
  });
  if (!folders.data) return null;
  const nameOf = (fid: number | null | undefined) => (fid == null ? "Unsorted" : (folders.data!.find((f) => f.id === fid)?.name ?? "Unsorted")); // a deleted folder reads as Unsorted
  // `made`: the project New project just made for this item. Undo then deletes it again, unless something else was filed there since.
  const move = (to: number | null, made?: { id: number; name: string }) =>
    file.mutate(to, {
      onSuccess: async ({ was: [{ folder_id: was_folder_id }] }) => {
        await refresh();
        const undo = async () => {
          await file.mutateAsync(was_folder_id);
          if (made) {
            const now = (await api.GET("/brands/{brand_id}/folders", { params: { path: { brand_id: brandId } } })).data?.find((f) => f.id === made.id);
            if (now && count(now) === 0) await must(api.DELETE("/folders/{folder_id}", { params: { path: { folder_id: made.id } } }));
          }
          await refresh();
        };
        const said = made ? `Made ${made.name} and moved this there.` : to === null ? "Moved to Unsorted." : `Moved to ${nameOf(to)}.`;
        toast(said, () => void undo().catch((e: Error) => toast(e.message, undefined, "error")));
      },
      onError: (e) => toast(e.message, undefined, "error"),
    });
  return (
    <>
      <Menu
        title="Folder"
        trigger={(p) => (
          <Button {...p} variant="ghost" dense icon={pick ? undefined : Folder} trailing={ChevronDown} busy={file.isPending} aria-label={pick ? `Folder: ${nameOf(folderId)}` : undefined} className={`max-w-full whitespace-nowrap ${pick ? pickClass : ""}`}>
            {pick ? (
              <>
                <span className="text-muted">Folder</span> {nameOf(folderId)}
              </>
            ) : (
              <>Folder: {nameOf(folderId)}</>
            )}
          </Button>
        )}
      >
        {(close) => (
          <>
            {nested(folders.data!).map(({ f, depth }) => (
              <MenuItem key={f.id} checked={f.id === folderId} onClick={() => { close(); if (f.id !== folderId) move(f.id); }}>
                <span style={{ paddingLeft: depth * 16 }}>{f.name}</span>
              </MenuItem>
            ))}
            <MenuItem checked={folderId == null} onClick={() => { close(); if (folderId != null) move(null); }}>
              Unsorted
            </MenuItem>
            {folders.data!.length === 0 && <p className="px-3 py-2 text-sm text-muted">No folders yet. Everything works without one.</p>}
            <MenuItem onClick={() => { close(); setNaming(""); }}>
              <Plus size={20} strokeWidth={1.75} aria-hidden />
              New folder
            </MenuItem>
            {file.isError && <p role="alert" className={`px-3 py-2 ${errorClass}`}>{file.error.message}</p>}
          </>
        )}
      </Menu>
      {naming !== null && (
        <Dialog title="New folder" cancelLabel="Not now" actionLabel="Make it and move this there" busy={make.isPending || file.isPending} holdReason={!naming.trim() ? "Give it a name" : make.isError ? make.error.message : null} onCancel={() => { setNaming(null); make.reset(); }} onConfirm={() => make.mutate(naming.trim())}>
          <Field label="Name" value={naming} maxLength={80} placeholder="November launch" onChange={(e) => { setNaming(e.target.value); make.reset(); }} />
        </Dialog>
      )}
    </>
  );
}
