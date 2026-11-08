import { useEffect, useRef, useState } from "react";
import { CircleCheckBig, Pause, Play, X } from "lucide-react";
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

const tag = <span className="absolute left-1.5 top-1.5 rounded-[3px] bg-black/60 px-1.5 text-xs/[14px] font-semibold text-white">Test sample</span>;

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
        <video ref={video} src={clip} poster={still} muted loop playsInline preload="none" aria-label={`${name} sample`} className="size-full object-cover" onTimeUpdate={(e) => setAt(e.currentTarget.currentTime / (e.currentTarget.duration || 1))} />
      ) : still ? (
        <img src={still} alt="" className="size-full object-cover" />
      ) : null}
      {(clip || still) && testTag && tag}
      {clip && (
        <button type="button" aria-label={`${playing ? "Pause" : "Play"} the ${name} sample`} onClick={(e) => (e.stopPropagation(), onPlay())} className="absolute inset-0 grid place-items-center text-white">
          <span className="grid size-11 place-items-center rounded-full bg-black/45 backdrop-blur-md">{playing ? <Pause size={14} aria-hidden /> : <Play size={14} aria-hidden />}</span>
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

const card = (sel: boolean, off: boolean) =>
  `flex shrink-0 flex-col overflow-hidden rounded-lg border bg-surface text-left ${sel ? "border-accent shadow-[0_0_0_1px_var(--accent)]" : "border-border hover:border-border-strong"} ${off ? "cursor-not-allowed opacity-55" : ""}`;
const Check = () => <CircleCheckBig size={14} aria-hidden className="shrink-0 text-accent-text" />;

/** A phone's card row scrolls the picked card into view (P-03). */
function useShown(value: string, small?: boolean) {
  const row = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (small) row.current?.querySelector<HTMLElement>("[aria-checked=true]")?.scrollIntoView?.({ inline: "nearest", block: "nearest" });
  }, [value, small]);
  return row;
}

/** Format cards (S2): picture, name, its line; Song "coming next" while its music provider is off, a format off in its
 *  guide "Off on this site". `small`: the phone's (P-03), name only. `locked`: a saved script's own, shown not picked. */
export function FormatCards({ formats, value, onPick, small, locked }: { formats: Format[]; value: string; onPick: (id: string) => void; small?: boolean; locked?: boolean }) {
  const shown = useShown(value + formats.length, small);
  return (
    <div ref={shown} role="radiogroup" aria-label="Format" className={`flex gap-3 ${small ? "-mx-3.5 overflow-x-auto px-3.5 pb-1" : "flex-wrap"}`}>
      {formats.map((f) => {
        const off = f.off ? (f.off === "off" ? OFF : SOON) : null;
        const sel = f.id === value;
        return (
          <button key={f.id} type="button" role="radio" aria-checked={sel} aria-disabled={!!off || (locked && !sel) || undefined} title={f.off && f.off !== "off" ? `${f.name} is coming next: ${f.off}.` : undefined} onClick={() => !off && !locked && onPick(f.id)} className={`${card(sel, !!off)} ${small ? "w-[120px]" : "w-[200px]"} ${locked && !sel ? "cursor-default opacity-55" : ""}`}>
            <div className={`relative ${small ? "h-[70px]" : "h-[84px]"} w-full bg-surface-3`}>
              {f.test_still && <img src={`/api/formats/${f.id}/test-sample.jpg`} alt="" className="size-full object-cover" />}
              {f.test_still && tag}
            </div>
            <span className="flex flex-col gap-0.5 px-2.5 py-2">
              <span className="flex items-center gap-2">
                <span className="text-sm font-semibold">{f.name}</span>
                <span className="flex-1" />
                {off && !small ? <span className="rounded-sm bg-surface-2 px-1.5 text-xs font-semibold text-muted">{off === OFF ? OFF : SOON}</span> : sel && <Check />}
              </span>
              {!small && <span className="line-clamp-2 text-xs text-muted">{sub(f)}</span>}
            </span>
          </button>
        );
      })}
    </div>
  );
}

/** Its short tag: "Dialogue only". */
export function onlyShort(l: Look, formats: { id: string; name: string }[]): string {
  return `${(l.formats ?? []).map((id) => formats.find((f) => f.id === id)?.name ?? id).join(" or ")} only`;
}

/** Style cards (S2): a sample that plays (one at a time), the style's line and its B-roll look; a style off on this
 *  site is greyed with "Off on this site" (S2-03), and one not made in the picked format says why (`only`). */
export function StyleCards({ looks, value, onPick, small, locked, only }: { looks: Look[]; value: string; onPick: (id: string) => void; small?: boolean; locked?: boolean; only?: (l: Look) => string | null }) {
  const [playing, setPlaying] = useState<string | null>(null);
  const shown = useShown(value + looks.length, small);
  return (
    <div ref={shown} role="radiogroup" aria-label="Style" className={`flex items-start gap-2 ${small ? "-mx-3.5 overflow-x-auto px-3.5 pb-1" : "overflow-x-auto pb-1"}`}>
      {looks.map((l) => {
        const m = lookMedia(l);
        const sel = l.id === value;
        const why = only?.(l) ?? null;
        const can = l.on && !locked && !why;
        // The picture plays its sample; the words under it pick the style (a radio holds no other button).
        return (
          <div key={l.id} className={`${card(sel, !l.on || !!why)} ${small ? "w-[100px]" : "w-[132px]"} ${locked && !sel ? "opacity-55" : ""}`}>
            <Sample name={l.name} clip={m.clip} still={m.still} testTag={m.tag} playing={playing === l.id} onPlay={() => setPlaying(playing === l.id ? null : l.id)} w="w-full" h={small ? "h-[130px]" : "h-[150px]"} />
            <button type="button" role="radio" aria-checked={sel} aria-disabled={!can || undefined} title={why ?? undefined} onClick={() => can && onPick(l.id)} className={`flex flex-col gap-0.5 px-2.5 py-2 text-left ${can ? "" : "cursor-default"}`}>
              <span className="flex items-center gap-1">
                <span className="text-sm font-semibold">{l.name}</span>
                <span className="flex-1" />
                {sel && <Check />}
              </span>
              {!small && <span className="line-clamp-2 text-xs text-muted">{sub(l)}</span>}
              {l.broll && <span className="text-xs text-muted">{small ? l.broll : brollLine(l)}</span>}
              {!l.on && !small && <span className="mt-1 self-start rounded-sm bg-surface-2 px-1.5 text-xs font-semibold text-muted">{OFF}</span>}
              {l.on && why && !small && <span className="mt-1 text-xs text-muted">{why}</span>}
            </button>
          </div>
        );
      })}
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
    <section ref={box} role="dialog" aria-label="B-roll look for this video" onKeyDown={(e) => e.key === "Escape" && (e.stopPropagation(), onClose())} className="absolute right-0 top-7 z-30 w-[600px] rounded-lg border border-border bg-surface shadow-raised">
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
