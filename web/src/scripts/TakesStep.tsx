import { useEffect, useState } from "react";
import { Ellipsis, Music, RotateCcw, Trash2 } from "lucide-react";
import { Badge, Banner, Button, Card, EmptyState, Menu, MenuItem, Skeleton } from "../components";
import { serverTime } from "../time";
import { errorText as errorClass } from "../ui";
import { TakePlayer, clock } from "./TakePlayer";
import { useAllowanceStop, type Script } from "./useScript";
import { useSongActions, useSongs, type SongTake } from "./useSongs";

/** Seconds since this was first shown, for "Making the song… 12 s". */
function useCount() {
  const [n, setN] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setN((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, []);
  return n;
}

function Making() {
  const n = useCount();
  return (
    <div role="status" className="space-y-2">
      <Skeleton className="h-11" />
      <p className="text-sm text-muted">Making the song…{n > 0 ? ` ${n} s` : ""}</p>
    </div>
  );
}

/** One take: its player, its state in words, and the press each state needs (flows S4). */
function TakeCard({ t, a, prices, readOnly, others }: { t: SongTake; a: ReturnType<typeof useSongActions>; prices: { take: number }; readOnly: boolean; others: SongTake[] }) {
  const label = `Take ${t.number}`;
  const otherReady = others.find((o) => o.status === "ready" && !o.out_of_date && !o.preferred);
  const preferBlock = t.status === "timing" ? "Reading the song's timing…" : t.out_of_date ? "This take sings older words." : null;
  const deleteBlock = t.preferred ? "Make another take Preferred first." : null;
  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="type-card">{label}</h3>
        {t.seconds !== null && <span className="text-sm tabular-nums text-muted">{clock(t.seconds)}</span>}
        {t.made_at && <span className="text-sm text-muted">made at {serverTime(t.made_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>}
        {t.preferred && <Badge tone="accent">Preferred</Badge>}
        {t.out_of_date && <Badge>Sings older words</Badge>}
        {t.timing_guessed && <Badge tone="warning">Timing guessed</Badge>}
        {!readOnly && t.status !== "making" && (
          <div className="ml-auto">
            <Menu
              title={label}
              align="right"
              trigger={(p) => (
                <button type="button" {...p} aria-label={`More for ${label}`} className="grid size-control place-items-center rounded-md text-muted hover:bg-surface-2">
                  <Ellipsis size={20} strokeWidth={1.75} aria-hidden />
                </button>
              )}
            >
              {(close) => (
                <>
                  <MenuItem
                    danger
                    disabled={!!deleteBlock}
                    onClick={() => {
                      close();
                      a.remove.mutate(t);
                    }}
                  >
                    <Trash2 size={20} strokeWidth={1.75} aria-hidden />
                    Delete take
                  </MenuItem>
                  {deleteBlock && <p className="px-3 pb-2 text-sm text-muted">{deleteBlock}</p>}
                </>
              )}
            </Menu>
          </div>
        )}
      </div>
      {t.status === "making" ? (
        <Making />
      ) : t.file_id !== null && t.seconds !== null ? (
        <TakePlayer fileId={t.file_id} seconds={t.seconds} peaks={t.peaks} label={label} />
      ) : null}
      {t.status === "timing" && <p role="status" className="text-sm text-muted">Reading the song's timing…</p>}
      {t.status === "failed" && (
        <div className="space-y-2">
          <p role="alert" className={errorClass}>{t.failed_reason ?? "This take didn't finish. Credits were returned."}</p>
          {!readOnly && t.retry_helps && (
            <Button variant="secondary" icon={RotateCcw} price={prices.take} busy={a.tryAgain.isPending && a.tryAgain.variables === t.id} onClick={() => a.tryAgain.mutate(t.id)}>
              Try again
            </Button>
          )}
        </div>
      )}
      {t.status === "timing_failed" && (
        <div className="space-y-2">
          <p role="alert" className={errorClass}>{t.failed_reason ?? "Couldn't read this take's timing. Nothing was charged."}</p>
          {!readOnly && (
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" busy={a.spread.isPending && a.spread.variables === t.id} onClick={() => a.spread.mutate(t.id)}>
                Use timing spread evenly · free
              </Button>
              {otherReady && (
                <Button variant="secondary" onClick={() => a.prefer.mutate(otherReady.id)}>
                  Make take {otherReady.number} Preferred
                </Button>
              )}
              {t.retry_helps && (
                <Button variant="ghost" icon={RotateCcw} busy={a.tryAgain.isPending && a.tryAgain.variables === t.id} onClick={() => a.tryAgain.mutate(t.id)}>
                  Try again · free
                </Button>
              )}
            </div>
          )}
        </div>
      )}
      {t.advice.length > 0 && (
        <ul className="space-y-1 text-sm text-warning" aria-label={`Advice for ${label}`}>
          {t.advice.map((x) => (
            <li key={x}>{x}</li>
          ))}
        </ul>
      )}
      {!readOnly && !t.preferred && (t.status === "ready" || t.status === "timing") && (
        <Button variant="secondary" spread className="sm:w-auto" disabled={!!preferBlock} reason={preferBlock} busy={a.prefer.isPending && a.prefer.variables === t.id} onClick={() => a.prefer.mutate(t.id)}>
          Make this Preferred
        </Button>
      )}
    </Card>
  );
}

/** Step 2 of a song script: make 2 takes of the lyrics, pick the Preferred one, make more, delete with Undo (flows S4). */
export function TakesStep({ script: s }: { script: Script }) {
  const songs = useSongs(s.id);
  const a = useSongActions(s.id);
  const data = songs.data;
  const stop = useAllowanceStop(s, data?.estimate_credits);
  if (songs.isPending)
    return (
      <div role="status" aria-label="Loading takes" className="grid gap-4 md:grid-cols-2">
        <Skeleton className="h-36" />
        <Skeleton className="h-36" />
      </div>
    );
  if (!data)
    return (
      <Banner title="Couldn't load the takes." action={<Button variant="secondary" onClick={() => void songs.refetch()}>Try again</Button>}>
        Nothing was changed.
      </Banner>
    );
  const readOnly = s.published;
  const takes = data.takes;
  // A refused press on a take (Try again past the week, say) says why, until the next press: only the latest one counts.
  const latest = [a.make, a.tryAgain, a.spread, a.prefer, a.remove].reduce((x, m) => (m.submittedAt > x.submittedAt ? m : x));
  const refused = latest !== a.make && latest.isError ? latest.error.message : null;
  const failed = a.make.isError && latest === a.make ? a.make.error.message : null;
  const make = (label: string, primary: boolean) => (
    <div className="space-y-1">
      <Button variant={primary ? "primary" : "secondary"} icon={Music} price={data.estimate_credits} disabled={stop !== null} reason={stop} busy={a.make.isPending} onClick={() => a.make.mutate(2)}>
        {label}
      </Button>
      {failed && <p role="alert" className={errorClass}>{failed}</p>}
    </div>
  );
  const current = takes.filter((t) => !t.out_of_date);
  return (
    <div className="space-y-4">
      {refused && <p role="alert" className={errorClass}>{refused}</p>}
      {!data.songs_on && <Banner tone="info" title="Songs aren't switched on here.">The lyrics and style still save. Takes can be made where songs are on.</Banner>}
      {takes.length === 0 ? (
        readOnly ? (
          <EmptyState icon={Music} title="No takes">This script was published without a song.</EmptyState>
        ) : (
          <EmptyState icon={Music} title="Make the song" action={data.songs_on ? make("Make 2 takes", true) : undefined}>
            You get 2 takes and pick one. Each take is a full song. The song sets the video's length.
          </EmptyState>
        )
      ) : (
        <>
          {!readOnly && takes.length > 0 && current.length === 0 && <Banner tone="warning" title="These takes sing older words.">Make 2 takes of the lyrics as they are now. The old ones stay playable.</Banner>}
          <div className="grid grid-cols-[minmax(0,1fr)] gap-4 md:grid-cols-2">
            {takes.map((t) => (
              <TakeCard key={t.id} t={t} a={a} prices={{ take: data.take_credits }} readOnly={readOnly} others={takes.filter((o) => o.id !== t.id)} />
            ))}
          </div>
          {!readOnly && data.songs_on && make(current.length === 0 ? "Make 2 takes" : "Make 2 more", current.length === 0)}
        </>
      )}
    </div>
  );
}
