import { useState, type ReactNode } from "react";
import { CircleHelp } from "lucide-react";
import { Link } from "react-router-dom";
import { Button, Modal } from "../components";
import { BrollPicker, FormatList, StyleCards, type Look } from "../newvideo/Cards";
import type { Draft } from "./useDraft";

/** "Movie · Dialogue": the picked style and format, as the Style chip and the dialog's foot say them. */
export const styleWords = (d: Pick<Draft, "look" | "format">) => [d.look?.name, d.format?.name].filter(Boolean).join(" · ");

/** Styles: how the words are delivered (the formats, a radio list) and how it looks (the styles, picture tiles that play
 *  their sample and name their B-roll look). A format with a host offers Change B-roll look…. From a saved script both
 *  are the script's own, shown locked. A pick is kept at once; Done closes. */
export function StylesDialog({ draft, onClose }: { draft: Draft; onClose: () => void }) {
  const { formats, looks, format, look, only, unused, broll, fixed, owner, pick } = draft;
  const [brolling, setBrolling] = useState(false);
  const foot = (
    <div className="flex items-center gap-3">
      <p className="min-w-0 flex-1 truncate text-sm text-muted">
        {fixed ? "From the script" : "Picked"}: <b className="font-semibold text-text">{styleWords(draft) || "nothing yet"}</b>
      </p>
      <Button onClick={onClose}>Done</Button>
    </div>
  );
  return (
    <Modal title="Styles" onClose={onClose} footer={foot}>
      <div className="flex flex-col gap-6 md:flex-row">
        <section aria-label="Format" className="flex shrink-0 flex-col gap-2 md:w-60">
          <h3 className="text-sm font-semibold">{fixed ? "From the script" : "How the words are delivered"}</h3>
          <FormatList formats={formats} value={format?.id ?? ""} onPick={(type) => pick({ type })} locked={!!fixed} />
        </section>
        <section aria-label="Style" className="relative flex min-w-0 flex-1 flex-col gap-2">
          <div className="flex flex-wrap items-baseline gap-x-2">
            <h3 className="text-sm font-semibold">How it looks</h3>
            <span className="text-sm text-muted">The B-roll follows the style.</span>
            <span className="flex-1" />
            {format?.host && look && (
              <button type="button" aria-expanded={brolling} onClick={() => setBrolling(!brolling)} className="inline-flex min-h-control items-center text-sm font-medium text-accent-text underline-offset-2 hover:underline lg:min-h-0">
                Change B-roll look…
              </button>
            )}
            {brolling && look && <BrollPicker looks={looks} style={look} value={broll} onPick={(b) => (pick({ broll_look: b }), setBrolling(false))} onClose={() => setBrolling(false)} />}
          </div>
          {unused && <p role="status" className="text-sm text-warning">{only(unused)} The style is {look?.name ?? "not picked"} for now.</p>}
          <StyleCards looks={looks} value={look?.id ?? ""} onPick={(l) => pick({ look: l, broll_look: null })} locked={!!fixed} only={only} />
        </section>
      </div>
      <OffNote formats={formats} looks={looks} owner={owner} />
    </Modal>
  );
}

/** Why a format or style is off here (S2-03): Song's music provider, a style the owner hasn't switched on. Each says
 *  whether it is the format or the style, as Zack D is both. */
function OffNote({ formats, looks, owner }: { formats: { name: string; off?: string | null }[]; looks: Look[]; owner: boolean }) {
  const parts: ReactNode[] = [];
  for (const f of formats.filter((x) => x.off))
    parts.push(<span key={f.name}>The <b className="font-semibold">{f.name}</b> format {f.off === "off" ? "is off on this site" : `is coming next: ${f.off}`}. </span>);
  const off = looks.filter((l) => !l.on);
  if (off.length)
    parts.push(
      <span key="looks">
        The{" "}
        {off.map((l, i) => (
          <span key={l.id}>
            {i > 0 && (i === off.length - 1 ? " and " : ", ")}
            <b className="font-semibold">{l.name}</b>
          </span>
        ))}{" "}
        {off.length === 1 ? "style is" : "styles are"} off on this site; the owner turns {off.length === 1 ? "it" : "them"} on in Settings → Looks.
      </span>,
    );
  if (!parts.length) return null;
  return (
    <div className="mt-5 flex items-start gap-2.5 rounded-lg border border-border bg-surface-2/60 px-3.5 py-3 text-sm text-muted">
      <CircleHelp size={16} strokeWidth={1.75} aria-hidden className="mt-px shrink-0 text-muted" />
      <span className="min-w-0 flex-1 [&_b]:text-text">{parts}</span>
      {owner && (
        <Link to="/settings?tab=looks" className="-my-2.5 inline-flex min-h-11 shrink-0 items-center font-medium text-accent-text underline-offset-2 hover:underline lg:my-0 lg:min-h-0">
          Settings → Looks
        </Link>
      )}
    </div>
  );
}
