import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowUp } from "lucide-react";
import { Link } from "react-router-dom";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { Button } from "../components";
import { useToast } from "../toast";

type Item = components["schemas"]["ThreadItem"] & { why?: string }; // `why`: the move's reason, when the server sends it
type Run = components["schemas"]["DirectorOut"];

const SHOWN = 8; // the newest few, with Show earlier

/** The conversation with the director on a video (v4, DECISIONS rule 33): what people asked and what it did, oldest
 *  first, then a box to ask for a change. A message after a delivery or a stop starts a revision run; during a run,
 *  the director reads it on its next turn. Spending is as ever: inside the budget it goes ahead, past it the owner says. */
export function DirectorChat({ projectId, thread, plain, canAsk }: { projectId: number; thread: Item[]; plain: (text: string) => string; canAsk: boolean }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [text, setText] = useState("");
  const [all, setAll] = useState(false);
  const end = useRef<HTMLLIElement>(null);
  const send = useMutation({
    mutationFn: async (body: string) => {
      const { data, error } = await api.POST("/projects/{project_id}/director/messages", { params: { path: { project_id: projectId } }, body: { text: body } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data: Run) => {
      setText("");
      queryClient.setQueryData(["director", projectId], data);
      return queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (e: Error) => toast(e.message, undefined, "error"),
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
            const when = new Date(t.at);
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
                  {t.status === "held" && (
                    <Link to="/approvals" className="text-sm text-accent-text underline-offset-2 hover:underline">
                      See it in Needs you
                    </Link>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
      {canAsk && (
        <form
          className="flex items-end gap-2 rounded-lg border border-border-strong bg-surface p-2 focus-within:border-focus"
          onSubmit={(e) => {
            e.preventDefault();
            if (ask && !send.isPending) send.mutate(ask);
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
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                e.currentTarget.form?.requestSubmit();
              }
            }}
            placeholder="Tell the director what to change"
            className="min-h-10 flex-1 resize-none bg-transparent px-1 py-1 text-base outline-none placeholder:text-faint"
          />
          <Button type="submit" variant="secondary" dense icon={ArrowUp} busy={send.isPending} disabled={!ask} aria-label="Send to the director" />
        </form>
      )}
    </div>
  );
}
