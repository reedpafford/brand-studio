/** The director's creative treatment, its first move on every run (Next-Lead; #1192): the hook, the story in one line,
 *  why it holds, the beats with what each is for, and the ending. It rides on its thread move as `treatment`; until the
 *  server sends that field nothing shows. */
export type Treatment = { hook: string; logline: string; why_it_holds: string; beats: { id?: string; purpose: string; picture: string }[]; ending?: string };

/** A move's treatment, when the server sends one (#1192's ThreadItem.treatment). */
export function treatmentOf(item: object): Treatment | null {
  const t = (item as { treatment?: Partial<Treatment> | null }).treatment;
  return t && typeof t.hook === "string" && Array.isArray(t.beats) ? (t as Treatment) : null;
}

/** The treatment as a card at its place in the thread; a later one says Changed. */
export function TreatmentCard({ t, changed }: { t: Treatment; changed?: boolean }) {
  return (
    <section aria-label="Treatment" className="space-y-3 rounded-lg border border-border bg-surface px-4 py-3.5">
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-semibold">{t.hook}</h3>
        {changed && <span className="shrink-0 rounded-sm border border-border px-1.5 text-sm leading-5 text-muted">Changed</span>}
      </div>
      <p>{t.logline}</p>
      <p className="text-muted">
        <span className="font-medium">Why it holds:</span> {t.why_it_holds}
      </p>
      <ol className="space-y-1.5">
        {t.beats.map((b, i) => (
          <li key={b.id ?? i} className="grid grid-cols-[1.25rem_minmax(0,1fr)] gap-2">
            <span className="text-muted tabular-nums">{i + 1}</span>
            <span>
              {b.picture}
              <span className="block text-sm text-muted">{b.purpose}</span>
            </span>
          </li>
        ))}
      </ol>
      {t.ending && <p className="text-sm text-muted">{t.ending}</p>}
    </section>
  );
}
