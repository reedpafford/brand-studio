import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Ellipsis, Folder, Plus } from "lucide-react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { api, must } from "../api/client";
import type { components } from "../api/schema";
import { Button, Dialog, Field, Menu, MenuItem, Panel, useToast } from "../components";
import { errorText as errorClass } from "../ui";
import { useMedia } from "../useMedia";

/** A brand's project (flows OR1). Internally a "folder": the database already calls a video a project. People only see "Project". */
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
const LISTS = ["scripts", "videos", "clip"]; // the lists a project filters

function useRefresh(brandId: number) {
  const queryClient = useQueryClient();
  return () => Promise.all(["folders", "scripts", "videos", "jobs", "project", "script-lib"].map((k) => queryClient.invalidateQueries({ queryKey: k === "folders" ? [k, brandId] : [k] })));
}

/** One project's Rename and Delete (the owner, or whoever made it): Delete moves its items to No project, with Undo. */
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
          {n > 0 ? `Its ${n} item${n === 1 ? "" : "s"} move to No project. Nothing inside is deleted.` : "Nothing is in it."}
        </Dialog>
      )}
    </>
  );
}

/** The brand's projects as a list (the left tab on desktop, a sheet on a phone): All, each project with its count, No project, New project.
 *  Picking one filters Scripts, Videos and Quick clips (?folder=); off those lists it opens Videos. */
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
    const to = LISTS.includes(section ?? "") ? pathname : `/b/${brandId}/videos`;
    const next = new URLSearchParams(LISTS.includes(section ?? "") ? params : undefined);
    if (folder) next.set("folder", folder);
    else next.delete("folder");
    navigate(`${to}${next.size ? `?${next}` : ""}`);
    onPicked?.();
  };
  const row = (key: string, label: string, n: number | null, folder: string | null, menu?: ReactNode) => {
    const on = LISTS.includes(section ?? "") && current === folder;
    return (
      <li key={key} className="flex items-center gap-1">
        <button type="button" aria-current={on ? "true" : undefined} aria-label={n !== null ? `${label} · ${n} item${n === 1 ? "" : "s"}` : undefined} onClick={() => go(folder)} className={`flex min-h-control min-w-0 flex-1 items-center gap-2 rounded-md px-3 text-left ${on ? "bg-surface-2 text-text" : "text-muted hover:bg-surface-2 hover:text-text"}`}>
          <span className="min-w-0 flex-1 truncate">{label}</span>
          {n !== null && <span className="text-xs tabular-nums">{n}</span>}
        </button>
        {menu}
      </li>
    );
  };
  return (
    <section aria-label="Projects" className="space-y-1">
      <ul className="space-y-0.5">
        {row("all", "All", null, null)}
        {folders.data.map((f) => row(String(f.id), f.name, count(f), String(f.id), f.can_manage ? <ProjectMenu folder={f} brandId={brandId} /> : undefined))}
        {row("none", "No project", null, "none")}
      </ul>
      {folders.data.length === 0 && <p className="px-3 text-sm text-muted">No projects yet. Everything works without one.</p>}
      <Button variant="ghost" dense icon={Plus} onClick={() => setNaming("")}>
        New project
      </Button>
      {naming !== null && (
        <Dialog title="New project" cancelLabel="Not now" actionLabel="Make the project" busy={make.isPending} holdReason={!naming.trim() ? "Give it a name" : make.isError ? make.error.message : null} onCancel={() => { setNaming(null); make.reset(); }} onConfirm={() => make.mutate(naming.trim())}>
          <Field label="Name" value={naming} maxLength={80} placeholder="November launch" onChange={(e) => { setNaming(e.target.value); make.reset(); }} />
        </Dialog>
      )}
    </section>
  );
}

/** On a list page where the side list isn't shown (a phone, the icon rail): "Project: All ▾", opening the list in a sheet. */
export function ProjectsChip({ brandId }: { brandId: number }) {
  const folders = useFolders(brandId);
  const folder = useFolderFilter();
  const [open, setOpen] = useState(false);
  const wide = useMedia("(min-width: 1280px)"); // there the side list shows them
  if (!folders.data || wide) return null;
  const name = folder === "none" ? "No project" : folder ? (folders.data.find((f) => String(f.id) === folder)?.name ?? "All") : "All";
  return (
    <>
      <Button variant="secondary" dense icon={Folder} trailing={ChevronDown} aria-haspopup="dialog" onClick={() => setOpen(true)}>
        Project: {name}
      </Button>
      {open && (
        <Panel title="Projects" onClose={() => setOpen(false)}>
          <ProjectsList brandId={brandId} onPicked={() => setOpen(false)} />
        </Panel>
      )}
    </>
  );
}

/** "Project: none ▾" on a script, video or quick clip: pick a project and it moves there, with Undo. */
export function ProjectPicker({ brandId, kind, id, folderId }: { brandId: number; kind: FolderKind; id: number; folderId: number | null | undefined }) {
  const folders = useFolders(brandId);
  const toast = useToast();
  const refresh = useRefresh(brandId);
  const file = useMutation({ mutationFn: (to: number | null) => must(api.POST("/folders/file", { body: { kind, id, folder_id: to } })).then((r) => r.data!) });
  if (!folders.data) return null;
  const nameOf = (fid: number | null | undefined) => (fid == null ? "none" : (folders.data!.find((f) => f.id === fid)?.name ?? "none")); // a deleted project reads as none
  const move = (to: number | null) =>
    file.mutate(to, {
      onSuccess: async ({ was_folder_id }) => {
        await refresh();
        toast(to === null ? "Moved to No project." : `Moved to ${nameOf(to)}.`, () => file.mutate(was_folder_id, { onSuccess: () => void refresh(), onError: (e) => toast(e.message, undefined, "error") }));
      },
      onError: (e) => toast(e.message, undefined, "error"),
    });
  return (
    <Menu
      title="Project"
      trigger={(p) => (
        <Button {...p} variant="ghost" dense icon={Folder} trailing={ChevronDown} busy={file.isPending}>
          Project: {nameOf(folderId)}
        </Button>
      )}
    >
      {(close) => (
        <>
          {folders.data!.map((f) => (
            <MenuItem key={f.id} checked={f.id === folderId} onClick={() => { close(); if (f.id !== folderId) move(f.id); }}>
              {f.name}
            </MenuItem>
          ))}
          <MenuItem checked={folderId == null} onClick={() => { close(); if (folderId != null) move(null); }}>
            No project
          </MenuItem>
          {folders.data!.length === 0 && <p className="px-3 py-2 text-sm text-muted">No projects yet. Make one in the Projects list.</p>}
          {file.isError && <p role="alert" className={`px-3 py-2 ${errorClass}`}>{file.error.message}</p>}
        </>
      )}
    </Menu>
  );
}
