import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { GOING, useJobs } from "../clip/History";
import { useBreakdown } from "./BreakdownPane";
import { ReviewChip } from "./Checks";
import { ClipsPane } from "./ClipsPane";
import { Dot } from "./OtherTakes";
import { StoryboardPane, useFrames } from "./StoryboardPane";
import { useProjectClips } from "./useProgress";

type Clip = components["schemas"]["ProjectClipOut"];
type Frame = components["schemas"]["FrameOut"];
type Shot = components["schemas"]["Shot"];

/** What the clip list says about a clip, as a dot and words. */
function clipStatus(c: Clip | undefined, f: Frame | undefined, making: boolean): [tone: "ok" | "need" | "run" | "none", words: string] {
  if (c?.approved) return ["ok", "Approved"];
  if (making || f?.drawing) return ["run", "Making…"];
  if (c?.stale || f?.still_stale) return ["need", "Out of date"];
  const picked = c?.takes.find((t) => t.id === c.picked_take_id);
  return picked ? ["need", `Check take ${picked.number}`] : ["none", "No take yet"];
}

/** A shot's script line as the list shows it: "BO: Is that… salmon?", or its action in brackets. */
const lineOf = (s: Shot) => (s.line ? (s.speaker ? `${s.speaker.toUpperCase()}: ${s.line}` : s.line) : s.action ? `(${s.action})` : "");

/** The Clips tab (v4): one place per clip. Left, the clips with their still, line and status; right, the one picked, with
 *  its takes, its still and its prompt. The stills' and the takes' one-press actions sit above the list. The stills and the
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
  /** The video's Update everything after this has the cost bar. */
  barTaken: boolean;
}) {
  const { projectId } = props;
  const frames = useFrames(projectId);
  const clips = useProjectClips(projectId);
  const jobs = useJobs();
  const breakdown = useBreakdown(projectId, props.scriptVersion);
  const [picked, setPicked] = useState<string | null>(null);
  // A Review row names the card to go to ("Clip c2", "Frame c2"): that clip is picked in the list.
  const to = useSearchParams()[0].get("to")?.match(/^(?:Clip|Frame) (c\d+)$/)?.[1];
  if (to && to !== picked) setPicked(to);
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
    return clipStatus(c, f, making(c, f));
  };
  const open = props.clipsLock === null; // the takes part, once the stills are approved
  // The cost bar's one press goes to the stills until they're approved, then to the takes (a hold says why they wait).
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
      barTaken={props.barTaken}
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
    <div className="space-y-4">
      <div className="space-y-2">
        {list && <ReviewChip projectId={projectId} />}
        <div ref={setStillsBar} className="space-y-2 empty:hidden" />
        <div ref={setClipsBar} className="space-y-2 empty:hidden" />
      </div>
      <div className={list ? "grid gap-4 lg:grid-cols-[18rem_minmax(0,1fr)] lg:gap-6" : ""}>
        {list && (
        <ul aria-label="Clip list" className="flex flex-col gap-1 lg:border-r lg:border-border lg:pr-4">
          {ids.map((id) => {
            const f = stills.find((r) => r.clip_id === id);
            const [tone, words] = status(id);
            const on = id === selected;
            return (
              <li key={id}>
                <button type="button" aria-current={on || undefined} onClick={() => setPicked(id)} className={`flex min-h-control w-full items-start gap-3 rounded-md p-2 text-left ${on ? "bg-surface-2" : "hover:bg-surface-2"}`}>
                  <span className="w-8 shrink-0 overflow-hidden rounded-sm bg-surface-3" style={{ aspectRatio: props.aspect.replace(":", " / ") }}>
                    {f?.file_id != null && <img src={fileUrl(f.file_id)} alt="" className="h-full w-full object-cover" />}
                  </span>
                  <span className="min-w-0 flex-1 space-y-0.5">
                    <span className="flex flex-wrap items-center justify-between gap-x-2">
                      <span className="font-medium tabular-nums">
                        Clip {id.replace(/^c/, "")}
                        {seconds(id) !== undefined && ` · ${seconds(id)} s`}
                      </span>
                      <Dot tone={tone}>{words}</Dot>
                    </span>
                    {line(id) && <span className="block truncate font-script text-sm text-muted">{line(id)}</span>}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
        )}
        <section className="min-w-0 space-y-4" aria-label={selected ? `Clip ${selected.replace(/^c/, "")}` : "Stills"}>
          {open && list && (
            <ClipsPane
              barTaken={props.barTaken}
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
    </div>
  );
}
