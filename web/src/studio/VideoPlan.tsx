import { FileText, LoaderCircle } from "lucide-react";
import { fileUrl } from "../api/upload";
import { duration, plural } from "./script";
import { linesOf, shotOf, type PlanScene } from "./videoData";

/** The Plan view: the clips grouped by scene as the server gives them. Each row is its number, its first frame once
 *  made, what it shows, who speaks and the line (or "Picture only"), and its length; the picked row opens to the shot.
 *  `clip` is the one picked (on the timeline too); `thumbs`: something has been filmed, so rows carry a frame. */
export function Plan({ scenes, clip, onPick, thumbs }: { scenes: PlanScene[]; clip: string | null; onPick: (clip: string) => void; thumbs: boolean }) {
  if (!scenes.length)
    return (
      <div className="hold bare">
        <FileText size={18} strokeWidth={1.75} aria-hidden />
        <b>The plan shows here first</b>
        <p>The hook, the story and every clip, before anything is filmed.</p>
      </div>
    );
  return scenes.map((s, n) => (
    <section key={s.id} aria-label={s.name || `Scene ${n + 1}`}>
      <h3>
        {s.name || `Scene ${n + 1}`}
        <span>
          {plural(s.clips.length, "clip")} · {duration(Math.round(s.clips.reduce((sum, c) => sum + c.seconds, 0)))}
        </span>
      </h3>
      <ol className={thumbs ? undefined : "nothumb"}>
        {s.clips.map((c) => {
          const open = c.clip_id === clip;
          const lines = linesOf(c);
          return (
            <li key={c.clip_id} className={open ? "open" : undefined}>
              <button type="button" aria-expanded={open} onClick={() => onPick(c.clip_id)}>
                <span className="n">{c.number}</span>
                {thumbs && (
                  <span className={`th ${c.frame_file_id != null ? "" : c.state === "making" ? "making" : "todo"}`}>
                    {c.frame_file_id != null ? <img src={fileUrl(c.frame_file_id)} alt="" /> : c.state === "making" && <LoaderCircle size={14} strokeWidth={1.75} aria-hidden className="spin" />}
                  </span>
                )}
                <span className="what">
                  <b>
                    {c.label || `Clip ${c.number}`}
                    {c.left && <span className="mk bad">Left out</span>}
                  </b>
                  {lines.map((l, i) => (
                    <span key={i} className="said">
                      {l.by && <i>{l.by}</i>}
                      {l.line}
                    </span>
                  ))}
                  {!lines.length && <span className="said silent">Picture only</span>}
                </span>
                <span className="len">{duration(Math.round(c.seconds))}</span>
              </button>
              {open && (
                <div className="more">
                  <p>{shotOf(c)}</p>
                  {c.left && <p>{c.left}</p>}
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  ));
}
