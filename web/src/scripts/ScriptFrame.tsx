import { Fragment, useId, type ReactNode, type TextareaHTMLAttributes } from "react";
import { textSize } from "../components/Field";
import { useViewOnly } from "../components/ViewOnly";

/** The v5 script page's top (C_NewScript, C_ScriptWrite, C_Directions): a 52 px bar, flush with the page's edges, with the
 *  breadcrumb on the left and the page's presses on the right. On a phone the presses wrap under the breadcrumb. */
export function ScriptTop({ crumbs, children }: { crumbs: ReactNode[]; children?: ReactNode }) {
  return (
    <header className="flex min-h-13 flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b border-border px-4 py-2 sm:px-6">
      <nav aria-label="Breadcrumb" className="min-w-0 text-sm text-muted">
        <ol className="flex flex-wrap items-center gap-x-2">
          {crumbs.map((c, i) => (
            <Fragment key={i}>
              {i > 0 && (
                <li aria-hidden className="select-none">
                  ›
                </li>
              )}
              <li className="min-w-0 break-words">{c}</li>
            </Fragment>
          ))}
        </ol>
      </nav>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </header>
  );
}

/** The 52 px row under the top: the script's settings as labelled pickers, and the steps on the right. On a phone the
 *  pickers wrap and the steps' one button takes its own line. */
export function SettingsRow({ children, steps }: { children?: ReactNode; steps: ReactNode }) {
  return (
    <div className="flex min-h-13 flex-wrap items-center gap-x-1.5 gap-y-2 border-b border-border px-4 py-2 sm:px-6">
      {children && (
        <div role="group" aria-label="Script settings" className="flex flex-wrap items-center gap-1">
          {children}
        </div>
      )}
      {/* With no pickers (G_Variations) the steps start at the left of their own row. */}
      <div className={`w-full lg:w-auto ${children ? "lg:ml-auto" : ""}`}>{steps}</div>
    </div>
  );
}

/** A setting's picker in that row: a quiet bordered press reading "Look House style ▾". */
// The value is bright and its label muted (C_NewScript), so the picker isn't the ghost button's grey all through.
// Tight enough that the pickers and the steps share one row beside the v6 rail (248 px, S0-01) at 1440.
export const pickClass = "border border-border text-sm text-text! !gap-1.5 lg:!px-2 [&>svg:last-child]:size-4";
export function PickLabel({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <span className="text-muted">{label}</span> {children}
    </>
  );
}

/** The script's words, counted the way the server counts them (script_library.spoken_seconds): the spoken part of each
 *  "NAME:" line at 4.8 words a second, or every word when there is no dialogue. A narrated script is read whole, NAME: or
 *  not (only scene headings and [directions] are silent), at 2.6 words a second, the server's slowest narrator
 *  (narration.SLOWEST): one "NARRATOR:" line over seven read lines once made 70 words "about 2 s". */
export function counts(text: string, narrated = false) {
  const lines = text.split("\n");
  const said = lines.map((l) => /^([A-Z][A-Z .'()-]*):(.*)$/.exec(l)).filter((m): m is RegExpExecArray => m !== null);
  const wordsIn = (t: string) => t.split(/\s+/).filter(Boolean).length;
  const words = wordsIn(text);
  const read = lines.filter((l) => !/^\s*(\[|\(|(INT|EXT)\.|SCENE\b)/i.test(l)).map((l) => l.replace(/^[A-Z][A-Z .'()-]*:/, ""));
  const spoken = narrated ? wordsIn(read.join(" ")) : said.reduce((n, m) => n + wordsIn(m[2]), 0) || words;
  return { speakers: new Set(said.map((m) => m[1].trim())).size, lines: said.length, words, seconds: Math.round(spoken / (narrated ? 2.6 : 4.8)) };
}

/** The most a script may be, as the server's (app/schemas.py SCRIPT_LONGEST): about 8,000 words, well over 10 minutes. */
export const MOST_SCRIPT = 50_000;

/** A script box never cuts a paste (Reed, 10 Nov: a long script stopped at "Share this with ev"); it counts near the most. */
export const scriptSize = (text: string) => textSize(text, MOST_SCRIPT, { what: "script", then: "Trim it or split it.", from: MOST_SCRIPT * 0.9 });

/** "68 words · about 14 s" under the box; "0 words · 0 s" when it's empty. */
export const lengthLine = (c: ReturnType<typeof counts>) => `${c.words} word${c.words === 1 ? "" : "s"} · ${c.words ? "about " : ""}${c.seconds} s`;
/** "2 speakers · 4 lines": only when the script has dialogue. */
export const speakersLine = (c: ReturnType<typeof counts>) => (c.lines === 0 ? "" : `${c.speakers} speaker${c.speakers === 1 ? "" : "s"} · ${c.lines} line${c.lines === 1 ? "" : "s"}`);

/** The v5 script box (C_NewScript, C_ScriptWrite): a centred 680 px column, the label with the save state on its right,
 *  the words in Courier Prime, and a line under it: a note or the speakers on the left, the length on the right. */
export function ScriptBox({ label, status, note, words, ...rest }: { label: string; status?: ReactNode; note?: ReactNode; words: string } & Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "className">) {
  const id = useId();
  const viewOnly = useViewOnly();
  const c = counts(words);
  const size = scriptSize(words);
  return (
    <div className="mx-auto flex w-full max-w-[680px] flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <label htmlFor={id} className="type-card">
          {label}
        </label>
        {status}
      </div>
      <textarea
        id={id}
        rows={18}
        aria-invalid={size.over || undefined}
        className={`min-h-[420px] w-full rounded-lg border bg-surface p-4 type-script text-text placeholder:text-muted ${size.over ? "border-danger" : "border-border-strong"}`}
        {...rest}
        readOnly={rest.readOnly || viewOnly}
      />
      <div className="flex flex-wrap justify-between gap-x-4 gap-y-1 text-xs text-muted">
        {size.error ? <span role="alert" className="text-danger">{size.error}</span> : <span>{note ?? speakersLine(c)}</span>}
        <span className="tabular-nums">{size.counter ?? lengthLine(c)}</span>
      </div>
    </div>
  );
}

/** v5's Shape setting, read only on a script: each video picks its own shape when it's made (Next-Lead, 2 Nov). */
export function ShapeChip({ value }: { value?: string }) {
  return (
    value ? (
      // C_Breakdown's read-only chip: filled, with the usual shape.
      <span title="Each video picks its shape" className="inline-flex min-h-control items-center gap-1.5 rounded-md bg-surface-2 px-2.5 text-sm text-text/80 lg:min-h-control-dense">
        <span className="text-muted">Shape</span> {value} · each video picks its shape
      </span>
    ) : (
      // New script and Script: short, so the row fits at 1440 (QA-12 on #1221).
      <span title="Each video picks its shape" className="inline-flex min-h-control items-center gap-1 rounded-md border border-border px-3 text-sm lg:min-h-control-dense lg:px-2.5">
        <span className="text-muted">Shape</span> Per video<span className="sr-only">: each video picks its shape</span>
      </span>
    )
  );
}
