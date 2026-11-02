/** The director's creative treatment, its first move on every run (Next-Lead): the hook, the story in one line, why it
 *  holds, and the beats with what each is for. The server's field is still to come; this is fed by a small typed prop
 *  and shows only when the field is there. */
export type Treatment = { hook: string; story: string; why: string; beats: { text: string; purpose: string }[]; changed?: boolean };

/** Whatever treatments the server sends with a video, oldest first (none until its field lands). */
export const treatmentsOf = (x: unknown): Treatment[] => {
  const t = (x as { treatments?: Treatment[]; treatment?: Treatment | null } | null | undefined) ?? {};
  return t.treatments ?? (t.treatment ? [t.treatment] : []);
};

export function TreatmentCard({ t }: { t: Treatment }) {
  return (
    <section aria-label="Treatment" className="space-y-3 rounded-lg border border-border bg-surface px-4 py-3.5">
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-semibold">{t.hook}</h3>
        {t.changed && <span className="shrink-0 rounded-sm border border-border px-1.5 text-sm leading-5 text-muted">Changed</span>}
      </div>
      <p>{t.story}</p>
      <p className="text-muted">
        <span className="font-medium">Why it holds:</span> {t.why}
      </p>
      <ol className="space-y-1.5">
        {t.beats.map((b, i) => (
          <li key={i} className="grid grid-cols-[1.25rem_minmax(0,1fr)] gap-2">
            <span className="text-muted tabular-nums">{i + 1}</span>
            <span>
              {b.text}
              <span className="block text-sm text-muted">{b.purpose}</span>
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
