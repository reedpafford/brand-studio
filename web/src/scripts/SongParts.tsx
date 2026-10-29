import { Music } from "lucide-react";
import { Card } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { useSaveSong, type Song } from "./SongStep";
import { TakePlayer, clock } from "./TakePlayer";
import { useCast } from "./useCast";
import type { Script } from "./useScript";
import { useSongs } from "./useSongs";

const NOBODY = "";

/** The song's version (slot 0) as saved, for a change that keeps everything else. */
const songOf = (s: Script): Song & { singer: string } => {
  const v = s.versions.find((x) => x.slot === 0);
  return { text: v?.text ?? "", style_line: v?.style_line ?? "", spoken_end_line: v?.spoken_end_line ?? "", singer: v?.singer ?? NOBODY };
};

/** Cast on a song script (flows S5): "Who sings on camera?" — one of the roles, or Nobody on camera (every shot B-roll). Saved at once, with Undo. */
export function SingerCard({ script: s }: { script: Script }) {
  const cast = useCast(s.id);
  const put = useSaveSong(s.id);
  const toast = useToast();
  const now = songOf(s);
  const roles = (cast.data ?? []).map((c) => c.role);
  const choices = [...roles, NOBODY];
  const pick = (singer: string) =>
    put.mutate({ ...now, singer }, { onSuccess: () => toast(singer ? `${singer} sings on camera.` : "Nobody sings on camera.", () => put.mutate(now)) });
  return (
    <Card className="max-w-[480px] space-y-3">
      <fieldset className="space-y-1" disabled={s.published || put.isPending}>
        <legend className="type-card pb-2">Who sings on camera?</legend>
        {choices.map((c) => (
          <label key={c || "nobody"} className="flex min-h-control cursor-pointer items-center gap-3 rounded-md px-2 hover:bg-surface-2">
            <input type="radio" name="singer" className="size-5" checked={now.singer === c} onChange={() => pick(c)} />
            <span>{c || "Nobody on camera"}</span>
          </label>
        ))}
      </fieldset>
      {now.singer === NOBODY && <p className="text-sm text-warning">No shot will lip-sync. The song plays over B-roll only.</p>}
      {roles.length === 0 && !cast.isPending && <p className="text-sm text-muted">No roles yet: the cast read adds a Singer when the lyrics name nobody.</p>}
      {put.isError && <p role="alert" className={errorClass}>{put.error.message}</p>}
    </Card>
  );
}

/** The Preferred take as a compact row: "Song: Take 2 · 0:31" with its player (flows S7, V1). */
export function SongRow({ scriptId }: { scriptId: number }) {
  const take = useSongs(scriptId).data?.takes.find((t) => t.preferred && !t.out_of_date);
  if (!take || take.file_id === null || take.seconds === null) return <p className="flex items-center gap-2 text-sm text-muted"><Music size={16} strokeWidth={1.75} aria-hidden /> No song yet</p>;
  const length = take.trim_to ?? take.seconds;
  return (
    <div className="space-y-1">
      <p className="text-sm">Song: Take {take.number} · {clock(length)}{take.trim_to != null ? " (trimmed)" : ""}</p>
      <TakePlayer fileId={take.file_id} seconds={take.seconds} peaks={take.peaks} label={`Take ${take.number}`} />
    </div>
  );
}

/** The Preferred take's length as "0:31" (its trimmed part, if trimmed), or null: for price lines like "About 40 credits to make · 0:31 song". */
export function useSongLength(scriptId: number, enabled: boolean) {
  const take = useSongs(scriptId, enabled).data?.takes.find((t) => t.preferred && !t.out_of_date);
  const seconds = take?.trim_to ?? take?.seconds;
  return seconds != null ? clock(seconds) : null;
}

/** The song's lines on a Publish card: the song, its style and who sings (flows S7). */
export function SongFacts({ script: s }: { script: Script }) {
  const now = songOf(s);
  return (
    <>
      <div>
        <dt className="font-medium text-muted">Song</dt>
        <dd><SongRow scriptId={s.id} /></dd>
      </div>
      <div>
        <dt className="font-medium text-muted">Style</dt>
        <dd>{now.style_line || "Upbeat pop (no style set)"}</dd>
      </div>
      <div>
        <dt className="font-medium text-muted">Singer</dt>
        <dd>{now.singer || "Nobody on camera"}</dd>
      </div>
    </>
  );
}
