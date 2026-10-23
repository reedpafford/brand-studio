import { useState, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { useBrandPieces } from "../clip/BrandPieces";
import { useToast } from "../toast";
import { btnPrimary, btnSecondary, errorText as errorClass, input, linkText } from "../ui";
import { clone, joinWithNext, patchShot, problemTarget, setHook, setScene, setSeam, splitAfter, type Breakdown, type Shot } from "./breakdownEdit";

const lines = (n: number[]) => (n.length === 0 ? "" : n.length === 1 ? `line ${n[0]}` : `lines ${Math.min(...n)}–${Math.max(...n)}`);
const small = `${input} min-h-9`;

/** A line of text with an Edit link that turns it into a one-line box. */
function EditableText({ value, label, onChange, children }: { value: string; label: string; onChange: (v: string) => void; children: ReactNode }) {
  const [editing, setEditing] = useState(false);
  if (editing)
    return <input className={small} aria-label={label} autoFocus value={value} onChange={(e) => onChange(e.target.value)} onBlur={() => setEditing(false)} onKeyDown={(e) => e.key === "Enter" && setEditing(false)} />;
  return (
    <span>
      {children}{" "}
      <button type="button" className={`${linkText} text-xs`} aria-label={`Edit ${label}`} onClick={() => setEditing(true)}>
        Edit
      </button>
    </span>
  );
}

type Picks = { characters: { key: string; name: string }[]; places: { key: string; name: string }[]; screens: { key: string; name: string; moments: string[] }[] };

function ShotEditor({ shot, picks, onChange }: { shot: Shot; picks: Picks; onChange: (patch: Partial<Shot>) => void }) {
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
          <label key={c.key} className="mr-3 inline-flex items-center gap-1">
            <input type="checkbox" checked={shot.character_ids.includes(c.key)} onChange={() => onChange({ character_ids: toggle(shot.character_ids, c.key) })} />
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
          <label key={s.key} className="mr-3 inline-flex items-center gap-1">
            <input type="checkbox" checked={shot.screen_ids.includes(s.key)} onChange={() => onChange({ screen_ids: toggle(shot.screen_ids, s.key) })} />
            {s.name}
          </label>
        ))}
      </fieldset>
      {shot.line && <p className="text-xs text-muted">To change the words, edit the script.</p>}
    </div>
  );
}

export function BreakdownView(props: {
  row: components["schemas"]["BreakdownOut"];
  projectId: number;
  brandId: number;
  scriptVersion: number;
  plannedSeconds: number;
  makeButton: (label: string, opts?: { ask?: string; primary?: boolean }) => ReactNode;
  failed: boolean;
  problem: ReactNode;
  name: (id: string | null) => string;
}) {
  const { row, projectId, scriptVersion, makeButton, name } = props;
  const queryClient = useQueryClient();
  const toast = useToast();
  const { pieces, screens } = useBrandPieces(props.brandId);
  const [draft, setDraft] = useState<Breakdown | null>(null);
  const [open, setOpen] = useState<string[]>([]);
  const [flash, setFlash] = useState<string | null>(null);
  const bd = draft ?? row.breakdown;
  const change = (fn: (b: Breakdown) => Breakdown) => setDraft(fn(clone(draft ?? row.breakdown)));

  const picks: Picks = {
    characters: pieces.filter((p) => p.type === "character").map((p) => ({ key: `char:${p.id}`, name: p.name })),
    places: pieces.filter((p) => p.type === "place").map((p) => ({ key: `place:${p.id}`, name: p.name })),
    screens: pieces.filter((p) => p.type === "screen").map((p) => ({ key: `screen:${p.id}`, name: p.name, moments: screens.find((s) => s.key === p.key)?.moments ?? [] })),
  };

  const save = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.PUT("/projects/{project_id}/breakdown", { params: { path: { project_id: projectId } }, body: draft! });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: async (saved) => {
      toast(saved.problems.length === 0 ? "Saved. No problems." : `Saved. ${saved.problems.length} problem${saved.problems.length === 1 ? "" : "s"} left.`);
      await queryClient.invalidateQueries({ queryKey: ["breakdown", projectId] });
    },
  });

  const goTo = (target: string) => {
    document.getElementById(target)?.scrollIntoView?.({ behavior: "smooth", block: "center" });
    setFlash(target);
    setTimeout(() => setFlash(null), 2500);
  };
  const ring = (id: string) => (flash === id ? "outline outline-2 outline-accent" : "");

  const shots = bd.scenes.flatMap((s) => s.shots);
  const total = Math.round(bd.clips.reduce((sum, c) => sum + c.seconds, 0));
  const dirty = draft !== null;
  const blockedBy = dirty ? "Save your changes first." : row.stale ? "Make a new breakdown first." : row.problems.length > 0 ? `Fix the ${row.problems.length} problem${row.problems.length === 1 ? "" : "s"} first.` : "Storyboard is coming soon.";

  return (
    <div className="space-y-4" aria-label="Breakdown">
      {row.stale && (
        <div className="space-y-2 rounded-md bg-warning-soft p-3 text-sm text-warning" role="status">
          <p>Made for script v{row.script_version}. The script is now v{scriptVersion}.</p>
          {makeButton("Make a new breakdown")}
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[length:var(--text-md)] font-semibold">
          Breakdown <span className="font-normal text-muted">· {row.source === "edit" ? "edited" : "made by Claude"} for script v{row.script_version}</span>
        </h2>
        {!row.stale && makeButton("Redo", { ask: row.source === "edit" || dirty ? "Replace this breakdown? Your edits are kept in History." : undefined })}
      </div>
      {props.failed && <p role="alert" className={errorClass}>The breakdown didn't finish. Nothing was charged for the failed part.</p>}
      {props.problem}
      {row.problems.length > 0 && (
        <section className="space-y-1 rounded-md bg-danger-soft p-3 text-sm text-danger" aria-label="Problems">
          <h3 className="font-semibold">Problems ({row.problems.length})</h3>
          <ul className="space-y-1">
            {row.problems.map((p) => {
              const target = problemTarget(p);
              return (
                <li key={p} className="flex items-start gap-2">
                  <span aria-hidden>•</span>
                  <span className="flex-1">{p}</span>
                  {target && (
                    <button className="underline" aria-label={`Go to: ${p}`} onClick={() => goTo(target)}>
                      Go to
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      )}
      {bd.hook !== undefined && (
        <p className="text-sm">
          <EditableText value={bd.hook} label="hook" onChange={(v) => change((b) => setHook(b, v))}>
            Hook: “{bd.hook}”
          </EditableText>
        </p>
      )}
      <p className="text-sm text-muted">
        {bd.scenes.length} scene{bd.scenes.length === 1 ? "" : "s"} · {shots.length} shot{shots.length === 1 ? "" : "s"} · {bd.clips.length} clip{bd.clips.length === 1 ? "" : "s"} · {total} s (planned {props.plannedSeconds} s)
      </p>
      {bd.scenes.map((scene) => (
        <section key={scene.id} className="space-y-2" aria-label={`Scene ${scene.id}`}>
          <h3 className="font-semibold">
            <EditableText value={scene.heading} label={`scene ${scene.id} heading`} onChange={(v) => change((b) => setScene(b, scene.id, { heading: v }))}>
              Scene {scene.id} — {scene.heading}
            </EditableText>
          </h3>
          <p className="text-sm text-muted">
            <EditableText value={scene.look} label={`scene ${scene.id} look`} onChange={(v) => change((b) => setScene(b, scene.id, { look: v }))}>
              {scene.look || "No look yet"}
            </EditableText>
          </p>
          {bd.clips
            .filter((c) => c.shot_ids.some((id) => scene.shots.some((s) => s.id === id)))
            .map((clip) => {
              const last = clip.id === bd.clips.at(-1)?.id;
              return (
                <div key={clip.id} id={`clip-${clip.id}`} className={`rounded-md border border-border bg-surface ${ring(`clip-${clip.id}`)}`} aria-label={`Clip ${clip.id}`}>
                  <div className="border-b border-border px-3 py-1 text-xs font-medium text-muted">
                    Clip {clip.id} · {clip.seconds} s
                  </div>
                  <ul className="divide-y divide-border">
                    {scene.shots.filter((s) => clip.shot_ids.includes(s.id)).map((s) => {
                      const editing = open.includes(s.id);
                      const lastInClip = clip.shot_ids.at(-1) === s.id;
                      return (
                        <li key={s.id} id={`shot-${s.id}`} className={`space-y-1 px-3 py-2 text-sm ${ring(`shot-${s.id}`)}`} aria-label={`Shot ${s.id}`}>
                          <div className="flex flex-wrap items-baseline gap-x-3">
                            <span className="font-medium">{s.id}</span>
                            <span className="text-muted">{s.seconds} s</span>
                            <span className="text-muted">{s.camera}</span>
                            <span className="ml-auto text-xs text-muted">{lines(s.script_lines)}</span>
                          </div>
                          <p>{s.action}</p>
                          {s.line && (
                            <p className="font-script">
                              {s.speaker ? `${s.speaker.toUpperCase()}: ` : ""}“{s.line}”
                            </p>
                          )}
                          {s.reaction && <p className="text-muted">Reaction: {s.reaction}</p>}
                          <p className="flex flex-wrap gap-2 text-xs">
                            {s.character_ids.map((id) => (
                              <span key={id} className="rounded-sm bg-surface-2 px-2 py-0.5">● {name(id)}</span>
                            ))}
                            {s.place_id && <span className="rounded-sm bg-surface-2 px-2 py-0.5">⌂ {name(s.place_id)}</span>}
                            {s.moment && <span className="rounded-sm bg-accent-soft px-2 py-0.5 text-accent-text">{s.moment}</span>}
                            {s.screen_ids.map((id) => (
                              <span key={id} className="rounded-sm bg-accent-soft px-2 py-0.5 text-accent-text">★ {name(id)}</span>
                            ))}
                          </p>
                          {editing && <ShotEditor shot={s} picks={picks} onChange={(patch) => change((b) => patchShot(b, s.id, patch))} />}
                          <div className="flex gap-3 text-xs">
                            <button className={linkText} aria-label={`${editing ? "Done with" : "Edit"} shot ${s.id}`} onClick={() => setOpen(editing ? open.filter((x) => x !== s.id) : [...open, s.id])}>
                              {editing ? "Done" : "Edit"}
                            </button>
                            {!lastInClip && (
                              <button className={linkText} aria-label={`Split clip ${clip.id} after shot ${s.id}`} onClick={() => change((b) => splitAfter(b, s.id))}>
                                Split clip after
                              </button>
                            )}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                  <div className="flex flex-wrap items-center gap-3 border-t border-border px-3 py-1 text-xs text-muted">
                    <EditableText value={clip.seam} label={`clip ${clip.id} seam`} onChange={(v) => change((b) => setSeam(b, clip.id, v))}>
                      {clip.seam === "end" ? "end" : `ends: ${clip.seam}`}
                    </EditableText>
                    {!last && (
                      <button className={linkText} aria-label={`Join clip ${clip.id} with the next clip`} onClick={() => change((b) => joinWithNext(b, clip.id))}>
                        Join with next clip
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
        </section>
      ))}
      {dirty && (
        <div className="sticky bottom-2 z-10 flex flex-wrap items-center gap-3 rounded-md border border-border bg-surface p-3 shadow-md" role="group" aria-label="Unsaved changes">
          <span className="flex-1 text-sm">You have unsaved changes.</span>
          <button className={btnPrimary} disabled={save.isPending} onClick={() => save.mutate()}>
            Save
          </button>
          <button className={btnSecondary} onClick={() => { setDraft(null); setOpen([]); }}>
            Discard
          </button>
        </div>
      )}
      {save.isError && <p role="alert" className={errorClass}>{save.error.message}</p>}
      <div className="space-y-1">
        <button className={btnPrimary} disabled>
          Next: Storyboard →
        </button>
        <p className="text-sm text-muted">{blockedBy}</p>
      </div>
    </div>
  );
}
