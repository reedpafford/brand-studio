import { useRef, useState, type CSSProperties, type ReactNode } from "react";
import { Clock, LoaderCircle, Pause, Play, TriangleAlert, Volume2, VolumeX } from "lucide-react";
import { fileUrl } from "../api/upload";
import { clock } from "../cut/useCutEdits";
import { clipNo } from "../projects/names";
import { Plan } from "./VideoPlan";
import { linesOf, shotOf, type Cell, type PlanScene } from "./videoData";

const VIEWS = ["cut", "plan", "cast"] as const;
type View = (typeof VIEWS)[number];
const ICON = { size: 14, strokeWidth: 1.75, "aria-hidden": true } as const;
const seconds = (s: number) => `${Math.round(s * 10) / 10} s`;
/** A clip that isn't in the cut, in a word or two (the timeline's label and the caption's). */
const STATE = { made: "not in the cut yet", making: "being made now", todo: "planned", left: "left out of the cut" } as const;

/** The film side of a video, to watch (the redesign, stage 2): three views. Cut is the player on the current cut's
 *  file, one caption for the picked clip, and the timeline: the cut's pieces each as wide as it is long, a time card as
 *  a short dark piece with its words, and each clip the cut doesn't hold (left out, being made, planned) at its place.
 *  The playhead follows the film and the pick follows the playhead. Before any cut, a clip's own take plays as it
 *  arrives. Plan and Cast are lists in its place (the film keeps its spot behind them); the timeline stays under all three. `finish` is two facts about the cut
 *  (captions, time cards); nothing here changes anything. */
export function Stage({ plan, cells, film, length, speed, aspect, finish, cast }: { plan: PlanScene[]; cells: Cell[]; film: number | null; length: number; speed: number; aspect: string; finish: { captions: boolean; cards: boolean } | null; cast: ReactNode }) {
  const clips = plan.flatMap((s) => s.clips);
  const [chosen, setView] = useState<View | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [at, setAt] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const cut = useRef<HTMLVideoElement>(null);
  const take = useRef<HTMLVideoElement>(null);

  // It opens on the plan until something is filmed, then on the film.
  const view = chosen ?? (film != null || cells.some((c) => c.state !== "todo") ? "cut" : "plan");
  const under = (t: number) => [...cells].reverse().find((c) => c.start != null && t >= c.start);
  const current = cells.find((c) => c.key === sel) ?? cells.find((c) => c.clip === sel && c.card == null) ?? (film != null ? under(at) : undefined) ?? cells.find((c) => c.state === "making") ?? cells[0];
  const planned = clips.find((c) => c.clip_id === current?.clip);
  const whole = film != null && current?.start != null; // the cut is on screen; else the picked clip's own take, or why there is none
  const screen = whole ? cut : take;
  const number = (c: Cell) => clips.find((x) => x.clip_id === c.clip)?.number ?? clipNo(c.clip);

  const pick = (c: Cell) => {
    setSel(c.key);
    if (film == null || c.start == null) return cut.current?.pause();
    setAt(c.start);
    if (cut.current) cut.current.currentTime = c.start / speed;
  };
  const show = (v: View) => {
    setView(v);
    if (v !== "cut") screen.current?.pause();
  };
  const play = () => {
    const v = screen.current;
    if (v?.paused) void v.play()?.catch(() => {});
    else v?.pause();
  };
  const events = { muted, playsInline: true, onPlay: () => setPlaying(true), onPause: () => setPlaying(false), onClick: play };
  const lines = planned ? linesOf(planned) : [];

  return (
    <section className="stage" aria-label="The video">
      <div className="stage-top">
        <div className="seg" role="group" aria-label="View">
          {VIEWS.map((v) => (
            <button key={v} type="button" aria-pressed={v === view} onClick={() => show(v)}>
              {v[0].toUpperCase() + v.slice(1)}
            </button>
          ))}
        </div>
        <span className="grow" />
        {finish && view === "cut" && (
          <p className="finish">
            Captions <b>{finish.captions ? "on" : "off"}</b> · Time cards <b>{finish.cards ? "on" : "off"}</b>
          </p>
        )}
      </div>
      <div className="stage-mid" hidden={view !== "cut"}>
        <div className="player">
          <div className="frame" style={{ "--ar": aspect.replace(":", " / ") } as CSSProperties}>
            {film != null && (
              <video
                ref={cut}
                src={fileUrl(film)}
                hidden={!whole}
                preload="metadata"
                aria-label="The cut"
                {...events}
                onTimeUpdate={(e) => {
                  const t = e.currentTarget.currentTime * speed;
                  setAt(t);
                  const now = under(t);
                  if (!e.currentTarget.paused && now && now.key !== sel) setSel(now.key); // the pick follows the film
                }}
              />
            )}
            {!whole &&
              (current?.file != null ? (
                <video key={current.file} ref={take} src={fileUrl(current.file)} preload="metadata" aria-label={`Clip ${number(current)}`} {...events} />
              ) : (
                <div className={`hold ${current?.state === "left" ? "bad" : ""}`}>
                  {current?.state === "left" ? <TriangleAlert size={18} strokeWidth={1.75} aria-hidden /> : current?.state === "making" ? <LoaderCircle size={18} strokeWidth={1.75} aria-hidden className="spin" /> : <Clock size={18} strokeWidth={1.75} aria-hidden />}
                  <b>{current?.state === "left" ? "Left out of the cut" : current?.state === "making" ? "Being made now" : "Not filmed yet"}</b>
                  <p>{planned ? shotOf(planned) : "The plan comes first. Clips show here as they are made."}</p>
                </div>
              ))}
          </div>
        </div>
        {current && (
          <div className="cap" role="group" aria-label="The picked clip" aria-live="polite">
            <p className="row">
              <b>{current.card != null ? "Time card" : `Clip ${number(current)}`}</b>
              <span className="meta">{[current.card != null ? `before clip ${number(current)}` : `of ${clips.length}`, seconds(current.seconds), current.start == null && current.state !== "left" && STATE[current.state]].filter(Boolean).join(" · ")}</span>
              {current.state === "left" && <span className="mk bad">Left out</span>}
            </p>
            {current.card != null ? (
              <p>{current.card}</p>
            ) : current.state === "left" ? (
              <p>{planned?.left}</p>
            ) : lines.length ? (
              lines.map((l, i) => (
                <p key={i} className="said">
                  {l.by && <i>{l.by}</i>}
                  {l.line}
                </p>
              ))
            ) : (
              <p>{current.said || (planned && shotOf(planned))}</p>
            )}
          </div>
        )}
      </div>
      {view === "plan" && (
        <div className="planview">
          <Plan scenes={plan} clip={current?.clip ?? null} onPick={(id) => pick(cells.find((c) => c.clip === id && c.card == null) ?? cells[0])} thumbs={cells.some((c) => c.poster != null)} />
        </div>
      )}
      {view === "cast" && <div className="castview">{cast}</div>}
      {cells.length > 0 && (
        <div className="strip">
          <div className="strip-h">
            <button type="button" className="btn soft square" aria-label={playing ? "Pause" : "Play"} disabled={view !== "cut" || (!whole && current?.file == null)} onClick={play}>
              {playing ? <Pause {...ICON} /> : <Play {...ICON} />}
            </button>
            <span className="time">{film != null ? `${clock(at)} / ${clock(length)}` : "No cut yet. Clips show here as they are made."}</span>
            <span className="grow" />
            <button type="button" className="btn ghost square" aria-label={muted ? "Sound on" : "Sound off"} onClick={() => setMuted(!muted)}>
              {muted ? <VolumeX {...ICON} /> : <Volume2 {...ICON} />}
            </button>
          </div>
          <div className={cells.length > 14 ? "track dense" : "track"} role="group" aria-label="Clips, in order, each as wide as it is long">
            {cells.map((c) => (
              <button
                key={c.key}
                type="button"
                className={`tc ${c.card != null ? "card" : c.state}`}
                style={{ "--s": c.seconds } as CSSProperties}
                aria-pressed={c === current}
                aria-label={c.card != null ? `Time card: ${c.card}` : [`Clip ${number(c)}`, seconds(c.seconds), c.start == null && STATE[c.state]].filter(Boolean).join(", ")}
                title={c.card ?? undefined}
                onClick={() => pick(c)}
              >
                {c.card != null ? <span className="words">{c.card}</span> : c.poster != null ? <img src={fileUrl(c.poster)} alt="" /> : c.state === "making" ? <LoaderCircle {...ICON} className="spin" /> : c.state === "left" && <TriangleAlert {...ICON} />}
                {c.card == null && <span className="n">{number(c)}</span>}
                {whole && c === current && <i aria-hidden className="playhead" style={{ left: `${Math.max(0, Math.min(100, ((at - c.start!) / c.seconds) * 100))}%` }} />}
              </button>
            ))}
          </div>
          <p className="ruler" aria-hidden>
            <span>0:00</span>
            <span>{film != null ? clock(length) : `about ${clock(cells.reduce((sum, c) => sum + c.seconds, 0))}`}</span>
          </p>
        </div>
      )}
    </section>
  );
}
