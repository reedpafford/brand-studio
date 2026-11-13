import { useRef, useState } from "react";
import { Pause, Play, Users } from "lucide-react";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { lookFitNote } from "../library/sheets";
import { plural } from "./script";
import { cameFrom, NOT_READY, type CastItem } from "./videoData";

type Asset = components["schemas"]["AssetOut"];
type Tile = { key: string; kind: "person" | "place" | "product"; name: string; picture: number | null; who: string; item?: CastItem };

/** A speaker's voice: its name, and its sample to hear when the server has one. */
function Voice({ of, voice }: { of: string; voice: NonNullable<CastItem["voice"]> }) {
  const audio = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  if (!voice.sample_url) return <span>Voice: {voice.name}</span>;
  return (
    <button type="button" className="btn soft" aria-label={`${playing ? "Stop" : "Play"} ${of}’s voice sample`} onClick={() => (playing ? audio.current?.pause() : void audio.current?.play()?.catch(() => {}))}>
      {playing ? <Pause size={14} strokeWidth={1.75} aria-hidden /> : <Play size={14} strokeWidth={1.75} aria-hidden />}
      {voice.name}
      <audio ref={audio} src={/^https?:/.test(voice.sample_url) ? voice.sample_url : `/api${voice.sample_url}`} preload="none" onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} />
    </button>
  );
}

/** The Cast view, to read: the people, then the places and the product, as tiles. The picked one's tray says who they
 *  are, where they come from, how many clips they are in, their voice, and the look check's advice or a look still on
 *  its way when the server gives them. `assets` adds what the checkpoint doesn't hold: who they are, and the product. */
export function Cast({ cast, assets }: { cast: CastItem[]; assets: Asset[] }) {
  const [picked, setPicked] = useState<string | null>(null);
  const about = (i: CastItem) => assets.find((a) => a.ref === i.ref || (a.slot_id != null && i.ref === `slot:${a.slot_id}`) || (a.kind === i.kind && a.library_item_id != null && a.library_item_id === i.library_item_id));
  const tiles: Tile[] = [
    ...cast.map((i): Tile => ({ key: i.ref, kind: i.kind === "character" ? "person" : "place", name: i.name, picture: i.preview_file_id, who: about(i)?.description ?? "", item: i })),
    ...assets.filter((a) => a.kind === "product").map((a): Tile => ({ key: a.ref, kind: "product", name: a.name, picture: a.file_id ?? null, who: a.description })),
  ];
  if (!tiles.length)
    return (
      <div className="hold bare">
        <Users size={18} strokeWidth={1.75} aria-hidden />
        <b>The cast shows here</b>
        <p>Everyone in the video, its places and the product, once the plan is written.</p>
      </div>
    );
  const pick = tiles.find((t) => t.key === picked) ?? tiles[0];
  const i = pick.item;
  const group = (title: string, list: Tile[], wide = false) =>
    list.length > 0 && (
      <>
        <h3>{title}</h3>
        <div className={wide ? "tiles wide" : "tiles"}>
          {list.map((t) => (
            <button key={t.key} type="button" className={`tile ${t.kind}`} aria-pressed={t === pick} onClick={() => setPicked(t.key)}>
              <span className="im">{t.picture != null && <img src={fileUrl(t.picture)} alt="" />}</span>
              <b>{t.name}</b>
              {t.item && <small>{cameFrom(t.item)}</small>}
            </button>
          ))}
        </div>
      </>
    );
  const others = tiles.filter((t) => t.kind !== "person");
  return (
    <>
      {group("People", tiles.filter((t) => t.kind === "person"))}
      {group(!others.some((t) => t.kind === "product") ? "Places" : others.some((t) => t.kind === "place") ? "Places and product" : "Product", others, true)}
      <div className="tray" role="status">
        <div>
          <b>{pick.name}</b>
          <span>{[pick.who, i && cameFrom(i), i && `in ${plural(i.clip_ids.length, "clip")}`].filter(Boolean).join(" · ")}</span>
          {i?.look_fit && <span className="advice">{lookFitNote(i.look_fit)}</span>}
          {i && NOT_READY[i.readiness] && <span className="advice">{NOT_READY[i.readiness]}</span>}
        </div>
        {i?.voice && <Voice of={pick.name} voice={i.voice} />}
      </div>
    </>
  );
}
