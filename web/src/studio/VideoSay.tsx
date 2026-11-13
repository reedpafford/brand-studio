import { useRef } from "react";
import { ArrowUp, Paperclip, X } from "lucide-react";
import { fileUrl } from "../api/upload";
import type { useNoteBox } from "../videos/runActions";
import { plural } from "./script";

/** The id the box is reached by: "Change the plan first" and a clip's "Tell the director…" put the cursor in it. */
export const BOX = "director-box";

/** The message box under the chat: a note to the director with up to six pictures or clips, for this video only.
 *  Enter sends, Shift+Enter is a new line; one press, one note, never sent again by itself. `box` is the current
 *  page's own box state (a refused note's words come back into it). `closed`: why it can't be used now. `note`: one
 *  line under it. `waiting`: the questions still open, said above it when there are several. */
export function Say({ box, placeholder, closed, note, error, waiting }: { box: ReturnType<typeof useNoteBox>; placeholder: string; closed: string | null; note: string | null; error: string | null; waiting: { id: number; topic: string }[] }) {
  const picker = useRef<HTMLInputElement>(null);
  const at = useRef(0);
  const next = () => document.getElementById(`ask-${waiting[at.current++ % waiting.length].id}`)?.scrollIntoView?.({ block: "center", behavior: "smooth" });
  const said = error ?? box.problem ?? (box.adding ? "Adding…" : note);
  return (
    <div className="saywrap">
      {waiting.length > 1 && (
        <p className="waiting">
          <i aria-hidden className="dot wait" />
          <span className="clip">{[`${waiting.length} waiting`, ...waiting.map((w) => w.topic).filter(Boolean)].join(" · ")}</span>
          <button type="button" onClick={next}>
            Next
          </button>
        </p>
      )}
      <form
        className="say"
        aria-label="Your message"
        onSubmit={(e) => {
          e.preventDefault();
          box.go();
        }}
      >
        <textarea
          id={BOX}
          rows={1}
          value={box.text}
          disabled={!!closed}
          aria-label="Tell the director what to change"
          placeholder={closed ?? placeholder}
          onChange={(e) => box.setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key !== "Enter" || e.shiftKey || e.nativeEvent.isComposing) return;
            e.preventDefault();
            box.go();
          }}
        />
        {box.files.length > 0 && (
          <ul className="files" aria-label="Sent with it, for this video only">
            {box.files.map((f) => (
              <li key={f.id} className="chipf">
                <Paperclip size={14} strokeWidth={1.75} aria-hidden />
                <a className="clip" href={fileUrl(f.id)} target="_blank" rel="noreferrer">
                  {f.name}
                </a>
                <button type="button" className="x" aria-label={`Take off ${f.name}`} onClick={() => box.remove(f.id)}>
                  <X size={14} strokeWidth={1.75} aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="row">
          <input ref={picker} type="file" accept="image/*,video/*" multiple hidden aria-label="Pictures or clips for this video" onChange={(e) => (void box.add(e.target.files), (e.target.value = ""))} />
          <button type="button" className="btn ghost square" aria-label="Add pictures or clips for this video" title={`Pictures or clips, for this video only (${plural(6, "file")} at most)`} disabled={!!closed || box.adding || box.files.length >= 6} onClick={() => picker.current?.click()}>
            <Paperclip size={14} strokeWidth={1.75} aria-hidden />
          </button>
          <span className={error || box.problem ? "bad" : undefined} role="status">
            {said}
          </span>
          <button type="submit" className="btn soft square" aria-label="Send to the director" disabled={!box.ready}>
            <ArrowUp size={14} strokeWidth={2} aria-hidden />
          </button>
        </div>
      </form>
    </div>
  );
}
