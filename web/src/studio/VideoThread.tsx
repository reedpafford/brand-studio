import { useEffect, useRef, useState, type ReactNode } from "react";
import { Check, ChevronRight, Clock, LoaderCircle, TriangleAlert } from "lucide-react";
import type { components } from "../api/schema";
import { mmss } from "../freestyle/FromScript";
import type { Said } from "../freestyle/Thread";
import { isOpen, type Ask } from "../videos/AskCard";
import { plain } from "../videos/director";
import { clock, runCost, stopLines, stoppedLine, timeLeft, useThinking, type Progress } from "../videos/RunCard";
import { leadingTreatment, openNote } from "../videos/thread";
import { treatmentOf, type Treatment } from "../videos/Treatment";
import { tinted } from "./ScriptBox";
import { parse, plural } from "./script";
import { Question } from "./VideoAsk";

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
 *  page reads it, only then), its steps each done, now or to come, what the run has cost, and who stopped it and when
 *  (an earlier Stop it carried on from is a line too). */
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
      {[...stopLines(r), ...(r.stopped ? [stoppedLine(r.stopped)] : [])].map((line) => (
        <p key={line} className="quiet small">
          {line}
        </p>
      ))}
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

/** The chat with the director: his first message as the script's opening lines, the treatment, the run's steps, the
 *  delivery notes, his notes and the replies, and each card the director asks with, oldest first; a note just sent
 *  shows at once (`sending`). The page draws the pieces that act and hands them in: the start card (`start`), what a
 *  stopped or failed run offers, what waits under the newest thing said (`after`: the cast's own OK, an ended run's
 *  presses), a line over the chat (`banner`) and the message box (`foot`). While it runs, one progress line is pinned
 *  above the box. */
export function Thread({ items, sending, progress, asks, clips, projectId, start, stopped, failed, after, banner, foot }: { items: Said[]; sending: { text: string; files: number } | null; progress: Progress | null; asks: Ask[]; clips: Clip[]; projectId: number; start: (a: Ask) => ReactNode; stopped: ReactNode; failed: ReactNode; after: ReactNode; banner: ReactNode; foot: ReactNode }) {
  const scroller = useRef<HTMLDivElement>(null);
  const story = leadingTreatment(items);
  const note = openNote(items);
  const first = items.find((t) => t.kind === "message")?.id;
  const waiting = asks.some((a) => a.kind === "start" && isOpen(a)) && !progress?.made; // a start card waiting: nothing runs yet
  const newest = `${items.length}:${items.at(-1)?.id}:${progress?.run}:${progress?.status}:${progress?.failed ? 1 : 0}:${asks.length}:${!!sending}`; // a card's own changes don't pull the chat down
  useEffect(() => {
    scroller.current?.scrollTo?.({ top: scroller.current.scrollHeight });
  }, [newest]);

  /** What the director says with one item of the thread; null when it says nothing here. */
  const says = (t: Said): ReactNode => {
    if (t.kind === "ask") {
      const a = asks.find((x) => x.id === t.ask_id);
      if (!a) return t.text ? <p>{t.text}</p> : null;
      return a.kind === "start" && isOpen(a) ? start(a) : <Question ask={a} />;
    }
    const treat = treatmentOf(t);
    if (treat) return t.id === story ? <Treat t={treat} /> : <Folded line="Earlier treatment"><Treat t={treat} /></Folded>;
    if (progress && t.run === progress.run)
      return waiting ? null : (
        <>
          <Run r={progress} projectId={projectId} />
          {stopped}
          {failed}
        </>
      );
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
    const part = his ? (
      <>
        {t.id === first ? <Script text={t.text} /> : <p>{t.text}</p>}
        {!!t.files?.length && <small>{plural(t.files.length, "file")} sent with it</small>}
      </>
    ) : (
      says(t)
    );
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
      {banner}
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
        {sending && (
          <div className="msg me">
            <div className="quote">
              <p>{sending.text}</p>
              <small>{[sending.files > 0 && plural(sending.files, "file"), "Sending…"].filter(Boolean).join(" · ")}</small>
            </div>
          </div>
        )}
        {after}
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
      {foot}
    </section>
  );
}
