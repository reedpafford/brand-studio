import type { components } from "../api/schema";
import { scenesOf, type Clip, type Row } from "../clips/data";
import type { Progress } from "../videos/RunCard";

type Piece = components["schemas"]["PieceOut"];
type Breakdown = components["schemas"]["BreakdownOut"]["breakdown"];
type Shot = Breakdown["scenes"][number]["shots"][number];

/** One clip of the plan: the row the lists show (its number, length, state and first frame), its shots (who speaks,
 *  the line, what the camera sees), its own take's file, why it was left out of the cut ("" when it wasn't), what the
 *  plan calls it ("" with no plan, or when that is only its number), and its time card's words ("" when none; `cardBefore`: on black before it). */
export type Planned = Row & { shots: Shot[]; file: number | null; left: string; name: string; card: string; cardBefore: boolean };
export type PlanScene = { id: number; name: string; clips: Planned[] };

/** The clips in plan order, grouped by scene as the server gives them (the run's record, else the plan itself). */
export function planOf(bd: Breakdown | null | undefined, clips: Clip[], run: Progress | null): PlanScene[] {
  const shots = new Map((bd?.scenes ?? []).flatMap((s) => s.shots ?? []).map((s) => [s.id, s]));
  const shown = new Map((bd?.clips ?? []).map((c) => [c.id, c.shot_ids.flatMap((id) => shots.get(id) ?? [])]));
  const rows = new Map(clips.map((c) => [c.clip_id, c]));
  return scenesOf(bd, clips, [], run).map((s) => ({
    id: s.id,
    name: s.name,
    clips: s.rows.map((r) => {
      const c = rows.get(r.clip_id);
      return { ...r, shots: shown.get(r.clip_id) ?? [], file: c?.file_id ?? null, left: c?.left_out ?? "", name: c?.name && c.name !== `Clip ${r.number}` ? c.name : "", card: c?.card ?? "", cardBefore: c?.card_before ?? false };
    }),
  }));
}

/** Who speaks in a clip and the line, shot by shot; none for a clip that is picture only. */
export const linesOf = (c: Planned) => c.shots.flatMap((s) => (s.line ? [{ by: s.speaker ?? "", line: s.line }] : []));
/** What a clip shows: each shot's action and camera, else the run's short line for it. */
export const shotOf = (c: Planned) => c.shots.map((s) => [s.action, s.camera].filter(Boolean).join(" ")).join(" ") || c.label;

/** One place on the timeline: a piece of the cut (a clip, or a time card with its words in `card`), or a clip the cut
 *  doesn't hold (`start` null): left out, being made, made since, or still planned. */
export type Cell = { key: string; clip: string; card: string | null; state: "made" | "making" | "todo" | "left"; seconds: number; start: number | null; poster: number | null; file: number | null; said: string };

export type CastItem = components["schemas"]["CastItemOut"];
/** A look that isn't ready, in the current site's words; one that is says nothing. */
export const NOT_READY: Partial<Record<CastItem["readiness"], string>> = { needs_look: "Needs a look", drawing: "Drawing", waiting_for_owner: "Waiting for the owner" };

/** One press, one request: the second click of a double-click does nothing. (A press is off while its request is in
 *  flight; this covers two clicks that land before the page has drawn that.) */
export const once = (f: () => void) => (e: { detail: number }) => void (e.detail > 1 || f());

/** One press the page offers: its words, its price when the server gave one, and `why` it can't be pressed now (the
 *  server's own words). `busy`: its request is in flight, so it can't be pressed again. */
export type Press = { label: string; price?: string; busy: boolean; why?: string | null; onPress: () => void };
/** Where a person or a place in the video comes from, in a few words. */
export const cameFrom = (i: CastItem) => (i.source === "library" ? "From your library" : i.source === "uploaded" ? "Uploaded for this video" : !i.source ? "No look yet" : i.kind === "place" ? "Drawn for this video" : "New for this video");

const isCard = (p: Piece) => p.take_id == null && !!p.card;

/** The timeline: the cut's pieces in order, and each planned clip the cut has no piece for, at its place in the plan. */
export function cellsOf(plan: Planned[], pieces: Piece[]): Cell[] {
  const order = plan.map((c) => c.clip_id);
  const cells: Cell[] = pieces.map((p) => ({ key: p.id, clip: p.clip_id, card: isCard(p) ? p.card! : null, state: "made", seconds: p.end - p.start, start: p.start, poster: p.poster_file_id, file: p.file_id, said: p.said }));
  for (const c of plan) {
    if (pieces.some((p) => p.clip_id === c.clip_id && !isCard(p))) continue;
    const state = c.left ? "left" : c.state === "making" ? "making" : c.take_id != null ? "made" : "todo";
    const next = cells.findIndex((x) => order.indexOf(x.clip) > order.indexOf(c.clip_id));
    cells.splice(next < 0 ? cells.length : next, 0, { key: c.clip_id, clip: c.clip_id, card: null, state, seconds: c.seconds, start: null, poster: c.frame_file_id, file: c.file, said: "" });
  }
  return cells;
}
