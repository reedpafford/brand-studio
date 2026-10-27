import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { useBrandPieces } from "../clip/BrandPieces";
import { useToast } from "../toast";
import { useMedia, useRail } from "../useMedia";
import { ActionBar } from "../shell/ActionBar";
import { Sheet } from "./Sheet";
import { ChevronRight, Ellipsis, MapPin, Pencil, Smartphone, TriangleAlert, User, Users } from "lucide-react";
import { Badge, Banner, Button, Menu, MenuItem } from "../components";
import { errorText as errorClass } from "../ui";
import { blocking, CAST } from "./problems";
import { plainWords } from "./names";
import { AdviceList, useKeep } from "./Keep";
import { useBreakdownFixes, useFixCast, useRemoveRef, type RefKind } from "./BreakdownFixes";
import { clone, joinWithNext, patchShot, problemTarget, setHook, setScene, setSeam, splitAfter, type Breakdown } from "./breakdownEdit";
import { EditableText, lineLabel, lines, ShotEditor, type Picks } from "./ShotEditor";

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
  onShowLines?: (lines: number[]) => void; // none in the writing flow: the words are on another step
  onDirty?: (dirty: boolean) => void;
  /** A plan saved on a library version (the writing flow), not on a video: saved through its own route, with no Keep anyway. */
  preview?: { save: (bd: Breakdown) => Promise<{ problems: string[] }>; fix: (problems: string[]) => Promise<{ fixed: string[] }>; fixCast: () => Promise<{ changed_shots: { shot_id: string; before: string[]; after: string[] }[] }>; keep: (problem: string, undo?: boolean) => void; keepBusy: boolean; again: ReactNode };
}) {
  const { row, projectId, makeButton, name, preview } = props;
  const queryClient = useQueryClient();
  const toast = useToast();
  const { pieces, screens } = useBrandPieces(props.brandId);
  const words = (p: string) => plainWords(p, (id) => name(id));
  const [draft, setDraft] = useState<Breakdown | null>(null);
  const [open, setOpen] = useState<string[]>([]);
  const [flash, setFlash] = useState<string | null>(null);
  const phone = useMedia("(max-width: 639px)");
  const rail = useRail();
  const [problemsOpen, setProblemsOpen] = useState(false);
  const [sheetShot, setSheetShot] = useState<string | null>(null);
  const line = props.line;
  const keep = useKeep(projectId, { of: "breakdown" });
  const real = blocking(row.problems, row.kept); // advice is listed apart, closed

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
      if (preview) return preview.save(draft!);
      const { data, error } = await api.PUT("/projects/{project_id}/breakdown", { params: { path: { project_id: projectId } }, body: draft! });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: async (saved) => {
      if (!preview) toast(saved.problems.length === 0 ? "Saved. No problems." : `Saved. ${saved.problems.length} problem${saved.problems.length === 1 ? "" : "s"} left.`);
      await queryClient.invalidateQueries({ queryKey: [preview ? "preview" : "breakdown", projectId] });
      // A new breakdown version replaces the frames and clips made from the old one.
      if (!preview) await Promise.all([queryClient.invalidateQueries({ queryKey: ["storyboard", projectId] }), queryClient.invalidateQueries({ queryKey: ["project-clips", projectId] })]);
    },
  });

  // Undo of a fix puts the breakdown that was there back. If the server refuses, the person is told why, in its words.
  const putBack = async (body: Breakdown) => {
    try {
      const r = preview ? await preview.save(body) : await api.PUT("/projects/{project_id}/breakdown", { params: { path: { project_id: projectId } }, body });
      const refused = r as { response?: Response; error?: unknown } | undefined;
      if (refused?.response && !refused.response.ok) toast(errorText(refused.error), undefined, "error");
      return r;
    } catch (e) {
      toast((e as Error).message, undefined, "error");
    }
  };
  // After a fix or its Undo: the new breakdown, and what was made from the old one.
  const refreshAll = async () => {
    await queryClient.invalidateQueries({ queryKey: [preview ? "preview" : "breakdown", projectId] });
    if (!preview) await Promise.all([queryClient.invalidateQueries({ queryKey: ["storyboard", projectId] }), queryClient.invalidateQueries({ queryKey: ["project-clips", projectId] }), queryClient.invalidateQueries({ queryKey: ["project", projectId] })]);
  };
  const fixCast = useFixCast({ projectId, preview: preview?.fixCast, was: row.breakdown, putBack, refresh: refreshAll });
  // Free one-click fixes for lines that are missing or changed, and for shots with nothing in them.
  const fixes = useBreakdownFixes({
    offered: (row as { fixes?: unknown[] }).fixes,
    open: real,
    was: row.breakdown,
    run: async (problems) => {
      if (preview) return preview.fix(problems);
      const { data, error } = await api.POST("/projects/{project_id}/breakdown/fix", { params: { path: { project_id: projectId } }, body: { problems } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    put: putBack,
    refresh: refreshAll,
  });
  const castOpen = real.filter((p) => p.startsWith(CAST));
  const castFix = castOpen.length > 0 && (
    <div className="space-y-1 pt-2">
      <Button variant="secondary" icon={Users} busy={fixCast.isPending} onClick={() => fixCast.mutate()}>
        Put the right cast in each shot
      </Button>
      <p className="text-sm text-muted">Free. Uses who the script names in each line.</p>
      {fixCast.error && <p role="alert" className={errorClass}>{fixCast.error.message}</p>}
    </div>
  );

  const goTo = (target: string) => {
    document.getElementById(target)?.scrollIntoView?.({ behavior: "smooth", block: "center" });
    setFlash(target);
    setTimeout(() => setFlash(null), 2500);
  };
  const ring = (id: string) => (flash === id ? "outline outline-2 outline-accent" : "");

  const shots = bd.scenes.flatMap((s) => s.shots);
  const total = Math.round(bd.clips.reduce((sum, c) => sum + c.seconds, 0));
  const dirty = draft !== null;
  // A shot that names someone the video doesn't have: take the name out (free). It saves at once, so it waits for unsaved edits.
  const removal = useRemoveRef({
    run: async (shotId, kind, ref, name) => {
      // The id goes to the server (two unknown people in one shot stay apart); the sentence is made here, in words.
      const { data, error } = await api.POST("/projects/{project_id}/shots/{shot_id}/remove-ref", { params: { path: { project_id: projectId, shot_id: shotId } }, body: { kind, name: ref } });
      if (!data) throw new Error(errorText(error));
      // There is no Undo (the video doesn't have them), so the toast says how to use them again.
      const again = { character: "add them in Cast & places, then pick them in this shot", place: "add it in Cast & places, then pick it in this shot", screen: "add it to the brand's screens, then pick it in this shot" }[kind];
      return { fixed: [`Removed ${name} from shot ${shotId}. To use ${kind === "character" ? "them" : "it"} again, ${again}.`] };
    },
    refresh: refreshAll,
  });
  const unknownNames = (row as { unknown_names?: Record<string, string> }).unknown_names ?? {};
  const calledUnknown = (id: string, kind: RefKind) => unknownNames[id] ?? `a ${kind}`; // the name the server knows, or what it is
  const removeRef = preview ? undefined : (shotId: string, kind: RefKind, ref: string, name: string) => removal.button(shotId, kind, ref, name, dirty ? "Save your changes first." : undefined);
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

  const goButton = (p: string, after?: () => void) => {
    const target = problemTarget(p);
    return (
      target && (
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
      )
    );
  };
  const problemList = (after?: () => void) => (
    <ul className="space-y-1 text-sm">
      {real.map((p) => (
        <li key={p} className="flex flex-wrap items-start gap-2">
          <span className="w-full py-3 sm:w-auto sm:flex-1">{words(p)}</span>
          {goButton(p, after)}
          {fixes.beside(p)}
          {p.startsWith(CAST) && (
            <Button variant="ghost" dense aria-label={`Keep anyway: ${words(p)}`} onClick={() => (preview ? preview.keep(p) : keep.mutate({ problem: p }))}>
              Keep anyway
            </Button>
          )}
        </li>
      ))}
    </ul>
  );

  return (
    <div className="space-y-4" aria-label="Breakdown">
      {row.stale && (
        <Banner tone="warning" title={preview ? "This plan was made for older words. Make it again so the shots match." : "These shots were made for an older script."} action={preview ? preview.again : makeButton("Make new shots", { primary: true })} />
      )}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted">
          {bd.scenes.length} scene{bd.scenes.length === 1 ? "" : "s"} · {shots.length} shot{shots.length === 1 ? "" : "s"} · {bd.clips.length} clip{bd.clips.length === 1 ? "" : "s"} · {total} s{preview ? "" : ` of ${props.plannedSeconds} s planned`}
          <span className="sr-only"> · {row.source === "edit" ? "edited" : "made by Claude"}</span>
        </p>
        {!row.stale && makeButton("Redo", { ask: row.source === "edit" || dirty ? "Replace this breakdown? Your edits are kept in History." : undefined })}
      </div>
      {props.failed && <p role="alert" className={errorClass}>The breakdown didn't finish. Nothing was charged for the failed part.</p>}
      {props.problem}
      {real.length > 0 && phone && (
        <>
          <button className="flex min-h-control w-full items-center gap-2 rounded-lg border border-danger bg-danger-soft px-3 text-left text-danger" aria-label="Problems" onClick={() => setProblemsOpen(true)}>
            <TriangleAlert size={20} strokeWidth={1.75} aria-hidden />
            <span className="flex-1 font-medium">
              {real.length} problem{real.length === 1 ? "" : "s"}
            </span>
            <ChevronRight size={20} strokeWidth={1.75} aria-hidden />
          </button>
          {problemsOpen && (
            <Sheet title={`Problems (${real.length})`} onClose={() => setProblemsOpen(false)}>
              {problemList(() => setProblemsOpen(false))}
              {fixes.all}
              {castFix}
            </Sheet>
          )}
        </>
      )}
      {real.length > 0 && !phone && (
        <section className="space-y-1 rounded-lg border border-danger bg-danger-soft p-4 text-sm" aria-label="Problems">
          <h3 className="flex items-center gap-2 font-semibold text-danger">
            <TriangleAlert size={20} strokeWidth={1.75} aria-hidden />
            {real.length} problem{real.length === 1 ? "" : "s"} {preview ? "in this plan" : "to fix before the storyboard"}
          </h3>
          {problemList()}
          {fixes.all}
          {castFix}
        </section>
      )}
      <AdviceList label={words} problems={row.problems} kept={row.kept} onKeep={preview ? preview.keep : (problem, undo) => keep.mutate({ problem, undo })} busy={preview ? preview.keepBusy : keep.isPending} extra={(p) => goButton(p)} />
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
                              {s.script_lines.length > 0 &&
                                (props.onShowLines ? (
                                  <Button type="button" variant="ghost" dense aria-label={`Show ${lines(s.script_lines)} in the script`} onClick={() => props.onShowLines!(s.script_lines)}>
                                    {lineLabel(s.script_lines)}
                                  </Button>
                                ) : (
                                  <span className="text-muted">{lineLabel(s.script_lines)}</span>
                                ))}
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
                          {editing && !phone && <ShotEditor shot={s} picks={picks} called={calledUnknown} remove={removeRef} onChange={(patch) => change((b) => patchShot(b, s.id, patch))} />}
                          {phone && sheetShot === s.id && (
                            <Sheet title={`Shot ${s.id}`} onClose={() => setSheetShot(null)}>
                              <ShotEditor shot={s} picks={picks} called={calledUnknown} remove={removeRef} onChange={(patch) => change((b) => patchShot(b, s.id, patch))} />
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
