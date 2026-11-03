import { useRef, useState, type ReactNode } from "react";
import { Pause, Play } from "lucide-react";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { Link, useParams } from "react-router-dom";
import { Button } from "../components";

type Item = components["schemas"]["ItemOut"];
type UsedIn = components["schemas"]["UsedIn"];

// G_Character's Used in: each video with where it is ("Delivered", "Working"), in plain words.
const USED: Record<UsedIn["status"], { label: string; dot: string }> = {
  needs_you: { label: "Needs attention", dot: "bg-warning" },
  making: { label: "Working", dot: "bg-accent" },
  done: { label: "Delivered", dot: "bg-success" },
};

/** One section of the item page: a title, an optional quiet press on the right, then its content (v5 G boards). */
function Section({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    // v5 G_Prop: the title sits about 8 px over its words; a section with a press keeps a 44 px row for it.
    <section aria-label={title} className="space-y-2 border-t border-border py-4">
      <div className={`flex items-center justify-between gap-2 ${action ? "min-h-control" : ""}`}>
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
        {/* A product's line leads, then its notes (G_Prop: "Grain-free salmon kibble for picky dogs. Label always readable…"). */}
        {kind === "prop" && item.short_description && <p className="text-text">{item.short_description}</p>}
        {item.notes ? <p className="whitespace-pre-line text-text">{item.notes}</p> : !(kind === "prop" && item.short_description) && <p className="text-muted">No description yet.</p>}
        {shared.length > 0 && <p className="text-sm text-muted">Shared with {shared.join(", ")}. Changes apply there too.</p>}
      </div>
      {kind === "prop" && (
        <>
          <Section title="Main claim">
            <p>{item.main_claim || <span className="text-muted">Not said yet.</span>}</p>
            {(item.advice ?? []).map((a) => (
              <p key={a} className="text-sm text-warning">{a}</p>
            ))}
          </Section>
        </>
      )}
      {kind !== "prop" && (
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
      )}
      {kind === "character" && (
        <>
          <Section title="Voice sample" action={quiet(item.voice_file_id ? "Replace voice" : "Add voice")}>
            {item.voice_file_id ? <VoicePlay fileId={item.voice_file_id} /> : <p className="text-sm text-muted">No voice sample yet.</p>}
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
      {/* G_Character has only the "Shared with" line; a place and a prop list their brands. */}
      {kind !== "character" && <Section title="Brands">
        <div className="flex flex-wrap gap-2">
          {brandNames.map((n) => (
            <span key={n} className="inline-flex h-7 items-center rounded-sm border border-border-strong px-2 text-sm">{n}</span>
          ))}
        </div>
      </Section>}
      <UsedInSection used={item.used_in ?? []} />
    </div>
  );
}

/** The videos that use this item (#1212), each linked, with where it is. */
function UsedInSection({ used }: { used: UsedIn[] }) {
  const { brandId } = useParams();
  return (
    <Section title="Used in">
      {used.length === 0 ? (
        <p className="text-sm text-muted">No videos yet.</p>
      ) : (
        <ul className="space-y-1">
          {used.map((u) => (
            <li key={u.project_id} className="flex flex-wrap items-center justify-between gap-x-3">
              <Link to={`/b/${brandId}/projects/${u.project_id}`} className="inline-flex min-h-11 min-w-0 items-center break-words text-sm hover:underline lg:min-h-8">{u.name}</Link>
              <span className="inline-flex items-center gap-1.5 text-xs text-muted">
                <span aria-hidden className={`size-2 rounded-full ${USED[u.status].dot}`} />
                {USED[u.status].label}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

/** The voice sample as one press (G_Character: "▶ Play · 0:12"), not the browser's audio bar. */
function VoicePlay({ fileId }: { fileId: number }) {
  const audio = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [secs, setSecs] = useState<number | null>(null);
  const time = (n: number) => `${Math.floor(n / 60)}:${String(Math.round(n % 60)).padStart(2, "0")}`;
  return (
    <div className="flex items-center gap-3">
      <Button variant="secondary" icon={playing ? Pause : Play} aria-label={playing ? "Pause the voice sample" : "Play the voice sample"} onClick={() => (playing ? audio.current?.pause() : void audio.current?.play())}>
        {playing ? "Pause" : "Play"}
      </Button>
      {secs !== null && <span className="text-sm tabular-nums text-muted">{time(secs)}</span>}
      <audio ref={audio} src={fileUrl(fileId)} preload="metadata" onLoadedMetadata={(e) => Number.isFinite(e.currentTarget.duration) && setSecs(e.currentTarget.duration)} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} className="hidden" />
    </div>
  );
}
