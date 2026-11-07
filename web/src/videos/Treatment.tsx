import { useState } from "react";

/** The director's creative treatment, its first move on every run (Next-Lead; #1192): the hook, the story in one line,
 *  why it holds, the beats with what each is for, and the ending. It rides on its thread move as `treatment`, with its
 *  style and format named and each beat's time (S3-02); until the server sends that field nothing shows. */
export type Beat = { id?: string; purpose: string; picture: string; start?: number; end?: number };
export type Treatment = { hook: string; logline: string; why_it_holds: string; beats: Beat[]; ending?: string; style?: string; format?: string };

/** A move's treatment, when the server sends one (#1192's ThreadItem.treatment). */
export function treatmentOf(item: object): Treatment | null {
  const t = (item as { treatment?: Partial<Treatment> | null }).treatment;
  return t && typeof t.hook === "string" && Array.isArray(t.beats) ? (t as Treatment) : null;
}

const SHOWN = 3; // beats before "+ N more beats" (board S3-02)

/** A beat's purpose as its row reads it: the name ("Hook"), then what it's for when the director says more. */
function named(purpose: string): [string, string] {
  const [name, ...rest] = purpose.split(/:\s|\s[—–-]\s|,\s/);
  const head = name.trim();
  return [head.charAt(0).toUpperCase() + head.slice(1), rest.join(", ").trim()];
}

/** The treatment as a card at its place in the thread (board S3-02): the director's line before it, then the style guide
 *  and format it follows, the story in one line, why it holds, and the beats with their times; a later one says Changed. */
export function TreatmentCard({ t, changed }: { t: Treatment; changed?: boolean }) {
  const [all, setAll] = useState(false);
  const beats = all ? t.beats : t.beats.slice(0, SHOWN);
  const more = t.beats.length - beats.length;
  const label = [t.style && `${t.style} style guide`, t.format && `${t.format} format`].filter(Boolean).join(" · ");
  return (
    <div className="space-y-1.5">
      {!changed && <p>Here’s how I’ll make it. Tell me if anything should change before I spend.</p>}
      <section aria-label="Treatment" className="space-y-2.5 rounded-lg border border-border bg-surface px-3.5 py-3">
        <div className="flex items-baseline gap-2">
          <h3 className="text-sm font-semibold">Treatment</h3>
          {label && <span className="min-w-0 truncate text-xs text-muted">{label}</span>}
          {changed && <span className="ml-auto shrink-0 rounded-sm border border-border px-1.5 text-sm leading-5 text-muted">Changed</span>}
        </div>
        <p>
          <span className="font-semibold">In one line:</span> {t.logline}
        </p>
        <p>
          <span className="font-semibold">Why it holds:</span> {t.why_it_holds}
        </p>
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">Beats</caption>
          <tbody>
            {beats.map((b, i) => {
              const [name, why] = named(b.purpose);
              return (
                <tr key={b.id ?? i} className="border-t border-border align-top">
                  <th scope="row" className="w-[7.5rem] py-2 pr-3 text-left font-semibold max-lg:w-[5.5rem]">
                    {name}
                  </th>
                  <td className="w-[4.5rem] whitespace-nowrap py-2 pr-3 text-muted tabular-nums">{b.start != null && b.end != null ? `${b.start}–${b.end} s` : ""}</td>
                  <td className="py-2">
                    {b.picture}
                    {why && <span className="block text-xs text-muted">{why}</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {more > 0 && (
          <button type="button" onClick={() => setAll(true)} className="text-xs text-muted hover:text-text max-lg:min-h-control">
            + {more} more {more === 1 ? "beat" : "beats"}
          </button>
        )}
        {(all || more === 0) && t.ending && (
          <p className="text-sm text-muted">
            <span className="font-medium">Ending:</span> {t.ending}
          </p>
        )}
      </section>
    </div>
  );
}
