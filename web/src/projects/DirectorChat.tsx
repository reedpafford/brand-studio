import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowUp } from "lucide-react";
import { Link } from "react-router-dom";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { Button } from "../components";
import { serverTime } from "../time";

type Item = components["schemas"]["ThreadItem"] & { why?: string }; // `why`: the move's reason, when the server sends it
type Run = components["schemas"]["DirectorOut"];

const SHOWN = 8; // the newest few, with Show earlier

/** The conversation with the director on a video (v4, DECISIONS rule 33): what people asked and what it did, oldest
 *  first, then a box to ask for a change. During a run the director reads it on its next turn; after a delivery or a stop
 *  it's saved, and Make it again (or Start again with this note) makes it: a message never starts a run by itself
 *  (the Producer, 2 Nov). Spending is as ever: inside the budget it goes ahead, past it the owner says. */
export function DirectorChat({ projectId, thread, plain, canAsk, owner, waiting }: { projectId: number; thread: Item[]; plain: (text: string) => string; canAsk: boolean; owner?: boolean; waiting?: string | null }) {
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
      return queryClient.invalidateQueries({ queryKey: ["jobs"] });
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
        <ol className="max-h-[28rem] space-y-3 overflow-y-auto pr-1" aria-label="Conversation with the director">
          {shown.map((t) => {
            const words = t.kind === "move" ? plain(t.text) || "Deciding what to do next." : t.text;
            const when = serverTime(t.at); // a server time without a zone is UTC (time.ts)
            const time = Number.isNaN(when.getTime()) ? "" : ` · ${when.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
            return t.kind === "message" ? (
              <li key={t.id} ref={t.id === last ? end : undefined} className="flex min-w-0 flex-col items-end gap-0.5 text-sm">
                <p className="text-xs text-muted tabular-nums">
                  {t.who}
                  {time}
                </p>
                <p className="max-w-[90%] whitespace-pre-line break-words rounded-lg bg-surface-2 px-3 py-2">{words}</p>
              </li>
            ) : (
              <li key={t.id} ref={t.id === last ? end : undefined} className="flex min-w-0 gap-2.5 text-sm">
                <span aria-hidden className="grid size-6 shrink-0 place-items-center rounded-full bg-accent-soft text-xs font-semibold text-accent-text">D</span>
                <div className="min-w-0 space-y-0.5">
                  <p className="text-xs text-muted tabular-nums">
                    Director{time}
                    {t.status === "running" && " · working"}
                    {t.status === "refused" && " · couldn't do it"}
                  </p>
                  <p className="whitespace-pre-line break-words">{words}</p>
                  {t.why && plain(t.why) && <p className="break-words text-muted">{plain(t.why)}</p>}
                  {t.status === "held" &&
                    (owner ? (
                      <Link to="/approvals" className="text-sm text-accent-text underline-offset-2 hover:underline">
                        See it in Needs you
                      </Link>
                    ) : (
                      <p className="text-muted">Waiting for approval.</p>
                    ))}
                </div>
              </li>
            );
          })}
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
