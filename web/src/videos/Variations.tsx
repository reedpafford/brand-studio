import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, must, polled } from "../api/client";
import { Dialog, TextArea } from "../components";
import { useRefreshIdeas } from "../folders/ideas";

const path = (projectId: number) => ({ params: { path: { project_id: projectId } } });

function Pick<T extends string | number>({ label, value, onPick, options }: { label: string; value: T; onPick: (v: T) => void; options: [T, string][] }) {
  return (
    <div role="radiogroup" aria-label={label} className="flex gap-0.5 rounded-md bg-surface-2 p-0.5">
      {options.map(([v, words]) => (
        <button key={String(v)} type="button" role="radio" aria-checked={value === v} onClick={() => onPick(v)} className={`flex h-control min-w-0 flex-1 items-center justify-center rounded-[5px] text-sm font-medium ${value === v ? "bg-surface text-text shadow-[0_1px_2px_rgb(28_27_25/0.06)]" : "text-muted"}`}>
          {words}
        </button>
      ))}
    </div>
  );
}

/** Make variations (Runway #2): on a finished video, 2 or 3 new videos with another hook or ending, the cast, look and every
 *  other clip kept. The director writes the ideas in one go; each lands in this folder as "<title> · variation A", waiting
 *  on its own card (its price, only the clips it changes) before anything is made. */
export function VariationsDialog({ brandId, projectId, onClose }: { brandId: number; projectId: number; onClose: () => void }) {
  const [count, setCount] = useState<2 | 3>(3);
  const [part, setPart] = useState<"hook" | "ending">("hook");
  const [note, setNote] = useState("");
  const [asked, setAsked] = useState(false);
  const refresh = useRefreshIdeas();
  const read = useQuery({
    queryKey: ["variations", projectId],
    refetchInterval: (q) => (q.state.data?.state === "writing" ? 2_000 : false),
    queryFn: () => polled(api.GET("/projects/{project_id}/variations", path(projectId)), null),
  });
  const make = useMutation({
    mutationFn: () => must(api.POST("/projects/{project_id}/variations", { ...path(projectId), body: { count, part, note } })),
    onSuccess: () => (setAsked(true), void read.refetch()),
  });
  const out = read.data;
  const done = asked && out?.state !== "writing";
  const shown = useRef(false);
  useEffect(() => {
    if (done && out?.state === "done" && !shown.current) {
      shown.current = true;
      void refresh(); // the folder shows them at once
    }
  });
  if (asked)
    return (
      <Dialog title="Variations" cancelLabel="Close" actionLabel="Done" onCancel={onClose} onConfirm={onClose}>
        {!done ? (
          <p role="status">{`The director is writing ${count} ideas for ${part === "hook" ? "the hook" : "the ending"}…`}</p>
        ) : out?.state === "done" ? (
          <>
            <p>Each waits on its own card, with its price, before anything is made:</p>
            <ul className="mt-2 space-y-1">
              {(out.videos ?? []).map((v) => (
                <li key={v.id}>
                  <Link to={`/b/${brandId}/videos/${v.id}`} onClick={onClose} className="inline-flex min-h-control items-center font-medium text-accent-text underline-offset-2 hover:underline lg:min-h-0">
                    {v.title}
                  </Link>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p role="alert">None of the ideas kept the rest of the video, so nothing was made. Try again, or say more in the note.</p>
        )}
      </Dialog>
    );
  return (
    <Dialog title="Make variations" cancelLabel="Not now" actionLabel="Make variations" busy={make.isPending || read.isPending} holdReason={out?.blocked || (make.error?.message ?? null)} onCancel={onClose} onConfirm={() => make.mutate()}>
      <div className="space-y-3">
        <p>New videos with another hook or ending. The cast, the look and every other clip stay; only the changed clips are made.</p>
        <Pick label="How many" value={count} onPick={setCount} options={[[2, "2 variations"], [3, "3 variations"]]} />
        <Pick label="What changes" value={part} onPick={setPart} options={[["hook", "The hook"], ["ending", "The ending"]]} />
        <TextArea label="Note (optional)" rows={2} value={note} placeholder="Open on the empty bowl" onChange={(e) => (setNote(e.target.value), make.reset())} />
      </div>
    </Dialog>
  );
}
