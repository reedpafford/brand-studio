import { useRef, useState } from "react";
import { ArrowRightLeft, Clock, Eye, EyeOff, Scissors, Volume2, X } from "lucide-react";
import { fileUrl } from "../api/upload";
import { Button } from "../components";
import { clock, clipLabel, useMusicChoices, useSwaps, type Cut, type EditBody, type Piece } from "./useCutEdits";

type Edit = (body: EditBody) => void;

/** One B-roll piece (S7-01): when it plays, what's said over it, what it can swap for, and its free edits. */
export function PieceInspector({
  canEdit,
  projectId,
  cut,
  piece,
  onEdit,
  trimming,
  onTrim,
  onSound,
  sounding,
  busy,
}: {
  projectId: number;
  cut: Cut;
  piece: Piece;
  onEdit: Edit;
  trimming: boolean;
  onTrim: () => void;
  onSound: () => void;
  sounding: boolean;
  busy: boolean;
  canEdit: boolean;
}) {
  const swaps = useSwaps(projectId, canEdit ? piece.id : null); // only those who may swap
  const [library, setLibrary] = useState(false);
  const all = swaps.data ?? [];
  const firstLibrary = all.find((s) => s.kind === "library");
  const shown = [...all.filter((s) => s.kind !== "library").slice(0, 3), ...(firstLibrary ? [firstLibrary] : [])];
  const hidden = cut.timeline.presenter?.spans.some((s) => s.hidden && s.start <= piece.start + 0.01 && s.end >= piece.end - 0.01);
  const price =
    cut.sound_usd != null
      ? `up to $${(Math.ceil(cut.sound_usd * 100 - 1e-9) / 100).toFixed(2)}`
      : cut.sound_credits < 1
        ? "under 1 credit"
        : `up to ${Math.ceil(cut.sound_credits)} credits`;
  const sound = cut.timeline.sfx.find((s) => s.piece === piece.id);
  const tile = (s: (typeof all)[number], label: string, opens = false) => (
    <li key={s.take_id} className="flex flex-col gap-1">
      <button
        type="button"
        aria-label={opens ? "Swap for one from the Library" : `Swap for ${label}`}
        aria-pressed={opens ? undefined : s.kind === "in_cut"}
        aria-expanded={opens ? library : undefined}
        disabled={busy || s.kind === "in_cut"}
        onClick={() => (opens ? setLibrary(!library) : onEdit({ kind: "swap", piece: piece.id, take_id: s.take_id }))}
        className={`h-[114px] w-16 overflow-hidden rounded-md bg-surface-2 ${s.kind === "in_cut" ? "outline-2 outline-offset-2 outline-accent" : ""}`}
      >
        {s.poster_file_id ? (
          <img src={fileUrl(s.poster_file_id)} alt="" className="h-full w-full object-cover" />
        ) : (
          <video src={`${fileUrl(s.file_id)}#t=0.1`} muted preload="metadata" className="h-full w-full object-cover" />
        )}
      </button>
      <span className="text-xs text-muted">{label}</span>
    </li>
  );
  return (
    <section className="flex flex-col gap-3" aria-label={`B-roll, ${clipLabel(piece.id).toLowerCase()}`}>
      <div className="flex items-baseline gap-2">
        <h3 className="text-md font-semibold">B-roll · {clipLabel(piece.id).toLowerCase()}</h3>
        <span className="text-sm text-muted tabular-nums">
          {clock(piece.start, true)} – {clock(piece.end, true)} · {(Math.round(piece.end * 10) / 10 - Math.round(piece.start * 10) / 10).toFixed(1)} s
        </span>
      </div>
      {piece.said && (
        <div className="flex flex-col gap-1">
          <span className="text-xs font-semibold text-muted">Said over it</span>
          <span className="text-sm">“{piece.said}”</span>
        </div>
      )}
      {canEdit && (
        <div className="flex flex-col gap-2">
          <span className="text-xs font-semibold text-muted">Swap for</span>
          <ul className="flex flex-wrap gap-2">
            {shown.map((s) => tile(s, s.kind === "in_cut" ? "In the cut" : s.kind === "library" ? "Library" : s.label, s.kind === "library"))}
          </ul>
          {library && (
            <ul className="flex flex-wrap gap-2" aria-label="From the Library">
              {all.filter((s) => s.kind === "library").map((s) => tile(s, s.label))}
            </ul>
          )}
        </div>
      )}
      {canEdit && (
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" icon={Clock} disabled={busy} onClick={() => onEdit({ kind: "retime", piece: piece.id })}>
            Re-time to the words
          </Button>
          <Button variant="secondary" icon={Scissors} aria-pressed={trimming} disabled={busy} onClick={onTrim}>
            Trim
          </Button>
          <Button variant="secondary" icon={Volume2} busy={sounding} disabled={busy || sound?.state === "making"} onClick={onSound}>
            {sound?.state === "ready" ? "Sound effects again" : "Add sound effects"} <span className="text-muted">· {price}</span>
          </Button>
          {cut.timeline.presenter && (
            <Button
              variant="secondary"
              icon={hidden ? EyeOff : Eye}
              disabled={busy}
              onClick={() => onEdit({ kind: "presenter", piece: piece.id, hidden: !hidden })}
            >
              {hidden ? "Presenter: show here" : "Presenter: hide here"}
            </Button>
          )}
        </div>
      )}
      {trimming && <span className="text-xs text-muted">Drag the piece's edges on the timeline, or use the arrow keys and Enter.</span>}
      <span className="text-xs text-muted">{canEdit ? "Edits in the cut are free. New takes are made in Clips and show their price." : NOT_YOURS}</span>
    </section>
  );
}

const NOT_YOURS = "Whoever made this video, or the owner, edits its cut.";
const LEVEL = (db: number) => (db >= 14 ? "A lot" : db >= 6 ? "Some" : "A little");

/** The music (S7-02): how much quieter under the voice, whether it rises when no one speaks, swap or remove it. */
export function MusicInspector({
  projectId,
  cut,
  onEdit,
  busy,
  canEdit,
  failed,
}: {
  projectId: number;
  cut: Cut;
  onEdit: Edit;
  busy: boolean;
  canEdit: boolean;
  /** the newest edit's error: the slider goes back to the level the cut really has */
  failed: Error | null;
}) {
  const music = cut.timeline.music!;
  const [db, setDb] = useState(music.quieter_db);
  const wait = useRef<ReturnType<typeof setTimeout>>(undefined);
  const keep = () => {
    clearTimeout(wait.current);
    if (!busy && db !== music.quieter_db) onEdit({ kind: "music", quieter_db: db });
  };
  const [server, setServer] = useState(music.quieter_db);
  const [refused, setRefused] = useState(failed);
  if (server !== music.quieter_db || refused !== failed) {
    setServer(music.quieter_db); // the server's value after an edit or Undo…
    setRefused(failed);
    setDb(music.quieter_db); // …or a refused edit: never a level the cut doesn't have
  }
  const [swapping, setSwapping] = useState(false);
  const choices = useMusicChoices(projectId, swapping);
  return (
    <section className="flex flex-col gap-3" aria-label="Music">
      <div className="flex items-baseline gap-2">
        <h3 className="text-md font-semibold">Music</h3>
        <span className="text-sm text-muted tabular-nums">
          “{music.name}” · 0:00 – {clock(cut.timeline.length)}
        </span>
      </div>
      <div className="flex flex-col gap-2">
        <span className="text-xs font-semibold text-muted">Under the voice</span>
        <label className="flex items-center gap-3 text-sm">
          <span className="w-[70px]">Quieter by</span>
          <input
            type="range"
            min={0}
            max={30}
            step={1}
            value={db}
            disabled={!canEdit}
            aria-disabled={busy || undefined}
            onChange={(e) => !busy && setDb(Number(e.target.value))}
            onPointerUp={keep}
            onBlur={keep}
            onKeyUp={() => {
              clearTimeout(wait.current);
              wait.current = setTimeout(keep, 600); // keys held or tapped: one edit once they stop
            }}
            className="grow accent-accent"
          />
          <span className="w-[90px] text-right">
            {LEVEL(db)} <span className="text-muted">(−{db} dB)</span>
          </span>
        </label>
        <div className="flex items-center gap-3 text-sm">
          <span className="w-[70px]">When no one speaks</span>
          <div className="inline-flex gap-0.5 rounded-md bg-surface-2 p-0.5" role="radiogroup" aria-label="When no one speaks">
            {(["down", "rise"] as const).map((g) => (
              <button
                key={g}
                type="button"
                role="radio"
                aria-checked={music.gaps === g}
                disabled={!canEdit}
                aria-disabled={busy || undefined}
                onClick={() => !busy && music.gaps !== g && onEdit({ kind: "music", gaps: g })}
                className={`rounded-sm px-3 py-1 text-sm ${music.gaps === g ? "bg-surface text-text shadow-raised" : "text-muted"}`}
              >
                {g === "down" ? "Stay down" : "Rise"}
              </button>
            ))}
          </div>
        </div>
      </div>
      {canEdit && (
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" icon={ArrowRightLeft} aria-expanded={swapping} onClick={() => setSwapping(!swapping)}>
            Swap the music
          </Button>
          <Button variant="secondary" icon={X} disabled={busy} onClick={() => onEdit({ kind: "music", removed: true })}>
            Remove
          </Button>
        </div>
      )}
      {!canEdit && <span className="text-xs text-muted">{NOT_YOURS}</span>}
      {swapping && (
        <ul className="flex flex-col gap-1" aria-label="Music to swap for">
          {(choices.data ?? [])
            .filter((m) => m.file_id !== music.file_id)
            .map((m) => (
              <li key={m.file_id}>
                <Button variant="ghost" disabled={busy} onClick={() => onEdit({ kind: "music", file_id: m.file_id })}>
                  “{m.name}”
                </Button>
              </li>
            ))}
          {choices.data && !choices.data.some((m) => m.file_id !== music.file_id) && <li className="text-sm text-muted">This brand has no other music yet.</li>}
        </ul>
      )}
    </section>
  );
}
