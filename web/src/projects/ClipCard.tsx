import { AutoFixLine, RetryLine } from "./AutoFixes";
import { useId, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { Check, TriangleAlert } from "lucide-react";
import { Badge, Button, buttonClass, pressLabel, useViewOnly } from "../components";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { JobClock } from "../clip/History";
import { btnPrimary, btnSecondary, input, linkText } from "../ui";
import { useMedia } from "../useMedia";
import { blockerNames, SheetWarning, type Blocker } from "./sheetBlocks";
import { blocking } from "./problems";
import { AdviceList, useKeep } from "./Keep";
import { useChange, type ChangeState } from "./ChangeBox";
import { FIX_NOTE, FixedNote, FixThisPrompt, refused } from "./FixClip";
import { checkedMark, CheckNotes, type ItemCheck } from "./Checks";
import { Dot, OtherTakes, Tag, takeReason } from "./OtherTakes";
import { LookTip } from "./LookFix";
import { ClipVersions } from "./VersionLists";
import { TakeSound } from "./TakeSound";

type Clip = components["schemas"]["ProjectClipOut"];
const ratio = (a: string) => a.replace(":", " / ");
const editLink = "text-accent-text hover:underline disabled:cursor-not-allowed disabled:text-disabled-text disabled:no-underline";
/** The prompt as the editor reads it: script font, five lines (Show all when there's more), and each [ImageN] as the name of what it points at. */
function PromptText({ clip }: { clip: Clip }) {
  const [all, setAll] = useState(false);
  const text = useRef<HTMLParagraphElement>(null);
  const [more, setMore] = useState(false);
  useLayoutEffect(() => {
    const el = text.current;
    if (el && !all) setMore(el.scrollHeight > el.clientHeight + 1);
  }, [clip.prompt, all]);
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
      <p ref={text} className={`whitespace-pre-wrap font-script text-xs leading-[1.6] text-text/80 [overflow-wrap:anywhere] ${all ? "" : "line-clamp-5"}`} aria-label={`Prompt for clip ${clip.clip_id}`}>
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
      {(more || all) && (
        <Button variant="ghost" dense onClick={() => setAll(!all)} aria-expanded={all}>
          {all ? "Show less" : "Show all"}
        </Button>
      )}
    </div>
  );
}

/** A take's failure in plain words: never the server's "Ask the owner for details." (rule 4). */
export const failureLine = (error: string | null | undefined) =>
  !error || /ask the owner/i.test(error) ? "The service couldn't finish this. Credits returned; try again." : error;

/** One video clip per breakdown clip: its takes side by side (the picked one, the others, Make a take), its still, its
 *  prompt and the change note. Approve take N approves the picked one. */
export function ClipCard(props: {
  words: (p: string) => string;
  fix: (p: string) => ReactNode;
  clip: Clip;
  projectId: number;
  aspect: string;
  poster: number | null;
  projectName: string;
  job: { id: number; status: string; created_at: string; started_at?: string | null; error?: string | null; waiting?: string } | undefined;
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
  /** The clip's script line (the Clips tab's detail). */
  line?: string;
  /** Where the Clips tab puts this clip's still, beside the prompt. */
  stillSlot?: (el: HTMLDivElement | null) => void;
}) {
  const viewOnly = useViewOnly(); // a video only its maker or the owner may change
  const { clip: c, stillSlot } = props;
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
  const words = (picked as (typeof picked & { words?: ItemCheck }) | undefined)?.words; // what it says against the script's lines
  // The chip says what the card holds now; a failed newest take is a line under it (it never hides a good picked take).
  const byCheck = (picked as (typeof picked & { approved_by?: string | null }) | undefined)?.approved_by === "check"; // rule 21: a clean take
  const status = c.approved ? (byCheck ? "Approved by the check" : "Approved") : props.busy ? null : c.stale ? "Out of date" : picked ? `Take ${picked.number} · ready to check` : failed ? "Didn't finish" : "Not made";
  const verb = c.takes.length === 0 ? "Make clip" : "Make another take";
  const change = (text: string) => (props.review && !c.stale ? setSeed({ text, n: (seed?.n ?? 0) + 1 }) : setNote(text)); // a check's note
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
  // The takes side by side (v5): three across on a phone, 170 px each on a desktop; the Another take tile is as tall.
  const tile = "flex w-[calc((100%-1.5rem)/3)] shrink-0 flex-col gap-2 lg:w-[170px]";
  const [rw, rh] = props.aspect.split(":").map(Number);
  const tall = `${Math.round((170 * (rh || 16)) / (rw || 9))}px`;
  const posterUrl = props.poster ? fileUrl(props.poster) : undefined;
  // One note for the next take (v5): typed, the Another take press rewrites the prompt with it and makes the take
  // ("up to", a Claude call first); empty, it makes the take as it is, at its exact price.
  const noteId = useId();
  const { box: noteBox, ...note2 } = useChange({
    kind: "clip",
    enabled: props.review,
    title: "Note for the next take",
    projectId: props.projectId,
    id: c.id,
    label: c.clip_id,
    change: lastChange,
    action: c.takes.length > 0 ? "Change it and make a new take" : "Change the prompt",
    hold: props.busy ? "This one is still being made" : null,
    stopFor: props.stopFor,
    snapshot: c.picked_take_id,
    seed,
    onUndo: c.takes.length > 1 ? (was) => props.onPick(c.takes.some((t) => t.id === was) ? was! : c.takes[c.takes.length - 2].id) : undefined,
  });
  const noted = props.review && !c.stale && note2.text.trim() !== "";
  const tilePrice = noted ? note2.price : props.cost;
  const tileWhy = noted ? (note2.changing ? null : note2.reason) : why;
  const tileName = noted ? note2.label : verb;
  const hover = useMedia("(hover: hover)");
  const [live, setLive] = useState(false); // the picked take's controls show under the pointer or focus (v5's plain tile)
  return (
    <li className="min-w-0 space-y-5 text-sm" aria-label={`Clip ${c.clip_id}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-0.5">
          <h3 className={`flex flex-wrap items-center gap-2 tabular-nums ${props.review ? "text-md font-semibold" : "type-section"}`}>
            Clip {c.clip_id.replace(/^c/, "")} · {c.seconds} s
            {/* The Clips tab's list says the status; the old page's card says it here. */}
            {!props.review && (
              <span className={`rounded-sm px-2 py-0.5 text-xs font-medium ${c.approved ? "bg-success-soft text-success" : status === "Didn't finish" ? "bg-danger-soft text-danger" : c.stale ? "bg-warning-soft text-warning" : "bg-surface-2"}`}>
                {status && `${status}${checkedMark(check)}`}
                {!status && <JobClock queued={props.job?.status === "queued"} making="Making…" since={props.job?.status === "queued" ? props.job.created_at : (props.job?.started_at ?? props.job?.created_at)} />}
              </span>
            )}
            {/* Its take shows an older Cast & places look (N6): still approved, and the Advice below says what to do. */}
            {c.take_stale && !props.busy && status !== "Out of date" && <Badge tone="warning">Out of date</Badge>}
          </h3>
          {props.line && <p className={`break-words font-script ${props.review ? "text-xs text-text/80" : ""}`}>{props.line}</p>}
        </div>
        <span className="flex flex-wrap gap-2">
          {picked && (
            <a className={`${buttonClass("ghost")} text-muted lg:min-h-control-dense lg:px-3`} href={fileUrl(picked.file_id)} download={`${props.projectName}-${c.clip_id}-take${picked.number}.mp4`}>
              Download
            </a>
          )}
          {picked && !c.approved && (
            <Button variant={props.review ? "secondary" : "primary"} dense icon={props.review ? undefined : Check} onClick={props.onApprove}>
              Approve take {picked.number}
            </Button>
          )}
          {c.approved && (
            <Button variant="secondary" dense disabled={viewOnly} onClick={props.onUnapprove}>
              Undo approval
            </Button>
          )}
        </span>
      </div>
      {failed && !props.busy && (
        <p role="status" className={`text-sm ${picked ? "text-muted" : "text-danger"}`}>
          {picked ? `The newest take didn't work; Take ${picked.number} is still picked. ` : c.takes.length > 0 && "The last try didn't finish; your other takes are below. "}
          <span>{failureLine(props.job?.error)}</span>
        </p>
      )}
      <LookTip text={c.look_fix} />
      {picked && <CheckNotes check={check} projectId={props.projectId} label={`clip ${c.clip_id}`} onChange={change} />}
      {picked && <CheckNotes check={words} projectId={props.projectId} label={`clip ${c.clip_id}`} what="the words" onChange={change} />}
      {failedBefore && <p role="status" className="text-sm text-muted">The last take, before your change, failed.</p>}
      {props.job?.waiting && <p role="status" className="text-sm text-muted">{props.job.waiting}</p>}
      <RetryLine clip={c} />
      {c.take_warning && !props.busy && <p role="status" className="text-sm text-warning">{c.take_warning}</p>}
      <div className="flex flex-wrap items-start gap-3 lg:gap-5">
        <div className={tile}>
          <div className="relative grid place-items-center overflow-hidden rounded-md bg-surface-2" style={{ aspectRatio: ratio(props.aspect) }}>
            {c.file_id ? (
              <video controls={live || !hover} muted tabIndex={0} src={fileUrl(c.file_id)} poster={posterUrl} className="h-full w-full object-cover" aria-label={`Video for clip ${c.clip_id}`} onMouseEnter={() => setLive(true)} onMouseLeave={() => setLive(false)} onFocus={() => setLive(true)} onBlur={() => setLive(false)} />
            ) : props.poster ? (
              <img src={posterUrl} alt={`Storyboard frame for clip ${c.clip_id}`} className="h-full w-full object-cover opacity-60" />
            ) : (
              <span className="text-muted">No video yet</span>
            )}
            {picked && <span aria-hidden className="pointer-events-none absolute inset-0 rounded-md ring-[1.5px] ring-inset ring-accent-text" />}
            {picked && !live && <Tag>Take {picked.number}</Tag>}
          </div>
          {picked ? (
            <><Dot tone={byCheck || picked.verdict === "clean" ? "ok" : picked.verdict === "flagged" ? "need" : "none"}>{byCheck ? "Approved by the check" : c.approved ? `Approved · ${takeReason(picked)}` : takeReason(picked)}</Dot><TakeSound projectId={props.projectId} clip={c} /></>
          ) : (
            <span className="text-xs text-muted">No take yet</span>
          )}
        </div>
        <OtherTakes takes={c.takes} pickedId={c.picked_take_id} clipId={c.clip_id} aspect={props.aspect} tile={tile} poster={posterUrl} fileName={(n) => `${props.projectName}-${c.clip_id}-take${n}.mp4`} disabled={viewOnly} onPick={props.onPick} />
        {note === null && editing === null && (
          <div className={`${tile} items-center justify-center gap-2.5 rounded-md border border-dashed border-border p-1 text-center lg:h-(--tall) lg:w-40 lg:p-3`} style={{ aspectRatio: ratio(props.aspect), "--tall": tall } as CSSProperties}>
            <span className="font-medium">{c.takes.length ? "Another take" : "Make a take"}</span>
            {/* A prompt only waiting for Prompt OK isn't a reason: the press marks it Prompt OK and makes the take (#751).
                With a note typed below, the press is the note's: the prompt is rewritten with it, then the take is made. */}
            <Button
              variant="secondary"
              dense
              charge={noted ? "estimate" : "fixed"}
              price={tilePrice}
              busy={noted && note2.busy}
              className="px-1.5! lg:px-3!"
              disabled={!!tileWhy}
              reason={tileWhy}
              aria-label={`${tileName}${tilePrice != null ? ` · ${pressLabel(tilePrice, noted ? "estimate" : "fixed")}` : ""}`}
              onClick={() => {
                if (noted) return note2.send();
                if (props.toRead) props.onLooksGood();
                props.onGenerate();
              }}
            >
              {noted && note2.changing ? "Changing…" : noted && note2.label === "Try again" ? "Try again" : noted && !c.takes.length ? "Change" : "Make"}
            </Button>
          </div>
        )}
      </div>
      <SheetWarning blockers={props.blockers} brandId={props.brandId} />
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
      <ClipVersions projectId={props.projectId} clipRowId={c.id} label={c.clip_id} hold={props.busy || props.fixBusy ? "Wait for this clip's take or prompt being made." : null} versions={c.versions ?? []} />
      {/* Its still beside its prompt and the note for the next take (v4). The Clips tab puts the storyboard's card in the slot:
          a thumbnail that opens the still's own presses, or the whole card while the still needs a look. */}
      <div className="flex flex-wrap items-start gap-4 border-t border-border pt-4">
        {stillSlot && <div ref={stillSlot} className="empty:hidden" />}
        <div className="min-w-[min(100%,16rem)] flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted">Prompt</span>
            {props.showPrompt && !props.toRead && <Badge tone="success" icon={Check}>Prompt OK</Badge>}
            {props.showPrompt && (
              <Button variant="secondary" dense icon={props.toRead ? Check : undefined} aria-label={`${props.toRead ? "Prompt OK" : "Undo Prompt OK"} for ${c.clip_id}`} onClick={props.toRead ? props.onLooksGood : props.onUndoLooksGood}>
                {props.toRead ? "Prompt OK" : "Undo Prompt OK"}
              </Button>
            )}
            <span className="flex-1" />
            {editing === null && (
              <button className={`${editLink} min-h-11 text-xs sm:min-h-0`} disabled={viewOnly} aria-label={`Edit the prompt for ${c.clip_id}`} onClick={() => setEditing(c.prompt)}>
                Edit prompt
              </button>
            )}
          </div>
          {(props.showPrompt || props.review) && c.prompt && editing === null && <PromptText clip={c} />}
          {updated && (
            <p className="text-muted" role="status">
              Prompt updated. Read it, then press {verb}.
            </p>
          )}
          {editing !== null && (
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
          )}
          {props.review && !c.stale && (
            <div ref={noteBox} className="space-y-2">
              <label htmlFor={noteId} className="block text-xs text-muted">
                Note for the next take
              </label>
              <input
                id={noteId}
                className="block min-h-control w-full max-w-[520px] rounded-md border border-border-strong bg-bg px-2.5 text-base text-text placeholder:text-muted lg:min-h-control-dense"
                aria-label={`Note for the next take ${c.clip_id}`}
                placeholder="What should change?"
                maxLength={500}
                value={note2.text}
                readOnly={note2.changing || viewOnly}
                onChange={(e) => note2.onText(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && noted && !tileWhy && !note2.busy) note2.send(); }}
              />
              {note2.lines}
            </div>
          )}
        </div>
      </div>
      {note !== null && (
        <div className="space-y-2">
          <label className="block">
            What's wrong?
            <textarea className={input} rows={3} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          <div className="flex gap-2">
            <Button
              dense
              charge="fixed" price={props.cost}
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
      {c.takes.length > 0 && note === null && editing === null && !props.review && (
        <button className={`${linkText} min-h-11 sm:min-h-9`} disabled={viewOnly} onClick={() => setNote("")}>
          Needs a change
        </button>
      )}
      {(props.review || !c.prompt) && props.rewrite /* never written: its only way out, everywhere */}
      {c.inserts.map((i) => (
        <label key={i.shot_id} className="flex min-h-11 w-full items-start gap-3 sm:min-h-0">
          <input type="checkbox" role="switch" disabled={viewOnly} className="mt-0.5 size-5 shrink-0 sm:size-4" checked={i.use_real_image} onChange={(e) => props.onRealImage(i.shot_id, e.target.checked)} />
          <span>
            Use the real image · {i.name} (shot {i.shot_id})
            <span className="block text-xs text-muted">Free. Shows the real picture at that moment.</span>
          </span>
        </label>
      ))}
    </li>
  );
}
