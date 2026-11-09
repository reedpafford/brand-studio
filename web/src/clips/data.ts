import type { components } from "../api/schema";
import { clipNo } from "../projects/names";

export type Clip = components["schemas"]["ProjectClipOut"] & { model?: ClipModel | null };
export type Take = Clip["takes"][number];
export type Frame = components["schemas"]["FrameOut"];
type Breakdown = components["schemas"]["BreakdownOut"]["breakdown"];
type Shot = Breakdown["scenes"][number]["shots"][number];

/** v6-models' piece F (SettingsOut's sibling on a clip): the model it's made with and one line on why. */
export type ClipModel = { id: string; name: string; why: string; by: "director" | "person" | "map" };

/** One clip's place in the run (v6-progress #1306, GET /projects/{id}/director/progress, ClipCellOut). */
export type State = "todo" | "making" | "waiting" | "failed" | "flagged" | "text" | "redone" | "done" | "too_long";
type Cell = { clip_id: string; number: string; scene: number; label: string; seconds: number; model: string; state: State; frame_file_id: number | null; take_id: number | null; note: string; percent: number | null; minutes_left: number | null; credits: string | null; changed: boolean; watched: boolean; found: boolean };
export type Progress = { status: string; clips: number; made: number; scenes: { id: number; name: string; total: number; done: number; clips: Cell[] }[]; counts: { all: number; needs_you: number; flagged: number; redone: number } };

/** A clip as the list shows it: from the run's record when there is one, else worked out from the clips and the plan. */
export type Row = Cell & { id: number | null; words: string; broll: boolean; said: string };
export type Scene = { id: number; name: string; rows: Row[]; done: number };
export type Filter = "all" | "needs" | "flagged" | "redone";

/** This person watched these takes: a clip the director changed stops being outlined for them (S3-09). */
export const markWatched = (projectId: number, takeIds: number[]) =>
  fetch(`/api/projects/${projectId}/director/seen`, { method: "POST", credentials: "same-origin", headers: { "content-type": "application/json" }, body: JSON.stringify({ take_ids: takeIds }) }).catch(() => null);

export { useFrames as useStoryboard } from "../projects/useProgress";

/** What the watch did that the boards call Flagged (it found something): remade it, held it, flagged it, or wasn't sure. */
const ACTED = ["redo", "held", "flagged", "unsure"];
const kept = (t: Take | undefined) => t?.watch?.action;

/** A clip's state when there's no run record: in the cut, flagged, redone, or not made yet. */
function derived(c: Clip | undefined): State {
  if (!c?.picked_take_id) return "todo";
  const picked = (c.takes ?? []).find((t) => t.id === c.picked_take_id);
  if (kept(picked) === "flagged" || kept(picked) === "unsure") return "flagged";
  if (picked?.watch?.action === "held") return "waiting";
  return (c.takes ?? []).some((t) => t.remade_from) ? "redone" : "done";
}

/** The clips in plan order, grouped by scene, each with what the boards show on its row (S6-01 to S6-05). */
export function scenesOf(bd: Breakdown | null | undefined, clips: Clip[], frames: Frame[], run: Progress | null | undefined): Scene[] {
  const shots = new Map<string, Shot & { scene: number }>();
  for (const s of bd?.scenes ?? []) for (const x of s.shots ?? []) shots.set(x.id, { ...x, scene: s.id }); // older plans may lack parts
  const plan = bd?.clips?.length ? bd.clips : clips.map((c) => ({ id: c.clip_id, shot_ids: [] as string[], seconds: c.seconds }));
  const cells = new Map((run?.scenes ?? []).flatMap((s) => (s.clips ?? []).map((c) => [c.clip_id, c] as const)));
  const names = new Map((run?.scenes ?? []).map((s) => [s.id, s.name]));
  const byId = new Map(clips.map((c) => [c.clip_id, c]));
  const out = new Map<number, Scene>();
  for (const p of plan) {
    const its = (p.shot_ids ?? []).map((id) => shots.get(id)).filter((x): x is Shot & { scene: number } => !!x);
    const c = byId.get(p.id);
    const cell = cells.get(p.id);
    const sceneId = cell?.scene ?? its[0]?.scene ?? 1;
    const heading = (bd?.scenes ?? []).find((s) => s.id === sceneId)?.heading ?? "";
    const scene = out.get(sceneId) ?? { id: sceneId, name: names.get(sceneId) ?? heading, rows: [], done: 0 };
    const picked = c?.takes?.find((t) => t.id === c.picked_take_id);
    const frame = frames.find((f) => f.clip_id === p.id && f.file_id);
    const row: Row = {
      clip_id: p.id,
      number: cell?.number ?? clipNo(p.id),
      scene: sceneId,
      label: cell?.label || its[0]?.action || "",
      seconds: cell?.seconds ?? c?.seconds ?? p.seconds,
      model: cell?.model || c?.model?.name || picked?.model || "",
      state: cell?.state ?? derived(c),
      frame_file_id: cell?.frame_file_id ?? frame?.file_id ?? null,
      take_id: cell?.take_id ?? c?.picked_take_id ?? null,
      note: cell?.note ?? "",
      percent: cell?.percent ?? null,
      minutes_left: cell?.minutes_left ?? null,
      credits: cell?.credits ?? null,
      changed: cell?.changed ?? false,
      watched: cell?.watched ?? true,
      found: cell?.found ?? c?.takes?.some((t) => ACTED.includes(t.watch?.action ?? "")) ?? false,
      id: c?.id ?? null,
      words: its.map((s) => s.line).filter(Boolean).join(" "),
      said: its.filter((s) => s.line).map((s) => (s.speaker ? `${s.speaker}: “${s.line}”` : `“${s.line}”`)).join("\n"), // a line each speaker (polish)
      broll: its.length > 0 && its.every((s) => !s.speaker),
    };
    scene.rows.push(row);
    if (row.take_id) scene.done += 1;
    out.set(sceneId, scene);
  }
  return [...out.values()].sort((a, b) => a.id - b.id);
}

export const needsYou = (r: Row) => r.state === "flagged" || r.state === "waiting" || r.state === "failed" || r.state === "too_long";
export const redone = (r: Row) => r.state === "redone" || r.state === "text";
export const passes = (f: Filter) => (r: Row) => f === "all" || (f === "needs" ? needsYou(r) : f === "flagged" ? r.state === "flagged" || r.found : redone(r));
