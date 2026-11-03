import { Fragment, type ReactNode } from "react";
import type { components } from "../api/schema";

type Breakdown = components["schemas"]["Breakdown"];

/** Each clip under the scene its first shot is in (C_Breakdown); scenes with no clip are left out. */
export function sceneGroups(plan: Breakdown) {
  const sceneOf = new Map(plan.scenes.flatMap((sc) => sc.shots.map((sh) => [sh.id, sc.id] as const)));
  return plan.scenes.map((scene) => ({ scene, clips: plan.clips.filter((c) => sceneOf.get(c.shot_ids[0]) === scene.id) })).filter((g) => g.clips.length > 0);
}

/** The Breakdown's clip table (v5 C_Breakdown): Clip | What happens | Who | Length, grouped by scene. A row opens the shots;
 *  a clip with a problem has a warning dot, and its problems sit right under its row. */
export function ClipTable({ plan, who, readOnly, onOpen, flagged, under }: { plan: Breakdown; who: (ids: string[]) => string; readOnly: boolean; onOpen: () => void; flagged: (clipId: string) => boolean; under: (clipId: string) => ReactNode }) {
  const shotById = new Map(plan.scenes.flatMap((sc) => sc.shots.map((sh) => [sh.id, sh] as const)));
  const groups = sceneGroups(plan);
  const number = new Map(groups.flatMap((g) => g.clips).map((c, i) => [c.id, i + 1]));
  const cols = "grid grid-cols-[56px_minmax(0,1fr)_56px] gap-x-4 sm:grid-cols-[64px_minmax(0,1fr)_160px_70px]";
  return (
    <div role="table" aria-label="Clips">
      <div role="row" className={`${cols} h-[34px] items-center border-b border-border px-3 text-xs text-muted`}>
        <span role="columnheader">Clip</span>
        <span role="columnheader">What happens</span>
        <span role="columnheader" className="hidden sm:block">Who</span>
        <span role="columnheader" className="text-right">Length</span>
      </div>
      {groups.map((g, gi) => (
        <div role="rowgroup" key={g.scene.id}>
          <div role="row" className="flex h-9 items-center gap-2.5 border-b border-border bg-surface px-3 font-medium">
            <span role="rowheader">
              Scene {gi + 1}
              {g.scene.heading ? ` · ${g.scene.heading}` : ""}
            </span>
            <span className="text-xs tabular-nums text-muted">
              {g.clips.length} clip{g.clips.length === 1 ? "" : "s"} · {Math.round(g.clips.reduce((t, c) => t + c.seconds, 0))} s
            </span>
          </div>
          {g.clips.map((c) => {
            const n = number.get(c.id);
            const shots = c.shot_ids.map((id) => shotById.get(id)).filter((x): x is NonNullable<typeof x> => !!x);
            const said = shots.map((sh) => [sh.line ? `${sh.speaker ? `${sh.speaker}: ` : ""}${sh.line}` : "", sh.action].filter(Boolean).join(" ")).join(" ");
            const people = who(shots.flatMap((sh) => sh.character_ids));
            const cells = (
              <>
                <span role="cell" className="tabular-nums">
                  Clip {n}
                  {flagged(c.id) && <span aria-label="Has a problem" className="ml-1.5 inline-block size-2 rounded-full bg-warning align-middle" />}
                </span>
                <span role="cell" className="type-script min-w-0 text-[13px] text-text/80">
                  {said}
                  <span className="block font-sans text-xs text-muted sm:hidden">{people}</span>
                </span>
                <span role="cell" className="hidden min-w-0 truncate sm:block">{people}</span>
                <span role="cell" className="text-right tabular-nums">{Math.round(c.seconds)} s</span>
              </>
            );
            return (
              <Fragment key={c.id}>
                {readOnly ? (
                  <div role="row" className={`${cols} min-h-12 items-center border-b border-border px-3 py-1.5`}>
                    {cells}
                  </div>
                ) : (
                  <button type="button" role="row" aria-label={`Clip ${n}: open the shots`} onClick={onOpen} className={`${cols} min-h-12 w-full items-center border-b border-border px-3 py-1.5 text-left hover:bg-surface-2`}>
                    {cells}
                  </button>
                )}
                {under(c.id)}
              </Fragment>
            );
          })}
        </div>
      ))}
    </div>
  );
}
