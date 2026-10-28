import { useState, type ReactNode } from "react";
import { Check, TriangleAlert } from "lucide-react";
import { Badge, Button } from "../components";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { Elapsed } from "../clip/History";
import { btnPrimary, btnSecondary, input, linkText } from "../ui";
import { SheetWarning, type Blocker } from "./sheetBlocks";
import { blocking } from "./problems";
import { AdviceList, useKeep } from "./Keep";
import { ChangeBox, type ChangeState } from "./ChangeBox";
import { FIX_NOTE, FixedNote, FixThisPrompt } from "./FixClip";

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

/** One video clip per breakdown clip: make takes, pick and approve one, then stitch them into the video. */
export function ClipCard(props: {
  words: (p: string) => string;
  fix: (p: string) => ReactNode;
  clip: Clip;
  projectId: number;
  aspect: string;
  poster: number | null;
  projectName: string;
  job: { status: string; created_at: string; error?: string | null } | undefined;
  busy: boolean;
  blockers: Blocker[];
  toRead: boolean;
  showPrompt: boolean;
  onLooksGood: () => void;
  onUndoLooksGood: () => void;
  brandId: number;
  cost: number | undefined;
  stopped: boolean;
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
  const failed = props.job?.status === "failed";
  const status = c.approved ? "Approved" : props.busy ? null : failed ? "Failed · credits returned" : c.stale ? "Made for an older breakdown" : c.file_id ? "Ready" : "Not made";
  const verb = c.takes.length === 0 ? "Make clip" : "Make another take";
  const price = props.cost === undefined ? "" : ` · ${Math.round(props.cost)} credits`;
  const picked = c.takes.find((t) => t.id === c.picked_take_id);
  // "Change this…" on a clip with no take only rewrites the prompt (no surprise paid take): say what to press next.
  const lastChange = c.change as ChangeState;
  const updated = props.review && c.takes.length === 0 && lastChange?.status === "done" && lastChange.note !== FIX_NOTE;
  return (
    <li className={`space-y-2 rounded-md bg-surface p-3 text-sm ${c.approved ? "border-2 border-success" : "border border-border"}`} aria-label={`Clip ${c.clip_id}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{c.clip_id} · {c.seconds} s</span>
        <span className={`ml-auto rounded-sm px-2 py-0.5 text-xs font-medium ${c.approved ? "bg-success-soft text-success" : failed ? "bg-danger-soft text-danger" : c.stale ? "bg-warning-soft text-warning" : "bg-surface-2"}`}>
          {status ?? (
            <>
              {props.job?.status === "queued" ? "Queued " : "Rendering "}
              {props.job && <Elapsed since={props.job.created_at} />}
            </>
          )}
        </span>
      </div>
      {failed && props.job?.error && <p role="status" className="text-sm text-danger">{props.job.error}</p>}
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
          {!props.toRead && <Badge tone="success" icon={Check}>Looks good</Badge>}
          <PromptText clip={c} />
        </div>
      )}
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
      {blocking(c.problems, c.kept).length > 0 && !c.stale && !props.fixBusy && !c.free_fix_used && <FixThisPrompt busy={false} onFix={props.onFix} />}
      {props.fixBusy && <FixThisPrompt busy onFix={props.onFix} />}
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
            <button
              className={`${btnPrimary} min-h-11 sm:min-h-9`}
              disabled={props.stopped || props.busy || !note.trim()}
              onClick={() => {
                props.onGenerate(note.trim());
                setNote(null);
              }}
            >
              Redo
              {price}
            </button>
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
          change={c.change as ChangeState}
          hold={props.busy ? "This one is still being made" : null}
          stopFor={props.stopFor}
          snapshot={c.picked_take_id}
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
              {props.toRead ? `Prompt updated. Read it, press Looks good, then press ${verb}.` : `Prompt updated. Press ${verb} to see it.`}
            </p>
          )}
          {c.picked_take_id !== null && !c.approved && (
            <button className={`${btnSecondary} min-h-11 sm:min-h-9`} onClick={props.onApprove}>
              ✓ Looks good
            </button>
          )}
          {c.approved && (
            <button className={`${btnSecondary} min-h-11 sm:min-h-9`} onClick={props.onUnapprove}>
              Undo approval
            </button>
          )}
          {props.showPrompt && (
            <Button variant="secondary" icon={props.toRead ? Check : undefined} aria-label={`Prompt for ${c.clip_id} ${props.toRead ? "looks good" : "undo looks good"}`} onClick={props.toRead ? props.onLooksGood : props.onUndoLooksGood}>
              {props.toRead ? "Looks good" : "Undo"}
            </Button>
          )}
          {note === null && (
            <button className={`${btnSecondary} min-h-11 sm:min-h-9`} disabled={props.toRead || props.stopped || props.busy || blocking(c.problems, c.kept).length > 0 || c.stale || props.blockers.length > 0} onClick={() => props.onGenerate()}>
            {verb}
            {price}
          </button>
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
