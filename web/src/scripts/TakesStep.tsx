import { useState } from "react";
import { Ellipsis, Music, Pencil, RotateCcw, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge, Banner, Button, Card, Dialog, EmptyState, Menu, MenuItem, Skeleton, buttonClass, wholeCredits } from "../components";
import { serverTime } from "../time";
import { JobClock } from "../clip/History";
import { errorText as errorClass } from "../ui";
import { TakePlayer, clock } from "./TakePlayer";
import type { Script } from "./useScript";
import { keepFirst, useSaveSong, type Song } from "./SongStep";
import { useToast } from "../toast";
import { useBrands } from "../shell/useBrands";
import { useSongActions, useSongs, type SongTake } from "./useSongs";

/** "Making the song… 0:12" (flows S4), counted from when its job started (#1033), so a reload keeps the time. Before it
 *  starts it reads "Waiting to start", counted from when it was first shown (a take doesn't say when it was asked). */
function Making({ started }: { started: string | null }) {
  const [shown] = useState(() => new Date().toISOString());
  return (
    <div role="status" className="space-y-2">
      <Skeleton className="h-11" />
      <p className="text-sm text-muted">
        <JobClock queued={!started} making="Making the song…" since={started ?? shown} />
      </p>
    </div>
  );
}

/** "· a video of about 40 credits": what this take's length means for a video (flows S4, V2a). */
export const videoCost = (t: SongTake) => {
  if (t.video_credits == null) return "";
  const c = wholeCredits(t.video_credits); // the server's figure can be fractional
  return ` · a video of about ${c} credit${c === 1 ? "" : "s"}`;
};

/** One take: its player, its state in words, and the press each state needs (flows S4). */
/** Try again shows what the server says it costs (`retry_credits`): a whole request, or free for a timing or a request that came back short. A timing failure that a retry can't fix leads to the other take or to Make 2 more under the cards. */
function TakeCard({ t, a, readOnly, others, onDefaultStyle }: { t: SongTake; a: ReturnType<typeof useSongActions>; readOnly: boolean; others: SongTake[]; onDefaultStyle?: () => void }) {
  const label = `Take ${t.number}`;
  const otherReady = others.find((o) => o.status === "ready" && !o.out_of_date && !o.preferred);
  const tooLong = t.over_cap && t.trim_to == null;
  const preferBlock = t.status === "timing" ? "Reading the song's timing…" : t.out_of_date ? "This take sings older words." : tooLong ? "A video of this take would go over the limit." : null;
  const deleteBlock = t.preferred ? "Make another take Preferred first." : null;
  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="type-card">{label}</h3>
        {t.seconds !== null && <span className="text-sm tabular-nums text-muted">{clock(t.seconds)}{videoCost(t)}</span>}
        {t.made_at && <span className="text-sm text-muted">made at {serverTime(t.made_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>}
        {t.preferred && <Badge tone="accent">Preferred</Badge>}
        {t.out_of_date && <Badge>Sings older words</Badge>}
        {t.timing_guessed && <Badge tone="warning">Timing guessed</Badge>}
        {t.trim_to != null && <Badge>Uses the first {clock(t.trim_to)}</Badge>}
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
        <Making started={t.started_at} />
      ) : t.file_id !== null && t.seconds !== null ? (
        <TakePlayer fileId={t.file_id} seconds={t.seconds} peaks={t.peaks} label={label} />
      ) : null}
      {t.status === "timing" && <p role="status" className="text-sm text-muted">Reading the song's timing…</p>}
      {t.status === "failed" && (
        <div className="space-y-2">
          <p role="alert" className={errorClass}>{t.failed_reason ?? "Didn't finish · nothing charged."}</p>
          {/* A refusal comes back the same for the same words and style, so it leads with changing them (flows S4 X);
              a timeout or a stall leads with Try again, with Edit after it. */}
          {!readOnly && (
            <div className="flex flex-wrap gap-2">
              {t.refused_for === "style" && onDefaultStyle && (
                <Button variant="secondary" onClick={onDefaultStyle}>
                  Use the default music style instead · free
                </Button>
              )}
              {t.retry_helps && !t.refused_for && (
                <Button variant="secondary" icon={RotateCcw} charge="fixed" price={t.retry_credits} busy={a.tryAgain.isPending && a.tryAgain.variables === t.id} onClick={() => a.tryAgain.mutate(t.id)}>
                  Try again
                </Button>
              )}
              <Link to="?edit=1" className={buttonClass(t.refused_for ? "secondary" : "ghost")}>
                <Pencil size={20} strokeWidth={1.75} aria-hidden />
                {t.refused_for === "words" ? "Edit lyrics" : t.refused_for === "style" ? "Edit music style" : "Edit lyrics or music style"}
              </Link>
              {t.retry_helps && t.refused_for && (
                <Button variant="ghost" icon={RotateCcw} charge="fixed" price={t.retry_credits} busy={a.tryAgain.isPending && a.tryAgain.variables === t.id} onClick={() => a.tryAgain.mutate(t.id)}>
                  Try again
                </Button>
              )}
            </div>
          )}
        </div>
      )}
      {t.status === "timing_failed" && (
        <div className="space-y-2">
          <p role="alert" className={errorClass}>{t.failed_reason ?? "Couldn't read this take's timing. Nothing was charged."}</p>
          {!readOnly && (
            <div className="flex flex-wrap gap-2">
              {/* Spread evenly and Try again work only when the file can be read; otherwise the other take, or more takes. */}
              {t.retry_helps && (
                <Button variant="secondary" busy={a.spread.isPending && a.spread.variables === t.id} onClick={() => a.spread.mutate(t.id)}>
                  Use timing spread evenly · free
                </Button>
              )}
              {otherReady && (
                <Button variant="secondary" onClick={() => a.prefer.mutate(otherReady.id)}>
                  Make take {otherReady.number} Preferred
                </Button>
              )}
              {t.retry_helps && (
                <Button variant="ghost" icon={RotateCcw} charge="fixed" price={t.retry_credits} busy={a.tryAgain.isPending && a.tryAgain.variables === t.id} onClick={() => a.tryAgain.mutate(t.id)}>
                  Try again
                </Button>
              )}
            </div>
          )}
        </div>
      )}
      {tooLong && (
        <div className="space-y-2">
          <p className="text-sm text-warning">This take is {t.seconds !== null ? clock(t.seconds) : "long"}: a video of it would go over the limit.</p>
          {/* With no other take Preferred, the trimmed take becomes the one used (flows S4). */}
          {!readOnly && t.fits_until != null && (
            <Button variant="secondary" busy={a.trim.isPending && a.trim.variables?.t.id === t.id} onClick={() => a.trim.mutate({ t, prefer: !t.preferred && !others.some((o) => o.preferred && !o.out_of_date) })}>
              Use the first {clock(t.fits_until)} · free
            </Button>
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
  const [keeping, setKeeping] = useState(false);
  const put = useSaveSong(s.id);
  const toast = useToast();
  const brand = useBrands().data?.find((b) => b.id === s.brand_id);
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
  const latest = [a.make, a.tryAgain, a.spread, a.prefer, a.trim, a.remove, put].reduce((x, m) => (m.submittedAt > x.submittedAt ? m : x));
  const refused = latest !== a.make && latest.isError ? latest.error.message : null;
  const failed = a.make.isError && latest === a.make ? a.make.error.message : null;
  // A refusal over the style (an artist's name, say): the style line is cleared, so the song is upbeat pop, with Undo. No brand music style exists yet (brand setup).
  const v = s.versions.find((x) => x.slot === 0);
  const now: Song = { text: v?.text ?? "", style_line: v?.style_line ?? "", spoken_end_line: v?.spoken_end_line ?? "" };
  const defaultStyle = now.style_line ? () => put.mutate({ ...now, style_line: "" }, { onSuccess: () => toast("The music style is cleared: the song will be upbeat pop. Make 2 takes again.", () => put.mutate(now)) }) : undefined;
  const current = takes.filter((t) => !t.out_of_date);
  // Rule 18 (Advice): does the part a cut drops hold the brand's end line?
  const endLine = brand?.end_line.trim().toLowerCase();
  const loseEnd = (dropped: string) => !!endLine && dropped.toLowerCase().includes(endLine);
  // Over the cap before any take of these lyrics (flows S4 B): the price line says so and Make gives way to the free fix.
  const cut = data.keep_lines !== null ? keepFirst(now.text, data.keep_lines) : null;
  const dropsEnd = !!cut && loseEnd(now.text.slice(cut.kept.length));
  const make = (label: string, primary: boolean) =>
    cut ? (
      <div className="space-y-2">
        <p className="text-sm text-warning">A song this long would go over the video limit (about {Math.ceil(data.video_estimate_credits)} credits to make).</p>
        {data.keep_lines ? (
          <Button variant={primary ? "primary" : "secondary"} onClick={() => setKeeping(true)}>
            Keep the first {data.keep_lines} line{data.keep_lines === 1 ? "" : "s"} · free
          </Button>
        ) : (
          <Link to="?edit=1" className={buttonClass(primary ? "primary" : "secondary")}>
            <Pencil size={20} strokeWidth={1.75} aria-hidden />
            Shorten the lyrics
          </Link>
        )}
      </div>
    ) : (
    <div className="space-y-1">
      <Button variant={primary ? "primary" : "secondary"} icon={Music} charge="fixed" price={data.estimate_credits} busy={a.make.isPending} onClick={() => a.make.mutate()}>
        {label}
      </Button>
      {failed && <p role="alert" className={errorClass}>{failed}</p>}
      <p className="text-sm text-muted">A video this long: about {Math.ceil(data.video_estimate_credits)} credits to make.</p>
    </div>
  );
  return (
    <div className="space-y-4">
      {refused && <p role="alert" className={errorClass}>{refused}</p>}
      {keeping && cut && data.keep_lines ? (
        <Dialog
          title={`Keep the first ${data.keep_lines} line${data.keep_lines === 1 ? "" : "s"}?`}
          cancelLabel="Not yet"
          actionLabel="Keep them"
          busy={put.isPending}
          onCancel={() => setKeeping(false)}
          onConfirm={() => put.mutate({ ...now, text: cut.kept }, { onSuccess: () => { setKeeping(false); toast(`Kept the first ${data.keep_lines} line${data.keep_lines === 1 ? "" : "s"}.`, () => put.mutate(now)); } })}
        >
          <span className="block">The song then ends on:</span>
          <span className="block type-script text-text">{cut.kept.split("\n").filter((l) => l.trim()).at(-1)}</span>
          <span className="block">{cut.dropped} sung line{cut.dropped === 1 ? " is" : "s are"} dropped. Undo puts them back.</span>
          {dropsEnd && <span className="block text-warning">The brand's end line is in the part dropped. On the Song step you can sing it at the end again, or speak it over the end.</span>}
        </Dialog>
      ) : null}
      {data.songs_note && <p className="text-sm text-muted">{data.songs_note}</p>}
      {!data.songs_on && <Banner tone="info" title="Songs aren't switched on here.">The lyrics and music style still save. Takes can be made where songs are on.</Banner>}
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
              <TakeCard key={t.id} t={t} a={a} readOnly={readOnly} others={takes.filter((o) => o.id !== t.id)} onDefaultStyle={defaultStyle} />
            ))}
          </div>
          {!readOnly && data.songs_on && make(current.length === 0 ? "Make 2 takes" : "Make 2 more", current.length === 0)}
        </>
      )}
    </div>
  );
}
