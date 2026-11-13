import { useState } from "react";
import { AudioLines, LoaderCircle } from "lucide-react";
import { fixLabel } from "../cut/CutEditor";
import { LEVEL } from "../cut/Inspector";
import type { Cut, useCutEdits } from "../cut/useCutEdits";
import type { useMakeCut } from "../projects/useProgress";
import { Popover } from "./Popover";
import { plural } from "./script";
import { once } from "./videoData";

type Edits = ReturnType<typeof useCutEdits>;

/** Captions and time cards: two switches, each a free edit of the cut. They can be set as soon as the video exists,
 *  so the start card carries them too; the cut made next follows them. */
export function Finish({ cut, edits }: { cut: Cut; edits: Edits }) {
  const row = (kind: "captions" | "cards", label: string, on: boolean) => (
    <button type="button" role="switch" aria-checked={on} disabled={edits.busy || !cut.can_edit} onClick={once(() => edits.edit.mutate({ kind, on: !on }))}>
      <i aria-hidden className="sw" />
      {label}
    </button>
  );
  return (
    <div className="finish" role="group" aria-label="The finish">
      {row("captions", "Captions", cut.timeline.captions)}
      {row("cards", "Time cards", cut.timeline.cards)}
    </div>
  );
}

/** The cut's music: how much quieter it sits under the voice (the same 0 to 30 the current site's slider sends, one
 *  edit when the slider is let go), off, or back on. Nothing here when the cut has no music. */
export function Music({ cut, edits }: { cut: Cut; edits: Edits }) {
  const music = cut.timeline.music;
  const [db, setDb] = useState<number | null>(null); // while the slider is held; null: the cut's own level
  if (!music || !cut.can_edit) return null;
  const level = db ?? music.quieter_db;
  const keep = () => {
    if (db != null && db !== music.quieter_db && !edits.busy) edits.edit.mutate({ kind: "music", quieter_db: db });
    setDb(null);
  };
  if (music.removed)
    return (
      <button type="button" className="btn ghost" disabled={edits.busy} onClick={once(() => edits.edit.mutate({ kind: "music", removed: false }))}>
        <AudioLines size={14} strokeWidth={1.75} aria-hidden />
        Music off <small>Put it back</small>
      </button>
    );
  return (
    <Popover
      label="Music"
      end
      facts
      button={(b) => (
        <button type="button" className="btn ghost" title={`“${music.name}”`} {...b}>
          <AudioLines size={14} strokeWidth={1.75} aria-hidden />
          Music
        </button>
      )}
    >
      {(close) => (
        <div className="conf">
          <b>“{music.name}”</b>
          <label>
            <span>
              Quieter under the voice <small>{`${LEVEL(level)} (−${level} dB)`}</small>
            </span>
            <input type="range" min={0} max={30} step={1} value={level} disabled={edits.busy} aria-label="Quieter under the voice, in decibels" onChange={(e) => setDb(Number(e.target.value))} onPointerUp={keep} onBlur={keep} />
          </label>
          <div>
            <button type="button" className="btn soft" disabled={edits.busy} onClick={once(() => (close(), edits.edit.mutate({ kind: "music", removed: true })))}>
              Turn the music off
            </button>
          </div>
        </div>
      )}
    </Popover>
  );
}

/** "Hook 2", "Hook 2 and Hook 3". */
const hooks = (openings: number[]) => new Intl.ListFormat("en-GB", { type: "conjunction" }).format(openings.map((k) => `Hook ${k}`));

/** Over the film: the cut being made, a cut that failed with its ways on, or the changes waiting for the next cut
 *  ("N changes not in the cut yet") with Undo all and Make the cut, both free. The count is the cut's own.
 *  A video with several versions: `behind` are the ones whose cut needs making again (a clip of theirs changed) and
 *  `uncut` the ones with no cut yet (each is cut after the first; the server doesn't say when one is on its way). The
 *  one press then makes every one of them, "Make the cuts", with the same request. */
export function Notice({ cut, edits, make, behind = [], uncut = [] }: { cut: Cut; edits: Edits; make: ReturnType<typeof useMakeCut>; behind?: number[]; uncut?: number[] }) {
  const several = behind.length + uncut.length > 0;
  const busy = edits.busy || make.isPending;
  const error = edits.error?.message ?? make.error?.message;
  const body = cut.making ? (
    <span role="status">
      <LoaderCircle size={14} strokeWidth={1.75} aria-hidden className="spin" /> <b>Cut {cut.making.number} is being made.</b> {cut.file_id != null ? "The one you have keeps playing until it is ready." : cut.making.doing}
    </span>
  ) : cut.failed ? (
    <>
      <span>
        <b>Cut {cut.failed.number} couldn’t be made.</b> {cut.failed.why}
      </span>
      {cut.can_edit &&
        cut.failed.fixes.map((f) => (
          <button key={f} type="button" className="btn soft" disabled={busy} onClick={once(() => edits.fix.mutate(f))}>
            {fixLabel(f)}
          </button>
        ))}
    </>
  ) : (cut.changes > 0 || several) && cut.can_edit ? (
    <>
      <span>
        {cut.changes > 0 ? (
          <>
            <b>{plural(cut.changes, "change")} not in the cut yet.</b> The cut keeps playing as it is until you make it again.
          </>
        ) : behind.length > 0 ? (
          <>
            <b>
              {hooks(behind)} {behind.length > 1 ? "need" : "needs"} a new cut.
            </b>{" "}
            A clip changed since. What you have keeps playing until it is made.
          </>
        ) : (
          <>
            <b>
              {hooks(uncut)} {uncut.length > 1 ? "have" : "has"} no cut yet.
            </b>{" "}
            A further version is cut right after the first. If it doesn’t arrive, make the cuts again.
          </>
        )}
      </span>
      {cut.can_undo && cut.changes > 0 && (
        <button type="button" className="btn ghost" disabled={busy} onClick={once(() => edits.step.mutate("undo-all"))}>
          Undo all
        </button>
      )}
      <button type="button" className="btn soft" disabled={busy} onClick={once(() => make.mutate())}>
        {several ? "Make the cuts" : "Make the cut"} <small>free</small>
      </button>
    </>
  ) : null;
  if (!body && !error) return null;
  return (
    <div className="notice">
      {body}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
