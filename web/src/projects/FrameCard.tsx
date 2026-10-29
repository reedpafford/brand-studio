import { useState, type ReactNode } from "react";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { btnPrimary, btnSecondary, errorText as errorClass, input, linkText } from "../ui";
import { useMedia } from "../useMedia";
import { Sheet } from "./Sheet";
import { SheetWarning, type Blocker } from "./sheetBlocks";
import { blocking } from "./problems";
import { AdviceList, useKeep } from "./Keep";
import { Badge, Button, creditsLabel } from "../components";
import { RotateCcw } from "lucide-react";
import { ChangeBox, type ChangeState } from "./ChangeBox";
import { SoftenedNote, SoftenIt, type Softened } from "./Soften";

type Frame = components["schemas"]["FrameOut"];
const ratio = (a: string) => a.replace(":", " / ");

export function FrameCard(props: {
  frame: Frame;
  projectId: number;
  aspect: string;
  busy: boolean;
  /** Why its still hasn't started yet, once it has waited a while (the server's plain sentence). */
  waiting?: string;
  error: string | null;
  failed: boolean;
  blockers: Blocker[];
  brandId: number;
  nameOf: (id: string) => string;
  words: (p: string) => string;
  fix: (p: string) => ReactNode;
  cost: number | undefined;
  stopped: boolean;
  stopFor: (cost: number | undefined) => string | null;
  oneStep: boolean;
  onPick: (file: number) => void;
  onRender: (note?: string) => void;
  onApprove: (yes: boolean) => void;
  onSave: (prompt: string) => void;
  softening: boolean;
  undoing: boolean;
  softened: Softened | null;
  softenedBySelf: boolean;
  onSoften: () => void;
  onUndoSoften: (before: string) => void;
  onOpen: () => void;
  /** Redo this frame (#749 LW3): an out-of-date frame written again from the new breakdown, then drawn. */
  redoing: boolean;
  /** A still was started for this frame after its last redo. */
  newerJob: boolean;
  onRedo: () => void;
  /** When this frame can't be redone alone (its clip's shots changed): the page's Redo storyboard. */
  redoAll: { label: string; held: boolean; onPress: () => void };
}) {
  const { frame: f } = props;
  const keep = useKeep(props.projectId, { of: "frame", id: f.id });
  const [editing, setEditing] = useState<string | null>(null);
  const [redo, setRedo] = useState<string | null>(null);
  const phone = useMedia("(max-width: 639px)");
  const verb = f.file_id === null ? "Make still" : "Redo";
  // A word the image model may refuse: Soften it or Draw it as is, in place of Make still; a refusal said plainly (QA-2).
  const refusable = f.file_id === null && f.problems.some((p) => /may refuse/.test(p));
  const refused = f.problems.find((p) => /refused to draw/.test(p));
  const changing = (f.change as ChangeState)?.status === "changing";
  // Redo this frame is not a note: its states show on the card, not in Change this…. It is "changing" until its new still
  // lands; then Undo stays on the card while the still in use is not the one from before the redo.
  const change = f.change as ChangeState;
  const redone = change?.note === "Redo this frame";
  // A failed redo says why until something newer is made for this frame (Make still after "its still didn't finish").
  const redoFailed = redone && change?.status === "failed" && !props.newerJob;
  const was = (change as { was_file_id?: number | null } | null)?.was_file_id;
  const before = redone && change?.status === "done" && was != null && f.file_id !== was && f.earlier.some((e) => (e as { file_id: number }).file_id === was) ? was : undefined;
  const redraws = f.file_id !== null && !props.stopped; // saving a prompt draws the still again (past a limit it is only saved)
  const price = props.cost !== undefined ? ` · ${creditsLabel(props.cost)}` : "";
  const redoForm = (
    <div className="space-y-2">
      <label className="block text-sm">
        What should change? (optional)
        <textarea className={input} rows={3} maxLength={500} value={redo ?? ""} onChange={(e) => setRedo(e.target.value)} />
      </label>
      <button
        className={`${btnPrimary} min-h-11 sm:min-h-9`}
        disabled={props.stopped}
        onClick={() => {
          props.onRender((redo ?? "").trim());
          setRedo(null);
        }}
      >
        Redo
        {price}
      </button>
    </div>
  );
  return (
    <li className="space-y-2 text-sm" aria-label={`Frame ${f.clip_id}`}>
      <div className={`relative grid place-items-center overflow-hidden rounded-md bg-surface-2 ${f.approved ? "border-2 border-accent" : "border border-border"}`} style={{ aspectRatio: ratio(props.aspect) }}>
        {f.approved && <span className="absolute right-2 top-2 rounded-full bg-accent px-2 py-0.5 text-xs font-medium text-on-accent">✓ Approved</span>}
        {!f.approved && f.still_stale && (
          <span className="absolute left-2 top-2">
            <Badge tone="warning">Out of date</Badge>
          </span>
        )}
        {!f.approved && !f.still_stale && f.redrawn && (
          <span className="absolute left-2 top-2">
            <Badge icon={RotateCcw}>Redrawn</Badge>
          </span>
        )}
        {props.busy ? (
          <span className="p-2 text-center text-muted">{props.waiting || "Drawing…"}</span>
        ) : f.file_id !== null && (f.change as ChangeState)?.status === "changing" ? (
          <>
            <img src={fileUrl(f.file_id)} alt={`Still for clip ${f.clip_id}`} className="h-full w-full object-cover opacity-50" />
            <span className="absolute inset-0 grid place-items-center text-sm font-medium">Making the change…</span>
          </>
        ) : f.file_id !== null ? (
          <button type="button" className="h-full w-full" aria-label={`Open the still for clip ${f.clip_id}`} onClick={props.onOpen}>
            <img src={fileUrl(f.file_id)} alt={`Still for clip ${f.clip_id}`} className="h-full w-full object-cover" />
          </button>
        ) : (
          <span className="text-muted">No still yet</span>
        )}
      </div>
      <div className="font-medium">
        {f.clip_id} · shot {f.shot_id}
      </div>
      {f.stale && <span className="inline-block rounded-sm bg-warning-soft px-2 py-0.5 text-xs font-medium text-warning">Breakdown changed: redo this frame</span>}
      {f.stale && f.redo_credits != null && (
        <Button busy={props.redoing} price={f.redo_credits} disabled={props.busy || changing || !!props.stopFor(f.redo_credits)} reason={props.stopFor(f.redo_credits)} onClick={props.onRedo}>
          Redo this frame
        </Button>
      )}
      {redoFailed && <p role="alert" className={errorClass}>{change?.error ?? "The redo didn't finish. Try again."}</p>}
      {before !== undefined && (
        <p className="flex flex-wrap items-center gap-2 text-sm text-muted" role="status">
          Redone from the new breakdown. The earlier still is kept.
          <Button variant="ghost" dense onClick={() => props.onPick(before)}>
            Undo
          </Button>
        </p>
      )}
      {f.stale && f.redo_credits == null && f.redo_blocked && (
        <div className="space-y-2">
          <p className="text-sm text-warning">{f.redo_blocked}</p>
          <button className={`${btnSecondary} min-h-11 sm:min-h-9`} disabled={props.redoAll.held} onClick={props.redoAll.onPress}>
            {props.redoAll.label}
          </button>
        </div>
      )}
      {props.error && <p role="alert" className={errorClass}>{props.error}</p>}
      {props.failed && <span className="inline-block rounded-sm bg-danger-soft px-2 py-0.5 text-xs font-medium text-danger">Didn't finish · credits returned</span>}
      <p className="flex flex-wrap gap-1 text-xs">
        {f.reference_ids.map((id) => (
          <span key={id} className="rounded-sm bg-surface-2 px-2 py-0.5">
            {id.startsWith("screen") ? "★ " : id.startsWith("char") ? "● " : id.startsWith("place") ? "⌂ " : ""}
            {props.nameOf(id)}
          </span>
        ))}
      </p>
      <SheetWarning blockers={props.blockers} brandId={props.brandId} />
      {blocking(f.problems).length > 0 && (
        <ul className="list-disc space-y-0.5 pl-5 text-xs text-danger" aria-label={`Problems for ${f.clip_id}`}>
          {blocking(f.problems).map((p) => (
            <li key={p}>
              {props.words(p)}
              {props.fix(p)}
            </li>
          ))}
        </ul>
      )}
      {props.softened && <SoftenedNote note={props.softenedBySelf ? "We softened this frame so it can be drawn." : "Softened. Here is what changed."} was={props.softened} busy={props.undoing} onUndo={() => props.onUndoSoften(props.softened!.before)} />}
      <AdviceList label={props.words} problems={f.problems} kept={f.kept} onKeep={(problem, undo) => keep.mutate({ problem, undo })} busy={keep.isPending} name={`Advice for ${f.clip_id}`} />
      {/* A word the image model may refuse is advice: soften it, or draw it as is (Reed, 2026-10-28). */}
      {refusable && (
        <div className="flex flex-wrap items-center gap-2">
          {refused && <p className="w-full text-sm text-danger">{props.words(refused)}</p>}
          <SoftenIt busy={props.softening} onSoften={props.onSoften} />
          <button className={`${btnSecondary} min-h-11 sm:min-h-9`} disabled={props.stopped || props.busy || blocking(f.problems).length > 0 || props.blockers.length > 0} onClick={() => props.onRender()}>
            Draw it as is{price}
          </button>
        </div>
      )}
      {editing !== null ? (
        <div className="space-y-2">
          <textarea className={input} rows={5} aria-label={`Prompt for clip ${f.clip_id}`} value={editing} onChange={(e) => setEditing(e.target.value)} />
          <div className="flex gap-2">
            <button className={`${redraws ? btnSecondary : btnPrimary} min-h-11 sm:min-h-9`} onClick={() => { props.onSave(editing); setEditing(null); }}>
              {redraws ? `Save and redraw · ${props.cost === undefined ? "…" : creditsLabel(props.cost)}` : "Save prompt"}
            </button>
            <button className={`${btnSecondary} min-h-11 sm:min-h-9`} onClick={() => setEditing(null)}>
              Cancel
            </button>
          </div>
          {f.file_id !== null && props.stopped && <p className="text-sm text-warning">Saving keeps the current still. {props.stopFor(props.cost)}</p>}
        </div>
      ) : (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2">
            {refusable ? null : f.file_id === null ? (
              <button className={`${btnSecondary} min-h-11 sm:min-h-9`} disabled={props.stopped || props.busy || blocking(f.problems).length > 0 || props.blockers.length > 0} onClick={() => props.onRender()}>
                {verb}
                {price}
              </button>
            ) : (
              <>
                <button
                  className={`${btnSecondary} min-h-11 sm:min-h-9`}
                  disabled={props.busy || (!f.approved && (f.stale || blocking(f.problems).length > 0))}
                  onClick={() => props.onApprove(!f.approved)}
                >
                  {f.approved ? "Undo approve" : "Approve"}
                </button>
                <button className={`${btnSecondary} min-h-11 sm:min-h-9`} disabled={props.stopped || props.busy || blocking(f.problems).length > 0 || props.blockers.length > 0} onClick={() => (props.oneStep ? props.onRender() : setRedo(redo === null ? "" : null))} aria-expanded={props.oneStep ? undefined : redo !== null}>
                  {props.oneStep ? "Make another" : verb}
                  {price}
                </button>
              </>
            )}
            <button className={`${linkText} min-h-11 sm:min-h-9`} aria-label={`Edit the prompt for clip ${f.clip_id}`} onClick={() => setEditing(f.prompt)}>
              {props.oneStep ? "Advanced: edit the prompt" : "Edit prompt"}
            </button>
          </div>
          {props.oneStep && f.file_id !== null && (
            <ChangeBox
              kind="frame"
              projectId={props.projectId}
              id={f.id}
              label={f.clip_id}
              change={redone ? null : change}
              hold={props.busy || changing ? "This one is still being made" : f.stale ? (f.redo_credits != null ? "Press Redo this frame first" : "Redo the storyboard first") : null}
              stopFor={props.stopFor}
              onUndo={f.earlier.length ? () => props.onPick((f.earlier.at(-1) as { file_id: number }).file_id) : undefined}
            />
          )}
          {redo !== null && !phone && redoForm}
          {redo !== null && phone && (
            <Sheet title={`Redo clip ${f.clip_id}`} closeLabel="Cancel" onClose={() => setRedo(null)}>
              {redoForm}
            </Sheet>
          )}
        </div>
      )}
    </li>
  );
}
