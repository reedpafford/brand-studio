import { useState, type ReactNode } from "react";
import { Button } from "../components";
import { input } from "../ui";
import { type RefKind } from "./BreakdownFixes";
import { type Shot } from "./breakdownEdit";

/** "Line 3" / "Lines 3–5"; empty for a shot with no script lines (a reaction, an insert, a montage shot). */
export const lineLabel = (n: number[]) => {
  const t = lines(n);
  return t.charAt(0).toUpperCase() + t.slice(1);
};
export const lines = (n: number[]) => (n.length === 0 ? "" : n.length === 1 ? `line ${n[0]}` : `lines ${Math.min(...n)}–${Math.max(...n)}`);
const small = `${input} min-h-11 sm:min-h-9`;
// Below sm every tap target is at least 44px tall.
const tap = "inline-flex min-h-11 items-center sm:min-h-0";

/** A line of text with an Edit link that turns it into a one-line box. */
export function EditableText({ value, label, onChange, children }: { value: string; label: string; onChange: (v: string) => void; children: ReactNode }) {
  const [editing, setEditing] = useState(false);
  if (editing)
    return <input className={small} aria-label={label} autoFocus value={value} onChange={(e) => onChange(e.target.value)} onBlur={() => setEditing(false)} onKeyDown={(e) => e.key === "Enter" && setEditing(false)} />;
  return (
    <span>
      {children}{" "}
      <Button type="button" variant="ghost" dense aria-label={`Edit ${label}`} onClick={() => setEditing(true)}>
        Edit
      </Button>
    </span>
  );
}

export type Picks = { characters: { key: string; name: string }[]; places: { key: string; name: string }[]; screens: { key: string; name: string; moments: string[] }[] };

/** A character, place or screen a shot names that the video doesn't have: it can only be taken out, and the server does that for free. */
export function ShotEditor({ shot, picks, called, remove, onChange }: { shot: Shot; picks: Picks; called: (id: string, kind: RefKind) => string; remove?: (shotId: string, kind: RefKind, ref: string, name: string) => ReactNode; onChange: (patch: Partial<Shot>) => void }) {
  const gone = [
    ...shot.character_ids.filter((id) => !picks.characters.some((c) => c.key === id)).map((id) => ({ kind: "character" as const, id })),
    ...(shot.place_id && !picks.places.some((p) => p.key === shot.place_id) ? [{ kind: "place" as const, id: shot.place_id }] : []),
    ...shot.screen_ids.filter((id) => !picks.screens.some((s) => s.key === id)).map((id) => ({ kind: "screen" as const, id })),
  ];
  const moments = [...new Set([...picks.screens.flatMap((s) => s.moments), ...(shot.moment ? [shot.moment] : [])])];
  const toggle = (list: string[], id: string) => (list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);
  const label = (t: string) => `Shot ${shot.id} ${t}`;
  return (
    <div className="space-y-2 rounded-md bg-surface-2 p-3">
      <label className="block text-xs">Action<input className={small} aria-label={label("action")} value={shot.action} onChange={(e) => onChange({ action: e.target.value })} /></label>
      <label className="block text-xs">Reaction<input className={small} aria-label={label("reaction")} value={shot.reaction ?? ""} onChange={(e) => onChange({ reaction: e.target.value || null })} /></label>
      <label className="block text-xs">Camera<input className={small} aria-label={label("camera")} value={shot.camera} onChange={(e) => onChange({ camera: e.target.value })} /></label>
      <label className="block text-xs">Seconds<input className={small} type="number" step={0.5} min={0.5} max={30} aria-label={label("seconds")} value={shot.seconds} onChange={(e) => onChange({ seconds: Number(e.target.value) })} /></label>
      <fieldset className="text-xs">
        <legend className="font-medium">Who's in it</legend>
        {picks.characters.map((c) => (
          <label key={c.key} className={`mr-3 min-w-11 gap-2 px-1 ${tap}`}>
            <input type="checkbox" className="size-5 sm:size-4" checked={shot.character_ids.includes(c.key)} onChange={() => onChange({ character_ids: toggle(shot.character_ids, c.key) })} />
            {c.name}
          </label>
        ))}
      </fieldset>
      <label className="block text-xs">
        Place
        <select className={small} aria-label={label("place")} value={shot.place_id ?? ""} onChange={(e) => onChange({ place_id: e.target.value || null })}>
          <option value="">None</option>
          {picks.places.map((p) => (
            <option key={p.key} value={p.key}>{p.name}</option>
          ))}
        </select>
      </label>
      <label className="block text-xs">
        Moment
        <select
          className={small}
          aria-label={label("moment")}
          value={shot.moment ?? ""}
          onChange={(e) => {
            const moment = e.target.value || null;
            // Picking a moment adds the screens that are always used for it.
            const add = moment ? picks.screens.filter((s) => s.moments.includes(moment)).map((s) => s.key) : [];
            onChange({ moment, screen_ids: [...new Set([...shot.screen_ids, ...add])] });
          }}
        >
          <option value="">None</option>
          {moments.map((m) => (
            <option key={m}>{m}</option>
          ))}
        </select>
      </label>
      <fieldset className="text-xs">
        <legend className="font-medium">Brand screens</legend>
        {picks.screens.map((s) => (
          <label key={s.key} className={`mr-3 min-w-11 gap-2 px-1 ${tap}`}>
            <input type="checkbox" className="size-5 sm:size-4" checked={shot.screen_ids.includes(s.key)} onChange={() => onChange({ screen_ids: toggle(shot.screen_ids, s.key) })} />
            {s.name}
          </label>
        ))}
      </fieldset>
      {remove &&
        gone.map((g) => (
          <div key={g.id} className="space-y-1 text-xs">
            <p>{called(g.id, g.kind).startsWith("a ") ? `This ${g.kind} isn't in this video.` : `${called(g.id, g.kind)} isn't in this video.`}</p>
            {remove(shot.id, g.kind, g.id, called(g.id, g.kind))}
          </div>
        ))}
      {shot.line && <p className="text-xs text-muted">To change the words, edit the script.</p>}
    </div>
  );
}
