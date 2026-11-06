import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, LoaderCircle, Pencil, Scissors, Sparkles, TriangleAlert } from "lucide-react";
import { api, errorText } from "../api/client";
import { fileUrl } from "../api/upload";
import { Banner, Button, Skeleton, buttonClass } from "../components";
import { useRail } from "../useMedia";
import { useCut, useMakeCut, useProjectClips } from "../projects/useProgress";
import { MusicInspector, PieceInspector } from "./Inspector";
import { Player, Words } from "./Player";
import { Timeline, type Selected } from "./Timeline";
import { clock, useCutEdits, type Cut, type Fix } from "./useCutEdits";

/** Screen 10, the cut editor (v6 S7-01 to S7-07; P-12 on a phone): the cut that plays, its words, the selected piece or
 *  the music, and the timeline. Edits are free and show at once on the timeline; Make the cut (free) makes the next Cut
 *  while this one keeps playing. It reads GET …/cut; the video page's preview panel mounts it in its Cut tab. */
export function CutEditor({
  projectId,
  aspect,
  projectName,
  onBack,
  auto,
}: {
  projectId: number;
  aspect: string;
  projectName: string;
  onBack?: () => void;
  /** no cut yet and every clip approved: make the first one by itself, once (free) */
  auto?: boolean;
}) {
  const rail = useRail();
  const cut = useCut(projectId);
  const make = useMakeCut(projectId);
  const edits = useCutEdits(projectId);
  const sound = useAddSound(projectId);
  const rows = useProjectClips(projectId).data;
  const asked = useRef(false);
  const firstReady =
    !!auto && !!cut.data && !cut.data.number && !cut.data.making && !cut.data.failed && cut.data.can_edit && !!rows?.length && rows.every((r) => r.approved);
  useEffect(() => {
    if (firstReady && !asked.current) {
      asked.current = true;
      make.mutate();
    }
  });
  const [at, setAt] = useState(0);
  const [selected, setSelected] = useState<Selected>(null);
  const [snap, setSnap] = useState(true);
  const [trimming, setTrimming] = useState(false);
  const c = cut.data;
  if (cut.isPending) return <Skeleton className="h-96" />;
  if (cut.isError || !c)
    return (
      <Banner
        title="The cut couldn't be loaded."
        action={
          <Button variant="secondary" onClick={() => void cut.refetch()}>
            Try again
          </Button>
        }
      />
    );
  const error = newest([edits.edit, edits.undoOne, edits.step, edits.fix, make, sound]);
  if (!c.number && !c.making && !c.failed) {
    if (make.isPending || !rows) return <Skeleton className="h-96" />; // the first press is on its way
    const left = rows.filter((r) => !r.approved).length;
    return (
      // no cut yet: made once every clip has its take (free)
      <div className="space-y-2" aria-label="Cut editor">
        {error && <Banner title={error.message} />}
        <Button
          disabled={!rows.length || left > 0}
          reason={!rows.length ? "Make the clips first" : left > 0 ? `Approve every clip first (${left} left)` : undefined}
          onClick={() => make.mutate()}
        >
          Make the cut <span className="opacity-80">· free</span>
        </Button>
        <p className="text-sm text-muted">Puts the clips together in order, with the voice, the music and the presenter.</p>
      </div>
    );
  }
  if (!c.number && !c.making)
    return (
      <div className="space-y-2">
        <Banners cut={c} onFix={(f) => edits.fix.mutate(f)} busy={edits.busy} />
        {error && <Banner title={error.message} />}
      </div>
    ); // the first failed

  if (!rail)
    return (
      <PhoneCut
        cut={c}
        projectId={projectId}
        aspect={aspect}
        projectName={projectName}
        at={at}
        onTime={setAt}
        onBack={onBack}
        onMake={() => make.mutate()}
        making={make.isPending}
        made={make}
      />
    );
  const edit = edits.edit.mutate;
  const piece = selected?.kind === "piece" ? c.timeline.pieces.find((p) => p.id === selected.id) : undefined;
  const first = piece ?? c.timeline.pieces.find((p) => p.start <= at && at < p.end) ?? c.timeline.pieces[0];
  const shown: Selected =
    selected?.kind === "music" && c.timeline.music && !c.timeline.music.removed ? selected : first ? { kind: "piece", id: first.id } : null;
  const building = !c.number && !!c.making;
  const clips = new Set(c.timeline.pieces.map((p) => p.clip_id)).size; // a split piece is still its clip
  const busy = edits.busy || make.isPending;
  const playerWidth = 236;
  return (
    <div className="flex flex-col gap-4" aria-label="Cut editor">
      <Banners cut={c} onFix={(f) => edits.fix.mutate(f)} busy={busy} />
      {error && <Banner title={error.message} />}
      {building ? (
        <FirstCut cut={c} aspect={aspect} width={playerWidth} />
      ) : (
        <>
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold">Cut {c.number}</h2>
            <span className="text-sm text-muted tabular-nums">
              {clock(c.timeline.length)} · {clips} clip{clips === 1 ? "" : "s"}
            </span>
            <span className="grow" />
            <TopRight cut={c} projectName={projectName} busy={busy} onUndoAll={() => edits.step.mutate("undo-all")} onMake={() => make.mutate()} />
          </div>
          <div className="flex items-start gap-5">
            {c.file_id && <Player fileId={c.file_id} length={c.timeline.length} at={at} onTime={setAt} width={playerWidth} aspect={aspect} />}
            <div className="flex min-w-0 grow flex-col gap-3">
              <div className="rounded-lg border border-border bg-surface p-3 shadow-card">
                <Words words={c.timeline.words} text={c.timeline.voice?.text ?? ""} at={at} onSeek={setAt} />
              </div>
              <div className="rounded-lg border border-border bg-surface p-3.5 shadow-card">
                {shown?.kind === "music" ? (
                  <MusicInspector projectId={projectId} cut={c} onEdit={edit} busy={busy} canEdit={c.can_edit} failed={edits.edit.error} />
                ) : first ? (
                  <PieceInspector
                    key={first.id}
                    canEdit={c.can_edit}
                    projectId={projectId}
                    cut={c}
                    piece={first}
                    onEdit={edit}
                    busy={busy}
                    trimming={trimming}
                    onTrim={() => setTrimming(!trimming)}
                    onSound={() => sound.mutate(first.clip_id)}
                    sounding={sound.isPending}
                  />
                ) : null}
              </div>
            </div>
          </div>
        </>
      )}
      <Timeline
        cut={c}
        at={at}
        selected={building ? null : shown}
        snap={snap}
        dim={building}
        building={building ? c.timeline.length * ((c.making?.percent ?? 0) / 100) : undefined}
        onSeek={setAt}
        onSelect={setSelected}
        onSnap={setSnap}
        onUndo={() => edits.step.mutate("undo")}
        onRedo={() => edits.step.mutate("redo")}
        onSplit={() => edit({ kind: "split", at, snap })}
        trimming={trimming}
        onTrim={(id, edge, t) => edit({ kind: "trim", piece: id, [edge]: t, snap })}
        onMusicBack={() => edit({ kind: "music", removed: false })}
        busy={busy}
        canEdit={c.can_edit}
      />
    </div>
  );
}

/** The newest press's error, if it failed: an older error goes once anything is pressed after it. */
function newest(presses: { submittedAt: number; error: Error | null }[]): Error | null {
  const last = presses.reduce((a, b) => (b.submittedAt > a.submittedAt ? b : a), presses[0]);
  return last?.error ?? null;
}

/** Sound effects on the selected piece's clip: #1291's own press (one MMAudio run, priced "up to"). */
function useAddSound(projectId: number) {
  const queryClient = useQueryClient();
  const clips = useProjectClips(projectId);
  return useMutation({
    mutationFn: async (clipId: string) => {
      const row = (clips.data ?? []).find((c) => c.clip_id === clipId);
      if (!row) throw new Error("That clip isn't in this video.");
      const { error, response } = await api.POST("/projects/{project_id}/clips/{clip_id}/sound", {
        params: { path: { project_id: projectId, clip_id: row.id } },
        body: { asked: "" },
      });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: () => Promise.all(["project-cut", "project-clips"].map((k) => queryClient.invalidateQueries({ queryKey: [k, projectId] }))),
  });
}

/** A failed cut's way forward, as the editor and Watch both offer it (rule 22). */
export const fixLabel = (f: Fix) => (f === "loop_music" ? "Loop the music to fit · free" : f === "remove_music" ? "Remove the music" : "Try again · free");

function Banners({ cut, onFix, busy }: { cut: Cut; onFix: (f: "loop_music" | "remove_music" | "again") => void; busy: boolean }) {
  const m = cut.making;
  if (m)
    return (
      <p className="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2.5 text-sm" role="status">
        <LoaderCircle size={14} strokeWidth={1.75} className="animate-spin text-accent-text" aria-hidden />
        {cut.number
          ? `Making Cut ${m.number}${m.changes ? ` with your ${m.changes} change${m.changes === 1 ? "" : "s"}` : ""} · free · about ${m.about_seconds} s. Cut ${cut.number} keeps playing until then.`
          : `Making the cut: ${m.doing} · ${m.percent}%`}
      </p>
    );
  if (cut.failed)
    return (
      <div className="flex items-center gap-2 rounded-lg bg-danger-soft px-3 py-2.5 text-sm text-danger" role="alert">
        <TriangleAlert size={14} strokeWidth={1.75} className="flex-none" aria-hidden />
        <span className="min-w-0 flex-1">{cut.failed.why}</span>
        {cut.can_edit &&
          cut.failed.fixes.map((f, i) => (
            <Button key={f} variant={i === 0 ? "primary" : "secondary"} disabled={busy} onClick={() => onFix(f)}>
              {fixLabel(f)}
            </Button>
          ))}
      </div>
    );
  if (cut.director.editing)
    return (
      <p className="flex items-start gap-2 rounded-lg bg-accent-soft px-3 py-2.5 text-sm text-accent-text" role="status">
        <Sparkles size={14} strokeWidth={1.75} className="mt-0.5 flex-none" aria-hidden />
        <span>
          <b className="font-semibold">The director is editing:</b> {cut.director.doing.replace(/\.$/, "")}. Its edits are marked with a dot.
        </span>
      </p>
    );
  return null;
}

function TopRight({ cut, projectName, busy, onUndoAll, onMake }: { cut: Cut; projectName: string; busy: boolean; onUndoAll: () => void; onMake: () => void }) {
  if (cut.making)
    return (
      <span className="text-sm text-muted">
        Cut {cut.making.number} in about {cut.making.about_seconds} s
      </span>
    );
  if (cut.director.editing)
    return (
      <span className="flex items-center gap-1 text-sm text-muted">
        <LoaderCircle size={12} strokeWidth={1.75} className="animate-spin" aria-hidden />
        Editing · you can watch
      </span>
    );
  if ((cut.changes > 0 || cut.out_of_date) && !cut.failed && cut.can_edit)
    return (
      <span className="flex items-center gap-2">
        {cut.changes > 0 && (
          <span className="flex items-center gap-1 text-sm text-warning">
            <Pencil size={12} strokeWidth={1.75} aria-hidden />
            {cut.changes} change{cut.changes === 1 ? "" : "s"} not in the cut yet
          </span>
        )}
        {cut.changes > 0 && (
          <Button variant="secondary" disabled={busy} onClick={onUndoAll}>
            Undo all
          </Button>
        )}
        <Button icon={Scissors} busy={busy} onClick={onMake}>
          Make the cut <span className="opacity-80">· free</span>
        </Button>
      </span>
    );
  if (!cut.file_id) return null;
  return (
    <a className={buttonClass(cut.failed ? "secondary" : "primary")} href={fileUrl(cut.file_id)} download={`${projectName}.mp4`}>
      <Download size={16} strokeWidth={1.75} aria-hidden />
      {cut.failed ? `Download Cut ${cut.number}` : "Download MP4"}
    </a>
  );
}

/** S7-04: the first cut is being made: a waiting player, the words, and the timeline greyed out until it's ready. */
function FirstCut({ cut, aspect, width }: { cut: Cut; aspect: string; width: number }) {
  return (
    <div className="flex items-start gap-5">
      <div
        className="flex flex-none flex-col items-center justify-center gap-2 rounded-[10px] bg-surface-2 text-muted"
        style={{ width, aspectRatio: aspect.replace(":", " / ") }}
      >
        <LoaderCircle size={24} strokeWidth={1.75} className="animate-spin" aria-hidden />
        <span className="text-sm">Making the cut</span>
      </div>
      <div className="flex min-w-0 grow flex-col gap-3">
        <div className="rounded-lg border border-border bg-surface p-3 shadow-card">
          <Words words={cut.timeline.words} text={cut.timeline.voice?.text ?? ""} at={0} onSeek={() => {}} />
        </div>
        <p className="text-sm text-muted">The timeline wakes up when the first cut is ready. Every clip is already in Clips.</p>
      </div>
    </div>
  );
}

/** P-12: the cut on a phone. It plays, lists the edits in this cut with Undo, and points to the director for more. */
function PhoneCut({
  cut,
  projectId,
  aspect,
  projectName,
  at,
  onTime,
  onBack,
  onMake,
  making,
  made,
}: {
  cut: Cut;
  projectId: number;
  aspect: string;
  projectName: string;
  at: number;
  onTime: (t: number) => void;
  onBack?: () => void;
  onMake: () => void;
  making: boolean;
  made: { submittedAt: number; error: Error | null };
}) {
  const edits = useCutEdits(projectId);
  const phoneError = newest([edits.undoOne, edits.fix, made]);
  const waiting = cut.can_edit && !cut.making && !cut.failed && (cut.changes > 0 || cut.out_of_date);
  const live = cut.edits.filter((e) => !e.undone && e.applies);
  return (
    <div className="flex flex-col" aria-label="Cut">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        {onBack && (
          <button type="button" aria-label="Back" onClick={onBack} className="flex size-9 items-center justify-center text-muted">
            ‹
          </button>
        )}
        <div className="flex flex-col">
          <span className="font-semibold">Cut {cut.number ?? 1}</span>
          <span className="text-xs text-muted">
            {clock(cut.timeline.length)} · {projectName}
          </span>
        </div>
      </div>
      <div className="space-y-2 px-3 pt-3">
        <Banners cut={cut} onFix={(f) => edits.fix.mutate(f)} busy={edits.busy} />
        {phoneError && <Banner title={phoneError.message} />}
        {waiting && (
          <Button icon={Scissors} busy={making} disabled={edits.busy} onClick={onMake} className="w-full">
            {cut.changes > 0 ? `${cut.changes} change${cut.changes === 1 ? "" : "s"} · ` : ""}Make the cut <span className="opacity-80">· free</span>
          </Button>
        )}
      </div>
      <div className="flex justify-center py-3">
        {cut.file_id ? (
          <Player fileId={cut.file_id} length={cut.timeline.length} at={at} onTime={onTime} width={200} aspect={aspect} />
        ) : (
          <div
            className="flex flex-col items-center justify-center gap-2 rounded-[10px] bg-surface-2 text-sm text-muted"
            style={{ width: 200, aspectRatio: aspect.replace(":", " / ") }}
          >
            <LoaderCircle size={24} strokeWidth={1.75} className="animate-spin" aria-hidden />
            Making the cut
          </div>
        )}
      </div>
      <h2 className="px-3.5 pt-1 pb-2 text-sm font-semibold">Edits in this cut</h2>
      <ul>
        {live.map((e) => (
          <li key={e.id} className="flex items-center gap-3 border-b border-border bg-surface px-3.5 py-2.5">
            <span className="rounded-sm bg-accent-soft px-1.5 text-xs font-medium text-accent-text tabular-nums">{clock(e.at)}</span>
            <span className="grow text-sm">
              {e.said}
              {e.director ? " (the director)" : ""}
            </span>
            {cut.can_edit && (
              <button type="button" className="min-h-11 text-sm text-accent-text" disabled={edits.busy} onClick={() => edits.undoOne.mutate(e.id)}>
                Undo
              </button>
            )}
          </li>
        ))}
        {!live.length && <li className="px-3.5 py-2.5 text-sm text-muted">No edits yet.</li>}
      </ul>
      <p className="px-3.5 py-2.5 text-xs text-muted">The full timeline is on desktop. Ask the director for any edit here.</p>
    </div>
  );
}
