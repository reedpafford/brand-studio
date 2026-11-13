import type { ReactNode } from "react";
import { useMedia } from "../useMedia";
import { parse, type Line } from "./script";

/** Words with anything in [brackets] dimmed. */
const aside = (words: string) => words.split(/(\[[^\]]*\])/).map((w, i) => (i % 2 ? <span key={i} className="ctx">{w}</span> : w));

/** One line in its tints: a note dim all through; a spoken line bright, with its speaker's name a step dimmer. */
export function tinted(p: Line): ReactNode {
  if (p.kind === "note") return <span className="ctx">{p.line}</span>;
  if (!p.label) return aside(p.line);
  const cut = p.line.indexOf(p.label) + p.label.length + 1; // the name and its colon
  return (
    <>
      <span className="nm">{p.line.slice(0, cut)}</span>
      {aside(p.line.slice(cut))}
    </>
  );
}

/** The script box: a page that fills the height and scrolls inside itself, with whatever is pinned under it (the
 *  read-out, the files, the controls) as `children`. The typed text is see-through; under it lies the same text in
 *  the same type, tinted by how each line reads (`parse`), so the two always line up. ⌘↵ presses Make it (`go`).
 *  On a desk the page opens with the cursor in it, ready for a paste; a phone waits for a tap. */
export function ScriptBox({ text, setText, go, describedBy, children }: { text: string; setText: (t: string) => void; go: () => void; describedBy: string; children: ReactNode }) {
  const desk = useMedia("(min-width: 901px)");
  return (
    <div className="composer">
      <div className="paper">
        <div className="sheet">
          <div className="ink" aria-hidden>
            {parse(text).map((p, i) => (
              <span key={i}>
                {i > 0 && "\n"}
                {tinted(p)}
              </span>
            ))}
            {"\u200b" /* a last empty line keeps its height, as it does in the box over it */}
          </div>
          <textarea
            value={text}
            autoFocus={desk}
            spellCheck={false}
            aria-label="Your script"
            aria-describedby={describedBy}
            placeholder="Paste your script"
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.metaKey || e.ctrlKey) && !e.nativeEvent.isComposing && (e.preventDefault(), go())}
          />
        </div>
      </div>
      {children}
    </div>
  );
}
