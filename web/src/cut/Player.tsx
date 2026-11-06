import { useEffect, useRef, useState } from "react";
import { Maximize2, Pause, Play, Volume2, VolumeX } from "lucide-react";
import { fileUrl } from "../api/upload";
import { clock } from "./useCutEdits";

/** The cut playing (S7-01): its own controls over the picture (play, time, sound, full screen) and a scrub line. The
 *  playhead lives on the page, so the words and the timeline follow it, and a click on them moves it. */
export function Player({
  fileId,
  length,
  at,
  onTime,
  width,
  aspect,
}: {
  fileId: number;
  length: number;
  at: number;
  onTime: (t: number) => void;
  width: number;
  aspect: string;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  useEffect(() => {
    const v = video.current;
    if (v && Math.abs(v.currentTime - at) > 0.25) v.currentTime = at;
  }, [at]);
  const toggle = () => {
    const v = video.current;
    if (!v) return;
    if (v.paused) void v.play()?.catch(() => setPlaying(false));
    else v.pause();
  };
  return (
    <div className="relative flex-none overflow-hidden rounded-[10px] bg-black shadow-raised" style={{ width, aspectRatio: aspect.replace(":", " / ") }}>
      <video
        ref={video}
        src={fileUrl(fileId)}
        className="h-full w-full object-cover"
        muted={muted}
        playsInline
        preload="metadata"
        aria-label="The cut"
        onTimeUpdate={(e) => onTime(e.currentTarget.currentTime)}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onClick={toggle}
      />
      <div className="absolute inset-x-0 bottom-0 flex flex-col gap-2 bg-(image:--media-shade) px-3 pt-6 pb-2.5 text-on-media max-lg:gap-4 max-lg:px-[17px] max-lg:pb-[17px]">
        <input
          type="range"
          aria-label="Where in the cut"
          min={0}
          max={length}
          step={0.1}
          value={Math.min(at, length)}
          onChange={(e) => onTime(Number(e.target.value))}
          className="h-[3px] w-full cursor-pointer accent-white max-lg:-my-5 max-lg:h-11" // a 44px hit area on a phone, the same thin bar
        />
        <div className="flex items-center gap-2.5 text-xs font-medium tabular-nums max-lg:gap-1.5">
          <button type="button" className={HIT} aria-label={playing ? "Pause" : "Play"} onClick={toggle}>
            {playing ? <Pause size={16} strokeWidth={1.75} aria-hidden /> : <Play size={16} strokeWidth={1.75} aria-hidden />}
          </button>
          <span className="whitespace-nowrap">
            {clock(at)} / {clock(length)}
          </span>
          <span className="grow" />
          <button type="button" className={HIT} aria-label={muted ? "Sound on" : "Sound off"} onClick={() => setMuted(!muted)}>
            {muted ? <VolumeX size={16} strokeWidth={1.75} aria-hidden /> : <Volume2 size={16} strokeWidth={1.75} aria-hidden />}
          </button>
          <button type="button" className={`${HIT} max-lg:ml-2`} aria-label="Full screen" onClick={() => void video.current?.requestFullscreen?.()}>
            <Maximize2 size={16} strokeWidth={1.75} aria-hidden />
          </button>
        </div>
      </div>
    </div>
  );
}

/** A 44px hit area round a 16px icon on a phone; the look stays the same (board P-12). Sound and Full screen sit 44px
 *  apart; `relative` puts the buttons over the time label and over the seek bar's tap area below its line. */
const HIT = "relative grid shrink-0 place-items-center max-lg:-m-3.5 max-lg:size-11";

/** The words under the player (S7-01): said, the one now, still to come. A click on a word plays from it. */
export function Words({
  words,
  text,
  at,
  onSeek,
}: {
  words: { word: string; start: number; end: number }[];
  text: string;
  at: number;
  onSeek: (t: number) => void;
}) {
  if (!words.length) return <p className="text-sm text-muted">{text}</p>;
  const now = words.findIndex((w) => at < w.end);
  return (
    <p className="flex flex-wrap gap-x-1 gap-y-0.5 text-sm leading-[22px]" aria-label="The words">
      {words.map((w, i) => (
        <button
          type="button"
          key={i}
          onClick={() => onSeek(w.start)}
          className={`rounded-xs px-0.5 ${i === now ? "bg-accent-soft text-accent-text" : now !== -1 && i > now ? "text-faint" : "text-text"}`}
          aria-current={i === now ? "true" : undefined}
        >
          {w.word}
        </button>
      ))}
    </p>
  );
}
