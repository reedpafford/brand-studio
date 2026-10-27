import type { components } from "../api/schema";

export type Breakdown = components["schemas"]["Breakdown"];
export type Shot = components["schemas"]["Shot"];

export const clone = (bd: Breakdown): Breakdown => structuredClone(bd);

/** Clip ids run c1, c2… in order and a clip's seconds are its shots' seconds added up, rounded up. */
function recompute(bd: Breakdown): Breakdown {
  const secs = new Map(bd.scenes.flatMap((s) => s.shots).map((s) => [s.id, s.seconds]));
  return {
    ...bd,
    clips: bd.clips.map((c, i) => ({ ...c, id: `c${i + 1}`, seconds: Math.ceil(c.shot_ids.reduce((sum, id) => sum + (secs.get(id) ?? 0), 0)) })),
  };
}

export function patchShot(bd: Breakdown, id: string, patch: Partial<Shot>): Breakdown {
  return recompute({ ...bd, scenes: bd.scenes.map((sc) => ({ ...sc, shots: sc.shots.map((s) => (s.id === id ? { ...s, ...patch } : s)) })) });
}

/** Cut the clip that holds this shot into two, right after the shot. */
export function splitAfter(bd: Breakdown, shotId: string): Breakdown {
  const clips = bd.clips.flatMap((c) => {
    const at = c.shot_ids.indexOf(shotId);
    if (at < 0 || at === c.shot_ids.length - 1) return [c];
    return [
      { ...c, shot_ids: c.shot_ids.slice(0, at + 1), seam: "your cut" },
      { ...c, shot_ids: c.shot_ids.slice(at + 1) },
    ];
  });
  return recompute({ ...bd, clips });
}

/** Join a clip with the one after it. The joined clip ends where the second one did. */
export function joinWithNext(bd: Breakdown, clipId: string): Breakdown {
  const i = bd.clips.findIndex((c) => c.id === clipId);
  if (i < 0 || i === bd.clips.length - 1) return bd;
  const [a, b] = [bd.clips[i], bd.clips[i + 1]];
  const clips = [...bd.clips.slice(0, i), { ...a, shot_ids: [...a.shot_ids, ...b.shot_ids], seam: b.seam }, ...bd.clips.slice(i + 2)];
  return recompute({ ...bd, clips });
}

export const setSeam = (bd: Breakdown, clipId: string, seam: string): Breakdown => ({ ...bd, clips: bd.clips.map((c) => (c.id === clipId ? { ...c, seam } : c)) });
export const setHook = (bd: Breakdown, hook: string): Breakdown => ({ ...bd, hook });
export const setScene = (bd: Breakdown, id: number, patch: { heading?: string; look?: string }): Breakdown => ({
  ...bd,
  scenes: bd.scenes.map((s) => (s.id === id ? { ...s, ...patch } : s)),
});

/** The shot or clip a problem sentence is about ("Shot 2.1 …", "Clip c3 …"), as an element id. */
export function problemTarget(text: string): string | null {
  const shot = /\bshot (\d+\.\d+)/i.exec(text);
  if (shot) return `shot-${shot[1]}`;
  const clip = /\bClip (c\d+)/.exec(text);
  return clip ? `clip-${clip[1]}` : null;
}
