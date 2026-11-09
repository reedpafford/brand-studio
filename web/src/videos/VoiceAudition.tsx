import { useEffect, useRef, useState } from "react";
import { Check, Clock, LoaderCircle, Pause, Play, RefreshCw, TriangleAlert } from "lucide-react";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { Button } from "../components";

type Ask = components["schemas"]["AskOut"];
type Price = components["schemas"]["AskPrice"];
type Voice = { id: string; name: string; note?: string; state?: string; sample_file_id?: number | null; sample_url?: string | null };

const spent = (p: Price | null | undefined) => (!p || !p.credits ? "" : p.usd != null ? `$${p.usd.toFixed(2)}` : `${Math.ceil(p.credits - 1e-9)} credit${Math.ceil(p.credits - 1e-9) === 1 ? "" : "s"}`);
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** One voice: play what it read (or its free sample), then use it. */
function Row({ v, on, canPick, busy, owner, onPick }: { v: Voice; on: boolean; canPick: boolean; busy: boolean; owner: boolean; onPick: () => void }) {
  const [playing, setPlaying] = useState(false);
  const audio = useRef<HTMLAudioElement>(null);
  useEffect(() => () => audio.current?.pause(), []);
  const src = v.sample_file_id != null ? fileUrl(v.sample_file_id) : v.sample_url ? `/api${v.sample_url}` : null;
  const reading = !src && ["queued", "running"].includes(v.state ?? "");
  const held = !src && v.state === "needs_owner_approval";
  const note = src || !v.state ? v.note : held ? (owner ? "Waiting for your OK" : "Waiting for the owner’s OK") : reading ? "Reading your script…" : "Didn’t read. Nothing was charged.";
  return (
    <div className={`flex items-center gap-3 rounded-md border px-3 py-2 ${on ? "border-[#c9ccf6] bg-accent-soft" : "border-border"}`}>
      <button type="button" disabled={!src} aria-label={`${playing ? "Pause" : "Play"} ${v.name}${v.state ? " reading your script" : ""}`} onClick={() => (playing ? audio.current?.pause() : void audio.current?.play()?.catch(() => {}))} className="grid size-control shrink-0 place-items-center rounded-md border border-border-button bg-surface disabled:opacity-50">
        {reading ? <LoaderCircle size={14} strokeWidth={1.75} aria-hidden className="animate-spin motion-reduce:animate-none" /> : held ? <Clock size={14} strokeWidth={1.75} aria-hidden /> : playing ? <Pause size={14} strokeWidth={1.75} aria-hidden /> : <Play size={14} strokeWidth={1.75} aria-hidden />}
        {src && <audio ref={audio} src={src} preload="none" onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} />}
      </button>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium">{v.name}</span>
        <span className="block truncate text-xs text-muted">{note}</span>
      </span>
      {on ? (
        <span className="flex shrink-0 items-center gap-1 text-xs font-semibold text-accent-text">
          <Check size={14} strokeWidth={1.75} aria-hidden />
          Picked
        </span>
      ) : (
        canPick && (
          <Button variant="secondary" busy={busy} onClick={onPick} aria-label={`Use ${v.name}`}>
            Use
          </Button>
        )
      )}
    </div>
  );
}

/** A presenter's voice audition on the card that casts them (Reed, 9 Nov: "finding the voice before generating"): the
 *  director's voices, each reading the script's opening; the pick is this video's voice, saved on a saved presenter. If
 *  none of them read, the card never dead-ends (rule 22): Read them again, or any voice unheard. */
export function VoiceAudition({ ask: a, who, owner, busy, onPick, onAgain }: { ask: Ask; who: string; owner: boolean; busy: boolean; onPick: (option: string) => void; onAgain: () => void }) {
  if (!a.audition.length) return null;
  const cost = spent(a.audition_spent);
  const can = a.can.includes("voice");
  if (a.voice) {
    return <p className="text-xs font-semibold text-muted">{`${cap(who)}’s voice: ${a.voice_name || a.audition.find((v) => v.id === a.voice)?.name || ""} · ${a.voice_saved ? "saved on them for their next video" : "for this video"}`}</p>;
  }
  return (
    <div role="group" aria-label={`${cap(who)}’s voice`} className="flex flex-col gap-1.5">
      <p className="text-xs font-semibold text-muted">{`Hear them read your script, then pick ${who}’s voice${cost ? ` · ${cost} for these reads` : ""}`}</p>
      {a.audition.map((v) => (
        <Row key={v.id} v={v} on={false} canPick={can && (v.sample_file_id != null || a.audition_failed)} busy={busy} owner={owner} onPick={() => onPick(v.id)} />
      ))}
      {a.audition_failed ? (
        <>
          <p className="flex items-center gap-2 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger">
            <TriangleAlert size={14} strokeWidth={1.75} aria-hidden className="shrink-0" />
            None of them read. Nothing was charged.
          </p>
          {a.can.includes("again") && (
            <Button variant="secondary" icon={RefreshCw} busy={busy} onClick={onAgain} className="self-start">
              Read them again
            </Button>
          )}
          {(a.other_voices ?? []).length > 0 && (
            <>
              <p className="text-xs font-semibold text-muted">Or pick any voice without hearing it read your script</p>
              <div className="flex max-h-[260px] flex-col gap-1.5 overflow-y-auto">
                {a.other_voices.map((o) => (
                  <Row key={o.id} v={o} on={false} canPick={can} busy={busy} owner={owner} onPick={() => onPick(o.id)} />
                ))}
              </div>
            </>
          )}
        </>
      ) : (
        <p className="text-xs text-muted">Nothing else is made until you pick: the whole video is timed to this voice.</p>
      )}
    </div>
  );
}
