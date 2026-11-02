import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Archive, ChevronDown, Folder, X } from "lucide-react";
import { api, errorText, must } from "../../api/client";
import { Button, Dialog, Menu, MenuItem, useToast } from "../../components";
import { useFolders } from "../../folders/Projects";
import { errorText as errorClass } from "../../ui";
import type { Row } from "./ScriptRow";

const plural = (n: number) => `${n} script${n === 1 ? "" : "s"}`;

/** What can be done to the picked scripts at once, with the endpoints that exist: move them to a project, or archive them
 *  (a script with no video yet goes to Deleted and archived, as its own Delete does). Undo after each. */
export function BulkBar({ brandId, picked, mayArchive, onDone }: { brandId: number; picked: Row[]; mayArchive: boolean; onDone: () => void }) {
  const folders = useFolders(brandId);
  const toast = useToast();
  const queryClient = useQueryClient();
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const refresh = () => Promise.all(["scripts", "folders"].map((k) => queryClient.invalidateQueries({ queryKey: [k] })));
  const n = picked.length;

  const move = async (to: number | null, name: string) => {
    setBusy(true);
    try {
      const was = await Promise.all(picked.map(async (r) => ({ id: r.id, from: (await must(api.POST("/folders/file", { body: { kind: "script", id: r.id, folder_id: to } }))).data!.was_folder_id })));
      await refresh();
      onDone();
      toast(`Moved ${plural(n)} to ${name}.`, async () => {
        await Promise.all(was.map((w) => must(api.POST("/folders/file", { body: { kind: "script", id: w.id, folder_id: w.from } })))).catch((e: Error) => toast(e.message, undefined, "error"));
        await refresh();
      });
    } catch (e) {
      toast((e as Error).message, undefined, "error");
    } finally {
      setBusy(false);
    }
  };

  const archive = async () => {
    setBusy(true);
    setProblem(null);
    const done: Row[] = [];
    for (const r of picked) {
      const { error, response } = await api.DELETE("/scripts/{script_id}", { params: { path: { script_id: r.id } } });
      if (!response.ok) {
        setProblem(`${r.title}: ${errorText(error)}`);
        break;
      }
      done.push(r);
    }
    setBusy(false);
    await refresh();
    if (done.length === 0) return;
    if (done.length === n) setAsking(false);
    onDone();
    toast(`Archived ${plural(done.length)}.`, async () => {
      await Promise.all(done.map((r) => api.POST("/scripts/{script_id}/restore", { params: { path: { script_id: r.id } } })));
      await refresh();
      toast(`Restored ${plural(done.length)}.`);
    });
  };

  const running = picked.some((r) => r.running);
  return (
    <div role="region" aria-label="Selected scripts" className="sticky bottom-[calc(var(--tabbar-h)+var(--actionbar-h)+8px)] z-10 flex flex-wrap items-center gap-2 rounded-lg border border-border bg-surface-2 p-2 shadow-(--shadow-raised) lg:bottom-4">
      <span className="px-2 text-sm font-medium tabular-nums">{n} selected</span>
      {folders.data && (
        <Menu
          title="Move to project"
          trigger={(p) => (
            <Button {...p} variant="secondary" dense icon={Folder} trailing={ChevronDown} busy={busy}>
              Move to project
            </Button>
          )}
        >
          {(close) => (
            <>
              {folders.data!.map((f) => (
                <MenuItem key={f.id} onClick={() => { close(); void move(f.id, f.name); }}>
                  {f.name}
                </MenuItem>
              ))}
              <MenuItem onClick={() => { close(); void move(null, "No project"); }}>No project</MenuItem>
            </>
          )}
        </Menu>
      )}
      <Button variant="secondary" dense icon={Archive} disabled={!mayArchive} reason={mayArchive ? null : "You can archive only your own drafts"} onClick={() => setAsking(true)}>
        Archive
      </Button>
      <Button variant="ghost" dense icon={X} aria-label="Clear the selection" onClick={onDone} />
      {asking && (
        <Dialog title={`Archive ${plural(n)}?`} actionLabel="Archive" danger busy={busy} onCancel={() => { setAsking(false); setProblem(null); }} onConfirm={() => void archive()}>
          They leave the library. Videos made from them stay, with their clips and downloads. A script with no video yet goes to Deleted and archived, where it can be restored.
          {running && " Anything still being made for them stops and isn't brought back."}
          {problem && <p role="alert" className={`mt-2 ${errorClass}`}>Couldn't archive {problem}</p>}
        </Dialog>
      )}
    </div>
  );
}
