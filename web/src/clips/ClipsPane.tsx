import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronLeft, ChevronRight, Play, Search } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { fileUrl } from "../api/upload";
import { GOING, useJobs } from "../clip/History";
import { Banner, Button, Skeleton } from "../components";
import { useProjectClips } from "../projects/useProgress";
import { useRunProgress } from "../videos/RunCard";
import { useMedia } from "../useMedia";
import { useOnChange } from "../useOnChange";
import { Empty, SOON } from "../videos/Empty";
import type { PaneProps } from "../videos/Preview";
import { ClipOpen } from "./ClipOpen";
import { RowStatus } from "./RowStatus";
import { needsYou, passes, redone, scenesOf, useStoryboard, type Filter, type Row, type Scene } from "./data";
import { useBreakdownOf } from "./useBreakdownOf";
import { useCast, type Cast } from "../cast/gate";

/** A clip whose still or take waits for the cast and places OK (#1331's paused clips): "Nate waits for the cast and places
 *  OK. Approve them in Cast to go on." */
function held(scenes: Scene[], gate: Cast | null): Scene[] {
  if (!gate?.paused_clips.length) return scenes;
  const waiting = gate.items.filter((i) => i.approval !== "approved");
  return scenes.map((s) => ({
    ...s,
    rows: s.rows.map((r) => {
      if (!gate.paused_clips.includes(r.clip_id) || r.take_id) return r;
      const who = waiting.filter((i) => i.clip_ids.includes(r.clip_id)).map((i) => i.name);
      const said = who.length ? `${who.length < 2 ? who.join("") : `${who.slice(0, -1).join(", ")} and ${who.at(-1)}`} wait${who.length === 1 ? "s" : ""}` : "This clip waits";
      return { ...r, state: "waiting" as const, note: `${said} for the cast and places OK. Approve them in Cast to go on.` };
    }),
  }));
}

/** The grid shows a video of this many clips or fewer until one is opened (S-gaps-08 1). */
const GRID = 12;
/** Over this many clips, only the open clip's scene starts unfolded (S6-04). */
const FOLDED = 30;

const lineTone = (r: Row) => (r.state === "flagged" || r.state === "waiting" ? "text-warning" : r.state === "failed" ? "text-danger" : "text-accent-text");

/** One clip in the list (S6-02, S6-04, S6-05, P-10): its still, number, length and model, what it shows, and its state. */
function ClipRow({ r, open, onOpen, phone }: { r: Row; open: boolean; onOpen: () => void; phone: boolean }) {
  return (
    <li>
      <button type="button" onClick={onOpen} aria-current={open || undefined} className={`flex w-full items-center gap-3 border-t border-border px-2.5 py-1.5 text-left ${open ? "bg-accent-soft" : "hover:bg-surface-2"} ${r.changed && !r.watched ? "outline-1 -outline-offset-1 outline-accent" : ""}`}>
        {r.frame_file_id ? <img src={fileUrl(r.frame_file_id)} alt="" className="h-16 w-9 shrink-0 rounded-[3px] bg-black object-cover" /> : <span aria-hidden className={`h-16 w-9 shrink-0 rounded-[3px] ${r.state === "making" ? "shimmer" : "border border-dashed border-border-strong bg-surface-2"}`} />}
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="flex items-baseline gap-2">
            <span className="shrink-0 text-sm font-semibold whitespace-nowrap">Clip {r.number}</span>
            {!phone && <span className="truncate text-xs text-muted">{[`${r.seconds} s`, r.model].filter(Boolean).join(" · ")}</span>}
          </span>
          <span className="truncate text-xs text-muted">{r.label}</span>
          {r.state === "making" && r.percent != null && (
            <span className="mt-1 h-1 w-40 overflow-hidden rounded-full bg-surface-3" role="progressbar" aria-valuenow={r.percent} aria-label={`Clip ${r.number} made so far`}>
              <i className="block h-full rounded-full bg-accent" style={{ width: `${r.percent}%` }} />
            </span>
          )}
          {r.note && !phone && <span className={`truncate text-xs ${r.state === "making" ? "text-muted" : lineTone(r)}`}>{r.note}</span>}
        </span>
        <RowStatus r={r} phone={phone} />
      </button>
    </li>
  );
}

/** A scene's header: folds its clips away, with how many are made (S6-04 "9 of 9"). */
function SceneHead({ s, open, onToggle, long, phone }: { s: Scene; open: boolean; onToggle: () => void; long: boolean; phone: boolean }) {
  const Chevron = open ? ChevronDown : ChevronRight;
  const name = long || phone ? `${s.id}. ${s.name}` : `Scene ${s.id}${s.name ? ` · ${s.name}` : ""}`;
  return (
    <button type="button" onClick={onToggle} aria-expanded={open} className={`flex w-full items-center gap-2 border-t border-border px-2.5 text-left first:border-t-0 ${phone ? "min-h-11 bg-transparent text-base font-semibold" : "min-h-9 bg-surface-2 text-xs font-medium text-muted"}`}>
      <Chevron size={phone ? 16 : 12} strokeWidth={1.75} aria-hidden />
      <span className={`flex-1 truncate ${phone ? "text-text" : "font-semibold text-text"}`}>{name}</span>
      <span className="tabular-nums">{long || phone ? `${s.done}${phone ? "/" : " of "}${s.rows.length}` : s.rows.length}</span>
    </button>
  );
}

/** A clip in the plan with no prompt yet: what it shows and what comes first. */
function NotMade({ row, lean }: { row: Row; lean: boolean }) {
  return (
    <section aria-label={`Clip ${row.number}`} className="flex flex-col gap-2">
      <h3 className="text-lg font-semibold">Clip {row.number}</h3>
      <p className="text-sm text-muted">{row.label}</p>
      <p className="text-sm">{lean ? "Not made yet: the director makes its take from the plan. Ask it in the chat to start." : "Not made yet: the director writes its prompt first, then makes its still and its take. Ask it in the chat to start."}</p>
    </section>
  );
}

/** The clip cards of a short video (S6-01): each plays in place, says its state and what it shows; a press opens it. */
function Grid({ rows, takes, onOpen, phone }: { rows: Row[]; takes: Map<string, number | null>; onOpen: (r: Row) => void; phone: boolean }) {
  return (
    <ul className={`grid gap-4 ${phone ? "grid-cols-2" : "grid-cols-[repeat(auto-fill,150px)]"}`}>
      {rows.map((r) => {
        const video = takes.get(r.clip_id);
        return (
          <li key={r.clip_id} className="flex min-w-0 flex-col gap-2">
            <button type="button" onClick={() => onOpen(r)} aria-label={`Open clip ${r.number}`} className={`relative aspect-[150/266] w-full overflow-hidden rounded-lg bg-black ${r.changed && !r.watched ? "outline-2 outline-offset-2 outline-accent" : ""}`}>
              {video ? <video src={fileUrl(video)} muted preload="metadata" className="size-full object-cover" /> : r.frame_file_id ? <img src={fileUrl(r.frame_file_id)} alt="" className="size-full object-cover" /> : <span className={`block size-full ${r.state === "making" ? "shimmer" : "bg-surface-2"}`} />}
              {video && (
                <span aria-hidden className="absolute inset-0 grid place-items-center">
                  <span className="grid size-11 place-items-center rounded-full bg-black/45 text-white backdrop-blur-sm">
                    <Play size={18} strokeWidth={1.75} />
                  </span>
                </span>
              )}
              <span className="absolute right-1.5 bottom-1.5 rounded-[3px] bg-black/60 px-1.5 text-[11px] leading-4 font-semibold text-white">{r.seconds} s</span>
            </button>
            {/* The name on one line and the state under it: a long state ("Making · about 1 min") never wraps "Clip 1" or
                runs into the next card (MAIN's run, video 233, at 1440 and 390). */}
            <span className="flex min-w-0 flex-col gap-0.5">
              <span className="whitespace-nowrap text-sm font-semibold">Clip {r.number}</span>
              <RowStatus r={r} phone={phone} wrap />
            </span>
            {!phone && <span className="whitespace-pre-line text-xs text-muted">{r.said || r.label}</span>}
          </li>
        );
      })}
    </ul>
  );
}

/** The video's Clips tab (v6 S6-01 to S6-06, P-10, P-11, S-gaps-08): grouped by scene, filtered, one clip open with its
 *  takes, prompt, model and why, what the director's watch found and did, and its presses with "up to" prices. Short
 *  videos open as a grid. Replaces ClipsPane and ClipsStep (rule 26). */
export function ClipsPane({ p, head, progress, go }: PaneProps) {
  const phone = !useMedia("(min-width: 768px)");
  const [params, setParams] = useSearchParams();
  const queryClient = useQueryClient();
  const clips = useProjectClips(p.id);
  // Takes, stills and rewrites land later: whenever this video's going jobs change, the clips and stills are read again.
  const jobs = useJobs(p.id);
  const going = jobs.data?.filter((j) => GOING.includes(j.status)).map((j) => j.id).join(",");
  useOnChange(going, () => {
    for (const queryKey of [["project-clips", p.id], ["storyboard", p.id], ["run-progress", p.id]]) void queryClient.invalidateQueries({ queryKey });
  });
  const frames = useStoryboard(p.id);
  const breakdown = useBreakdownOf(p.id);
  const run = useRunProgress(p.id);
  const cast = useCast(p.id);
  const [filter, setFilter] = useState<Filter>("all");
  const [find, setFind] = useState("");
  const [folded, setFolded] = useState<Record<number, boolean>>({});
  const scenes = useMemo(() => held(scenesOf(breakdown.data?.breakdown, clips.data ?? [], frames.data ?? [], run.data), cast.data ?? null), [breakdown.data, clips.data, frames.data, run.data, cast.data]);
  const rows = scenes.flatMap((s) => s.rows);
  // A Review row's old link (?to=Clip c2) opens that clip.
  const openId = params.get("clip") ?? params.get("to")?.match(/c\d+/i)?.[0] ?? null;
  // A long list always has one clip open (S6-02, S6-04): the first that needs you, else the first.
  const opened = rows.find((r) => r.clip_id === openId) ?? (rows.length > GRID && !phone ? (rows.find(needsYou) ?? rows[0] ?? null) : null);
  const open = (r: Row | null) => setParams((now) => (r ? now.set("clip", r.clip_id) : now.delete("clip"), now), { replace: true });
  if (clips.isPending || breakdown.isPending || run.isPending) return <Skeleton className="h-64" />;
  if (clips.isError) return <Banner tone="warning" title="Couldn’t load the clips." action={<Button variant="secondary" onClick={() => void clips.refetch()}>Try again</Button>} />;
  if (rows.length === 0) return <Empty title="The clips fill in here">{progress.shots.made ? "The director writes each clip’s prompt, then makes its takes. They show here as they land." : SOON}</Empty>;
  // The filter's own rule counts what it lists, on the phone and the desktop alike (MAIN's run: 5 against 6).
  const counts = { all: rows.length, needs_you: rows.filter(needsYou).length, flagged: rows.filter((r) => r.state === "flagged" || r.found).length, redone: rows.filter(redone).length };
  const made = run.data?.made ?? rows.filter((r) => r.take_id).length;
  const seconds = rows.reduce((n, r) => n + r.seconds, 0);
  const long = rows.length > FOLDED;
  const q = find.trim().toLowerCase();
  const shown = (r: Row) => passes(filter)(r) && (!q || `clip ${r.number} ${r.label} ${r.words}`.toLowerCase().includes(q));
  const takes = new Map((clips.data ?? []).map((c) => [c.clip_id, c.file_id]));
  const clip = opened && (clips.data ?? []).find((c) => c.clip_id === opened.clip_id);
  const filters: [Filter, string, number][] = [["all", "All", counts.all], ["needs", "Needs you", counts.needs_you], ["flagged", "Flagged", counts.flagged], ["redone", "Redone", counts.redone]];
  const seg = (
    <div role="tablist" aria-label="Show" className="inline-flex max-w-full gap-0.5 overflow-x-auto rounded-md bg-surface-2 p-0.5">
      {filters
        .filter(([f]) => !phone || f !== "needs")
        .map(([f, word, n]) => (
          <button key={f} type="button" role="tab" aria-selected={filter === f} onClick={() => (setFilter(f), f === "all" && rows.length <= GRID && open(null))} className={`inline-flex h-7 shrink-0 items-center rounded-[5px] px-3 text-[13px] font-medium ${filter === f ? "bg-surface text-text shadow-[var(--shadow-soft,0_1px_2px_rgb(28_27_25/0.06))]" : "text-muted"} max-sm:h-11`}>
            {word} {n}
          </button>
        ))}
    </div>
  );
  // A phone opens one clip full screen (P-11); Back returns to the list.
  if (phone && opened && !clip)
    return (
      <div className="flex flex-col gap-3">
        <Button variant="ghost" icon={ChevronLeft} className="self-start" onClick={() => open(null)}>
          All clips
        </Button>
        <NotMade row={opened} lean={p.engine === "one_pass"} />
      </div>
    );
  if (phone && opened && clip)
    return (
      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <Button variant="ghost" icon={ChevronLeft} aria-label="Back to the clips" onClick={() => open(null)} />
          <span className="flex flex-col">
            <span className="text-base font-semibold">Clip {opened.number}</span>
            <span className="text-xs text-muted">{[`Scene ${opened.scene}`, `${opened.seconds} s`, opened.model].filter(Boolean).join(" · ")}</span>
          </span>
        </div>
        <ClipOpen key={clip.id} p={p} head={head} row={opened} clip={clip} frames={frames.data ?? []} scene={scenes.find((s) => s.id === opened.scene)!} phone onCast={() => go("cast")} />
      </div>
    );
  // A short video opens as cards until one is pressed (S6-01, S-gaps-08 1).
  if (rows.length <= GRID && !opened && filter === "all" && !q)
    return (
      <div className="flex flex-col gap-4">
        <div className="flex items-baseline justify-between gap-3">
          {!phone && <h2 className="text-lg font-semibold">Clips</h2>}
          <span className={`${phone ? "text-xs" : "text-sm"} text-muted`}>
            {rows.length} clip{rows.length === 1 ? "" : "s"} · {seconds} s{made === rows.length ? " · all in the cut" : ` · ${made} made`}
          </span>
        </div>
        <Grid rows={rows} takes={takes} onOpen={open} phone={phone} />
      </div>
    );
  const list = (
    <ul aria-label="Clips by scene" className={`overflow-hidden ${phone ? "" : "rounded-lg border border-border bg-surface"}`}>
      {scenes.map((s) => {
        const visible = s.rows.filter(shown);
        if (visible.length === 0) return null;
        const unfolded = folded[s.id] ?? (filter !== "all" || !!q || !long || (opened ? opened.scene === s.id : s === scenes.find((x) => x.done < x.rows.length) || s === scenes[0]));
        return (
          <li key={s.id}>
            <SceneHead s={s} open={unfolded} long={long} phone={phone} onToggle={() => setFolded({ ...folded, [s.id]: !unfolded })} />
            {unfolded && (
              <ul>
                {visible.map((r) => (
                  <ClipRow key={r.clip_id} r={r} open={opened?.clip_id === r.clip_id} onOpen={() => open(r)} phone={phone} />
                ))}
              </ul>
            )}
          </li>
        );
      })}
    </ul>
  );
  return (
    <div className="@container flex min-h-0 flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        {seg}
        {long && !phone && (
          <label className="flex h-[30px] w-[200px] items-center gap-2 rounded-md border border-border-strong bg-bg px-2 text-sm text-muted">
            <Search size={14} strokeWidth={1.75} aria-hidden />
            <input value={find} onChange={(e) => setFind(e.target.value)} placeholder="Find a clip or a line" aria-label="Find a clip or a line" className="min-w-0 flex-1 bg-transparent text-text outline-none placeholder:text-muted" />
          </label>
        )}
        <span className="flex-1" />
        {!phone && <span className="text-sm text-muted">{long || made < rows.length ? `${made} of ${rows.length} made` : rows.length <= GRID ? `${rows.length} clips · grouped by scene` : "Grouped by scene"}</span>}
      </div>
      {rows.length <= GRID && opened && !phone && (
        <button type="button" onClick={() => (setFilter("all"), open(null))} className="inline-flex items-center gap-1 self-start text-sm text-muted hover:text-text">
          <ChevronLeft size={14} strokeWidth={1.75} aria-hidden />
          All clips
        </button>
      )}
      {phone ? (
        list
      ) : (
        // The preview has a set width now (Reed, 9 Nov): below 720px of room the list goes above the open clip (a short video's
        // list hides, its "All clips" is the way back), so the clip keeps the width its takes and details need.
        <div className="flex min-h-0 flex-col gap-4 @[720px]:flex-row @[720px]:items-start">
          <div className={`w-full @[720px]:w-[240px] ${long ? "@[760px]:w-[330px]" : "@[760px]:w-[300px]"} max-h-48 shrink-0 overflow-y-auto @[720px]:max-h-[calc(100dvh-220px)] ${rows.length <= GRID && opened ? "hidden @[720px]:block" : ""}`}>{list}</div>
          <div className="min-w-0 flex-1">{opened && clip ? <ClipOpen key={clip.id} p={p} head={head} row={opened} clip={clip} frames={frames.data ?? []} scene={scenes.find((s) => s.id === opened.scene)!} phone={false} onCast={() => go("cast")} /> : opened ? <NotMade row={opened} lean={p.engine === "one_pass"} /> : <p className="pt-2 text-sm text-muted">Pick a clip to see its takes, its prompt and what the director did.</p>}</div>
        </div>
      )}
    </div>
  );
}
