/** Editing a scene plan (flows P1 "Editing"): every line stays once and in order, so a line only moves across the edge it sits on,
 *  a split starts a new scene at a line, and a join folds a scene into the one before it. The words are never touched (rule 19). */
export type PlanLine = { n: number; text: string; action: string; star: boolean; product?: string | null };
export type PlanScene = { id: string; part: string; place: string; time: string; cast_ids: string[]; lines: PlanLine[] };

const copy = (scenes: PlanScene[]) => scenes.map((s) => ({ ...s, cast_ids: [...s.cast_ids], lines: s.lines.map((l) => ({ ...l })) }));
const tidy = (scenes: PlanScene[]) => scenes.filter((s) => s.lines.length > 0);

/** The first line of a scene to the scene before, or its last line to the scene after. Any other move would break the order. */
export function moveLine(scenes: PlanScene[], si: number, li: number, dir: -1 | 1): PlanScene[] {
  const out = copy(scenes);
  const from = out[si];
  const to = out[si + dir];
  if (!from || !to) return scenes;
  if (dir === -1 && li !== 0) return scenes;
  if (dir === 1 && li !== from.lines.length - 1) return scenes;
  const [line] = from.lines.splice(li, 1);
  if (dir === -1) to.lines.push(line);
  else to.lines.unshift(line);
  return tidy(out);
}

/** A new scene starting at this line, in the same place and time with the same people (edit them after). */
export function splitAt(scenes: PlanScene[], si: number, li: number): PlanScene[] {
  const out = copy(scenes);
  const s = out[si];
  if (!s || li <= 0 || li >= s.lines.length) return scenes;
  const rest = s.lines.splice(li);
  out.splice(si + 1, 0, { ...s, id: `${s.id}-new`, cast_ids: [...s.cast_ids], lines: rest });
  return out;
}

/** This scene and the next become one, keeping this one's place, time and part; the people of both. */
export function joinNext(scenes: PlanScene[], si: number): PlanScene[] {
  const out = copy(scenes);
  const s = out[si];
  const next = out[si + 1];
  if (!s || !next) return scenes;
  s.lines.push(...next.lines);
  s.cast_ids = [...new Set([...s.cast_ids, ...next.cast_ids])];
  out.splice(si + 1, 1);
  return out;
}

export function toggleStar(scenes: PlanScene[], si: number, li: number): PlanScene[] {
  const out = copy(scenes);
  const l = out[si]?.lines[li];
  if (!l) return scenes;
  l.star = !l.star;
  if (!l.star) l.product = null;
  return out;
}

/** The typed edits on a card: place, time, part, and each line's action. */
export function editScene(scenes: PlanScene[], si: number, patch: { place: string; time: string; part: string; actions: string[] }): PlanScene[] {
  const out = copy(scenes);
  const s = out[si];
  if (!s) return scenes;
  s.place = patch.place;
  s.time = patch.time;
  s.part = patch.part;
  s.lines.forEach((l, i) => (l.action = patch.actions[i] ?? l.action));
  return out;
}

/** What the server's PUT takes: no ids or words, only the grouping and what we see (the line numbers carry the words). */
export const toPut = (scenes: PlanScene[]) => ({
  scenes: scenes.map((s) => ({ part: s.part, place: s.place, time: s.time, cast_ids: s.cast_ids, lines: s.lines.map((l) => ({ n: l.n, action: l.action, star: l.star, ...(l.product ? { product: l.product } : {}) })) })),
});
