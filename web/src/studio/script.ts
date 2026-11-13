/** One line of a pasted script, as the box reads it: said out loud (`said`, or a `hook`), or not (`note`); a blank line
 *  has no kind. `label` is what leads a spoken line ("PAIGE (V.O.)", "Hook 2 (proven winner)"), `by` the speaker alone
 *  ("PAIGE"), `words` what is said, and `beat` marks a line of [what is going on]. */
export type Line = { line: string; kind?: "said" | "hook" | "note"; label?: string; by?: string; words?: string; beat?: boolean };

const SPOKEN = /^([A-Z][A-Z0-9 .'’-]*?(?:\s*\([^)]*\))?):\s*(.+)$/; // "PAIGE (V.O.): …"
const PART = /^((?:Hook|Body|CTA|Verse|Chorus|Bridge|Intro|Outro)\b[^:]{0,60}):\s*(.+)$/i; // "Hook 2 (proven winner): …"
const NOTE = /^(?:\[.*\]|https?:\/\/\S+|(?:Intention|Why|Inspo|Mood|Cast|Plate|Notes?|For claude|How it looks|Script|Lyrics)\b[^:]{0,28}:.*|[A-Z0-9][^a-z]{2,46}[A-Z0-9])$/;
const HEAD = /^(?:Body|Hook|CTA|V\d+|Version|Part|Scene|Verse|Chorus|Bridge|Intro|Outro)\b.{0,44}[^.!?…"”]$/i; // "Body:", "BODY (plays after each hook)"

/** Reads a pasted script line by line, the way Reed writes them. Said out loud: a line that starts with a NAME, a
 *  "Hook 1:" line, and plain paragraphs. Not said: everything down to a "Script:" line, [brackets], "Intention:" /
 *  "Why:" / "Inspo:" / "Mood:" / "Cast:" / "Plate:" lines, links, and headings ("V1 - ACTION START", "Body:").
 *  A guess for the eye only: the script is sent as pasted, and the director decides what is spoken. */
export function parse(text: string): Line[] {
  const lines = text.split("\n");
  const mark = lines.findIndex((l) => /^\s*script(\/lyrics)?:\s*$/i.test(l));
  return lines.map((line, i) => {
    const t = line.trim();
    if (!t) return { line };
    const part = PART.exec(t);
    if (part) return { line, kind: /^hook/i.test(t) ? "hook" : "said", label: part[1], words: part[2] };
    if (i <= mark) return { line, kind: "note" };
    const spoken = SPOKEN.exec(t);
    if (spoken) return { line, kind: "said", label: spoken[1], by: spoken[1].replace(/\s*\(.*/, "").trim(), words: spoken[2] };
    if (NOTE.test(t) || HEAD.test(t)) return { line, kind: "note", beat: t.startsWith("[") };
    return { line, kind: "said", words: t };
  });
}

/** The speakers named in the script, each once, as written ("STROLLER MOM"): the roles the Cast menu offers. */
export const roles = (text: string) => [...new Set(parse(text).flatMap((p) => (p.by ? [p.by] : [])))];
/** A role as the Cast menu shows it: "Stroller Mom". */
export const roleName = (role: string) => role.toLowerCase().replace(/(^|\s)\S/g, (c) => c.toUpperCase());

/** How many openings the script has, as it writes them: a line of its own ("Hook 1", "HOOK 2 (the long one)") with
 *  the opening under it, or the opening on the line ("Hook 2: If your pool has a gate…"). */
const opens = (p: Line) => p.kind === "hook" || (p.kind === "note" && /^hook\b/i.test(p.line.trim()));
export const hookCount = (text: string) => parse(text).filter(opens).length;

/** "1 clip", "3 clips". */
export const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;
/** A length in words: "45 s", "6 min 38 s". */
export const duration = (s: number) => (s < 90 ? `${s} s` : `${Math.floor(s / 60)} min${s % 60 ? ` ${s % 60} s` : ""}`);

/** The line under the script box: its voices, spoken lines and a rough length (said words at 2.5 a second, four
 *  seconds for each line of [what is going on], the first hook only), or how to write one while the box is empty. */
export function readOut(text: string): string {
  const read = parse(text).filter((p) => p.kind);
  if (!read.length) return "Put what’s going on in [brackets]. Lines that start with a name are spoken.";
  const said = read.filter((p) => p.kind === "said");
  const hooks = read.filter((p) => p.kind === "hook");
  const named = said.filter((p) => p.by);
  const words = (p: Line) => (p.words ?? "").replace(/\[[^\]]*\]/g, "").split(/\s+/).filter(Boolean).length;
  const loose = said.filter((p) => !p.by).reduce((n, p) => n + words(p), 0) + (hooks[0] ? words(hooks[0]) : 0);
  const seconds = named.reduce((n, p) => n + Math.max(3, words(p) / 2.5 + 1.5), 0) + loose / 2.5 + read.filter((p) => p.beat).length * 4;
  const voices = new Set(named.map((p) => p.by)).size + (loose ? 1 : 0);
  const lines = said.length + (hooks.length ? 1 : 0);
  const openings = read.filter(opens).length;
  const spoken = lines ? `${plural(voices, "voice")} · ${plural(lines, "spoken line")}` : "Nothing is spoken";
  return `${openings > 1 ? `${openings} hooks · ` : ""}${spoken} · about ${duration(Math.max(5, Math.round(seconds / 5) * 5))}. Your words are never changed.`;
}
