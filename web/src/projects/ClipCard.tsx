import { AutoFixLine, RetryLine } from "./AutoFixes";
import { useState, type ReactNode } from "react";
import { Check, TriangleAlert } from "lucide-react";
import { Badge, Button } from "../components";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { Elapsed } from "../clip/History";
import { btnPrimary, btnSecondary, input, linkText } from "../ui";
import { blockerNames, SheetWarning, type Blocker } from "./sheetBlocks";
import { blocking } from "./problems";
import { AdviceList, useKeep } from "./Keep";
import { ChangeBox, type ChangeState } from "./ChangeBox";
import { FIX_NOTE, FixedNote, FixThisPrompt, refused } from "./FixClip";
import { checkedMark, CheckNotes, type ItemCheck } from "./Checks";

type Clip = components["schemas"]["ProjectClipOut"];
const ratio = (a: string) => a.replace(":", " / ");

/** The prompt as the editor reads it: script font, five lines with Show all, and each [ImageN] as the name of what it points at. */
function PromptText({ clip }: { clip: Clip }) {
  const [all, setAll] = useState(false);
  const images = clip.references.filter((r) => r.kind === "image");
  // A picture is named by what it is for; the first frame is "frame:<clip>", and an id with a colon is never shown.
  const name = (n: number) => {
    const ref = images[n - 1];
    if (!ref) return `Picture ${n}`;
    if (ref.role === "storyboard frame" || ref.id.startsWith("frame:") || ref.role.startsWith("frame:")) return "Storyboard frame";
    return ref.role && !ref.role.includes(":") ? ref.role : `Picture ${n}`;
  };
  const parts = clip.prompt.split(/(\[Image\d+\])/);
  return (
    <div className="space-y-1">
      <p className={`whitespace-pre-wrap rounded-md bg-surface-2 p-3 font-script leading-[1.6] [overflow-wrap:anywhere] ${all ? "" : "line-clamp-5"}`} aria-label={`Prompt for clip ${clip.clip_id}`}>
        {parts.map((t, i) => {
          const n = /^\[Image(\d+)\]$/.exec(t)?.[1];
          return n ? (
            <span key={i} className="mx-0.5 inline-block rounded-sm bg-accent-soft px-1.5 font-sans text-xs font-semibold text-accent-text">
              {name(Number(n))}
            </span>
          ) : (
            t
          );
        })}
      </p>
      <Button variant="ghost" dense onClick={() => setAll(!all)} aria-expanded={all}>
        {all ? "Show less" : "Show all"}
      </Button>
    </div>
  );
}

/** A take's failure in plain words: never the server's "Ask the owner for details." (rule 4). */
export const failureLine = (error: string | null | undefined) =>
  !error || /ask the owner/i.test(error) ? "The service couldn't finish this. Credits returned; try again." : error;

/** One video clip per breakdown clip: make takes, pick and approve one, then stitch them into the video. */
export function ClipCard(props: {
  words: (p: string) => string;
  fix: (p: string) => ReactNode;
  clip: Clip;
  projectId: number;
  aspect: string;
  poster: number | null;
  projectName: string;
  job: { id: number; status: string; created_at: string; error?: string | null; waiting?: string } | undefined;
  busy: boolean;
  blockers: Blocker[];
  toRead: boolean;
  showPrompt: boolean;
  onLooksGood: () => void;
  onUndoLooksGood: () => void;
  brandId: number;
  cost: number | undefined;
  stopFor: (cost: number | undefined) => string | null;
  review: boolean;
  onGenerate: (note?: string) => void;
  onPick: (takeId: number) => void;
  onApprove: () => void;
  onUnapprove: () => void;
  onRealImage: (shotId: string, on: boolean) => void;
  onSave: (prompt: string) => void;
  rewrite: ReactNode;
  fixBusy: boolean;
  fixSaid: string | null;
  onFix: () => void;
  onUndoFix: (before: string) => void;
  undoing: boolean;
}) {
  const { clip: c } = props;
  const keep = useKeep(props.projectId, { of: "clip", id: c.id });
  const [editing, setEditing] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [seed, setSeed] = useState<{ text: string; n: number }>();
  const lastChange = c.change as ChangeState;
  // A take that failed before the prompt was changed (Change it, or the free fix) is about the old prompt: it no longer
  // marks the clip as failed. The change's job_id is its rewrite's, or for a fix in code the project's newest job then.
  const failedBefore = props.job?.status === "failed" && lastChange?.status === "done" && (lastChange.job_id ?? 0) >= props.job.id;
  const failed = props.job?.status === "failed" && !failedBefore;
  const picked = c.takes.find((t) => t.id === c.picked_take_id);
  const check = (picked as (typeof picked & { check?: ItemCheck }) | undefined)?.check; // the picked take's advisory check (P4)
  // The chip says what the card holds now; a failed newest take is a line under it (it never hides a good picked take).
  const status = c.approved ? "Approved" : props.busy ? null : c.stale ? "Out of date" : picked ? `Take ${picked.number} · ready to check` : failed ? "Didn't finish" : "Not made";
  const verb = c.takes.length === 0 ? "Make clip" : "Make another take";
  const problems = blocking(c.problems, c.kept).length > 0;
  // A grey paid button always says why, naming the press that moves it on.
  const why = props.blockers.length > 0
      ? `Approve ${blockerNames(props.blockers)}'s sheet first.`
      : c.stale
        ? "Rewrite this clip's prompt first."
        : problems
          ? "Fix the problems above first."
          : props.busy
            ? "A take is being made."
            : props.stopFor(props.cost);
  // "Change this…" on a clip with no take only rewrites the prompt (no surprise paid take): say what to press next.
  // A change always clears "Looks good" (the prompt must be read again), so the line only shows while it is waiting to be read.
  const updated = props.review && props.toRead && c.takes.length === 0 && lastChange?.status === "done" && lastChange.note !== FIX_NOTE;
  return (
    <li className={`space-y-2 rounded-md bg-surface p-3 text-sm ${c.approved ? "border-2 border-success" : "border border-border"}`} aria-label={`Clip ${c.clip_id}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{c.clip_id} · {c.seconds} s</span>
        <span className={`ml-auto rounded-sm px-2 py-0.5 text-xs font-medium ${c.approved ? "bg-success-soft text-success" : status === "Didn't finish" ? "bg-danger-soft text-danger" : c.stale ? "bg-warning-soft text-warning" : "bg-surface-2"}`}>
          {status && `${status}${checkedMark(check)}`}
          {!status && (
            <>
              {props.job?.status === "queued" ? "Waiting " : "Making… "}
              {props.job && <Elapsed since={props.job.created_at} />}
            </>
          )}
        </span>
      </div>
      {failed && !props.busy && (
        <p role="status" className={`text-sm ${picked ? "text-muted" : "text-danger"}`}>
          {picked ? `The newest take didn't work; Take ${picked.number} is still picked. ` : c.takes.length > 0 && "The last try didn't finish; your other takes are below. "}
          <span>{failureLine(props.job?.error)}</span>
        </p>
      )}
      {picked && <CheckNotes check={check} projectId={props.projectId} label={`clip ${c.clip_id}`} onChange={(text) => (props.review && !c.stale ? setSeed({ text, n: (seed?.n ?? 0) + 1 }) : setNote(text))} />}
      {failedBefore && <p role="status" className="text-sm text-muted">The last take, before your change, failed.</p>}
      {props.job?.waiting && <p role="status" className="text-sm text-muted">{props.job.waiting}</p>}
      <RetryLine clip={c} />
      {c.take_warning && !props.busy && <p role="status" className="text-sm text-warning">{c.take_warning}</p>}
      <div className="grid place-items-center overflow-hidden rounded-md bg-surface-2" style={{ aspectRatio: ratio(props.aspect), maxHeight: "24rem" }}>
        {c.file_id ? (
          <video controls muted src={fileUrl(c.file_id)} poster={props.poster ? fileUrl(props.poster) : undefined} className="h-full w-full object-cover" aria-label={`Video for clip ${c.clip_id}`} />
        ) : props.poster ? (
          <img src={fileUrl(props.poster)} alt={`Storyboard frame for clip ${c.clip_id}`} className="h-full w-full object-cover" />
        ) : (
          <span className="text-muted">No video yet</span>
        )}
      </div>
      <SheetWarning blockers={props.blockers} brandId={props.brandId} />
      {props.showPrompt && (
        <div className="space-y-1">
          {!props.toRead && <Badge tone="success" icon={Check}>Prompt OK</Badge>}
          <PromptText clip={c} />
        </div>
      )}
      <AutoFixLine projectId={props.projectId} clip={c} />
      {blocking(c.problems, c.kept).length > 0 && (
        <ul className="list-disc space-y-0.5 pl-5 text-xs text-danger" aria-label={`Problems for ${c.clip_id}`}>
          {blocking(c.problems, c.kept).map((p) => (
            <li key={p}>
              {props.words(p)}
              {props.fix(p)}
              {/* Once the free fix was tried the card is never a dead end: keep it anyway (Undo is under Advice). */}
              {c.free_fix_used && c.prompt && ( // a clip never written has nothing to keep
                <Button variant="ghost" dense busy={keep.isPending} aria-label={`Keep it anyway: ${props.words(p)}`} onClick={() => keep.mutate({ problem: p })}>
                  Keep it anyway
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {blocking(c.problems, c.kept).length > 0 && !c.stale && !props.fixBusy && !c.free_fix_used && <FixThisPrompt busy={false} onFix={props.onFix} moderated={refused(c.problems)} />}
      {props.fixBusy && <FixThisPrompt busy onFix={props.onFix} moderated={refused(c.problems)} />}
      {blocking(c.problems, c.kept).length > 0 && !c.stale && !props.fixBusy && (props.fixSaid ?? (c.free_fix_used ? "We couldn't fix this one automatically." : null)) && (
        <p role="status" className="flex items-start gap-2 text-sm text-warning">
          <TriangleAlert size={16} strokeWidth={1.75} aria-hidden className="mt-0.5 shrink-0" />
          {props.fixSaid ?? (c.prompt ? "We couldn't fix this one automatically." : "Rewrite this clip's prompt below writes it, at its price.")}
        </p>
      )}
      {(() => {
        const change = c.change as { note?: string; status?: string; before?: string; after?: string } | null;
        return change?.note === FIX_NOTE && change.status === "done" && change.before !== undefined && change.after !== undefined && change.after === c.prompt ? (
          <FixedNote before={change.before} after={change.after} busy={props.undoing} onUndo={() => props.onUndoFix(change.before!)} />
        ) : null;
      })()}
      <AdviceList label={props.words} problems={c.problems} kept={c.kept} onKeep={(problem, undo) => keep.mutate({ problem, undo })} busy={keep.isPending} name={`Advice for ${c.clip_id}`} />
      {c.takes.length > 0 && (
        <fieldset className="flex flex-wrap items-center gap-3">
          <legend className="sr-only">Takes for clip {c.clip_id}</legend>
          <span className="text-muted">Takes:</span>
          {[...c.takes].reverse().map((t) => (
            <label key={t.id} className="inline-flex min-h-11 items-center gap-1 sm:min-h-0">
              <input type="radio" name={`takes-${c.id}`} className="size-5 sm:size-4" checked={t.id === c.picked_take_id} onChange={() => props.onPick(t.id)} />
              Take {t.number}
            </label>
          ))}
        </fieldset>
      )}
      {note !== null && (
        <div className="space-y-2">
          <label className="block">
            What's wrong?
            <textarea className={input} rows={3} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          <div className="flex gap-2">
            <Button
              dense
              price={props.cost}
              disabled={!!props.stopFor(props.cost) || props.busy || !note.trim()}
              reason={props.busy ? "A take is being made." : props.stopFor(props.cost) ?? (note.trim() ? null : "Say what's wrong first.")}
              onClick={() => {
                props.onGenerate(note.trim());
                setNote(null);
              }}
            >
              Redo
            </Button>
            <button className={`${btnSecondary} min-h-11 sm:min-h-9`} onClick={() => setNote(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}
      {(props.review || !c.prompt) && props.rewrite /* never written: its only way out, everywhere */}
      {props.review && !c.stale && (
        <ChangeBox
          kind="clip"
          projectId={props.projectId}
          id={c.id}
          label={c.clip_id}
          change={lastChange}
          action={c.takes.length > 0 ? "Change it and make a new take" : "Change the prompt"}
          hold={props.busy ? "This one is still being made" : null}
          stopFor={props.stopFor}
          snapshot={c.picked_take_id}
          seed={seed}
          onUndo={c.takes.length > 1 ? (was) => props.onPick(c.takes.some((t) => t.id === was) ? was! : c.takes[c.takes.length - 2].id) : undefined}
        />
      )}
      {c.inserts.map((i) => (
        <label key={i.shot_id} className="flex min-h-11 w-full items-start gap-3 sm:min-h-0">
          <input type="checkbox" role="switch" className="mt-0.5 size-5 shrink-0 sm:size-4" checked={i.use_real_image} onChange={(e) => props.onRealImage(i.shot_id, e.target.checked)} />
          <span>
            Use the real image · {i.name} (shot {i.shot_id})
            <span className="block text-xs text-muted">Free. Shows the real picture at that moment.</span>
          </span>
        </label>
      ))}
      {editing !== null ? (
        <div className="space-y-2">
          <textarea className={input} rows={5} aria-label={`Prompt for ${c.clip_id}`} value={editing} onChange={(e) => setEditing(e.target.value)} />
          <div className="flex gap-2">
            <button className={btnPrimary} onClick={() => { props.onSave(editing); setEditing(null); }}>
              Save prompt
            </button>
            <button className={btnSecondary} onClick={() => setEditing(null)}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          {updated && (
            <p className="w-full text-muted" role="status">
              Prompt updated. Read it, then press {verb}.
            </p>
          )}
          {c.picked_take_id !== null && !c.approved && (
            <Button variant="secondary" dense icon={Check} onClick={props.onApprove}>
              Approve take
            </Button>
          )}
          {c.approved && (
            <button className={`${btnSecondary} min-h-11 sm:min-h-9`} onClick={props.onUnapprove}>
              Undo approval
            </button>
          )}
          {props.showPrompt && (
            <Button variant="secondary" icon={props.toRead ? Check : undefined} aria-label={`${props.toRead ? "Prompt OK" : "Undo Prompt OK"} for ${c.clip_id}`} onClick={props.toRead ? props.onLooksGood : props.onUndoLooksGood}>
              {props.toRead ? "Prompt OK" : "Undo Prompt OK"}
            </Button>
          )}
          {/* A prompt only waiting for Prompt OK isn't a reason: the press marks it Prompt OK and makes the take (#751). */}
          {note === null && (
            <Button variant="secondary" dense price={props.cost} disabled={!!why} reason={why} onClick={() => { if (props.toRead) props.onLooksGood(); props.onGenerate(); }}>
              {verb}
            </Button>
          )}
          {c.takes.length > 0 && note === null && !props.review && (
            <button className={`${linkText} min-h-11 sm:min-h-9`} onClick={() => setNote("")}>
              Needs a change
            </button>
          )}
          {picked && (
            <a className={`${linkText} inline-flex min-h-11 items-center sm:min-h-9`} href={fileUrl(picked.file_id)} download={`${props.projectName}-${c.clip_id}-take${picked.number}.mp4`}>
              Download
            </a>
          )}
          <button className={`${linkText} min-h-11 sm:min-h-9`} aria-label={`Edit the prompt for ${c.clip_id}`} onClick={() => setEditing(c.prompt)}>
            {props.review ? "Advanced: edit the prompt" : "Edit prompt"}
          </button>
        </div>
      )}
    </li>
  );
}
