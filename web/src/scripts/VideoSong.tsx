import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Download, Music, RotateCcw, Trash2 } from "lucide-react";
import { api, errorText } from "../api/client";
import { fileUrl } from "../api/upload";
import type { components } from "../api/schema";
import { useMe } from "../auth/useMe";
import { Badge, Banner, Button, Card, Dialog, Panel, Skeleton, buttonClass } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { TakePlayer, clock } from "./TakePlayer";
import { weekStop } from "./useScript";
import { videoCost } from "./TakesStep";
import type { SongTake } from "./useSongs";

type Project = components["schemas"]["ProjectOut"];
const BUSY: SongTake["status"][] = ["making", "timing"];
const length = (t: SongTake) => t.trim_to ?? t.seconds;

/** A song video's takes (its version's, then its own) and the one it is timed to (flows V2a). */
function useVideoSongs(projectId: number, enabled = true) {
  return useQuery({
    enabled,
    queryKey: ["video-songs", projectId],
    queryFn: async () => {
      const { data, error } = await api.GET("/projects/{project_id}/songs", { params: { path: { project_id: projectId } } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    refetchInterval: (q) => (q.state.data?.takes.some((t) => BUSY.includes(t.status)) ? 3000 : false),
  });
}

/** Why "Make 2 more" can't be pressed by this person, or null: an editor's own script is billed to the week, anyone else's to the video's budget; Reed is never limited. */
function useMakeStop(p: Project, price: number | undefined): string | null {
  const { data: me } = useMe();
  const week = useQuery({ enabled: !!p.own_script && me?.role === "editor", queryKey: ["allowance"], queryFn: async () => (await api.GET("/credits/me")).data ?? null });
  if (price === undefined || me?.role !== "editor") return null;
  if (p.own_script) return week.data ? weekStop(week.data, price) : null;
  return p.credits_used + price > p.budget_credits ? "That's more than this video's budget." : null;
}

/** Change song: every take this video can use, the current one marked, "Use this take" (Undo), Make 2 more, and the over-cap trim. */
function ChangeSong({ project: p, onClose, hasShots, hasClips }: { project: Project; onClose: () => void; hasShots: boolean; hasClips: boolean }) {
  const songs = useVideoSongs(p.id);
  const queryClient = useQueryClient();
  const toast = useToast();
  const [asking, setAsking] = useState<SongTake | null>(null);
  const data = songs.data;
  const stop = useMakeStop(p, data?.estimate_credits);
  const refresh = () => Promise.all([queryClient.invalidateQueries({ queryKey: ["video-songs", p.id] }), queryClient.invalidateQueries({ queryKey: ["project", p.id] })]);
  const ok = async <T,>(call: Promise<{ data?: T; error?: unknown; response: Response }>) => {
    const { data: d, error, response } = await call;
    if (!response.ok) throw new Error(errorText(error));
    return d as T;
  };
  const use = useMutation({
    mutationFn: (t: SongTake) => ok(api.PUT("/projects/{project_id}/song", { params: { path: { project_id: p.id } }, body: { take_id: t.id } })),
    onSuccess: async (r, t) => {
      setAsking(null);
      await refresh();
      const was = r?.was_song_take_id;
      toast(`Take ${t.number} is this video's song.`, was ? () => void ok(api.PUT("/projects/{project_id}/song", { params: { path: { project_id: p.id } }, body: { take_id: was } })).then(refresh) : undefined);
    },
  });
  const make = useMutation({ mutationFn: () => ok(api.POST("/projects/{project_id}/songs", { params: { path: { project_id: p.id } } })), onSuccess: refresh });
  const again = useMutation({ mutationFn: (id: number) => ok(api.POST("/songs/{take_id}/try-again", { params: { path: { take_id: id } } })), onSuccess: refresh });
  const trim = useMutation({
    mutationFn: (t: SongTake) => ok(api.POST("/songs/{take_id}/trim", { params: { path: { take_id: t.id } } })),
    onSuccess: async (t) => {
      await refresh();
      toast(`Take ${t?.number} now uses its first ${t?.trim_to ? clock(t.trim_to) : "part"}. The whole take is kept.`, () => void ok(api.DELETE("/songs/{take_id}/trim", { params: { path: { take_id: t!.id } } })).then(refresh));
    },
  });
  const remove = useMutation({
    mutationFn: async (t: SongTake) => {
      await ok(api.DELETE("/songs/{take_id}", { params: { path: { take_id: t.id } } }));
      return t;
    },
    onSuccess: async (t) => {
      await refresh();
      toast(`Take ${t.number} deleted.`, () => void ok(api.POST("/songs/{take_id}/restore", { params: { path: { take_id: t.id } } })).then(refresh));
    },
  });
  // Only the latest press's refusal shows, until the next press.
  const latest = [use, make, again, trim, remove].reduce((x, m) => (m.submittedAt > x.submittedAt ? m : x));
  const refused = latest.isError ? latest.error.message : null;
  const press = (t: SongTake) => (hasShots ? setAsking(t) : use.mutate(t));
  const current = data?.takes.find((t) => t.id === data.song_take_id);

  return (
    <Panel title="Change song" onClose={onClose}>
      {!data ? (
        songs.isError ? (
          <Banner title="Couldn't load the takes." action={<Button variant="secondary" onClick={() => void songs.refetch()}>Try again</Button>}>Nothing was changed.</Banner>
        ) : (
          <div role="status" aria-label="Loading takes" className="space-y-3">
            <Skeleton className="h-28" />
            <Skeleton className="h-28" />
          </div>
        )
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-muted">The lyrics are final. Which take this video uses is yours to choose; the script and other videos don't change.</p>
          {refused && <p role="alert" className={errorClass}>{refused}</p>}
          <ul className="space-y-3">
            {data.takes.map((t) => {
              const inUse = t.id === data.song_take_id;
              const tooLong = t.over_cap && t.trim_to == null;
              const why = t.status === "timing" ? "Reading the song's timing…" : t.status !== "ready" ? null : tooLong ? "Too long for this video." : null;
              return (
                <li key={t.id}>
                  <Card className="space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="type-card">Take {t.number}</h3>
                      {length(t) != null && <span className="text-sm tabular-nums text-muted">{clock(length(t)!)}{videoCost(t)}</span>}
                      {inUse && <Badge tone="accent">In this video</Badge>}
                      {t.in_video && <Badge>Made in this video</Badge>}
                      {t.trim_to != null && <Badge>Uses the first {clock(t.trim_to)}</Badge>}
                      {t.timing_guessed && <Badge tone="warning">Timing guessed</Badge>}
                    </div>
                    {t.status === "making" ? (
                      <p role="status" className="text-sm text-muted">Making…</p>
                    ) : t.file_id !== null && t.seconds !== null ? (
                      <TakePlayer fileId={t.file_id} seconds={t.seconds} peaks={t.peaks} label={`Take ${t.number}`} />
                    ) : null}
                    {(t.status === "failed" || t.status === "timing_failed") && (
                      <div className="space-y-2">
                        <p role="alert" className={errorClass}>{t.failed_reason ?? "Didn't finish · nothing charged."}</p>
                        {t.refused_for && <p className="text-sm text-muted">The lyrics are final in a video: try again, or use another take.</p>}
                        {/* The lyrics are final in a video: the way on is another take, or this one again when a retry can help. */}
                        {t.retry_helps && (
                          <Button variant="ghost" icon={RotateCcw} price={t.status === "failed" ? data.estimate_credits : 0} busy={again.isPending && again.variables === t.id} onClick={() => again.mutate(t.id)}>
                            Try again
                          </Button>
                        )}
                      </div>
                    )}
                    {tooLong && t.fits_until != null && (
                      <Button variant="secondary" busy={trim.isPending && trim.variables?.id === t.id} onClick={() => trim.mutate(t)}>
                        Use the first {clock(t.fits_until)} · free
                      </Button>
                    )}
                    {/* Only takes this video made can be deleted, and not the one it uses (flows V2a); Undo brings it back. */}
                    {t.in_video && !inUse && t.status !== "making" && (
                      <Button variant="ghost" icon={Trash2} busy={remove.isPending && remove.variables?.id === t.id} onClick={() => remove.mutate(t)}>
                        Delete take
                      </Button>
                    )}
                    {!inUse && (t.status === "ready" || t.status === "timing") && (
                      <Button variant="secondary" spread className="sm:w-auto" disabled={!!why} reason={why} busy={use.isPending && use.variables?.id === t.id} onClick={() => press(t)}>
                        Use this take
                      </Button>
                    )}
                  </Card>
                </li>
              );
            })}
          </ul>
          {data.songs_on && (
            <Button variant="secondary" icon={Music} price={data.estimate_credits} disabled={stop !== null} reason={stop} busy={make.isPending} onClick={() => make.mutate()}>
              Make 2 more takes
            </Button>
          )}
          <p className="text-sm text-muted">Same lyrics and style. {p.own_script ? "Counted in your week." : "Counted in this video's budget."}</p>
        </div>
      )}
      {asking && (
        <Dialog title={`Use take ${asking.number}?`} cancelLabel="Not yet" actionLabel="Use it" busy={use.isPending} onCancel={() => setAsking(null)} onConfirm={() => use.mutate(asking)}>
          The shots keep their lines and Sung marks; their times move to take {asking.number} (free).{current && hasClips ? ` Clips already made for take ${current.number} go out of date.` : ""}
        </Dialog>
      )}
    </Panel>
  );
}

/** The video's song as one row above the shots: play, "Song: Take 2 · 0:31", Change song (flows V2a). */
export function SongStrip({ project: p, hasShots, hasClips = false }: { project: Project; hasShots: boolean; hasClips?: boolean }) {
  const songs = useVideoSongs(p.id);
  const [open, setOpen] = useState(false);
  const t = songs.data?.takes.find((x) => x.id === songs.data?.song_take_id);
  return (
    <Card className="flex flex-wrap items-center gap-3">
      <div className="min-w-0 flex-1 basis-60">
        {songs.isPending ? (
          <Skeleton className="h-11" />
        ) : t && t.file_id !== null && t.seconds !== null ? (
          <div className="space-y-1">
            <p className="text-sm">Song: Take {t.number} · {clock(length(t)!)}</p>
            <TakePlayer fileId={t.file_id} seconds={t.seconds} peaks={t.peaks} label={`Take ${t.number}`} />
          </div>
        ) : (
          <p className="text-sm text-muted">{songs.isError ? "Couldn't load the song." : "No song picked for this video yet."}</p>
        )}
      </div>
      <Button variant="secondary" icon={Music} onClick={() => setOpen(true)}>
        Change song
      </Button>
      {open && <ChangeSong project={p} hasShots={hasShots} hasClips={hasClips} onClose={() => setOpen(false)} />}
    </Card>
  );
}

/** The video's song as one inline control for the Video settings row: "Song: Take 2 · 0:31 ▾", opening Change song.
 * No frame of its own; the row gives it. Without knowing whether shots or clips exist, Use this take asks first and warns about clips. */
export function SongSetting({ project: p, hasShots = true, hasClips = true }: { project: Project; hasShots?: boolean; hasClips?: boolean }) {
  const songs = useVideoSongs(p.id);
  const [open, setOpen] = useState(false);
  const t = songs.data?.takes.find((x) => x.id === songs.data?.song_take_id);
  const label = t ? `Song: Take ${t.number}${length(t) != null ? ` · ${clock(length(t)!)}` : ""}` : songs.isPending ? "Song…" : "Song: pick a take";
  return (
    <>
      <Button variant="secondary" icon={Music} trailing={ChevronDown} onClick={() => setOpen(true)} aria-haspopup="dialog">
        {label}
      </Button>
      {open && <ChangeSong project={p} hasShots={hasShots} hasClips={hasClips} onClose={() => setOpen(false)} />}
    </>
  );
}

/** "0:00–0:04"; a shot under 2 s gets tenths ("0:03.2–0:03.8"), so it never reads "0:03–0:03" (Flow-QA on #826). */
const tenths = (x: number) => {
  const r = Math.round(x * 10) / 10; // rounded first, so 59.97 reads 1:00.0, never 0:60.0
  return `${Math.floor(r / 60)}:${(r % 60).toFixed(1).padStart(4, "0")}`;
};
const span = (start: number, end: number) => (end - start < 2 ? `${tenths(start)}–${tenths(end)}` : `${clock(start)}–${clock(end)}`);

/** A song shot's place in the song, in the Breakdown row: "0:00–0:04", Sung or B-roll, and Timing guessed (flows V2).
 * A shot the timing doesn't cover yet (just added or split) says "Needs timing" instead of a made-up time. */
export function SongShotTime({ part, shotId }: { part: components["schemas"]["SongPart"]; shotId: string }) {
  const t = part.shots[shotId];
  if (!t) return <Badge tone="warning">Needs timing</Badge>;
  return (
    <>
      <span className="tabular-nums">{span(t.start, t.end)}</span>
      <Badge tone={t.sung ? "accent" : undefined}>{t.sung ? "Sung" : "B-roll"}</Badge>
      {t.guessed && <Badge tone="warning">Timing guessed</Badge>}
    </>
  );
}

/** Final cut on a song video (flows V6): "Song: take 2, laid under the whole video", Download the song, and, when the video
 * now uses another take, a line saying so (the server marks the video out of date; Make it again is free). */
export function FinalSong({ projectId, madeWith }: { projectId: number; madeWith: number | null | undefined }) {
  const songs = useVideoSongs(projectId, madeWith != null); // a video without a song never asks
  if (madeWith == null) return null; // not a song video
  const takes = songs.data?.takes ?? [];
  const t = takes.find((x) => x.id === madeWith);
  const now = takes.find((x) => x.id === songs.data?.song_take_id);
  if (songs.isPending) return <Skeleton className="h-6 w-2/3" />;
  // The take in the cut may since have been deleted: the line about the take in use still shows.
  if (!t && !now) return null;
  return (
    <div className="space-y-2" aria-label="The song">
      <p className="text-sm">{t ? `Song: take ${t.number}, laid under the whole video` : "Song: an earlier take, laid under the whole video"}</p>
      {now && now.id !== madeWith && <p className="text-sm text-warning">This video now uses take {now.number}. Make it again to lay it under (free).</p>}
      {t && t.file_id != null && (
        <a className={buttonClass("secondary")} href={fileUrl(t.file_id)} download={`song-take-${t.number}.mp3`}>
          <Download size={20} strokeWidth={1.75} aria-hidden />
          Download the song
        </a>
      )}
    </div>
  );
}

/** Whether a song video's final cut is out of date because its song changed (the video now uses another take), for the banner's words. */
export function useSongChanged(projectId: number, madeWith: number | null | undefined) {
  const songs = useVideoSongs(projectId, madeWith != null);
  const now = songs.data?.song_take_id;
  return madeWith != null && now != null && now !== madeWith;
}
