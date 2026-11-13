import { useState, type CSSProperties, type PointerEvent as ReactPointerEvent } from "react";
import { MessageSquare, Pencil, RefreshCw, Volume2 } from "lucide-react";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { useClipActions } from "../clips/useClipActions";
import { useAddSound } from "../cut/CutEditor";
import type { Cut, Piece, useCutEdits } from "../cut/useCutEdits";
import { upTo } from "../videos/money";
import type { Head } from "../videos/VideoHead";
import { linesOf, once, shotOf, type Cell, type Planned } from "./videoData";

type Clip = components["schemas"]["ProjectClipOut"];
const ICON = { size: 14, strokeWidth: 1.75, "aria-hidden": true } as const;
const seconds = (s: number) => `${Math.round(s * 10) / 10} s`;
const LEAST = 0.5; // the shortest piece the cut keeps
/** A clip that isn't in the cut, in a word or two (the timeline's label and the caption's). */
export const STATE = { made: "not in the cut yet", making: "being made now", todo: "planned", left: "left out of the cut" } as const;

/** Trim one piece of the cut: a bar as long as its take, the part the cut keeps marked on it, and a handle at each
 *  end. Drag a handle, or move it with the arrow keys (Shift for a whole second) and press Enter; one edge is sent at
 *  a time, in the cut's own seconds, when it is let go. `take`: how long the take is, as far as the plan knows. */
function Trim({ piece, take, busy, onTrim }: { piece: Piece; take: number; busy: boolean; onTrim: (edge: "start" | "end", t: number) => void }) {
  const [moving, setMoving] = useState<{ edge: "start" | "end"; t: number } | null>(null);
  const lo = piece.start - piece.in_point;
  const hi = Math.max(piece.end, lo + take);
  const at = { start: piece.start, end: piece.end, ...(moving && { [moving.edge]: moving.t }) };
  const held = (edge: "start" | "end", t: number) => Math.round((edge === "start" ? Math.max(lo, Math.min(at.end - LEAST, t)) : Math.min(hi, Math.max(at.start + LEAST, t))) * 10) / 10;
  const pct = (t: number) => `${((t - lo) / (hi - lo)) * 100}%`;
  const keep = () => {
    if (moving && !busy && moving.t !== piece[moving.edge]) onTrim(moving.edge, moving.t);
    setMoving(null);
  };
  const drag = (edge: "start" | "end") => (e: ReactPointerEvent<HTMLButtonElement>) => {
    if (!e.currentTarget.hasPointerCapture?.(e.pointerId)) return;
    const bar = e.currentTarget.parentElement!.getBoundingClientRect();
    setMoving({ edge, t: held(edge, lo + ((e.clientX - bar.left) / bar.width) * (hi - lo)) });
  };
  return (
    <div className="ed-g">
      <h4>
        Trim
        <span>
          {seconds(at.start - lo)} to {seconds(at.end - lo)} of the take
        </span>
      </h4>
      <div className="trim">
        <span className="keep" style={{ left: pct(at.start), right: `calc(100% - ${pct(at.end)})` } as CSSProperties} />
        {(["start", "end"] as const).map((edge) => (
          <button
            key={edge}
            type="button"
            className="hd"
            role="slider"
            aria-label={edge === "start" ? "Start of the clip" : "End of the clip"}
            aria-valuemin={0}
            aria-valuemax={Math.round((hi - lo) * 10) / 10}
            aria-valuenow={Math.round((at[edge] - lo) * 10) / 10}
            aria-valuetext={seconds(at[edge] - lo)}
            aria-disabled={busy || undefined}
            style={{ left: pct(at[edge]) }}
            onPointerDown={(e) => (e.preventDefault(), e.currentTarget.focus(), e.currentTarget.setPointerCapture?.(e.pointerId))}
            onPointerMove={drag(edge)}
            onPointerUp={keep}
            onPointerCancel={() => setMoving(null)}
            onBlur={keep}
            onKeyDown={(e) => {
              if (e.key === "Enter") return keep();
              if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
              e.preventDefault();
              e.stopPropagation();
              setMoving({ edge, t: held(edge, at[edge] + (e.key === "ArrowRight" ? 1 : -1) * (e.shiftKey ? 1 : 0.1)) });
            }}
          />
        ))}
      </div>
    </div>
  );
}

/** Under the film: the picked clip. Its name and what is said; "Another take" at its price (a take the director
 *  flagged is remade with the director's own note, as the current site does) and "Edit clip", which opens the small
 *  editor in place: its takes, each to watch and to use (the cut is then made again, free), trim, sound effects, and
 *  "Tell the director…", which starts a note about this clip. A clip left out of the cut says why and offers the note:
 *  the server refuses to send a refused prompt again as it is. A time card is its words. */
export function Caption({ projectId, cell, planned, of, clip, head, cut, edits, peek, onPeek, onTell }: { projectId: number; cell: Cell; planned: Planned | undefined; of: number; clip: Clip | undefined; head: Head; cut: Cut | null; edits: ReturnType<typeof useCutEdits>; peek: number | null; onPeek: (file: number | null) => void; onTell: (about: string) => void }) {
  const [editing, setEditing] = useState<string | null>(null);
  const act = useClipActions(projectId, clip?.id ?? 0, () => cut?.file_id != null);
  const sound = useAddSound(projectId);
  const card = cell.card != null;
  const number = planned?.number ?? cell.clip.replace(/^c/, "");
  const picked = clip?.takes.find((t) => t.id === clip.picked_take_id);
  const flagged = picked?.watch && (picked.watch.action === "flagged" || picked.watch.action === "unsure") ? picked.watch : null;
  const busy = act.run.isPending || sound.isPending;
  const making = cell.state === "making" || planned?.state === "making";
  const open = editing === cell.key && !!clip?.takes.length && !card;
  const piece = cut?.can_edit ? cut.timeline.pieces.find((p) => p.id === cell.key && p.take_id != null) : undefined;
  const lines = planned ? linesOf(planned) : [];
  const price = clip ? upTo(head, clip.take_credits) : "";
  const another = clip && (
    <button type="button" className="btn ghost" disabled={busy || making} title={making ? "A take of this clip is being made." : undefined} onClick={once(() => act.take(flagged?.note ?? ""))}>
      <RefreshCw {...ICON} />
      {flagged ? "Remake it" : "Another take"}{" "}
      <small>{price}</small>
    </button>
  );
  const tell = (label: string, kind: string) => (
    <button type="button" className={`btn ${kind}`} onClick={() => onTell(`Clip ${number}: `)}>
      <MessageSquare {...ICON} />
      {label}
    </button>
  );
  const error = act.run.error?.message ?? sound.error?.message;
  return (
    <div className={open ? "cap open" : "cap"} role="group" aria-label="The picked clip">
      <p className="row">
        <b>{card ? "Time card" : planned?.name || `Clip ${number}`}</b>
        <span className="meta">{[card ? `before clip ${number}` : `${planned?.name ? `Clip ${number}` : ""} of ${of}`.trim(), seconds(cell.seconds), cell.start == null && cell.state !== "left" && STATE[cell.state]].filter(Boolean).join(" · ")}</span>
        {cell.state === "left" && <span className="mk bad">Left out</span>}
        <span className="acts">
          {open ? (
            <button type="button" className="btn soft" autoFocus onClick={() => (setEditing(null), onPeek(null))}>
              Done
            </button>
          ) : cell.state === "left" ? (
            tell("Tell the director how to change it", "soft")
          ) : (
            !card &&
            !!clip?.takes.length && (
              <>
                <button type="button" className="btn ghost" onClick={() => (onPeek(null), setEditing(cell.key))}>
                  <Pencil {...ICON} />
                  Edit clip
                </button>
                {another}
              </>
            )
          )}
        </span>
      </p>
      {open && clip ? (
        <div className="ed">
          <div className="ed-g">
            <h4>Takes</h4>
            <div className="takes">
              {clip.takes.map((t) => {
                const used = t.id === clip.picked_take_id;
                const shown = peek === t.file_id || (peek == null && used);
                return (
                  <span key={t.id} className="tkw">
                    <button type="button" className="tk" aria-pressed={shown} aria-label={`Watch take ${t.number}`} onClick={() => onPeek(used ? null : t.file_id)}>
                      <video src={fileUrl(t.file_id)} preload="metadata" muted playsInline tabIndex={-1} />
                      <span>
                        <b>Take {t.number}</b>
                        <small>{used ? (cut?.file_id != null ? "In the cut" : "In use") : "Not used"}</small>
                      </span>
                    </button>
                    {shown && !used && (
                      <button type="button" className="btn soft" disabled={busy} onClick={once(() => (act.pickTake(t), onPeek(null)))}>
                        Use this take
                      </button>
                    )}
                  </span>
                );
              })}
              {another}
            </div>
          </div>
          {piece && <Trim piece={piece} take={clip.seconds} busy={edits.busy} onTrim={(edge, t) => edits.edit.mutate({ kind: "trim", piece: piece.id, [edge]: t, snap: true })} />}
          <div className="ed-f">
            {picked && (clip.sound?.state === "none" || clip.sound?.state === "removed") && (
              <button type="button" className="btn soft" disabled={busy} onClick={once(() => sound.mutate(clip.clip_id))}>
                <Volume2 {...ICON} />
                Add sound effects{" "}
                <small>{upTo(head, clip.sound.credits)}</small>
              </button>
            )}
            {clip.sound?.state === "making" && <span className="quiet small">Sound effects are being made…</span>}
            {picked && clip.sound?.state === "ready" && (
              <button type="button" className="btn soft" disabled={busy} onClick={once(act.unsound)}>
                <Volume2 {...ICON} />
                Remove the sound effects
              </button>
            )}
            {tell("Tell the director…", "ghost")}
          </div>
        </div>
      ) : card ? (
        <p>{cell.card}</p>
      ) : cell.state === "left" ? (
        <p>{planned?.left}</p>
      ) : (
        <>
          {flagged && (
            <p>
              <b>{flagged.found || "The director isn’t sure about this take."}</b> It is left as it is.
            </p>
          )}
          {lines.length
            ? lines.map((l, i) => (
                <p key={i} className="said">
                  {l.by && <i>{l.by}</i>}
                  {l.line}
                </p>
              ))
            : !flagged && <p>{cell.said || (planned && shotOf(planned))}</p>}
        </>
      )}
      {act.recut && <p className="quiet small">Making the cut again with your pick…</p>}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
