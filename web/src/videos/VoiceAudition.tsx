import { useEffect, useRef, useState } from "react";
import { Check, LoaderCircle, Pause, Play } from "lucide-react";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { Button } from "../components";

type Ask = components["schemas"]["AskOut"];
type Voice = components["schemas"]["Audition"];
type Price = components["schemas"]["AskPrice"];

const spent = (p: Price | null | undefined) => (!p || !p.credits ? "" : p.usd != null ? `$${p.usd.toFixed(2)}` : `${Math.ceil(p.credits - 1e-9)} credit${Math.ceil(p.credits - 1e-9) === 1 ? "" : "s"}`);

/** One voice reading the script's opening: play it, then use it. */
function Row({ v, on, canPick, busy, onPick }: { v: Voice; on: boolean; canPick: boolean; busy: boolean; onPick: () => void }) {
  const [playing, setPlaying] = useState(false);
  const audio = useRef<HTMLAudioElement>(null);
  useEffect(() => () => audio.current?.pause(), []);
  const ready = v.sample_file_id != null;
  return (
    <div className={`flex items-center gap-3 rounded-md border px-3 py-2 ${on ? "border-[#c9ccf6] bg-accent-soft" : "border-border"}`}>
      <button type="button" disabled={!ready} aria-label={`${playing ? "Pause" : "Play"} ${v.name} reading your script`} onClick={() => (playing ? audio.current?.pause() : void audio.current?.play()?.catch(() => {}))} className="grid size-control shrink-0 place-items-center rounded-md border border-border-button bg-surface disabled:opacity-50">
        {!ready ? <LoaderCircle size={14} strokeWidth={1.75} aria-hidden className="animate-spin motion-reduce:animate-none" /> : playing ? <Pause size={14} strokeWidth={1.75} aria-hidden /> : <Play size={14} strokeWidth={1.75} aria-hidden />}
        {ready && <audio ref={audio} src={fileUrl(v.sample_file_id!)} preload="none" onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} />}
      </button>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium">{v.name}</span>
        <span className="block truncate text-xs text-muted">{ready ? v.note : v.state === "failed" ? "Didn’t read. Nothing was charged." : "Reading your script…"}</span>
      </span>
      {on ? (
        <span className="flex shrink-0 items-center gap-1 text-xs font-semibold text-accent-text">
          <Check size={14} strokeWidth={1.75} aria-hidden />
          Picked
        </span>
      ) : (
        canPick && ready && (
          <Button variant="secondary" busy={busy} onClick={onPick} aria-label={`Use ${v.name}`}>
            Use
          </Button>
        )
      )}
    </div>
  );
}

/** A presenter's voice audition on the card that casts them (Reed, 9 Nov: "finding the voice before generating"): the
 *  director's voices, each reading the script's opening; the pick is this video's voice and saved on the presenter. */
export function VoiceAudition({ ask: a, who, busy, onPick }: { ask: Ask; who: string; busy: boolean; onPick: (option: string) => void }) {
  if (!a.audition.length) return null;
  const cost = spent(a.audition_spent);
  return (
    <div role="group" aria-label={`${who}’s voice`} className="flex flex-col gap-1.5">
      <p className="text-xs font-semibold text-muted">{a.voice ? `${who}’s voice · saved on them for their next video` : `Hear them read your script, then pick ${who}’s voice${cost ? ` · ${cost} for these reads` : ""}`}</p>
      {a.audition.map((v) => (
        <Row key={v.id} v={v} on={a.voice === v.id} canPick={a.can.includes("voice")} busy={busy} onPick={() => onPick(v.id)} />
      ))}
      {!a.voice && <p className="text-xs text-muted">Nothing else is made until you pick: the whole video is timed to this voice.</p>}
    </div>
  );
}
