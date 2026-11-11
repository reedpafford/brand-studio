import { useEffect, useRef, useState } from "react";
import { Check as CheckIcon, CircleCheckBig, Pause, Play, X } from "lucide-react";
import { fileUrl } from "../api/upload";
import type { components } from "../api/schema";
import { Button } from "../components";
import type { Format } from "../scripts/useFormats";

export type Look = components["schemas"]["LookOut"];
/** S2-03: Song's music provider is off ("coming next"); a format or style off on this site. */
const SOON = "coming next";
const OFF = "Off on this site";

/** A look's card pictures: the owner's approved sample (Settings → Looks) once there is one, else the 3 Nov test sample
 *  shipped with the site; `tag` says "Test sample" on the paid tests, never on the site's own frame (House). A sample the
 *  test site's stand-ins made (a plain grey picture) never hides the real test sample. */
export function lookMedia(l: Look) {
  if (l.sample_clip_id && !l.sample_stand_in) return { clip: fileUrl(l.sample_clip_id), still: l.sample_still_id ? fileUrl(l.sample_still_id) : undefined, tag: false };
  return { clip: l.test_clip ? `/api/looks/${l.id}/test-sample.mp4` : undefined, still: l.test_still ? `/api/looks/${l.id}/test-sample.jpg` : undefined, tag: !!l.test_tag };
}
/** "B-roll: near-real inserts" from its guide's `broll:` line ("Near-real inserts"). */
export const brollLine = (l: Look) => (l.broll ? `B-roll: ${l.broll.charAt(0).toLowerCase()}${l.broll.slice(1)}` : "");
/** The card's short line, else its blurb (cut to two lines) until the guide has one. */
const sub = (x: { card?: string; blurb: string }) => x.card || x.blurb;

const tag = <span className="absolute left-2 top-2 rounded-sm bg-black/45 px-1.5 text-xs font-medium text-white/90 backdrop-blur-sm">Test sample</span>;

/** A picture that can play its clip: one at a time on the page (`playing`), muted, looping, with a progress line. */
function Sample({ name, clip, still, testTag, playing, onPlay, w, h }: { name: string; clip?: string; still?: string; testTag: boolean; playing: boolean; onPlay: () => void; w: string; h: string }) {
  const video = useRef<HTMLVideoElement>(null);
  const [at, setAt] = useState(0);
  useEffect(() => {
    const v = video.current;
    if (!v) return;
    if (playing) void v.play?.()?.catch(() => {});
    else v.pause?.();
  }, [playing]);
  return (
    <div className={`relative ${w} ${h} shrink-0 overflow-hidden bg-surface-3`}>
      {clip ? (
        <video ref={video} src={clip} poster={still} muted loop playsInline preload="none" aria-label={`${name} sample`} className="size-full object-cover transition-transform duration-(--dur-slow) ease-out group-hover:scale-[1.03]" onTimeUpdate={(e) => setAt(e.currentTarget.currentTime / (e.currentTarget.duration || 1))} />
      ) : still ? (
        <img src={still} alt="" className="size-full object-cover transition-transform duration-(--dur-slow) ease-out group-hover:scale-[1.03]" />
      ) : (
        // A style with no sample made or shipped yet (Movie, MAIN's run 276): said, never a blank box.
        <span className="grid size-full place-items-center px-2 text-center text-xs text-muted">No sample yet</span>
      )}
      {(clip || still) && testTag && tag}
      {clip && (
        <button type="button" aria-label={`${playing ? "Pause" : "Play"} the ${name} sample`} onClick={(e) => (e.stopPropagation(), onPlay())} className="absolute inset-0 grid place-items-center text-white">
          <span className={`grid size-11 place-items-center rounded-full bg-black/35 ring-1 ring-white/25 backdrop-blur-md transition-[opacity,transform,background-color] duration-(--dur-fast) ease-out group-hover:scale-105 group-hover:bg-black/50 group-hover:opacity-100 lg:size-10 ${playing ? "opacity-100" : "opacity-80 lg:opacity-0 lg:group-focus-within:opacity-100"}`}>{playing ? <Pause size={14} aria-hidden /> : <Play size={14} aria-hidden />}</span>
        </button>
      )}
      {playing && (
        <span aria-hidden className="absolute inset-x-1.5 bottom-1.5 h-1 overflow-hidden rounded-xs bg-white/30">
          <i className="block h-full bg-white" style={{ width: `${Math.round(at * 100)}%` }} />
        </span>
      )}
    </div>
  );
}

// A card or tile lifts under the pointer; the picked one has an indigo edge. An off one keeps its words readable and greys its
// picture. Its corners and ground are its own.
const card = (sel: boolean, off: boolean) =>
  `group flex shrink-0 flex-col overflow-hidden border text-left transition-[border-color,box-shadow,transform] duration-(--dur-fast) ease-out ${sel ? "border-accent ring-2 ring-accent" : off ? "border-border" : "border-border hover:-translate-y-0.5 hover:border-border-button hover:shadow-hover active:translate-y-0"} ${off ? "cursor-not-allowed [&_img]:opacity-60 [&_img]:grayscale [&_video]:opacity-60 [&_video]:grayscale" : ""}`;
// A gallery poster: no edge line of its own (the picture is the edge); it lifts under the pointer, and the picked one
// has the indigo ring set off from the picture.
const poster = (sel: boolean, off: boolean) =>
  `group flex shrink-0 flex-col overflow-hidden border text-left shadow-soft transition-[box-shadow,transform] duration-(--dur) ease-out ${sel ? "border-accent ring-2 ring-accent ring-offset-2 ring-offset-bg" : off ? "border-transparent" : "border-transparent hover:-translate-y-1 hover:shadow-hover active:translate-y-0"} ${off ? "cursor-not-allowed [&_img]:opacity-60 [&_img]:grayscale" : ""}`;
const Check = () => <CircleCheckBig size={14} strokeWidth={2} aria-hidden className="animate-fade shrink-0 text-accent" />;

/** The formats as a radio list (the Styles dialog): each with its line; Song says why it is "coming next" while its
 *  music provider is off, a format off in its guide is "Off on this site". `locked`: a saved script's own, shown not picked. */
export function FormatList({ formats, value, onPick, locked }: { formats: Format[]; value: string; onPick: (id: string) => void; locked?: boolean }) {
  return (
    <div role="radiogroup" aria-label="Format" className="flex flex-col gap-1">
      {formats.map((f) => {
        const off = f.off ? (f.off === "off" ? OFF : SOON) : null;
        const sel = f.id === value;
        const no = !!off || (locked && !sel);
        return (
          <button key={f.id} type="button" role="radio" aria-checked={sel} aria-disabled={no || undefined} onClick={() => !no && onPick(f.id)} className={`flex min-h-control items-start gap-2.5 rounded-md border px-2.5 py-2 text-left transition-colors duration-(--dur-fast) ${sel ? "border-accent-line bg-accent-soft" : `border-transparent ${no ? "" : "hover:bg-surface-2"}`} ${no ? "cursor-not-allowed" : ""} ${locked && !sel ? "opacity-55" : ""}`}>
            <span aria-hidden className={`mt-0.5 grid size-4 shrink-0 place-items-center rounded-full border ${sel ? "border-accent bg-accent text-on-accent" : "border-border-strong bg-surface"}`}>{sel && <CheckIcon size={12} />}</span>
            <span className="flex min-w-0 flex-1 flex-col gap-0.5">
              <span className="flex flex-wrap items-center gap-x-2">
                <span className={`text-sm font-semibold ${off ? "text-muted" : ""}`}>{f.name}</span>
                {off && <span className="rounded-sm bg-surface-2 px-1.5 text-xs font-medium text-muted">{off}</span>}
              </span>
              <span className="text-xs text-muted">{off === SOON ? `${f.off!.charAt(0).toUpperCase()}${f.off!.slice(1)}.` : sub(f)}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

/** Style tiles (the Styles dialog): a sample that plays (one at a time), the style's line and its B-roll look; the picked
 *  one has the indigo ring; a style off on this site is greyed with "Off on this site" (S2-03), and one not made in the
 *  picked format says why (`only`). */
export function StyleCards({ looks, value, onPick, locked, only }: { looks: Look[]; value: string; onPick: (id: string) => void; locked?: boolean; only?: (l: Look) => string | null }) {
  const [playing, setPlaying] = useState<string | null>(null);
  return (
    <div role="radiogroup" aria-label="Style" className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-4">
      {looks.map((l) => {
        const m = lookMedia(l);
        const sel = l.id === value;
        const why = only?.(l) ?? null;
        const can = l.on && !locked && !why;
        // The picture plays its sample; the words under it pick the style (a radio holds no other button).
        return (
          <div key={l.id} className={`${card(sel, !l.on || !!why)} w-full rounded-xl bg-surface ${locked && !sel ? "opacity-55" : ""}`}>
            {/* A picture with a clip plays it; one with none picks the style, like the words under it (a dead press, 11 Nov). */}
            <div onClick={() => !m.clip && can && onPick(l.id)} className={!m.clip && can ? "cursor-pointer" : ""}>
              <Sample name={l.name} clip={m.clip} still={m.still} testTag={m.tag} playing={playing === l.id} onPlay={() => setPlaying(playing === l.id ? null : l.id)} w="w-full" h="aspect-[4/5]" />
            </div>
            <button type="button" role="radio" aria-checked={sel} aria-disabled={!can || undefined} title={why ?? undefined} onClick={() => can && onPick(l.id)} className={`flex min-h-control flex-1 flex-col gap-0.5 px-3 py-2.5 text-left ${can ? "" : "cursor-default"}`}>
              <span className="flex items-center gap-1">
                <span className={`text-sm font-semibold ${l.on && !why ? "" : "text-muted"}`}>{l.name}</span>
                <span className="flex-1" />
                {sel && <Check />}
              </span>
              <span className="line-clamp-2 text-xs text-muted">{sub(l)}</span>
              {l.broll && <span className="text-xs text-muted">{brollLine(l)}</span>}
              {!l.on && <span className="mt-auto self-start rounded-sm bg-surface-2 px-1.5 text-xs font-medium text-muted">{OFF}</span>}
              {l.on && why && <span className="mt-1 text-xs text-muted">{why}</span>}
            </button>
          </div>
        );
      })}
    </div>
  );
}

/** The styles as a gallery (Home, under the box): 9:16 posters, the ones switched on first, arriving one after another.
 *  A poster shows its sample still and plays the sample clip under the pointer or on focus (muted, one at a time), with
 *  the style's name large and its line over a shade at the foot; under the pointer it lifts, its B-roll look slides in
 *  and its own picture glows out from under it. A style with no sample is a text poster, its line on a tint. Pressing
 *  one picks the style (the indigo ring and a check); one off on this site is greyed and says so. */
export function StyleGallery({ looks, value, onPick }: { looks: Look[]; value: string; onPick: (l: Look) => void }) {
  const [playing, setPlaying] = useState<string | null>(null);
  return (
    <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 lg:gap-4">
      {[...looks.filter((l) => l.on), ...looks.filter((l) => !l.on)].map((l, i) => {
        const m = lookMedia(l);
        const sel = l.id === value;
        const play = (on: boolean) => setPlaying((p) => (on ? l.id : p === l.id ? null : p));
        return (
          <li key={l.id} className="animate-rise group/poster relative min-w-0" style={{ animationDelay: `${i * 45}ms` }}>
            {/* The poster's own colours, soft and low under it: only for the one under the pointer or picked. */}
            {m.still && l.on && (
              <span aria-hidden className={`pointer-events-none absolute inset-x-5 bottom-0 top-8 translate-y-3 transition-opacity duration-(--dur) ease-out ${sel ? "opacity-45" : "opacity-0 group-hover/poster:opacity-55"}`}>
                <img src={m.still} alt="" className="size-full rounded-xl object-cover blur-xl saturate-150" />
              </span>
            )}
            <button type="button" aria-pressed={sel} aria-disabled={!l.on || undefined} onClick={() => l.on && onPick(l)} onMouseEnter={() => play(true)} onMouseLeave={() => play(false)} onFocus={() => play(true)} onBlur={() => play(false)} className={`${poster(sel, !l.on)} relative aspect-[9/16] w-full rounded-xl ${m.still ? "bg-surface-3" : l.on ? "bg-accent-soft text-accent-text" : "bg-surface-2 text-muted"}`}>
              {m.still && <img src={m.still} alt="" loading="lazy" className="absolute inset-0 size-full object-cover transition-transform duration-(--dur-slow) ease-out group-hover:scale-[1.04]" />}
              {playing === l.id && m.clip && l.on && <video ref={(v) => void v?.play?.()?.catch(() => {})} src={m.clip} poster={m.still} muted loop playsInline aria-hidden className="animate-fade absolute inset-0 size-full scale-[1.04] object-cover" />}
              <span className="absolute inset-x-0 bottom-0 flex flex-col bg-(image:--media-shade) px-4 pb-4 pt-20 text-white">
                <span className="type-headline text-balance">{l.name}</span>
                {m.still && <span className="line-clamp-2 pt-0.5 text-sm text-white/85">{sub(l)}</span>}
                {m.still && l.broll && l.on && (
                  <span className="grid grid-rows-[0fr] opacity-0 transition-[grid-template-rows,opacity] duration-(--dur) ease-out group-hover:grid-rows-[1fr] group-hover:opacity-100 group-focus-visible:grid-rows-[1fr] group-focus-visible:opacity-100">
                    <span className="overflow-hidden">
                      <span className="block pt-2 text-xs text-white/70">{brollLine(l)}</span>
                    </span>
                  </span>
                )}
                {!l.on && <span className="mt-1 self-start rounded-sm bg-black/45 px-1.5 text-xs font-medium text-white/90">{OFF}</span>}
              </span>
              {!m.still && (
                <span className="absolute inset-x-0 bottom-20 top-0 flex items-center px-4">
                  <span className="line-clamp-5 text-sm font-medium leading-snug sm:text-base sm:leading-snug">{sub(l)}</span>
                </span>
              )}
              {sel && (
                <span className="animate-pop absolute right-3 top-3 grid size-7 place-items-center rounded-full bg-accent text-on-accent shadow-press">
                  <CheckIcon size={16} strokeWidth={2.5} aria-hidden />
                </span>
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

/** Home's small stage over the headline: the picked style's sample playing (muted, looping; a still when motion is
 *  reduced) between its two neighbours, fanned like a hand of posters. Decoration only: the gallery below does the picking. */
export function StyleFan({ looks, look }: { looks: Look[]; look?: Look }) {
  const shown = looks.filter((l) => l.on && lookMedia(l).still);
  const at = shown.findIndex((l) => l.id === look?.id);
  if (at < 0 || shown.length < 3) return null;
  const side = (step: number) => lookMedia(shown[(at + step + shown.length) % shown.length]).still;
  const mid = lookMedia(shown[at]);
  const still = typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
  const frame = "absolute bottom-0 aspect-[9/16] overflow-hidden rounded-lg border border-white/70 bg-surface-3 shadow-raised";
  return (
    <div aria-hidden className="relative mx-auto h-44 w-72">
      <img key={`l${shown[at].id}`} src={side(-1)} alt="" className={`animate-fade ${frame} left-6 h-36 origin-bottom-right -rotate-[9deg] object-cover opacity-90`} />
      <img key={`r${shown[at].id}`} src={side(1)} alt="" className={`animate-fade ${frame} right-6 h-36 origin-bottom-left rotate-[9deg] object-cover opacity-90`} />
      <span key={shown[at].id} className={`animate-rise ${frame} left-1/2 h-44 -translate-x-1/2`}>
        {mid.clip && !still ? <video src={mid.clip} poster={mid.still} muted loop playsInline autoPlay className="size-full object-cover" /> : <img src={mid.still} alt="" className="size-full object-cover" />}
      </span>
    </div>
  );
}

/** "Change B-roll look…" (S-gaps-01, 1): the style's own B-roll first, then the other styles' B-roll looks; Use this
 *  look keeps the host, voice and cast in the style. Only for a format with a host. */
export function BrollPicker({ looks, style, value, onPick, onClose }: { looks: Look[]; style: Look; value: string | null; onPick: (id: string | null) => void; onClose: () => void }) {
  const [picked, setPicked] = useState(value ?? style.id);
  const rows = [style, ...looks.filter((l) => l.id !== style.id && l.on)];
  const box = useRef<HTMLElement>(null);
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    box.current?.querySelector<HTMLElement>("[aria-checked=true]")?.focus();
    return () => opener?.focus?.();
  }, []);
  return (
    <section ref={box} role="dialog" aria-label="B-roll look for this video" onKeyDown={(e) => e.key === "Escape" && (e.stopPropagation(), onClose())} className="absolute right-0 top-7 z-30 w-full max-w-[600px] rounded-lg border border-border bg-surface shadow-raised">
      <div className="flex items-center border-b border-border px-3 py-2.5">
        <h3 className="text-sm font-semibold">B-roll look for this video</h3>
        <span className="flex-1" />
        <button type="button" aria-label="Close" onClick={onClose} className="grid size-6 place-items-center rounded-md text-muted hover:bg-surface-2">
          <X size={14} aria-hidden />
        </button>
      </div>
      <div className="flex flex-col gap-3 p-3">
        <p className="text-sm text-muted">The B-roll follows the style unless you pick another look here. The presenter and voice don’t change.</p>
        <div role="radiogroup" aria-label="B-roll look" className="flex items-start gap-2 overflow-x-auto">
          {rows.map((l) => {
            const m = lookMedia(l);
            const own = l.id === style.id;
            return (
              <button key={l.id} type="button" role="radio" aria-checked={picked === l.id} onClick={() => setPicked(l.id)} className="flex w-[112px] shrink-0 flex-col gap-1 text-left">
                <span className={`block h-[150px] w-[112px] overflow-hidden rounded-md bg-surface-3 ${picked === l.id ? "outline-2 outline-offset-1 outline-accent" : ""}`}>{m.still && <img src={m.still} alt="" className="size-full object-cover" />}</span>
                <span className="text-sm font-semibold">{l.broll || l.name}</span>
                <span className="text-xs text-muted">{own ? `${l.name}’s own · default` : `from ${l.name}`}</span>
              </button>
            );
          })}
        </div>
        <div className="flex items-center gap-2">
          <Button dense onClick={() => onPick(picked === style.id ? null : picked)}>Use this look</Button>
          <Button variant="secondary" dense onClick={() => onPick(null)}>Back to the style’s own</Button>
          <span className="flex-1" />
          <span className="text-xs text-muted">The price on Make it updates</span>
        </div>
      </div>
    </section>
  );
}
