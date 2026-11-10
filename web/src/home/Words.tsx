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
export function Words({ text, size, setText, go, rail, narrated, id = WORDS_ID, label = "Paste a script, or describe the video", placeholder = PLACEHOLDER, inDialog }: { text: string; size: ReturnType<typeof scriptSize>; setText: (t: string) => void; go: () => void; rail: boolean; narrated: boolean; id?: string; label?: string; placeholder?: string; /** the dialog focuses it itself, after noting what opened it (focus goes back there on closing) */ inDialog?: boolean }) {
  const [editing, setEditing] = useState(false);
  const lines = text.split("\n").filter((l) => l.trim());
  const c = counts(text, narrated);
  const fold = !editing && lines.length > (rail ? 5 : 3);
  const note = size.error ? <p role="alert" className="pt-1 text-sm text-danger">{size.error}</p> : size.counter ? <p className="pt-1 text-xs tabular-nums text-muted">{size.counter}</p> : null;
  if (fold)
    return (
      <>
        <button id={id} type="button" onClick={() => setEditing(true)} className="block min-h-24 w-full text-left font-script text-sm leading-[1.6]">
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
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <textarea
        id={id}
        autoFocus={editing || (rail && !inDialog)}
        data-autofocus={(rail && inDialog) || undefined}
        rows={rail ? 4 : 3}
        aria-invalid={size.over || undefined}
        value={text}
        placeholder={placeholder}
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

/** "My words are: A script | An idea": the guess from the words (`readsAsScript`) until the person flips it. */
export function WordsAre({ idea, onPick }: { idea: boolean; onPick: (idea: boolean) => void }) {
  return (
    <div role="radiogroup" aria-label="My words are" className="flex flex-wrap items-center gap-x-2 gap-y-1">
      <span aria-hidden className="text-xs text-muted">
        My words are:
      </span>
      <span className="flex w-full gap-0.5 rounded-lg bg-surface-2 p-0.5 sm:inline-flex sm:w-auto">
        {KINDS.map((k) => (
          <button key={k.name} type="button" role="radio" aria-checked={k.idea === idea} onClick={() => onPick(k.idea)} className={`flex min-h-control flex-1 flex-col items-center justify-center rounded-md px-2 py-1 text-xs font-medium transition-[background-color,color,box-shadow] duration-(--dur-fast) ease-out sm:flex-none sm:flex-row sm:gap-1 sm:px-2.5 lg:min-h-6.5 lg:py-0 ${k.idea === idea ? "bg-surface text-text shadow-soft" : "text-muted hover:text-text"}`}>
            {k.name} <span className="font-normal text-muted">({k.hint})</span>
          </button>
        ))}
      </span>
    </div>
  );
}
