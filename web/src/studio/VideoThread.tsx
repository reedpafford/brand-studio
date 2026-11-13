import { useEffect, useRef, useState, type ReactNode } from "react";
import { Check, ChevronRight, Clock, LoaderCircle, TriangleAlert } from "lucide-react";
import { Link } from "react-router-dom";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { mmss } from "../freestyle/FromScript";
import type { Said } from "../freestyle/Thread";
import { isOpen, said as price, type Ask } from "../videos/AskCard";
import { plain } from "../videos/director";
import { clock, runCost, stoppedLine, timeLeft, useThinking, type Progress } from "../videos/RunCard";
import { leadingTreatment, openNote } from "../videos/thread";
import { treatmentOf, type Treatment } from "../videos/Treatment";
import { tinted } from "./ScriptBox";
import { duration, parse, plural } from "./script";
import { cameFrom, type CastItem } from "./videoData";

type Note = components["schemas"]["DeliveryNoteOut"];
type Clip = components["schemas"]["ProjectClipOut"];

const ICON = { size: 14, strokeWidth: 1.75, "aria-hidden": true } as const;
const STEP = {
  done: ["Done", <Check key="i" {...ICON} />],
  now: ["Now", <LoaderCircle key="i" {...ICON} className="spin" />],
  wait: ["Waiting", <Clock key="i" {...ICON} />],
  bad: ["Stopped here", <TriangleAlert key="i" {...ICON} />],
  todo: ["To come", null],
} as const;

/** His first message: the pasted script's opening lines, tinted as the script box tints them, the rest a press away. */
function Script({ text }: { text: string }) {
  const [all, setAll] = useState(false);
  const lines = parse(text).filter((p) => p.kind);
  return (
    <>
      {(all ? lines : lines.slice(0, 2)).map((p, i) => (
        <p key={i}>{tinted(p)}</p>
      ))}
      {lines.length > 2 && (
        <button type="button" aria-expanded={all} onClick={() => setAll(!all)}>
          {all ? "Show less" : `Show all ${lines.length} lines`}
        </button>
      )}
    </>
  );
}

/** The director's treatment: the hook, the story in one line, and why it holds. */
const Treat = ({ t }: { t: Treatment }) => (
  <dl className="treat">
    <dt>Hook</dt>
    <dd>{t.hook}</dd>
    <dt>Story</dt>
    <dd>{t.logline}</dd>
    <dt>Why it holds</dt>
    <dd>{t.why_it_holds}</dd>
  </dl>
);

/** Something an earlier one replaced (a treatment, a delivery note), folded to its line; it opens in place. */
const Folded = ({ line, children }: { line: string; children: ReactNode }) => (
  <details className="fold">
    <summary>
      <ChevronRight {...ICON} />
      {line}
    </summary>
    {children}
  </details>
);

/** The run that is going, or the last one: the director's thinking while the plan is written (read as the current
 *  page reads it, only then), its steps each done, now or to come, what the run has cost, and what stopped it. */
function Run({ r, projectId }: { r: Progress; projectId: number }) {
  const quiet = (r.status === "working" || r.status === "revising") && !r.scenes.length;
  const live = useThinking(projectId, quiet);
  const cost = runCost(r);
  return (
    <>
      {live?.thinking && (
        <details className="fold" open>
          <summary>
            <ChevronRight {...ICON} />
            Thinking
          </summary>
          <p className="think">{live.thinking}</p>
        </details>
      )}
      {!!live?.written.length && (
        <ul className="own" aria-label="The plan so far">
          {live.written.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      )}
      <ul className="steps" aria-label="The director’s steps">
        {r.steps.map((s) => (
          <li key={s.key} className={s.state}>
            <i>{STEP[s.state][1]}</i>
            <span>
              <span className="sr-only">{STEP[s.state][0]}: </span>
              {s.text}
              {s.sub && <small>{s.sub}</small>}
            </span>
          </li>
        ))}
      </ul>
      {cost && <p className="quiet small">{cost}</p>}
      {r.stopped && <p>{stoppedLine(r.stopped)}</p>}
      {r.failed && (
        <p>
          <b>{r.failed.title}.</b> {r.failed.why}
        </p>
      )}
    </>
  );
}

/** A delivery note as the server words it: what it made, what it watched and redid, what remains uncertain (a clip
 *  that couldn't be made is its first open item), what it needs, and what the video has cost. */
function Delivery({ n }: { n: Note }) {
  return (
    <>
      <h4 className="own">What I made</h4>
      <p>{n.made}</p>
      {n.redid.length > 0 && (
        <>
          <h4 className="own">What I watched and redid</h4>
          <ul className="own">
            {n.redid.map((r, i) => (
              <li key={i}>
                <b>{mmss(r.at)}</b> {r.text}
              </li>
            ))}
          </ul>
        </>
      )}
      {(n.unsure || n.open.length > 0) && (
        <>
          <h4 className="own">What remains uncertain</h4>
          <ul className="own open">
            {[n.unsure, ...n.open].filter(Boolean).map((o, i) => (
              <li key={i}>{o}</li>
            ))}
          </ul>
        </>
      )}
      <h4 className="own">What I need from you</h4>
      <p>{n.needs}</p>
      <p className="quiet small">{n.cost}</p>
    </>
  );
}

/** A card the director asks with, to read only: the question and why, then what it offers (a story's choices, the
 *  brand's saved items, the options drawn) or, on a start card, the plan, the cast and each clip's price. Answering is
 *  on the current site. One already answered, or no longer needed, is a line. */
function Card({ a, to, cast, planned }: { a: Ask; to: string; cast: CastItem[]; planned: { clips: number; seconds: number } }) {
  if (!isOpen(a))
    return (
      <p className="folded">
        <b>{a.question}</b>
        <small>{a.state === "not_needed" ? `No longer needed. ${a.closed}` : a.answered_by ? `Answered by ${a.answered_by}` : "Answered"}</small>
      </p>
    );
  const start = a.kind === "start";
  const making = a.money?.making ?? []; // what a start card's run will make, clip by clip
  const drawn = a.options.filter((o) => o.file_id != null);
  return (
    <section className="ask" aria-label={a.question}>
      <p className="ask-h">
        <i aria-hidden className="dot wait" />
        {start ? "Ready to start" : "The director needs you"}
      </p>
      <h3>{a.question}</h3>
      {a.why && <p className="why">{a.why}</p>}
      {a.choices.length > 0 && (
        <ul className="picks">
          {a.choices.map((c) => (
            <li key={c.key}>
              <small>{a.pick === c.key ? `${c.key} · the director’s pick` : c.key}</small>
              <b>{c.title}</b>
              <span>{c.why}</span>
            </li>
          ))}
        </ul>
      )}
      {a.saved.length > 0 && (
        <>
          <h4>{a.saved_in || "Saved"}</h4>
          <ul className="names">
            {a.saved.map((o) => (
              <li key={o.id} className="pill">
                {o.name}
              </li>
            ))}
          </ul>
        </>
      )}
      {drawn.length > 0 && (
        <ul className="cast-s">
          {drawn.map((o) => (
            <li key={o.index}>
              <img src={fileUrl(o.file_id!)} alt="" />
              <b>Option {o.index + 1}</b>
            </li>
          ))}
        </ul>
      )}
      {start && planned.clips > 0 && (
        <p className="why">
          The plan is on the right: {plural(planned.clips, "clip")}, about {duration(planned.seconds)}.
        </p>
      )}
      {start && cast.length > 0 && (
        <ul className="cast-s" aria-label="The cast and places">
          {cast.map((i) => (
            <li key={i.ref}>
              {i.preview_file_id != null ? <img src={fileUrl(i.preview_file_id)} alt="" /> : <span aria-hidden className="im" />}
              <b>{i.name}</b>
              <small>{cameFrom(i)}</small>
              {i.voice && <small>Voice: {i.voice.name}</small>}
            </li>
          ))}
        </ul>
      )}
      {making.length > 0 && (
        <ul className="chg" aria-label="What it will make">
          {making.map((c) => (
            <li key={c.clip}>
              <span>Clip {c.clip}</span>
              <small>{c.seconds} s</small>
              <em>{price(c.price)}</em>
            </li>
          ))}
        </ul>
      )}
      <Link className="btn go" to={to}>
        Answer this on the current site
      </Link>
    </section>
  );
}

/** The chat with the director, to read (the redesign, stage 2): his first message as the script's opening lines, the
 *  treatment, the run's steps, the delivery notes, his notes and the replies, and each card the director asks with,
 *  oldest first. While it runs, one progress line is pinned under it. Nothing is sent from here: changing anything is
 *  on the current site (`current`). */
export function Thread({ items, progress, asks, clips, cast, planned, projectId, current }: { items: Said[]; progress: Progress | null; asks: Ask[]; clips: Clip[]; cast: CastItem[]; planned: { clips: number; seconds: number }; projectId: number; current: string }) {
  const scroller = useRef<HTMLDivElement>(null);
  const story = leadingTreatment(items);
  const note = openNote(items);
  const first = items.find((t) => t.kind === "message")?.id;
  const waiting = asks.some((a) => a.kind === "start" && isOpen(a)) && !progress?.made; // a start card waiting: nothing runs yet
  const newest = `${items.length}:${items.at(-1)?.id}:${progress?.status}`;
  useEffect(() => {
    scroller.current?.scrollTo?.({ top: scroller.current.scrollHeight });
  }, [newest]);

  /** What the director says with one item of the thread; null when it says nothing here. */
  const says = (t: Said): ReactNode => {
    if (t.kind === "ask") {
      const a = asks.find((x) => x.id === t.ask_id);
      return a ? <Card a={a} to={current} cast={cast} planned={planned} /> : t.text ? <p>{t.text}</p> : null;
    }
    const treat = treatmentOf(t);
    if (treat) return t.id === story ? <Treat t={treat} /> : <Folded line="Earlier treatment"><Treat t={treat} /></Folded>;
    if (progress && t.run === progress.run) return waiting ? null : <Run r={progress} projectId={projectId} />;
    if (t.note) return t.id === note ? <Delivery n={t.note} /> : <Folded line={["Earlier delivery note", t.note.cut != null && `Cut ${t.note.cut}`, t.note.seconds > 0 && mmss(t.note.seconds)].filter(Boolean).join(" · ")}><Delivery n={t.note} /></Folded>;
    const why = plain(t.why ?? "", clips);
    return (
      <>
        <p>
          {(t.status === "running" || t.status === "queued") && <LoaderCircle {...ICON} className="spin" />}
          {plain(t.text, clips) || "Deciding what to do next."}
        </p>
        {why && <p className="quiet">{why}</p>}
      </>
    );
  };
  // His messages are bubbles; what the director says in a row reads as one message, under one name and time.
  const groups: { id: string; at: string; his: boolean; parts: ReactNode[] }[] = [];
  for (const t of items) {
    const his = t.kind === "message";
    const part = his ? t.id === first ? <Script text={t.text} /> : <p>{t.text}</p> : says(t);
    if (part == null) continue;
    const last = groups.at(-1);
    const said = (
      <div key={t.id} className={his ? "quote" : undefined}>
        {part}
      </div>
    );
    if (last && !his && !last.his) last.parts.push(said);
    else groups.push({ id: t.id, at: t.at, his, parts: [said] });
  }
  const running = progress && (progress.status === "working" || progress.status === "revising") ? progress : null;
  return (
    <section className="thread" aria-label="The director">
      <div className="msgs" ref={scroller}>
        {groups.map((g) =>
          g.his ? (
            <div key={g.id} className="msg me">
              {g.parts}
            </div>
          ) : (
            <div key={g.id} className="msg">
              <p className="who">
                Director <time>{clock(g.at)}</time>
              </p>
              {g.parts}
            </div>
          ),
        )}
      </div>
      {running && (
        <div className="pinned" role="status">
          <p className="st-row">
            <b>{running.made < running.clips ? `${running.made} of ${plural(running.clips, "clip")} made` : running.title}</b>
            {!!running.minutes_left && <span>{timeLeft(running.minutes_left)}</span>}
          </p>
          {running.clips > 0 && (
            <div className="meter" aria-hidden>
              <i style={{ width: `${Math.min(100, Math.round((100 * (running.made + 0.5)) / running.clips))}%` }} />
            </div>
          )}
        </div>
      )}
      <p className="tocurrent quiet small">
        To change something, <Link to={current}>open this video on the current site</Link>.
      </p>
    </section>
  );
}
