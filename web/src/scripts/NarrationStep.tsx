import { useEffect, useState } from "react";
import { Mic, RotateCcw, Trash2 } from "lucide-react";
import { fileUrl } from "../api/upload";
import { Badge, Banner, Button, Card, EmptyState, Skeleton } from "../components";
import { errorText as errorClass } from "../ui";
import { TakePlayer, clock } from "./TakePlayer";
import { useAllowanceStop, type Script } from "./useScript";
import { useSongActions, useSongs, type SongTake } from "./useSongs";

/** A narration is a song take of kind "narration" (Next-Server #858), with its voice and, when pauses were trimmed, its length before. */
type Narration = SongTake;
const VOICE = "Sarah"; // until the server names the version's voice (SongsOut.voice, #907); choosing it comes later
const WORDS = { noun: "Narration", picked: "is the one used" };

function Elapsed() {
  const [n, setN] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setN((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, []);
  return <>{n > 0 ? ` ${n} s` : ""}</>;
}

/** One narration: its player, length, pauses trimmed, its state in words and the press each state needs (flows N1). */
function NarrationCard({ t, a, readOnly, price }: { t: Narration; a: ReturnType<typeof useSongActions>; readOnly: boolean; price: number }) {
  const label = `Narration ${t.number}`;
  const length = t.seconds;
  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="type-card">{label}</h3>
        {length != null && <span className="text-sm tabular-nums text-muted">{clock(length)}</span>}
        <span className="text-sm text-muted">{t.voice ?? VOICE}</span>
        {t.preferred && !t.out_of_date && <Badge tone="accent">In use</Badge>}
        {t.out_of_date && <Badge>Reads older words</Badge>}
        {t.timing_guessed && <Badge tone="warning">Timing guessed</Badge>}
      </div>
      {t.status === "making" ? (
        <p role="status" className="text-sm text-muted">Making the narration…<Elapsed /></p>
      ) : t.status === "timing" ? (
        <p role="status" className="text-sm text-muted">Measuring the sentences…<Elapsed /></p>
      ) : t.file_id !== null && t.seconds !== null ? (
        <TakePlayer fileId={t.file_id} seconds={t.seconds} peaks={t.peaks} label={label} />
      ) : null}
      {/* The music bed under the narration (#912); where music is switched off it stays "none" and nothing shows. */}
      {t.status === "ready" && t.music_status === "making" && <p role="status" className="text-sm text-muted">Making the music…<Elapsed /></p>}
      {t.music_status === "ready" && (
        <div className="space-y-1">
          <p className="text-sm text-muted">With music under it.</p>
          {t.music_file_id != null && <audio controls preload="none" src={fileUrl(t.music_file_id)} aria-label={`The music for ${label}`} className="w-full" />}
        </div>
      )}
      {t.music_status === "failed" && (
        <div className="space-y-2">
          <p role="alert" className="text-sm text-warning">{t.music_reason || "The music didn't finish. Nothing was charged for it."} The narration is kept.</p>
          {!readOnly && (
            <Button variant="secondary" icon={RotateCcw} price={t.music_credits} busy={a.musicAgain.isPending && a.musicAgain.variables === t.id} onClick={() => a.musicAgain.mutate(t.id)}>
              Try the music again
            </Button>
          )}
        </div>
      )}
      {t.untrimmed_seconds != null && length != null && <p className="text-sm text-muted">Pauses trimmed: {clock(t.untrimmed_seconds)} → {clock(length)}</p>}
      {(t.sentences ?? []).length > 0 && (
        <details>
          <summary className="flex min-h-11 cursor-pointer items-center text-sm">Each sentence's start · {t.sentences.length}</summary>
          <ul className="space-y-1 text-sm">
            {t.sentences.map((x, i) => (
              <li key={i} className="flex gap-3"><span className="w-10 shrink-0 tabular-nums text-muted">{clock(x.start)}</span><span className="min-w-0 break-words">{x.text}</span></li>
            ))}
          </ul>
        </details>
      )}
      {t.advice.map((x) => (
        <p key={x} className="text-sm text-muted">{x}</p>
      ))}
      {(t.status === "failed" || t.status === "timing_failed") && (
        <div className="space-y-2">
          <p role="alert" className={errorClass}>{t.failed_reason ?? "The narration didn't finish. Nothing was charged."}</p>
          {!readOnly && t.retry_helps && (
            <Button variant="secondary" icon={RotateCcw} price={t.status === "failed" ? price : 0} busy={a.tryAgain.isPending && a.tryAgain.variables === t.id} onClick={() => a.tryAgain.mutate(t.id)}>
              Try again
            </Button>
          )}
        </div>
      )}
      {t.out_of_date && <p className="text-sm text-muted">It reads words that have since changed, so it can't be used. It stays here to listen to.</p>}
      {!readOnly && (
        <div className="flex flex-wrap gap-2">
          {t.status === "ready" && !t.out_of_date && !t.preferred && (
            <Button variant="secondary" busy={a.prefer.isPending && a.prefer.variables === t.id} onClick={() => a.prefer.mutate(t.id)}>
              Use this narration
            </Button>
          )}
          {!t.preferred && t.status !== "making" && t.status !== "timing" && (
            <Button variant="ghost" icon={Trash2} busy={a.remove.isPending && a.remove.variables?.id === t.id} onClick={() => a.remove.mutate(t)} aria-label={`Delete ${label}`}>
              Delete
            </Button>
          )}
        </div>
      )}
    </Card>
  );
}

/** Step 2 of a Narrated script: one voice reads the whole script (flows N1). Make it, use one, make another; the one used stays until another is. */
export function NarrationStep({ script: s }: { script: Script }) {
  const songs = useSongs(s.id);
  const a = useSongActions(s.id, WORDS);
  const data = songs.data;
  const stop = useAllowanceStop(s, data?.estimate_credits);
  if (songs.isPending)
    return (
      <div role="status" aria-label="Loading the narration" className="space-y-4">
        <Skeleton className="h-36" />
      </div>
    );
  if (!data)
    return (
      <Banner title="Couldn't load the narration." action={<Button variant="secondary" onClick={() => void songs.refetch()}>Try again</Button>}>
        Nothing was changed.
      </Banner>
    );
  const readOnly = s.published;
  const narrations = data.takes as Narration[];
  const latest = [a.make, a.tryAgain, a.musicAgain, a.prefer, a.remove].reduce((x, m) => (m.submittedAt > x.submittedAt ? m : x));
  const refused = latest.isError ? latest.error.message : null;
  const making = narrations.some((t) => t.status === "making" || t.status === "timing"); // the server refuses a second one meanwhile
  const used = narrations.find((t) => t.preferred && !t.out_of_date);
  const older = narrations.length > 0 && narrations.every((t) => t.out_of_date);
  const noWords = !!data.songs_note && !data.estimate_credits;
  const make = (label: string, primary: boolean) => (
    // With nothing for the narrator to read, the server sends why (songs_note) and no price (#920): the press says it, greyed.
    <Button variant={primary ? "primary" : "secondary"} icon={Mic} price={noWords ? undefined : data.estimate_credits} disabled={noWords || stop !== null || making} reason={noWords ? data.songs_note! : stop ?? (making ? "One is being made" : null)} busy={a.make.isPending} onClick={() => a.make.mutate()}>
      {label}
    </Button>
  );
  return (
    <div className="max-w-[720px] space-y-4">
      {refused && <p role="alert" className={errorClass}>{refused}</p>}
      {data.songs_note && !noWords && <p className="text-sm text-muted">{data.songs_note}</p>}
      {!data.songs_on && <Banner tone="info" title="Narration isn't switched on here.">The words still save. A narration can be made where it's on.</Banner>}
      {narrations.length === 0 ? (
        readOnly ? (
          <EmptyState icon={Mic} title="No narration">This script was published without a narration.</EmptyState>
        ) : (
          <EmptyState icon={Mic} title="Make the narration" action={data.songs_on ? make("Make the narration", true) : undefined}>
            One voice reads the whole script. Voice: {data.voice || VOICE}.
          </EmptyState>
        )
      ) : (
        <>
          {older && !readOnly && <p className="text-sm">The words changed since the last narration. Make the narration again to use them.</p>}
          <ul className="grid gap-4 [&>li]:min-w-0">
            {narrations.map((t) => (
              <li key={t.id}>
                <NarrationCard t={t} a={a} readOnly={readOnly} price={data.estimate_credits} />
              </li>
            ))}
          </ul>
          {!readOnly && data.songs_on && (
            <div className="space-y-1">
              {make(older ? "Make the narration" : "Make another", older || !used)}
              {used && !older && <p className="text-sm text-muted">Narration {used.number} stays in use until you use the new one.</p>}
            </div>
          )}
        </>
      )}
    </div>
  );
}
