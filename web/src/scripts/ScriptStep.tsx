import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Lock, Pencil, Sparkles, Undo2 } from "lucide-react";
import { api, errorText } from "../api/client";
import { useJobs } from "../clip/History";
import { Badge, Banner, Button, Card, Dialog, Field, TextArea } from "../components";
import { ScriptText } from "../projects/ScriptTab";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { DescriptionForm } from "./DescriptionForm";
import { ReelBlock, useReelImport } from "./ReelImport";
import { useAllowanceStop, usePatchScript, useWriteWords, type Script } from "./useScript";

const GOING = ["queued", "running"];

/** Claude writes the script from the About fields (the reference reel, when it has one): the price first, and Undo puts the earlier words back. */
function WriteWithClaude({ script: s, text, hasUnsaved, onWritten }: { script: Script; text: string; hasUnsaved: boolean; onWritten: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const hasReference = !!s.reference_id;
  const estimate = useQuery({ queryKey: ["write-estimate", s.id], queryFn: async () => (await api.GET("/scripts/{script_id}/write/estimate", { params: { path: { script_id: s.id } } })).data ?? null });
  const credits = estimate.data?.credits;
  const stop = useAllowanceStop(s, credits);
  const patch = usePatchScript(s.id);
  const put = useWriteWords(s.id);
  const jobs = useJobs();
  const last = jobs.data?.filter((j) => j.kind === "write-claude" && j.script_id === s.id && j.step !== "enhance").sort((a, b) => b.id - a.id)[0];
  const [asking, setAsking] = useState(false);
  const before = useRef(text); // the words as they were when Claude was asked, for Undo
  const write = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/scripts/{script_id}/write", { params: { path: { script_id: s.id } } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });
  // Just started: it counts as writing until the job list has caught up and says otherwise.
  const startedId = write.data?.id;
  const writing = (!!last && GOING.includes(last.status)) || (startedId !== undefined && (last?.id ?? 0) < startedId);
  const seen = useRef(last?.status);
  useEffect(() => {
    if (seen.current !== last?.status && last?.status === "succeeded" && startedId !== undefined && last.id >= startedId) {
      void queryClient.invalidateQueries({ queryKey: ["script-lib", s.id] });
      void queryClient.invalidateQueries({ queryKey: ["script-cast", s.id] }); // the write also found the roles
      onWritten();
      const earlier = before.current;
      toast("Script written.", () => put.mutate(earlier));
    }
    seen.current = last?.status;
  }, [last?.status]); // eslint-disable-line react-hooks/exhaustive-deps
  const press = () => {
    before.current = text;
    setAsking(false);
    write.mutate();
  };
  if (writing || write.isPending)
    return (
      <div role="status" className="space-y-1">
        <p className="flex items-center gap-2"><Sparkles size={20} strokeWidth={1.75} aria-hidden /> Claude is writing the script…</p>
        <p className="text-sm text-muted">It shows here when it's ready. You can leave this page.</p>
      </div>
    );
  return (
    <div className="space-y-2">
      {hasReference && (
        <>
          <p className="text-sm text-muted">{s.new_lines ? "Writes new lines in the reel's voice and pacing. The shots and beats still follow the reel." : "Keeps the reel's lines word for word and rewrites only what the brand swap needs."}</p>
          <label className="flex min-h-control items-center gap-3">
            <input type="checkbox" role="switch" className="size-5" checked={s.new_lines} disabled={patch.isPending} onChange={(e) => patch.mutate({ new_lines: e.target.checked })} />
            Write new lines in the same style
          </label>
        </>
      )}
      {last?.status === "failed" && <p role="alert" className={errorClass}>The last try didn't finish. Credits were returned.</p>}
      {write.isError && <p role="alert" className={errorClass}>{write.error.message}</p>}
      <Button variant="secondary" icon={Sparkles} price={credits} disabled={credits === undefined || stop !== null || patch.isPending} reason={stop} onClick={() => (text.trim() || hasUnsaved ? setAsking(true) : press())}>
        {last?.status === "failed" ? "Try again" : "Have Claude write it for me"}
      </Button>
      {credits !== undefined && <p className="text-sm text-muted">Writes it from the About fields below. Includes finding the roles.</p>}
      {asking && (
        <Dialog title="Write a new script?" cancelLabel="Keep mine" actionLabel="Write it" onCancel={() => setAsking(false)} onConfirm={press}>
          This replaces the words that are here{hasUnsaved ? ", including what you haven't saved" : ""}. Undo puts them back.
        </Dialog>
      )}
    </div>
  );
}

/** A script made from a reel starts as "Untitled reel": its Title is a box right here, not behind About. */
function ReelTitle({ script: s }: { script: Script }) {
  const patch = usePatchScript(s.id);
  const [title, setTitle] = useState<string | null>(null);
  return (
    <form
      className="flex max-w-[680px] flex-col gap-2 sm:flex-row sm:items-end"
      onSubmit={(e) => {
        e.preventDefault();
        if (title?.trim()) patch.mutate({ title: title.trim() }, { onSuccess: () => setTitle(null) });
      }}
    >
      <div className="min-w-0 flex-1">
        <Field label="Title" value={title ?? s.title} onChange={(e) => setTitle(e.target.value)} error={patch.isError ? patch.error.message : null} maxLength={200} />
      </div>
      {title !== null && title.trim() !== s.title && (
        <Button type="submit" variant="secondary" busy={patch.isPending} disabled={!title.trim()}>
          Save title
        </Button>
      )}
    </form>
  );
}

/** Title, what it's for, the reference reel and notes: closed until opened, and where Claude's script comes from. */
function About({ script: s }: { script: Script }) {
  const patch = usePatchScript(s.id);
  const toast = useToast();
  const [open, setOpen] = useState(false);
  if (s.published) return null;
  return (
    <details open={open} onToggle={(e) => setOpen(e.currentTarget.open)} className="group max-w-[680px] rounded-lg border border-border bg-surface px-4">
      <summary className="flex min-h-11 cursor-pointer items-center gap-2 py-2 font-medium">
        <span className="min-w-0 flex-1">
          About this script
          <span className="block truncate text-sm font-normal text-muted">{s.title}{s.description ? ` · ${s.description}` : ""}</span>
        </span>
        <ChevronRight size={20} strokeWidth={1.75} aria-hidden className="shrink-0 group-open:hidden" />
        <ChevronDown size={20} strokeWidth={1.75} aria-hidden className="hidden shrink-0 group-open:block" />
      </summary>
      {open && (
      <div className="pb-4">
        <DescriptionForm
          initial={{ title: s.title, description: s.description, notes: s.notes, reference_id: s.reference_id, reference_replace: s.reference_replace }}
          submitLabel="Save"
          busy={patch.isPending}
          error={patch.isError ? patch.error.message : null}
          onSubmit={(d) => patch.mutate(d, { onSuccess: () => toast("Saved.") })}
        />
      </div>
      )}
    </details>
  );
}

/** Step 1, the script: the editor is the main thing (Save is explicit and leaving with unsaved words asks first), with the optional Claude draft and the About fields under it. */
export function ScriptStep({ script: s, brandName, onDirty }: { script: Script; brandName?: string; onDirty: (dirty: boolean) => void }) {
  const write = useWriteWords(s.id);
  const reel = useReelImport(s.id);
  const queryClient = useQueryClient();
  const toast = useToast();
  const original = s.versions.find((v) => v.slot === 0);
  const text = original?.text ?? "";
  const approved = original?.status === "approved";
  const [draft, setDraft] = useState<string | null>(null); // the editor's words once changed; null follows the saved ones
  const dirty = draft !== null && draft !== text;
  useEffect(() => onDirty(dirty), [dirty]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => onDirty(false), []); // eslint-disable-line react-hooks/exhaustive-deps
  const undoApproval = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.DELETE("/scripts/{script_id}/drafts/{slot}/approve", { params: { path: { script_id: s.id, slot: 0 } } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data) => queryClient.setQueryData(["script-lib", s.id], data),
  });
  // A script made from a reel keeps the reel's lines word for word; the ones rewritten for the brand swap are marked, with the reel's original under each.
  const marks = ((original?.rewritten ?? []) as { line_index: number; was: string }[]).filter((m) => typeof m.line_index === "number");
  const fromReel = s.reel_imported && !!reel.data;
  const kept = Math.max((reel.data?.transcript.length ?? 0) - marks.length, 0);
  const marked = fromReel && marks.length > 0 && !approved;
  return (
    <div className="space-y-4">
      <ReelBlock scriptId={s.id} published={s.published} createdById={s.created_by_id} />
      {!!reel.data && !s.published && <ReelTitle script={s} />}
      {fromReel && !s.new_lines && !approved && marks.length > 0 && (
        <Banner tone="info" title={`From the reel: ${kept} line${kept === 1 ? "" : "s"} kept, ${marks.length} rewritten${brandName ? ` for ${brandName}` : ""}. Check them, then approve.`} />
      )}
      {fromReel && (marks.length > 0 || s.new_lines) && <p className="text-sm text-muted">{s.new_lines ? "New lines, in the style of the reel." : `Marked lines were rewritten${brandName ? ` for ${brandName}` : ""}. Everything else is said as in the reel.`}</p>}
      {s.published || approved ? (
        <div className="space-y-3">
          {!s.published && (
            <div className="flex flex-wrap items-center gap-2">
              <Badge icon={Lock}>Words final</Badge>
              <Button variant="secondary" icon={Undo2} busy={undoApproval.isPending} onClick={() => undoApproval.mutate()}>
                Undo approval to edit
              </Button>
              {undoApproval.isError && <p role="alert" className={errorClass}>{undoApproval.error.message}</p>}
            </div>
          )}
          <ScriptText text={text} />
        </div>
      ) : marked && draft === null ? (
        <div className="space-y-3">
          <div>
            <Button variant="secondary" icon={Pencil} onClick={() => setDraft(text)}>
              Edit
            </Button>
          </div>
          <ScriptText
            text={text}
            rewritten={marks.map((m) => m.line_index + 1)}
            around={(line, where) => {
              const m = where === "after" ? marks.find((x) => x.line_index + 1 === line) : undefined;
              return m ? (
                <li key={`was${line}`} className="grid grid-cols-[2.5rem_1fr] gap-2 text-sm text-muted">
                  <span aria-hidden />
                  <span className="ml-4 sm:ml-8">Was: {m.was}</span>
                </li>
              ) : null;
            }}
          />
        </div>
      ) : (
        <Card className="max-w-[680px] space-y-3">
          <TextArea label="Your script" rows={14} maxLength={50000} placeholder="Paste or write the script here" value={draft ?? text} onChange={(e) => setDraft(e.target.value)} />
          {write.isError && <p role="alert" className={errorClass}>{write.error.message}</p>}
          <div className="flex flex-wrap items-center gap-2">
            <Button
              busy={write.isPending}
              disabled={!dirty || !(draft ?? "").trim()}
              reason={!dirty ? (text.trim() ? "Nothing changed yet" : "Write or paste the script first") : undefined}
              onClick={() => write.mutate(draft ?? "", { onSuccess: () => { setDraft(null); toast("Saved."); } })}
            >
              Save script
            </Button>
            {dirty && <span className="text-sm text-warning">Not saved yet</span>}
            {dirty && (
              <Button variant="ghost" onClick={() => setDraft(null)}>
                Discard changes
              </Button>
            )}
          </div>
        </Card>
      )}
      {!s.published && !approved && !fromReel && (
        <Card className="max-w-[680px]">
          <WriteWithClaude script={s} text={text} hasUnsaved={dirty} onWritten={() => setDraft(null)} />
        </Card>
      )}
      <About script={s} />
    </div>
  );
}
