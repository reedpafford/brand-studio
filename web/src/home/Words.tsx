import { useState } from "react";
import { counts, scriptSize } from "../scripts/ScriptFrame";

export const WORDS_ID = "new-video-words";
const PLACEHOLDER = "Paste a script, or describe the video. “A Dr. Pickle rant about beer bellies, under a minute, ending on the capsule.”";

/** Whether the words read as a script (kept word for word) rather than an idea (the director writes the script first):
 *  40 words or more, a speaker line ("NATE: …", "Dr. Pickle: …") or a scene heading (SCENE 1, INT., EXT.). A guess the
 *  person can flip. */
export function readsAsScript(text: string): boolean {
  if (text.split(/\s+/).filter(Boolean).length >= 40) return true;
  return text.split("\n").some((l) => /^\s*[A-Z][\w.'()-]*( [\w.'()-]+){0,2}:/.test(l) || /^\s*(SCENE\b|INT\.|EXT\.)/.test(l));
}

/** The words box: the script font as you type; away from it, a long script folds to four lines and its length (S2-02).
 *  It never cuts a paste: near the most it counts the characters, past it it says so (`scriptSize`). */
export function Words({ text, size, setText, go, rail, narrated }: { text: string; size: ReturnType<typeof scriptSize>; setText: (t: string) => void; go: () => void; rail: boolean; narrated: boolean }) {
  const [editing, setEditing] = useState(false);
  const lines = text.split("\n").filter((l) => l.trim());
  const c = counts(text, narrated);
  const fold = !editing && lines.length > (rail ? 5 : 3);
  const note = size.error ? <p role="alert" className="pt-1 text-sm text-danger">{size.error}</p> : size.counter ? <p className="pt-1 text-xs tabular-nums text-muted">{size.counter}</p> : null;
  if (fold)
    return (
      <>
        <button id={WORDS_ID} type="button" onClick={() => setEditing(true)} className="block min-h-24 w-full text-left font-script text-sm leading-[1.6]">
          <span className="sr-only">Edit the words: </span>
          {lines.slice(0, rail ? 4 : 2).map((l, i) => (
            <span key={i} className="block">{l}</span>
          ))}
          <span className="block text-muted">{`+ ${lines.length - (rail ? 4 : 2)} more lines${rail ? ` · ${c.words} words · about ${c.seconds} s` : ""}`}</span>
        </button>
        {note}
      </>
    );
  return (
    <>
      <label htmlFor={WORDS_ID} className="sr-only">
        Paste a script, or describe the video
      </label>
      <textarea
        id={WORDS_ID}
        autoFocus={editing || rail}
        rows={rail ? 4 : 3}
        aria-invalid={size.over || undefined}
        value={text}
        placeholder={PLACEHOLDER}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => setEditing(false)}
        onKeyDown={(e) => e.key === "Enter" && (e.metaKey || e.ctrlKey) && !e.nativeEvent.isComposing && (e.preventDefault(), go())}
        className="field-sizing-content min-h-24 w-full resize-none bg-transparent font-script text-sm leading-[1.6] text-text outline-none! placeholder:font-sans placeholder:text-base placeholder:text-muted"
      />
      {note}
    </>
  );
}

const KINDS = [
  { idea: false, name: "A script", hint: "kept word for word" },
  { idea: true, name: "An idea", hint: "write the script for me" },
];

/** "My words are: A script | An idea", one quiet line under the words: the guess from the words (`readsAsScript`) until
 *  the person flips it. A phone drops the lead-in (the group still says it) so both choices fit across, each over its hint. */
export function WordsAre({ idea, onPick }: { idea: boolean; onPick: (idea: boolean) => void }) {
  return (
    <div role="radiogroup" aria-label="My words are" className="flex items-center gap-1 text-xs">
      <span aria-hidden className="pr-1 text-muted max-sm:hidden">
        My words are:
      </span>
      {KINDS.map((k) => (
        <button key={k.name} type="button" role="radio" aria-checked={k.idea === idea} onClick={() => onPick(k.idea)} className={`flex min-h-control flex-1 flex-col items-center justify-center rounded-lg px-2 py-1 font-medium transition-colors duration-(--dur-fast) ease-out sm:flex-none sm:flex-row sm:gap-1 sm:rounded-full sm:px-2.5 lg:min-h-6 lg:py-0 ${k.idea === idea ? "bg-surface-2 text-text" : "text-muted hover:text-text"}`}>
          {k.name} <span className="font-normal text-muted">({k.hint})</span>
        </button>
      ))}
    </div>
  );
}
