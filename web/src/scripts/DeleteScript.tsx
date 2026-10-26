import { useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Ellipsis, Trash2 } from "lucide-react";
import { api, errorText } from "../api/client";
import { useMe } from "../auth/useMe";
import { useJobs } from "../clip/History";
import { Dialog, Menu, MenuItem } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";

type Target = { id: number; title: string; made: boolean };
type Who = { created_by_id: number | null; published: boolean; title: string; id: number; versions: { project_id?: number | null }[] };

/** Reed: any script. An editor: only their own unpublished drafts. Anyone else: not offered. */
export function useMayDelete() {
  const { data: me } = useMe();
  return (s: Pick<Who, "created_by_id" | "published">) => me?.role === "owner" || (!!me && s.created_by_id === me.id && !s.published);
}

export const toTarget = (s: Who): Target => ({ id: s.id, title: s.title, made: s.versions.some((v) => !!v.project_id) });

/** Delete (or archive, when a video was made) with a confirm first and Undo after. Render `dialog` somewhere on the page. */
export function useDeleteScript(onDeleted?: () => void) {
  const [target, setTarget] = useState<Target | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const toast = useToast();
  const jobs = useJobs();
  // Something still being made for the script itself (its words, a reel read, variations, Directions, the plan). A video made from it carries on, so its jobs don't count.
  const running = !!target && (jobs.data ?? []).some((j) => j.script_id === target.id && !j.project_id && ["queued", "running", "needs_owner_approval"].includes(j.status));
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["scripts"] });
  const close = () => (setTarget(null), setProblem(null));

  const undo = (t: Target) => async () => {
    const { response } = await api.POST("/scripts/{script_id}/restore", { params: { path: { script_id: t.id } } });
    if (!response.ok) return toast(`Couldn't bring "${t.title}" back.`, undefined, "error");
    await refresh();
    toast(`Restored "${t.title}".`);
  };
  const confirm = async () => {
    if (!target) return;
    setBusy(true);
    setProblem(null);
    const { error, response } = await api.DELETE("/scripts/{script_id}", { params: { path: { script_id: target.id } } });
    setBusy(false);
    if (!response.ok) return setProblem(errorText(error));
    const t = target;
    close();
    await refresh();
    toast(`${t.made ? "Archived" : "Deleted"} "${t.title}".`, undo(t));
    onDeleted?.();
  };
  const dialog = target && (
    <Dialog title={target.made ? `Archive "${target.title}"?` : `Delete "${target.title}"?`} actionLabel={target.made ? "Archive" : "Delete"} danger busy={busy} onCancel={close} onConfirm={() => void confirm()}>
      {target.made ? "It leaves the library. The videos made from it stay, with their clips and downloads." : "Its versions and cast go too."}
      {running && " Anything still being made for this script stops and isn't brought back."}
      {problem && <p role="alert" className={`mt-2 ${errorClass}`}>Couldn't do that. Nothing changed. {problem}</p>}
    </Dialog>
  );
  return { ask: setTarget, dialog };
}

/** The "..." menu with Delete script in it: on a script's page, and on a library row (icon only, 36px desktop, 44px phone). */
export function ScriptMenu({ title, onDelete, children }: { title: string; onDelete: () => void; children?: ReactNode }) {
  return (
    <Menu
      title={`More for ${title}`}
      align="right"
      trigger={(p) => (
        <button type="button" {...p} aria-label={`More for ${title}`} className="grid size-control place-items-center rounded-md text-muted hover:bg-surface-2 lg:size-9">
          <Ellipsis size={20} strokeWidth={1.75} aria-hidden />
        </button>
      )}
    >
      {(close) => (
        <>
          {children}
          <MenuItem
            danger
            onClick={() => {
              close();
              onDelete();
            }}
          >
            <Trash2 size={20} strokeWidth={1.75} aria-hidden />
            Delete script
          </MenuItem>
        </>
      )}
    </Menu>
  );
}
