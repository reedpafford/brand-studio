import { useRef, useState, type CSSProperties, type ReactNode } from "react";
import { Clock, LoaderCircle, Pause, Play, TriangleAlert, Volume2, VolumeX } from "lucide-react";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { clock, type Cut, type useCutEdits } from "../cut/useCutEdits";
import { clipNo } from "../projects/names";
import type { useMakeCut } from "../projects/useProgress";
import type { Head } from "../videos/VideoHead";
import { Caption, STATE } from "./VideoClip";
import { Finish, Music, Notice } from "./VideoCut";
import { Plan } from "./VideoPlan";
import { shotOf, type Cell, type PlanScene, type Versions } from "./videoData";

const VIEWS = ["cut", "plan", "cast"] as const;
type View = (typeof VIEWS)[number];
const ICON = { size: 14, strokeWidth: 1.75, "aria-hidden": true } as const;
const seconds = (s: number) => `${Math.round(s * 10) / 10} s`;

/** The film side of a video: three views. Cut is the player on the current cut's file, one caption for the picked
 *  clip with its presses (./VideoClip), and the timeline: the cut's pieces each as wide as it is long, a time card as a
 *  short dark piece with its words, and each clip the cut doesn't hold (left out, being made, planned) at its place.
 *  The playhead follows the film and the pick follows the playhead. Before any cut, a clip's own take plays as it
 *  arrives; a take picked in the clip's editor plays in the film's place. Plan and Cast are lists in its place; the
 *  timeline stays under all three. Over the film: the changes waiting for the next cut; captions, time cards and the
 *  music are the cut's own free edits (./VideoCut). `onTell`: start a note to the director about a clip.
 *  A video with several `versions` (one for each opening of its script, over the same body) has a switch by the views:
 *  `cut` and `cells` are then the version on screen, and `first` the cut itself, which every edit acts on. */
export function Stage({ projectId, plan, cells, cut, first, versions, rows, head, aspect, edits, make, cast, onTell }: { projectId: number; plan: PlanScene[]; cells: Cell[]; cut: Cut | null; first: Cut | null; versions?: Versions; rows: components["schemas"]["ProjectClipOut"][]; head: Head; aspect: string; edits: ReturnType<typeof useCutEdits>; make: ReturnType<typeof useMakeCut>; cast: ReactNode; onTell: (about: string) => void }) {
  const clips = plan.flatMap((s) => s.clips);
  const film = cut?.file_id ?? null;
  const length = cut?.timeline.length ?? 0;
  const speed = cut?.timeline.speed || 1;
  const [chosen, setView] = useState<View | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [peek, setPeek] = useState<number | null>(null); // a take picked in the clip's editor, to watch
  const [at, setAt] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const whole$ = useRef<HTMLVideoElement>(null);
  const take$ = useRef<HTMLVideoElement>(null);

  // It opens on the plan until something is filmed, then on the film.
  const view = chosen ?? (film != null || cells.some((c) => c.state !== "todo") ? "cut" : "plan");
  const under = (t: number) => [...cells].reverse().find((c) => c.start != null && t >= c.start);
  const current = cells.find((c) => c.key === sel) ?? cells.find((c) => c.clip === sel && c.card == null) ?? (film != null ? under(at) : undefined) ?? cells.find((c) => c.state === "making") ?? cells[0];
  const planned = clips.find((c) => c.clip_id === current?.clip);
  const whole = film != null && current?.start != null && peek == null; // the cut is on screen; else one take, or why there is none
  const screen = whole ? whole$ : take$;
  const shown = peek ?? current?.file ?? null;
  const number = (c: Cell) => clips.find((x) => x.clip_id === c.clip)?.number ?? clipNo(c.clip);

  const pick = (c: Cell) => {
    setSel(c.key);
    setPeek(null);
    if (film == null || c.start == null) return whole$.current?.pause();
    setAt(c.start);
    if (whole$.current) whole$.current.currentTime = c.start / speed;
  };
  /** Another version on screen: its film from the start, with `clip` picked (a row of the plan) or its first. */
  const turn = (opening: number, clip: string | null = null) => {
    screen.current?.pause();
    setSel(clip);
    setPeek(null);
    setAt(0);
    versions?.show(opening);
  };
  /** A row of the plan: its clip is picked, in its own version when it is another opening's. */
  const open = (id: string) => {
    const other = versions && clips.find((c) => c.clip_id === id)?.opening;
    if (other && other !== versions.on) return turn(other, id);
    pick(cells.find((c) => c.clip === id && c.card == null) ?? cells[0]);
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
        {versions && (
          <div className="seg" role="group" aria-label="Version">
            {versions.list.map((x) => (
              <button key={x.opening} type="button" aria-pressed={x.opening === versions.on} title={x.name && x.name !== `V${x.opening}` ? x.name : undefined} onClick={() => x.opening !== versions.on && turn(x.opening)}>
                V{x.opening}
              </button>
            ))}
          </div>
        )}
        <span className="grow" />
        {first && view === "cut" && <Finish cut={first} edits={edits} />}
      </div>
      {first && view === "cut" && <Notice cut={first} edits={edits} make={make} behind={versions?.behind} uncut={versions?.uncut} cutting={versions?.cutting} />}
      <div className="stage-mid" hidden={view !== "cut"}>
        <div className="player">
          <div className="frame" style={{ "--ar": aspect.replace(":", " / ") } as CSSProperties}>
            {film != null && (
              <video
                ref={whole$}
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
              (shown != null ? (
                <video key={shown} ref={take$} src={fileUrl(shown)} preload="metadata" aria-label={current ? `Clip ${number(current)}` : "A take"} {...events} />
              ) : (
                <div className={`hold ${current?.state === "left" ? "bad" : ""}`}>
                  {current?.state === "left" ? <TriangleAlert size={18} strokeWidth={1.75} aria-hidden /> : current?.state === "making" ? <LoaderCircle size={18} strokeWidth={1.75} aria-hidden className="spin" /> : <Clock size={18} strokeWidth={1.75} aria-hidden />}
                  <b>{current?.state === "left" ? "Left out of the cut" : current?.state === "making" ? "Being made now" : "Not filmed yet"}</b>
                  <p>{planned ? shotOf(planned) : "The plan comes first. Clips show here as they are made."}</p>
                </div>
              ))}
          </div>
        </div>
        {current && <Caption key={current.key} projectId={projectId} cell={current} planned={planned} of={clips.length} clip={rows.find((r) => r.clip_id === current.clip)} head={head} cut={first} hook={versions && planned ? planned.opening : 0} fixed={!!versions && versions.on > 1} edits={edits} peek={peek} onPeek={(f) => (whole$.current?.pause(), setPeek(f))} onTell={onTell} />}
      </div>
      {view === "plan" && (
        <div className="planview">
          <Plan scenes={plan} clip={current?.clip ?? null} onPick={open} thumbs={cells.some((c) => c.poster != null || c.file != null)} />
        </div>
      )}
      {view === "cast" && <div className="castview">{cast}</div>}
      {cells.length > 0 && (
        <div className="strip">
          <div className="strip-h">
            <button type="button" className="btn soft square" aria-label={playing ? "Pause" : "Play"} disabled={view !== "cut" || (!whole && shown == null)} onClick={play}>
              {playing ? <Pause {...ICON} /> : <Play {...ICON} />}
            </button>
            <span className="time">{film != null ? `${clock(at)} / ${clock(length)}` : versions && first?.file_id != null ? "No cut yet." : "No cut yet. Clips show here as they are made."}</span>
            <span className="grow" />
            {first && <Music cut={first} edits={edits} />}
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
                {c.card != null ? <span className="words">{c.card}</span> : c.poster != null ? <img src={fileUrl(c.poster)} alt="" /> : c.file != null ? <video src={`${fileUrl(c.file)}#t=0.1`} muted preload="metadata" /> : c.state === "making" ? <LoaderCircle {...ICON} className="spin" /> : c.state === "left" && <TriangleAlert {...ICON} />}
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
