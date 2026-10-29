import { useEffect, useRef, useState } from "react";
import { Pause, Play } from "lucide-react";
import { fileUrl } from "../api/upload";

let playing: HTMLAudioElement | null = null; // one take plays at a time
const BARS = 48; // few enough to fit a phone with room between them

/** The loudest peak in each of BARS groups, so the waveform never sets a width of its own. */
const squeeze = (peaks: number[]) => (peaks.length <= BARS ? peaks : Array.from({ length: BARS }, (_, i) => Math.max(...peaks.slice(Math.floor((i * peaks.length) / BARS), Math.floor(((i + 1) * peaks.length) / BARS)))));

/** "0:31" */
export const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

/** A take's player: 44px play/pause, the waveform from the server's peaks as the seek bar (never decoded here), and "0:12 / 0:31". */
export function TakePlayer({ fileId, seconds, peaks, label }: { fileId: number; seconds: number; peaks: number[]; label: string }) {
  const audio = useRef<HTMLAudioElement>(null);
  const [on, setOn] = useState(false);
  const [at, setAt] = useState(0);
  useEffect(() => () => audio.current?.pause(), []);
  const toggle = () => {
    const a = audio.current;
    if (!a) return;
    if (!a.paused) return a.pause();
    if (playing && playing !== a) playing.pause();
    playing = a;
    void a.play()?.catch(() => setOn(false));
  };
  const bars = squeeze(peaks.length > 0 ? peaks : Array.from({ length: BARS }, () => 0.15));
  const done = seconds > 0 ? at / seconds : 0;
  return (
    <div className="flex items-center gap-3">
      <audio ref={audio} src={fileUrl(fileId)} preload="none" onPlay={() => setOn(true)} onPause={() => setOn(false)} onEnded={() => setOn(false)} onTimeUpdate={(e) => setAt(e.currentTarget.currentTime)} />
      <button type="button" onClick={toggle} aria-label={`${on ? "Pause" : "Play"} ${label}`} className="grid size-control shrink-0 place-items-center rounded-full bg-surface-3 text-text hover:bg-surface-2">
        {on ? <Pause size={20} strokeWidth={1.75} aria-hidden /> : <Play size={20} strokeWidth={1.75} aria-hidden />}
      </button>
      <div className="relative h-11 min-w-0 flex-1">
        <div aria-hidden className="flex h-full items-center gap-px overflow-hidden">
          {bars.map((p, i) => (
            <span key={i} className={`min-w-0 flex-1 rounded-full ${i / bars.length < done ? "bg-accent" : "bg-border-strong"}`} style={{ height: `${Math.max(8, p * 100)}%` }} />
          ))}
        </div>
        <input
          type="range"
          min={0}
          max={seconds || 0}
          step={0.1}
          value={at}
          aria-label={`Seek in ${label}`}
          aria-valuetext={`${clock(at)} of ${clock(seconds)}`}
          onChange={(e) => {
            const t = Number(e.target.value);
            setAt(t);
            if (audio.current) audio.current.currentTime = t;
          }}
          className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
        />
      </div>
      <span className="shrink-0 text-sm tabular-nums text-muted">
        {clock(at)} / {clock(seconds)}
      </span>
    </div>
  );
}
