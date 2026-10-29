import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Music, RotateCcw } from "lucide-react";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { useMe } from "../auth/useMe";
import { Badge, Banner, Button, Card, Dialog, Panel, Skeleton } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { TakePlayer, clock } from "./TakePlayer";
import { weekStop } from "./useScript";
import type { SongTake } from "./useSongs";

type Project = components["schemas"]["ProjectOut"];
const BUSY: SongTake["status"][] = ["making", "timing"];
const length = (t: SongTake) => t.trim_to ?? t.seconds;

/** A song video's takes (its version's, then its own) and the one it is timed to (flows V2a). */
function useVideoSongs(projectId: number) {
  return useQuery({
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
function ChangeSong({ project: p, onClose, hasShots }: { project: Project; onClose: () => void; hasShots: boolean }) {
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
  // Only the latest press's refusal shows, until the next press.
  const latest = [use, make, again, trim].reduce((x, m) => (m.submittedAt > x.submittedAt ? m : x));
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
                      {length(t) != null && <span className="text-sm tabular-nums text-muted">{clock(length(t)!)}</span>}
                      {inUse && <Badge tone="accent">In this video</Badge>}
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
          The shots keep their lines and Sung marks; their times move to take {asking.number} (free).{current ? ` Clips already made for take ${current.number} go out of date.` : ""}
        </Dialog>
      )}
    </Panel>
  );
}

/** The video's song as one row above the shots: play, "Song: Take 2 · 0:31", Change song (flows V2a). */
export function SongStrip({ project: p, hasShots }: { project: Project; hasShots: boolean }) {
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
      {open && <ChangeSong project={p} hasShots={hasShots} onClose={() => setOpen(false)} />}
    </Card>
  );
}
