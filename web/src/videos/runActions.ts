import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { uploadFile } from "../api/upload";
import { refreshJobs } from "../jobs/refresh";

type Run = components["schemas"]["DirectorOut"];

/** A run that is going: a start card waiting for Make it runs nothing (S3-02). */
export const runGoing = (run: Run | null | undefined) => run?.status === "running" && run.make_it == null && !run.turns.every((t) => t.status === "needs_owner_approval");

/** What the message box asks for: offline, after a delivery, while the plan is still being written, or any other time. */
export const boxPlaceholder = (online: boolean, delivered: boolean, planning: boolean) =>
  !online ? "You can type; it sends when you’re back" : delivered ? "Say what to change: “warmer light in scene 2”, “swap the B-roll at 0:14”…" : planning ? "Add anything the director should know" : "Tell the director what to change";

/** One press on a video's run. The server answers the run as it now is; what else reads from it (`also`) is read again. */
function useRunPress<V = void>(id: number, fsId: number | null | undefined, post: (v: V) => Promise<{ data?: Run; error?: unknown }>, also: string[], then?: () => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (v: V) => {
      const { data, error } = await post(v);
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["director", id], data);
      if (fsId) void queryClient.invalidateQueries({ queryKey: ["freestyle", fsId] });
      for (const key of also) void queryClient.invalidateQueries({ queryKey: [key, id] });
      then?.();
      return refreshJobs(queryClient);
    },
  });
}

const at = (id: number) => ({ params: { path: { project_id: id } } });

/** Stop the director on a video with no freestyle of its own: it makes no more moves. `then`: once it has stopped. */
export const useStop = (id: number, fsId: number | null | undefined, then?: () => void) => useRunPress(id, fsId, () => api.POST("/projects/{project_id}/director/stop", at(id)), ["idea"], then);

/** The run's other presses, each with no body: Make it again (a new run), Carry on (the same run goes on, up to the rest
 *  of its own price), Start the plan again (a new run with its own start card), and a note to the director with up to
 *  six pictures or clips. None is ever sent twice or again by itself. */
export function useRunPresses(id: number, fsId: number | null | undefined) {
  return {
    again: useRunPress(id, fsId, () => api.POST("/projects/{project_id}/director", at(id)), ["idea"]),
    carry: useRunPress(id, fsId, () => api.POST("/projects/{project_id}/director/carry-on", at(id)), ["idea", "run-progress"]),
    planAgain: useRunPress(id, fsId, () => api.POST("/projects/{project_id}/director/plan-again", at(id)), ["idea"]),
    // A locked line's answer comes at once (S3-14): the cards are read again.
    saveNote: useRunPress(id, fsId, ({ text, files }: { text: string; files: number[] }) => api.POST("/projects/{project_id}/director/messages", { ...at(id), body: { text, ...(files.length ? { files } : {}) } }), ["asks"]),
  };
}

/** The message box's own state (S3): the words, up to six pictures or clips uploaded for this video only, and one send
 *  a press. The box empties at once; a refused note's words and files come back to it. `off`: it can't be used now. */
export function useNoteBox({ busy, off, onSend }: { busy?: boolean; off: boolean; onSend: (text: string, files: number[], done: () => void, refused: () => void) => void }) {
  const [text, setText] = useState("");
  const [files, setFiles] = useState<{ id: number; name: string }[]>([]);
  const [adding, setAdding] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const sending = useRef(false); // one press, one note: a second click before the first returns does nothing
  useEffect(() => {
    if (!busy) sending.current = false;
  }, [busy]);
  const ready = !!text.trim() && !busy && !adding && !off;
  const go = () => {
    if (!ready || sending.current) return;
    sending.current = true;
    const [was, wasFiles] = [text, files];
    setText("");
    setFiles([]);
    onSend(was.trim(), wasFiles.map((f) => f.id), () => (sending.current = false), () => ((sending.current = false), setText(was), setFiles(wasFiles)));
  };
  const add = async (list: FileList | null) => {
    setProblem(null);
    setAdding(true);
    try {
      for (const f of Array.from(list ?? []).slice(0, 6 - files.length)) {
        const stored = await uploadFile(f);
        setFiles((now) => [...now, { id: stored.id, name: f.name }]);
      }
    } catch (e) {
      setProblem((e as Error).message);
    } finally {
      setAdding(false);
    }
  };
  return { text, setText, files, remove: (id: number) => setFiles((now) => now.filter((x) => x.id !== id)), adding, problem, ready, go, add };
}
