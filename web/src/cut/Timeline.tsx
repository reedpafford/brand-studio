import { useRef, useState, type KeyboardEvent, type PointerEvent as ReactPointerEvent, type ReactNode } from "react";
import { AudioLines, Check, Film, Mic, RotateCw, Scissors, RotateCcw, UserRound, Volume2, type LucideIcon } from "lucide-react";
import { fileUrl } from "../api/upload";
import { clock, type Cut } from "./useCutEdits";

export type Selected = { kind: "piece"; id: string } | { kind: "music" } | null;

type Props = {
  cut: Cut;
  at: number;
  selected: Selected;
  snap: boolean;
  dim?: boolean;
  /** the cut is still being made for the first time: pieces past this many seconds aren't laid out yet */
  building?: number;
  onSeek: (t: number) => void;
  onSelect: (s: Selected) => void;
  onSnap: (on: boolean) => void;
  onUndo: () => void;
  onRedo: () => void;
  onSplit: () => void;
  /** a selected piece's edge dragged to a new time (Trim) */
  onTrim?: (piece: string, edge: "start" | "end", t: number) => void;
  trimming?: boolean;
  /** the music was removed: put it back (free) */
  onMusicBack?: () => void;
  /** an edit is on its way: the edit presses wait */
  busy?: boolean;
  /** whoever made the video, or the owner: everyone else only watches */
  canEdit?: boolean;
};

const ROWS: [string, LucideIcon][] = [
  ["Presenter", UserRound],
  ["B-roll", Film],
  ["Voice", Mic],
  ["Music", AudioLines],
  ["Sound effects", Volume2],
];

/** The cut on five tracks (S7-01): Presenter, B-roll, Voice, Music, Sound effects, with the playhead, a ruler every 5 s,
 *  Undo, Redo, Split at the playhead and Snap to words. Changed pieces are outlined; the director's edits carry a dot. */
export function Timeline(props: Props) {
  const {
    cut,
    at,
    selected,
    snap,
    dim,
    building,
    onSeek,
    onSelect,
    onSnap,
    onUndo,
    onRedo,
    onSplit,
    onTrim,
    trimming,
    onMusicBack,
    busy,
    canEdit = true,
  } = props;
  const tl = cut.timeline;
  const length = Math.max(tl.length, 0.1);
  const lane = useRef<HTMLDivElement>(null);
  const pct = (t: number) => `${(Math.min(Math.max(t, 0), length) / length) * 100}%`;
  const span = (a: number, b: number) => ({
    left: pct(a),
    width: `calc(${pct(b - a)} - 2px)`,
  });
  const timeAt = (clientX: number) => {
    const box = lane.current?.getBoundingClientRect();
    return box ? Math.min(Math.max(((clientX - box.left) / box.width) * length, 0), length) : 0;
  };
  // Trim: an edge follows the pointer (captured, so it can't leak to the next tap) and is kept only if it moved;
  // with the keyboard, arrows move it a tenth (Shift: a second), Enter keeps it, Escape puts it back.
  const [moving, setMoving] = useState<{ piece: string; edge: "start" | "end"; t: number; x: number; moved: boolean } | null>(null);
  const grab = (piece: string, edge: "start" | "end", t: number) => (e: ReactPointerEvent<HTMLSpanElement>) => {
    e.stopPropagation();
    if (busy) return; // an edit is on its way: the handles stay, locked
    e.currentTarget.setPointerCapture?.(e.pointerId);
    setMoving({ piece, edge, t, x: e.clientX, moved: false });
  };
  const follow = (e: ReactPointerEvent) => moving && setMoving({ ...moving, t: timeAt(e.clientX), moved: moving.moved || Math.abs(e.clientX - moving.x) > 4 });
  const drop = (keep: boolean) => {
    if (moving && keep && moving.moved && !busy) onTrim?.(moving.piece, moving.edge, moving.t);
    setMoving(null);
  };
  const nudge = (piece: string, edge: "start" | "end", t: number) => (e: KeyboardEvent) => {
    if (busy) return;
    const step = e.shiftKey ? 1 : 0.1;
    const now = moving?.piece === piece && moving.edge === edge ? moving.t : t;
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();
      setMoving({ piece, edge, t: Math.min(Math.max(now + (e.key === "ArrowLeft" ? -step : step), 0), length), x: 0, moved: true });
    } else if (e.key === "Enter") drop(true);
    else if (e.key === "Escape") drop(false);
  };
  const ticks = Array.from({ length: Math.floor(length / 5) + 1 }, (_, i) => i * 5).filter((s) => s < length);
  const seg = "absolute top-1.5 bottom-1.5 flex items-center overflow-hidden rounded-sm px-1.5 text-xs font-medium whitespace-nowrap";
  const row = (name: string, Icon: LucideIcon, lanes: ReactNode, first = false) => (
    <div className="flex h-11 border-t border-border" key={name}>
      <div className="flex w-[132px] flex-none items-center gap-1.5 border-r border-border bg-surface px-3 text-xs font-medium text-muted">
        <Icon size={14} strokeWidth={1.75} aria-hidden />
        {name}
      </div>
      <div ref={first ? lane : undefined} className="relative flex-1 bg-surface-2/40" onClick={(e) => onSeek(timeAt(e.clientX))}>
        {lanes}
      </div>
    </div>
  );
  const dot = (
    <span className="absolute top-0.5 right-0.5 size-1.5 rounded-full bg-accent">
      <span className="sr-only">The director's edit</span>
    </span>
  );
  const spans = (tl.presenter?.spans ?? []).filter((s) => building === undefined || s.start < building); // S7-04: so far
  const presenter = spans.map((s, i) => (
    <div
      key={i}
      className={`${seg} border border-success/40 bg-success-soft text-success ${s.hidden ? "opacity-40" : ""}`}
      style={span(s.start, building === undefined ? s.end : Math.min(s.end, building))}
    >
      {s.hidden
        ? "hidden"
        : `${i === 0 ? `${tl.presenter!.name} · ` : ""}bottom ${s.side}${i > 0 && s.side !== tl.presenter!.spans[0].side ? " (switched)" : ""}${s.size !== "medium" ? ` · ${s.size}` : ""}`}
      {s.director && dot}
    </div>
  ));
  const broll = tl.pieces.map((raw) => {
    const p = moving?.piece === raw.id ? { ...raw, [moving.edge]: moving.t } : raw;
    const on = selected?.kind === "piece" && selected.id === p.id;
    if (building !== undefined && p.start > building)
      return <div key={p.id} className={`${seg} border border-dashed border-border-strong bg-surface-2`} style={span(p.start, p.end)} />;
    return (
      <button
        key={p.id}
        type="button"
        aria-label={`B-roll ${p.id.replace(/^c/, "clip ")}, ${clock(p.start)} to ${clock(p.end)}${p.changed ? ", not in the cut yet" : ""}${p.director ? ", the director's edit" : ""}`}
        aria-pressed={on}
        onClick={(e) => {
          e.stopPropagation();
          onSelect({ kind: "piece", id: p.id });
          onSeek(Math.max(at, p.start) < p.end ? Math.max(at, p.start) : p.start);
        }}
        className={`${seg} bg-black p-0 ${on ? "z-[2] outline-2 outline-offset-1 outline-accent" : ""}`}
        style={span(p.start, p.end)}
      >
        {p.poster_file_id ? (
          <img src={fileUrl(p.poster_file_id)} alt="" className="h-full w-full object-cover" />
        ) : (
          p.file_id && <video src={`${fileUrl(p.file_id)}#t=0.1`} muted preload="metadata" className="h-full w-full object-cover" />
        )}
        {p.changed && (
          <span className="absolute inset-0 rounded-sm border-2 border-warning">
            <span className="sr-only">Not in the cut yet</span>
          </span>
        )}
        {p.director && dot}
      </button>
    );
  });
  const trimmed = selected?.kind === "piece" && trimming && onTrim && canEdit ? tl.pieces.find((p) => p.id === selected.id) : undefined;
  const handles = trimmed
    ? (["start", "end"] as const).map((edge) => {
        const t = moving?.piece === trimmed.id && moving.edge === edge ? moving.t : trimmed[edge];
        return (
          <span
            key={edge}
            role="slider"
            aria-label={edge === "start" ? "Trim the start" : "Trim the end"}
            aria-valuemin={0}
            aria-valuemax={length}
            aria-valuenow={Math.round(t * 10) / 10}
            aria-valuetext={clock(t, true)}
            aria-disabled={busy || undefined}
            tabIndex={0}
            onClick={(e) => e.stopPropagation()}
            onPointerDown={grab(trimmed.id, edge, t)}
            onPointerMove={follow}
            onPointerUp={() => drop(true)}
            onPointerCancel={() => drop(false)}
            onKeyDown={nudge(trimmed.id, edge, trimmed[edge])}
            onBlur={() => moving && !moving.x && drop(false)}
            className="absolute top-1 bottom-1 z-[3] w-2 -translate-x-1/2 cursor-ew-resize touch-none rounded-sm bg-accent"
            style={{ left: pct(t) }}
          />
        );
      })
    : null;
  const voice = tl.voice && (
    <div className={`${seg} border border-accent/40 bg-accent-soft text-accent-text`} style={span(0, length)}>
      {tl.voice.label} · “{tl.voice.text.length > 110 ? `${tl.voice.text.slice(0, 110)}…` : tl.voice.text}”
    </div>
  );
  const removed = tl.music?.removed && (
    <div className={`${seg} border border-dashed border-border-strong text-muted`} style={span(0, length)}>
      Music removed
      {canEdit && onMusicBack && (
        <button type="button" className="ml-2 text-accent-text" disabled={busy} onClick={(e) => (e.stopPropagation(), onMusicBack())}>
          Put it back
        </button>
      )}
    </div>
  );
  const music = tl.music && !tl.music.removed && (
    <button
      type="button"
      aria-pressed={selected?.kind === "music"}
      onClick={(e) => {
        e.stopPropagation();
        onSelect({ kind: "music" });
      }}
      className={`${seg} border border-(--track-music)/30 bg-(--track-music-soft) text-(--track-music) ${selected?.kind === "music" ? "z-[2] outline-2 outline-offset-1 outline-accent" : ""}`}
      style={span(0, length)}
    >
      <span className="relative z-[1]">
        Music · “{tl.music.name}” · {tl.music.quieter_db >= 14 ? "much quieter" : tl.music.quieter_db >= 6 ? "quieter" : "a little quieter"} under the voice
      </span>
      <svg className="absolute inset-0 h-full w-full" preserveAspectRatio="none" viewBox="0 0 614 32" aria-hidden>
        <path
          d={tl.music.gaps === "rise" ? "M0 8 L4 26 L608 26 L614 8" : "M0 26 L614 26"}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.2"
          strokeDasharray="3 2"
        />
      </svg>
      {tl.music.director && dot}
    </button>
  );
  const sfx = tl.sfx.map((s) => (
    <div key={s.piece} className={`${seg} border border-warning/40 bg-warning-soft text-warning`} style={{ left: pct(s.start), minWidth: 52 }}>
      <Volume2 size={12} strokeWidth={1.75} aria-hidden />
      <span className="ml-1">{s.asked || "sound"}</span>
      {s.director && dot}
    </div>
  ));
  return (
    <div className={`relative overflow-hidden rounded-lg border border-border bg-surface ${dim ? "pointer-events-none opacity-45" : ""}`} aria-label="Timeline">
      <div className="flex h-9 items-center gap-2 border-b border-border px-2.5">
        <IconPress label="Undo" onClick={onUndo} disabled={!canEdit || busy || !cut.can_undo}>
          <RotateCcw size={14} strokeWidth={1.75} aria-hidden />
        </IconPress>
        <IconPress label="Redo" onClick={onRedo} disabled={!canEdit || busy || !cut.can_redo}>
          <RotateCw size={14} strokeWidth={1.75} aria-hidden />
        </IconPress>
        <IconPress label="Split at the playhead" onClick={onSplit} disabled={!canEdit || busy || !tl.pieces.length}>
          <Scissors size={14} strokeWidth={1.75} aria-hidden />
        </IconPress>
        <span className="text-xs text-muted">Split at the playhead</span>
        <span className="grow" />
        <label className="flex cursor-pointer items-center gap-2 rounded-sm text-xs text-muted focus-within:outline-2 focus-within:outline-focus">
          Snap to words
          <input type="checkbox" className="sr-only" checked={snap} onChange={(e) => onSnap(e.target.checked)} />
          <span
            className={`flex size-4 items-center justify-center rounded-sm border ${snap ? "border-accent bg-accent text-on-accent" : "border-border-strong bg-surface"}`}
            aria-hidden
          >
            {snap && <Check size={12} strokeWidth={2.5} />}
          </span>
        </label>
        <span className="text-xs text-muted tabular-nums">
          · {clock(at, true)} / {clock(length, true)}
        </span>
      </div>
      <div className="flex">
        <div className="w-[132px] flex-none" />
        <div className="relative h-6 flex-1 text-xs text-muted tabular-nums">
          {ticks.map((s) => (
            <span key={s} className="absolute bottom-0.5" style={{ left: pct(s) }}>
              {clock(s)}
              <i className="absolute -bottom-0.5 left-0 h-[5px] w-px bg-border-strong" />
            </span>
          ))}
        </div>
      </div>
      {row("Presenter", ROWS[0][1], presenter)}
      {row(
        "B-roll",
        ROWS[1][1],
        <>
          {broll}
          {handles}
        </>,
        true,
      )}
      {row("Voice", ROWS[2][1], voice)}
      {row("Music", ROWS[3][1], music || removed)}
      {row("Sound effects", ROWS[4][1], sfx)}
      {!dim && (
        <div
          className="pointer-events-none absolute top-9 bottom-0 z-[3] w-0.5 bg-danger"
          style={{
            left: `calc(132px + (100% - 132px) * ${Math.min(at / length, 1)})`,
          }}
          aria-hidden
        >
          <span className="absolute top-0 -left-1 size-2.5 rounded-xs bg-danger" />
        </div>
      )}
    </div>
  );
}

function IconPress({ label, onClick, disabled, children }: { label: string; onClick: () => void; disabled?: boolean; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
      className="flex size-7 items-center justify-center rounded-md text-muted hover:bg-surface-2 hover:text-text disabled:text-faint"
    >
      {children}
    </button>
  );
}
