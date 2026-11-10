import { useEffect, useRef, useState } from "react";
import { Skeleton, pillClass, pillStrip } from "../components";
import { OFF, lookMedia, type Look } from "../newvideo/Cards";
import type { StoryCard } from "./useDraft";

/** A story card's picture: its style's sample still, and the sample clip while `playing` (muted, looping); the style's
 *  name in small capitals and the card's title over a shade at the foot. Off on this site: greyed, and it says so. */
export function CardPicture({ card, look, playing, small }: { card: StoryCard; look?: Look; playing: boolean; small?: boolean }) {
  const m = look ? lookMedia(look) : { clip: undefined, still: undefined };
  const video = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    if (playing) void video.current?.play?.()?.catch(() => {});
  }, [playing]);
  return (
    <span className={`relative block aspect-[9/16] w-full overflow-hidden bg-surface-3 ${card.on ? "" : "[&_img]:opacity-60 [&_img]:grayscale"}`}>
      {m.still ? (
        <img src={m.still} alt="" loading="lazy" className="absolute inset-0 size-full object-cover" />
      ) : (
        // A style with no sample yet (Movie): the card's plot line stands in for the picture, never a blank box.
        !small && <span className="absolute inset-x-0 top-0 px-3 pt-3 text-left text-sm leading-snug text-muted">{card.subtitle}</span>
      )}
      {playing && m.clip && card.on && <video ref={video} src={m.clip} poster={m.still} muted loop playsInline aria-hidden className="absolute inset-0 size-full object-cover" />}
      <span className={`absolute inset-x-0 bottom-0 flex flex-col gap-0.5 text-left text-white ${small ? "px-1.5 pb-1.5 pt-6" : "px-3 pb-3 pt-12"}`} style={{ background: "var(--media-shade)" }}>
        {!small && <span className="text-[11px] font-semibold uppercase tracking-wider text-white/75">{card.style_name}</span>}
        <span className={small ? "line-clamp-2 text-[11px] font-medium leading-tight" : "text-sm font-semibold leading-snug"}>{card.title}</span>
        {!card.on && !small && <span className="self-start rounded-sm bg-black/45 px-1.5 text-xs font-medium text-white/90">{OFF}</span>}
      </span>
    </span>
  );
}

/** Story cards (Home): proven story shapes as 9:16 picture cards, filtered by style; a card plays its style's sample
 *  under the pointer or on focus, one at a time, and opens its dialog. Nothing shows when the server offers none. */
export function StoryCards({ cards, loading, looks, onOpen }: { cards: StoryCard[]; loading: boolean; looks: Look[]; onOpen: (c: StoryCard) => void }) {
  const [style, setStyle] = useState("");
  const [playing, setPlaying] = useState<string | null>(null);
  if (!loading && !cards.length) return null;
  const styles = [...new Map(cards.map((c) => [c.style, c.style_name])).entries()];
  const shown = cards.filter((c) => !style || c.style === style);
  const grid = "grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5";
  return (
    <section aria-labelledby="story-cards" className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h2 id="story-cards" className="type-section">Story cards</h2>
        <p className="text-sm text-muted">Proven story shapes. Pick one, add your product and idea.</p>
      </div>
      {loading ? (
        <div className={grid} role="status" aria-label="Loading story cards">
          {[0, 1, 2, 3, 4].map((n) => <Skeleton key={n} className={`aspect-[9/16] rounded-lg ${n === 4 ? "max-xl:hidden" : ""}`} />)}
        </div>
      ) : (
        <>
          {styles.length > 1 && (
            <div role="group" aria-label="Show cards in" className={`${pillStrip} text-sm`}>
              {[["", "All"], ...styles].map(([id, name]) => (
                <button key={id} type="button" aria-pressed={style === id} onClick={() => setStyle(id)} className={pillClass(style === id)}>
                  {name}
                </button>
              ))}
            </div>
          )}
          <ul className={grid}>
            {shown.map((c) => (
              <li key={c.id} className="min-w-0">
                <button
                  type="button"
                  aria-disabled={!c.on || undefined}
                  onClick={() => c.on && onOpen(c)}
                  onMouseEnter={() => setPlaying(c.id)}
                  onMouseLeave={() => setPlaying((p) => (p === c.id ? null : p))}
                  onFocus={() => setPlaying(c.id)}
                  onBlur={() => setPlaying((p) => (p === c.id ? null : p))}
                  className={`block w-full overflow-hidden rounded-lg border border-border transition-[border-color,box-shadow,transform] duration-(--dur-fast) ease-out ${c.on ? "hover:-translate-y-px hover:border-border-button hover:shadow-hover active:translate-y-0" : "cursor-not-allowed"}`}
                >
                  <CardPicture card={c} look={looks.find((l) => l.id === c.style)} playing={playing === c.id} />
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
