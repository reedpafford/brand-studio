import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { useBrandPieces } from "../clip/BrandPieces";
import { useToast } from "../toast";
import { useMedia, useRail } from "../useMedia";
import { ActionBar } from "../shell/ActionBar";
import { Sheet } from "./Sheet";
import { ChevronRight, Ellipsis, MapPin, Pencil, Smartphone, TriangleAlert, User } from "lucide-react";
import { Badge, Banner, Button, Menu, MenuItem } from "../components";
import { errorText as errorClass, input } from "../ui";
import { clone, joinWithNext, patchShot, problemTarget, setHook, setScene, setSeam, splitAfter, type Breakdown, type Shot } from "./breakdownEdit";

const lines = (n: number[]) => (n.length === 0 ? "" : n.length === 1 ? `line ${n[0]}` : `lines ${Math.min(...n)}–${Math.max(...n)}`);
const small = `${input} min-h-11 sm:min-h-9`;
// Below sm every tap target is at least 44px tall.
const tap = "inline-flex min-h-11 items-center sm:min-h-0";

/** A line of text with an Edit link that turns it into a one-line box. */
function EditableText({ value, label, onChange, children }: { value: string; label: string; onChange: (v: string) => void; children: ReactNode }) {
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
  line: number | null;
  onShowLines: (lines: number[]) => void;
  onDirty?: (dirty: boolean) => void;
}) {
  const { row, projectId, makeButton, name } = props;
  const queryClient = useQueryClient();
  const toast = useToast();
  const { pieces, screens } = useBrandPieces(props.brandId);
  const [draft, setDraft] = useState<Breakdown | null>(null);
  const [open, setOpen] = useState<string[]>([]);
  const [flash, setFlash] = useState<string | null>(null);
  const phone = useMedia("(max-width: 639px)");
  const rail = useRail();
  const [problemsOpen, setProblemsOpen] = useState(false);
  const [sheetShot, setSheetShot] = useState<string | null>(null);
  const line = props.line;

  // A line picked in the script brings its shot into view.
  useEffect(() => {
    if (line === null) return;
    const shot = row.breakdown.scenes.flatMap((s) => s.shots).find((s) => s.script_lines.includes(line));
    if (shot) document.getElementById(`shot-${shot.id}`)?.scrollIntoView?.({ behavior: "smooth", block: "center" });
  }, [line, row.breakdown]);
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
  // The frame's Next button waits while edits are unsaved.
  const { onDirty } = props;
  useEffect(() => {
    onDirty?.(dirty);
    return () => onDirty?.(false);
  }, [dirty, onDirty]);

  // Desktop: a bar sticks to the bottom of the window. Below 1024 it takes the action bar's place (Next steps aside while edits are unsaved).
  const bar = (
    <div className={rail ? "sticky bottom-2 z-10 flex flex-wrap items-center gap-3 rounded-md border border-border bg-surface p-3 shadow-md" : "space-y-2"} role="group" aria-label="Unsaved changes">
      <span className={rail ? "flex-1 text-sm" : "block text-sm text-muted"}>You have unsaved changes.</span>
      <Button busy={save.isPending} onClick={() => save.mutate()}>
        Save changes
      </Button>
      <Button
        variant="ghost"
        onClick={() => {
          setDraft(null);
          setOpen([]);
        }}
      >
        Discard
      </Button>
    </div>
  );

  const problemList = (after?: () => void) => (
    <ul className="space-y-1 text-sm">
      {row.problems.map((p) => {
        const target = problemTarget(p);
        return (
          <li key={p} className="flex items-start gap-2">
            <span className="flex-1 py-3">{p}</span>
            {target && (
              <Button
                variant="ghost"
                dense
                trailing={ChevronRight}
                aria-label={`Go to: ${p}`}
                onClick={() => {
                  after?.();
                  goTo(target);
                }}
              >
                Go to
              </Button>
            )}
          </li>
        );
      })}
    </ul>
  );

  return (
    <div className="space-y-4" aria-label="Breakdown">
      {row.stale && (
        <Banner tone="warning" title="These shots were made for an older script." action={makeButton("Make new shots", { primary: true })} />
      )}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted">
          {bd.scenes.length} scene{bd.scenes.length === 1 ? "" : "s"} · {shots.length} shot{shots.length === 1 ? "" : "s"} · {bd.clips.length} clip{bd.clips.length === 1 ? "" : "s"} · {total} s of {props.plannedSeconds} s planned
          <span className="sr-only"> · {row.source === "edit" ? "edited" : "made by Claude"}</span>
        </p>
        {!row.stale && makeButton("Redo", { ask: row.source === "edit" || dirty ? "Replace this breakdown? Your edits are kept in History." : undefined })}
      </div>
      {props.failed && <p role="alert" className={errorClass}>The breakdown didn't finish. Nothing was charged for the failed part.</p>}
      {props.problem}
      {row.problems.length > 0 && phone && (
        <>
          <button className="flex min-h-control w-full items-center gap-2 rounded-lg border border-danger bg-danger-soft px-3 text-left text-danger" aria-label="Problems" onClick={() => setProblemsOpen(true)}>
            <TriangleAlert size={20} strokeWidth={1.75} aria-hidden />
            <span className="flex-1 font-medium">
              {row.problems.length} problem{row.problems.length === 1 ? "" : "s"}
            </span>
            <ChevronRight size={20} strokeWidth={1.75} aria-hidden />
          </button>
          {problemsOpen && (
            <Sheet title={`Problems (${row.problems.length})`} onClose={() => setProblemsOpen(false)}>
              {problemList(() => setProblemsOpen(false))}
            </Sheet>
          )}
        </>
      )}
      {row.problems.length > 0 && !phone && (
        <section className="space-y-1 rounded-lg border border-danger bg-danger-soft p-4 text-sm" aria-label="Problems">
          <h3 className="flex items-center gap-2 font-semibold text-danger">
            <TriangleAlert size={20} strokeWidth={1.75} aria-hidden />
            {row.problems.length} problem{row.problems.length === 1 ? "" : "s"} to fix before the storyboard
          </h3>
          {problemList()}
        </section>
      )}
      {bd.hook !== undefined && (
        <p className="text-sm">
          <EditableText value={bd.hook} label="hook" onChange={(v) => change((b) => setHook(b, v))}>
            Hook: “{bd.hook}”
          </EditableText>
        </p>
      )}
      {bd.scenes.map((scene) => (
        <section key={scene.id} className="space-y-3" aria-label={`Scene ${scene.id}`}>
          <div>
            <p className="type-eyebrow text-muted">Scene {scene.id}</p>
            <h3 className="font-script text-lg font-bold">
              <EditableText value={scene.heading} label={`scene ${scene.id} heading`} onChange={(v) => change((b) => setScene(b, scene.id, { heading: v }))}>
                {scene.heading}
              </EditableText>
            </h3>
            <p className="text-sm text-muted">
              <EditableText value={scene.look} label={`scene ${scene.id} look`} onChange={(v) => change((b) => setScene(b, scene.id, { look: v }))}>
                {scene.look || "No look yet"}
              </EditableText>
            </p>
          </div>
          {bd.clips
            .filter((c) => c.shot_ids.some((id) => scene.shots.some((s) => s.id === id)))
            .map((clip) => {
              const last = clip.id === bd.clips.at(-1)?.id;
              return (
                <div key={clip.id} id={`clip-${clip.id}`} className={`overflow-hidden rounded-xl border border-border bg-surface shadow-card ${ring(`clip-${clip.id}`)}`} aria-label={`Clip ${clip.id}`}>
                  <div className="flex items-center gap-2 border-b border-border px-4 py-2 font-display font-bold">
                    Clip {clip.id} · {clip.seconds} s
                    {last && <Badge>End line</Badge>}
                  </div>
                  <ul className="divide-y divide-border">
                    {scene.shots.filter((s) => clip.shot_ids.includes(s.id)).map((s) => {
                      const editing = open.includes(s.id);
                      const lastInClip = clip.shot_ids.at(-1) === s.id;
                      const canMove = !lastInClip || !last;
                      return (
                        <li key={s.id} id={`shot-${s.id}`} className={`space-y-1 px-4 py-3 ${ring(`shot-${s.id}`)} ${line !== null && s.script_lines.includes(line) ? "bg-accent-soft" : ""}`} aria-label={`Shot ${s.id}`}>
                          <div className="flex flex-wrap items-center gap-x-3 text-sm">
                            <span className="font-medium text-muted">{s.id}</span>
                            <span className="tabular-nums">{s.seconds} s</span>
                            <span className="text-muted">{s.camera}</span>
                            <span className="ml-auto flex items-center gap-1">
                              <Button type="button" variant="ghost" dense aria-label={`Show ${lines(s.script_lines)} in the script`} onClick={() => props.onShowLines(s.script_lines)}>
                                {lines(s.script_lines)[0].toUpperCase() + lines(s.script_lines).slice(1)}
                              </Button>
                              <Button
                                type="button"
                                variant="ghost"
                                dense
                                icon={Pencil}
                                aria-label={`${editing && !phone ? "Done with" : "Edit"} shot ${s.id}`}
                                onClick={() => (phone ? setSheetShot(s.id) : setOpen(editing ? open.filter((x) => x !== s.id) : [...open, s.id]))}
                              >
                                {editing && !phone ? "Done" : "Edit"}
                              </Button>
                              {canMove && (
                                <Menu
                                  title={`Shot ${s.id}`}
                                  align="right"
                                  trigger={(t) => (
                                    <button type="button" {...t} aria-label={`More for shot ${s.id}`} className="grid size-control place-items-center rounded-md text-muted hover:bg-surface-2 lg:size-control-dense">
                                      <Ellipsis size={20} strokeWidth={1.75} aria-hidden />
                                    </button>
                                  )}
                                >
                                  {(close) => (
                                    <>
                                      {!lastInClip && (
                                        <MenuItem
                                          onClick={() => {
                                            close();
                                            change((b) => splitAfter(b, s.id));
                                          }}
                                        >
                                          Split clip {clip.id} after shot {s.id}
                                        </MenuItem>
                                      )}
                                      {lastInClip && !last && (
                                        <MenuItem
                                          onClick={() => {
                                            close();
                                            change((b) => joinWithNext(b, clip.id));
                                          }}
                                        >
                                          Join clip {clip.id} with the next clip
                                        </MenuItem>
                                      )}
                                    </>
                                  )}
                                </Menu>
                              )}
                            </span>
                          </div>
                          <p>{s.action}</p>
                          {s.line && (
                            <p className="font-script">
                              {s.speaker ? `${s.speaker.toUpperCase()}: ` : ""}“{s.line}”
                            </p>
                          )}
                          {s.reaction && <p className="text-sm text-muted">Reaction: {s.reaction}</p>}
                          <p className="flex flex-wrap gap-2 text-xs">
                            {s.character_ids.map((id) => (
                              <Badge key={id} icon={User}>{name(id)}</Badge>
                            ))}
                            {s.place_id && <Badge icon={MapPin}>{name(s.place_id)}</Badge>}
                            {s.moment && <Badge tone="accent">{s.moment}</Badge>}
                            {s.screen_ids.map((id) => (
                              <Badge key={id} tone="accent" icon={Smartphone}>{name(id)}</Badge>
                            ))}
                          </p>
                          {editing && !phone && <ShotEditor shot={s} picks={picks} onChange={(patch) => change((b) => patchShot(b, s.id, patch))} />}
                          {phone && sheetShot === s.id && (
                            <Sheet title={`Shot ${s.id}`} onClose={() => setSheetShot(null)}>
                              <ShotEditor shot={s} picks={picks} onChange={(patch) => change((b) => patchShot(b, s.id, patch))} />
                            </Sheet>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                  <div className="flex flex-wrap items-center gap-3 border-t border-border px-4 py-2 text-sm text-muted">
                    <EditableText value={clip.seam} label={`clip ${clip.id} seam`} onChange={(v) => change((b) => setSeam(b, clip.id, v))}>
                      {clip.seam === "end" ? "End" : `Ends: ${clip.seam}`}
                    </EditableText>
                  </div>
                </div>
              );
            })}
        </section>
      ))}
      {dirty && (rail ? bar : <ActionBar phone>{bar}</ActionBar>)}
      {save.isError && <p role="alert" className={errorClass}>{save.error.message}</p>}
    </div>
  );
}
