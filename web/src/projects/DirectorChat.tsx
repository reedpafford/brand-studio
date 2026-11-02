import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowUp } from "lucide-react";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { Button } from "../components";
import { refreshJobs } from "../jobs/refresh";
import { Item, type Said } from "../freestyle/Thread";

type Run = components["schemas"]["DirectorOut"];

const SHOWN = 8; // the newest few, with Show earlier

/** The conversation with the director on a video (v4, DECISIONS rule 33): what people asked and what it did, oldest
 *  first, then a box to ask for a change. During a run the director reads it on its next turn; after a delivery or a stop
 *  it's saved, and Make it again (or Start again with this note) makes it: a message never starts a run by itself
 *  (the Producer, 2 Nov). Spending is as ever: inside the budget it goes ahead, past it the owner says. */
export function DirectorChat({ projectId, thread, plain, canAsk, owner, waiting }: { projectId: number; thread: Said[]; plain: (text: string) => string; canAsk: boolean; owner?: boolean; waiting?: string | null }) {
  const queryClient = useQueryClient();
  const [text, setText] = useState("");
  const [all, setAll] = useState(false);
  const end = useRef<HTMLLIElement>(null);
  const sending = useRef(false); // one press, one note: a second click before the first returns does nothing
  const send = useMutation({
    mutationFn: async (body: string) => {
      const { data, error } = await api.POST("/projects/{project_id}/director/messages", { params: { path: { project_id: projectId } }, body: { text: body } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSettled: () => {
      sending.current = false;
    },
    onSuccess: (data: Run) => {
      setText("");
      queryClient.setQueryData(["director", projectId], data);
      return refreshJobs(queryClient);
    },
  });
  const last = thread.at(-1)?.id;
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "nearest" }); // keep the newest in view (returns nothing: no cleanup)
  }, [last]);
  const shown = all ? thread : thread.slice(-SHOWN);
  const ask = text.trim();
  return (
    <div className="flex min-h-0 flex-col gap-3">
      {thread.length > shown.length && (
        <Button variant="ghost" dense onClick={() => setAll(true)}>
          Show earlier ({thread.length - shown.length})
        </Button>
      )}
      {thread.length > 0 && (
        <ol className="flex max-h-[28rem] flex-col gap-5 overflow-y-auto pr-1" aria-label="Conversation with the director">
          {shown.map((t) => (
            <Item key={t.id} ref={t.id === last ? end : undefined} t={t} owner={owner} words={t.kind === "move" ? plain(t.text) || "Deciding what to do next." : t.text} why={t.why ? plain(t.why) : undefined} />
          ))}
        </ol>
      )}
      {waiting && <p className="text-sm text-muted" role="status">{waiting}</p>}
      {canAsk && (
        <form
          className="flex items-end gap-2 rounded-lg border border-border-strong bg-surface p-2 focus-within:border-focus"
          onSubmit={(e) => {
            e.preventDefault();
            if (!ask || sending.current) return;
            sending.current = true;
            send.mutate(ask);
          }}
        >
          <label htmlFor={`ask-${projectId}`} className="sr-only">
            Tell the director what to change
          </label>
          <textarea
            id={`ask-${projectId}`}
            rows={2}
            maxLength={2000}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              if (send.isError) send.reset();
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                e.currentTarget.form?.requestSubmit();
              }
            }}
            placeholder="Tell the director what to change"
            className="min-h-10 flex-1 resize-none bg-transparent px-1 py-1 text-base outline-none placeholder:text-faint"
          />
          <Button type="submit" variant="secondary" dense icon={ArrowUp} busy={send.isPending} disabled={!ask || send.isPending} aria-label="Send to the director" />
        </form>
      )}
      {send.isError && (
        <p role="alert" className="text-sm text-danger">
          {send.error.message /* the server's own words, e.g. "Too many messages; wait a moment" */}
        </p>
      )}
    </div>
  );
}
