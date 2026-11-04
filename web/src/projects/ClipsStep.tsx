import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { GOING, useJobs } from "../clip/History";
import { useBreakdown } from "./BreakdownPane";
import { ReviewChip } from "./Checks";
import { ClipsPane } from "./ClipsPane";
import { HostPieces } from "./HostPieces";
import { Dot } from "./OtherTakes";
import { StoryboardPane, useFrames } from "./StoryboardPane";
import { useProjectClips } from "./useProgress";

type Clip = components["schemas"]["ProjectClipOut"];
type Frame = components["schemas"]["FrameOut"];
type Shot = components["schemas"]["Shot"];

/** What the clip list says about a clip, as a dot and words. */
function clipStatus(c: Clip | undefined, f: Frame | undefined, making: boolean, failed: boolean): [tone: "ok" | "need" | "run" | "none", words: string] {
  if (c?.approved) return ["ok", "Approved"];
  if (making || f?.drawing) return ["run", "Making"];
  if (c?.stale || f?.still_stale) return ["need", "Out of date"];
  const picked = c?.takes.find((t) => t.id === c.picked_take_id);
  return picked ? ["need", `Check take ${picked.number}`] : failed ? ["need", "Didn't finish"] : ["none", "No take yet"];
}

/** A shot's script line as the list shows it: "BO: Is that… salmon?", or its action in brackets. */
const lineOf = (s: Shot) => (s.line ? (s.speaker ? `${s.speaker.toUpperCase()}: ${s.line}` : s.line) : s.action ? `(${s.action})` : "");

/** The Clips tab (v4): one place per clip. Left, the clips with their still, line and status; right, the one picked, with
 *  its takes, then its still as a thumbnail beside its prompt and the note for the next take. The stills' and the takes' one-press actions sit above the list. The stills and the
 *  takes keep their own panes (their locks, holds and prices); this only lays them out. */
export function ClipsStep(props: {
  projectId: number;
  brandId: number;
  aspect: string;
  projectName: string;
  used: number;
  budget: number;
  scriptVersion: number;
  castRedraw?: { [key: string]: unknown } | null;
  clipCount?: number;
  /** Why the takes can't be made yet (the stills aren't approved), or null. */
  clipsLock: string | null;
  stillsHold: string | null;
  clipsHold: { why: string; at: string } | null;
}) {
  const { projectId } = props;
  const frames = useFrames(projectId);
  const clips = useProjectClips(projectId);
  const jobs = useJobs();
  const breakdown = useBreakdown(projectId, props.scriptVersion);
  const [picked, setPicked] = useState<string | null>(null);
  // A Review row names the card to go to ("Clip c2", "Frame c2"): that clip is picked once, when the address names it, so a
  // press on another clip in the list still wins while ?to= stays in the address (QA-11).
  const to = useSearchParams()[0].get("to")?.match(/^(?:Clip|Frame) (c\d+)$/)?.[1];
  const [toSeen, setToSeen] = useState<string>();
  if (to !== toSeen) {
    setToSeen(to);
    if (to) setPicked(to);
  }
  const [stillsBar, setStillsBar] = useState<HTMLDivElement | null>(null);
  const [clipsBar, setClipsBar] = useState<HTMLDivElement | null>(null);
  const [still, setStill] = useState<HTMLDivElement | null>(null);
  const plan = breakdown.data?.breakdown;
  const shots = new Map((plan?.scenes ?? []).flatMap((s) => s.shots).map((s) => [s.id, s]));
  const line = (clipId: string) =>
    (plan?.clips.find((c) => c.id === clipId)?.shot_ids ?? []).map((id) => shots.get(id)).filter((s): s is Shot => !!s).map(lineOf).find(Boolean) ?? "";
  const rows = clips.data ?? [];
  const stills = frames.data ?? [];
  const ids = [...new Set([...stills.map((f) => f.clip_id), ...rows.map((c) => c.clip_id)])];
  const going = (j: { status: string }) => GOING.includes(j.status);
  const making = (c?: Clip, f?: Frame) => (jobs.data ?? []).some((j) => going(j) && ((c && j.step === "clip_take" && j.project_clip_id === c.id) || (f && j.step === "frame" && j.frame_id === f.id)));
  const status = (id: string) => {
    const c = rows.find((r) => r.clip_id === id);
    const f = stills.find((r) => r.clip_id === id);
    // Its newest take failed, and not before a change to its prompt (that one is about the old prompt).
    const last = (jobs.data ?? []).filter((j) => c && j.step === "clip_take" && j.project_clip_id === c.id).sort((a, b) => b.id - a.id)[0];
    const change = c?.change as { status?: string; job_id?: number } | null | undefined;
    const failed = last?.status === "failed" && !(change?.status === "done" && (change.job_id ?? 0) >= last.id);
    return clipStatus(c, f, making(c, f), failed);
  };
  const open = props.clipsLock === null; // the takes part, once the stills are approved
  // The stills come first until they're approved, then the takes (a hold says why they wait).
  const stillsFirst = !open;
  // Until one is picked: the first clip whose take needs you, else the first still to approve, else the first.
  const stillToApprove = (id: string) => stills.some((f) => f.clip_id === id && f.file_id !== null && !f.approved);
  const selected = picked && ids.includes(picked) ? picked : (ids.find((id) => status(id)[0] === "need") ?? ids.find(stillToApprove) ?? ids[0]);
  const hasCard = open && rows.some((c) => c.clip_id === selected);
  // Nothing drawn and no clips yet: the stills' own first screen (Make the stills). The stills' pane stays where it is in
  // the page either way, so a run it started (draw every still once the frames are written) carries on as the list fills.
  const list = ids.length > 0;
  const only = list ? (selected ?? "") : undefined;
  const storyboard = (
    <StoryboardPane
      second={!stillsFirst}
      hold={props.stillsHold}
      castRedraw={props.castRedraw}
      oneStep
      clips={props.clipCount}
      projectId={projectId}
      brandId={props.brandId}
      aspect={props.aspect}
      used={props.used}
      budget={props.budget}
      only={only}
      bar={list ? stillsBar : undefined}
      into={hasCard ? still : null}
    />
  );
  const seconds = (id: string) => rows.find((c) => c.clip_id === id)?.seconds ?? plan?.clips.find((c) => c.id === id)?.seconds;
  return (
    // v5 (B_VideoSteps): the clip list on the left, edge to edge under the tabs; the picked clip on the right.
    <div className={list ? "grid gap-5 lg:-mx-8 lg:-mt-4 lg:grid-cols-[340px_minmax(0,1fr)] lg:gap-0" : ""}>
      {list && (
        <div className="min-w-0 lg:border-r lg:border-border">
          <ul aria-label="Clip list" className="flex flex-col border-t border-border lg:border-t-0">
            {ids.map((id) => {
              const f = stills.find((r) => r.clip_id === id);
              const [tone, words] = status(id);
              const on = id === selected;
              return (
                <li key={id}>
                  <button type="button" aria-current={on || undefined} onClick={() => setPicked(id)} className={`grid w-full grid-cols-[28px_minmax(0,1fr)] items-center gap-3 border-b border-border px-4 py-2 text-left ${on ? "bg-surface-2" : "hover:bg-surface-2"}`}>
                    <span className="block w-7 overflow-hidden rounded-md bg-surface-3" style={{ aspectRatio: props.aspect.replace(":", " / ") }}>
                      {f?.file_id != null && <img src={fileUrl(f.file_id)} alt="" className="h-full w-full object-cover" />}
                    </span>
                    <span className="flex min-w-0 flex-col gap-0.5">
                      <span className="flex flex-wrap items-center justify-between gap-x-2">
                        <span className="text-sm font-medium tabular-nums">
                          Clip {id.replace(/^c/, "")}
                          {seconds(id) !== undefined && ` · ${seconds(id)} s`}
                        </span>
                        <Dot tone={tone}>{words}</Dot>
                      </span>
                      {line(id) && <span className="block truncate font-script text-xs text-text/80">{line(id)}</span>}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
          {/* The whole step's presses (Redo stills, the Review list) sit under the list, out of the clip's way. */}
          <div className="space-y-2 pt-4 lg:p-4">
            <ReviewChip projectId={projectId} />
            <div ref={setStillsBar} className="space-y-2 empty:hidden" />
            <div ref={setClipsBar} className="space-y-2 empty:hidden" />
            <HostPieces projectId={projectId} aspect={props.aspect} />
          </div>
        </div>
      )}
      <section className={`min-w-0 space-y-4 ${list ? "lg:px-8 lg:py-6" : ""}`} aria-label={selected ? `Clip ${selected.replace(/^c/, "")}` : "Stills"}>
        {open && list && (
          <ClipsPane
            hold={props.clipsHold?.why ?? null}
            review
            projectId={projectId}
            brandId={props.brandId}
            aspect={props.aspect}
            projectName={props.projectName}
            used={props.used}
            budget={props.budget}
            only={selected ?? null}
            bar={clipsBar}
            stillSlot={setStill}
            line={line}
          />
        )}
        {storyboard}
      </section>
    </div>
  );
}
