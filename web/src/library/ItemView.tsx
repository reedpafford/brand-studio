import type { ReactNode } from "react";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { Button } from "../components";

type Item = components["schemas"]["ItemOut"];

/** One section of the item page: a title, an optional quiet press on the right, then its content (v5 G boards). */
function Section({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section aria-label={title} className="space-y-3 border-t border-border py-4">
      <div className="flex min-h-control items-center justify-between gap-2">
        <h2 className="text-sm font-medium">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

const Thumb = ({ id, alt, label, tall }: { id: number; alt: string; label?: string; tall?: boolean }) => (
  <figure className="relative">
    <img src={fileUrl(id)} alt={alt} className={`${tall ? "h-30" : "h-24"} w-24 rounded-md border border-border bg-surface-2 object-cover`} />
    {label && <figcaption className="absolute bottom-1.5 left-1.5 rounded-sm bg-black/60 px-1.5 py-0.5 text-xs text-white">{label}</figcaption>}
  </figure>
);

/** A character, place or prop as a page (v5 G_Character, G_Place, G_Prop): its name, its words, then one section each for its
 *  pictures, voice and outfits (a character), what it is and its claim (a prop), and its brands. Every change is made
 *  under Edit, so each section's press opens it. */
export function ItemView({ item, kind, shared, brandNames, onEdit }: { item: Item; kind: "character" | "place" | "prop"; shared: string[]; brandNames: string[]; onEdit: () => void }) {
  const pictures = item.image_file_ids ?? [];
  const outfits = item.outfits ?? [];
  const quiet = (label: string) => (
    <Button variant="ghost" dense onClick={onEdit}>
      {label}
    </Button>
  );
  return (
    <div>
      <div className="space-y-1 pb-4">
        <h1 className="type-page">{item.name}</h1>
        {item.notes ? <p className="whitespace-pre-line text-text">{item.notes}</p> : <p className="text-muted">No description yet.</p>}
        {shared.length > 0 && <p className="text-sm text-muted">Shared with {shared.join(", ")}. Changes apply there too.</p>}
      </div>
      {kind === "prop" && (
        <>
          <Section title="What it is">
            <p>{item.short_description || <span className="text-muted">Not said yet.</span>}</p>
          </Section>
          <Section title="Main claim">
            <p>{item.main_claim || <span className="text-muted">Not said yet.</span>}</p>
            {(item.advice ?? []).map((a) => (
              <p key={a} className="text-sm text-warning">{a}</p>
            ))}
          </Section>
        </>
      )}
      {kind === "character" && (
        <>
          <Section title="Pictures" action={quiet("Add image")}>
            {item.source_photo_file_id || pictures.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {item.source_photo_file_id && <Thumb id={item.source_photo_file_id} alt={`${item.name}, source photo`} label="Source photo" />}
                {pictures.map((id, n) => (
                  <Thumb key={id} id={id} alt={`${item.name} ${n + 1}`} />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted">No pictures yet.</p>
            )}
            {item.source_photo_file_id && <p className="text-sm text-muted">The source photo makes the sheet; it isn't used in videos.</p>}
          </Section>
          <Section title="Voice sample" action={quiet(item.voice_file_id ? "Replace voice" : "Add voice")}>
            {item.voice_file_id ? <audio controls src={fileUrl(item.voice_file_id)} aria-label="Play the voice sample" className="w-full max-w-md" /> : <p className="text-sm text-muted">No voice sample yet.</p>}
          </Section>
          <Section title="Outfits" action={quiet("Add outfit")}>
            {outfits.length > 0 ? (
              <ul className="flex flex-wrap gap-4">
                {outfits.map((o, i) => (
                  <li key={i} className="space-y-1.5">
                    {o.file_ids[0] ? <Thumb id={o.file_ids[0]} alt={o.name} tall /> : <div className="h-30 w-24 rounded-md border border-border bg-surface-2" aria-hidden />}
                    <p className="text-sm text-muted">{o.name}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted">No outfits yet.</p>
            )}
          </Section>
        </>
      )}
      <Section title="Brands">
        <div className="flex flex-wrap gap-2">
          {brandNames.map((n) => (
            <span key={n} className="inline-flex h-7 items-center rounded-sm border border-border-strong px-2 text-sm">{n}</span>
          ))}
        </div>
      </Section>
    </div>
  );
}
