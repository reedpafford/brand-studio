import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronDown, CircleCheckBig, CircleStop, Clock, LoaderCircle, TriangleAlert, X } from "lucide-react";
import { api, errorText, polled } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { Button } from "../components";
import { refreshJobs } from "../jobs/refresh";
import { mmss } from "../freestyle/FromScript";
import { serverTime } from "../time";

export type Progress = components["schemas"]["ProgressOut"];
type Note = components["schemas"]["DeliveryNoteOut"];
type Cell = components["schemas"]["ClipCellOut"];
type Scene = components["schemas"]["RunSceneOut"];

const LIVE = ["working", "revising", "waiting"];
const clock = (iso: string) => serverTime(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });

/** A clip is being made though the run has ended (Try again on a failed clip). */
const making = (r: Progress) => r.scenes.some((s) => s.clips.some((c) => c.state === "making"));

/** The newest run's live record (v6 piece C), read again every 3 s while it works, revises or waits, or a clip is made. */
export function useRunProgress(projectId: number, enabled = true) {
  return useQuery({
    queryKey: ["run-progress", projectId],
    enabled: enabled && projectId > 0,
    refetchInterval: (q) => (q.state.data && (LIVE.includes(q.state.data.status) || making(q.state.data)) ? 3_000 : false),
    queryFn: () => polled(api.GET("/projects/{project_id}/director/progress", { params: { path: { project_id: projectId } } }), null),
  });
}

/** "This person has watched these takes" (Watch the changes, or a frame played): the outline comes off. Free. */
export function useSeen(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (takeIds: number[]) => {
      if (!takeIds.length) return;
      await api.POST("/projects/{project_id}/director/seen", { params: { path: { project_id: projectId } }, body: { take_ids: takeIds } });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["run-progress", projectId] }),
  });
}

// A clip's frame on the strip (S3-03): made, being made, still to do, redone after watching (amber), or changed since this
// person watched it (accent), until they do.
function look(c: Cell): "todo" | "making" | "redo" | "fresh" | "bad" | "done" {
  if (c.state === "todo") return "todo";
  if (c.state === "making") return "making";
  if (c.changed && !c.watched) return "fresh";
  if (c.state === "redone" || c.state === "text" || c.state === "flagged" || c.state === "waiting") return "redo";
  if (c.state === "failed" || c.state === "too_long") return "bad"; // too long for its model: never shown as done
  return "done";
}
const RING = { fresh: "outline outline-[1.5px] outline-offset-1 outline-accent", redo: "outline outline-[1.5px] outline-offset-1 outline-need-dot", bad: "outline outline-[1.5px] outline-offset-1 outline-danger", making: "outline outline-[1.5px] outline-offset-1 outline-accent", todo: "", done: "" };

/** One frame: its still, or the empty or working place it fills. */
function Frame({ c, className, onPick }: { c: Cell; className: string; onPick?: (c: Cell) => void }) {
  const l = look(c);
  const body =
    l === "todo" ? (
      <span className={`block border border-dashed border-border-strong bg-surface-2 ${className}`} />
    ) : l === "making" || c.frame_file_id == null ? (
      <span className={`block bg-[linear-gradient(110deg,#ececf0_30%,#f6f6f8_45%,#ececf0_60%)] ${className} ${RING[l]}`} />
    ) : (
      <img src={fileUrl(c.frame_file_id)} alt="" className={`block object-cover ${className} ${RING[l]}`} />
    );
  const name = `Clip ${c.number}${c.note ? `: ${c.note}` : ""}`;
  return onPick ? (
    <button type="button" aria-label={name} title={name} onClick={() => onPick(c)} className="shrink-0">
      {body}
    </button>
  ) : (
    <span title={name} className="shrink-0">
      {body}
    </span>
  );
}

/** The video as a strip of real frames, scene by scene (the signature, S3-03): each scene's frames side by side with its
 *  name under them; the scene being made is named in the accent. `big`: the Cut tab's strip (S3-09), a frame a press. */
export function Filmstrip({ scenes, at, big, onPick }: { scenes: Scene[]; at?: number; big?: boolean; onPick?: (c: Cell) => void }) {
  return (
    <ol aria-label="The video, scene by scene" className={`flex items-end overflow-x-auto ${big ? "gap-2" : "gap-1.5"}`}>
      {scenes.map((s, i) => (
        <li key={s.id} className="flex shrink-0 flex-col gap-1">
          <span className="flex gap-0.5">
            {s.clips.map((c) => (
              <Frame key={c.clip_id} c={c} onPick={onPick} className={big ? "h-[43px] w-6 rounded-[3px]" : "h-[39px] w-[22px] rounded-[3px]"} />
            ))}
          </span>
          {s.name && <span className={`max-w-full truncate text-[11px] font-medium ${at === i + 1 ? "text-accent-text" : "text-muted"}`}>{s.name}</span>}
        </li>
      ))}
    </ol>
  );
}

/** On a phone (P-04, P-05): one frame a scene, its count under it; before a scene has clips, its name (never "0/0",
 *  MAIN's run, video 233). */
export function SceneRow({ scenes }: { scenes: Scene[] }) {
  return (
    <ol aria-label="The video, scene by scene" className="flex gap-2 overflow-x-auto">
      {scenes.map((s) => {
        const shown = s.clips.find((c) => c.frame_file_id != null && c.state !== "todo") ?? s.clips.find((c) => c.state === "making") ?? s.clips[0];
        return (
          <li key={s.id} className="flex shrink-0 flex-col items-center gap-1">
            {shown && <Frame c={{ ...shown, changed: s.clips.some((c) => c.changed && !c.watched), watched: false }} className="h-[78px] w-11 rounded-md" />}
            {s.total > 0 ? (
              <span className="text-xs tabular-nums text-muted">
                {s.done}/{s.total}
              </span>
            ) : (
              s.name && <span className="max-w-24 truncate text-xs text-muted">{s.name}</span>
            )}
          </li>
        );
      })}
    </ol>
  );
}

const ICON = {
  now: <LoaderCircle size={14} strokeWidth={1.75} aria-hidden className="shrink-0 text-accent-text" />,
  wait: <Clock size={14} strokeWidth={1.75} aria-hidden className="shrink-0 text-warning" />,
  done: <CircleCheckBig size={14} strokeWidth={1.75} aria-hidden className="shrink-0 text-success" />,
  bad: <TriangleAlert size={14} strokeWidth={1.75} aria-hidden className="shrink-0 text-danger" />,
  stop: <CircleStop size={14} strokeWidth={1.75} aria-hidden className="shrink-0 text-muted" />,
};
const STEP = {
  done: ["bg-success-soft text-success", <Check key="d" size={12} strokeWidth={2} aria-hidden />],
  now: ["bg-accent-soft text-accent", <LoaderCircle key="n" size={12} strokeWidth={2} aria-hidden />],
  todo: ["border-[1.5px] border-border-strong", null],
  wait: ["bg-warning-soft text-warning", <Clock key="w" size={12} strokeWidth={2} aria-hidden />],
  bad: ["bg-danger-soft text-danger", <X key="b" size={12} strokeWidth={2} aria-hidden />],
} as const;

const left = (min: number) => (min >= 60 ? `about ${Math.floor(min / 60)} h ${min % 60} min left` : `about ${min} min left`);
const LONG = 60; // a long video (S3-13: 118 clips) reads as a row a scene, not a frame a clip

/** The run's one live card (S3-03 folded, S3-04 open, S3-08 stopped, S3-11 failed, S3-12 revising, S3-13 long; P-04 on a
 *  phone): its head, the strip of frames, and every step a press away. */
export function RunCard({ progress: r, phone }: { progress: Progress; phone: boolean }) {
  const [open, setOpen] = useState(false);
  const long = r.clips > LONG;
  const steps = (
    <ol aria-label="Every step" className="mt-2.5 flex flex-col border-t border-border pt-1">
      {r.steps.map((s) => {
        const [cls, icon] = STEP[s.state];
        return (
          <li key={s.key} className="flex items-start gap-2.5 py-[7px] text-[13px] leading-[18px]">
            <span className={`grid size-[18px] shrink-0 place-items-center rounded-full ${cls}`}>{icon}</span>
            <span className="min-w-0 flex-1">
              <span className={s.state === "now" ? "font-medium" : ""}>{s.text}</span>
              {s.sub && <span className="block text-xs text-muted">{s.sub}</span>}
            </span>
          </li>
        );
      })}
    </ol>
  );
  const toggle = (
    <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="ml-auto inline-flex shrink-0 items-center justify-end gap-1 text-sm text-muted hover:text-text max-lg:min-h-control max-lg:min-w-control">
      {!phone && (open ? "Hide steps" : "Every step")}
      <ChevronDown size={phone ? 14 : 12} strokeWidth={1.75} aria-hidden className={open ? "rotate-180" : ""} />
      {phone && <span className="sr-only">{open ? "Hide steps" : "Every step"}</span>}
    </button>
  );
  const shown = r.scenes.slice(0, 8);
  const body = long ? (
    <div>
      <div className="mb-2 h-1 overflow-hidden rounded-sm bg-surface-3" aria-hidden>
        <i className="block h-full rounded-sm bg-accent" style={{ width: `${r.clips ? Math.round((100 * r.made) / r.clips) : 0}%` }} />
      </div>
      <ol aria-label="Scenes">
        {shown.map((s, i) => (
          <li key={s.id} className="flex items-center gap-3 border-t border-border py-1.5 text-[13px]">
            <span className={`min-w-0 flex-1 truncate ${s.done > 0 && s.done < s.total ? "font-medium" : ""}`}>
              {s.name ? `${i + 1}. ${s.name}` : `Scene ${i + 1}`}
            </span>
            <span className="h-1 w-[120px] overflow-hidden rounded-sm bg-surface-3" aria-hidden>
              <i className="block h-full rounded-sm bg-accent" style={{ width: `${s.total ? Math.round((100 * s.done) / s.total) : 0}%` }} />
            </span>
            <span className="w-11 text-right tabular-nums text-muted">{s.total > 0 && `${s.done}/${s.total}`}</span>
          </li>
        ))}
      </ol>
      {(r.scenes.length > shown.length || !!r.minutes_left) && (
        <p className="pt-1.5 text-xs text-muted">{[r.scenes.length > shown.length && `+ ${r.scenes.length - shown.length} more scenes`, !!r.minutes_left && left(r.minutes_left)].filter(Boolean).join(" · ")}</p>
      )}
    </div>
  ) : phone ? (
    <SceneRow scenes={r.scenes} />
  ) : (
    <Filmstrip scenes={r.scenes} at={r.status === "working" || r.status === "revising" ? r.scene_at : undefined} />
  );
  const waiting = r.tone === "wait" && r.sub;
  const banner = waiting && r.status === "waiting"; // says the wait once: never also in the head line (polish)
  return (
    <section aria-label={r.title} className="rounded-lg border border-border bg-surface shadow-[0_1px_2px_rgb(28_27_25/0.06),0_2px_8px_rgb(28_27_25/0.04)]">
      <div className="flex min-w-0 items-center gap-2 px-3 py-2.5">
        {ICON[r.tone]}
        <span className="shrink-0 text-[13px] font-semibold">{r.title}</span>
        {!phone && r.sub && !banner && <span className="min-w-0 truncate text-[13px] text-muted">· {r.sub}</span>}
        {toggle}
      </div>
      <div className="px-3 pb-3">
        {phone && r.sub && !banner && <p className="mb-2 text-xs text-muted">{[r.sub, r.redone > 0 && `${r.redone} redone after watching`].filter(Boolean).join(" · ")}</p>}
        {body}
        {banner && (
          <p className="mt-2.5 flex items-center gap-2 rounded-md bg-warning-soft px-2.5 py-2 text-[13px] text-warning">
            <Clock size={14} strokeWidth={1.75} aria-hidden className="shrink-0" />
            {r.sub}
          </p>
        )}
        {r.actual_usd != null && (
          <p className="mt-2 text-xs tabular-nums text-muted">
            {[r.cost || `$${r.actual_usd.toFixed(2)} spent on this run`, r.expected_usd != null && `about $${r.expected_usd.toFixed(2)} (estimate)`].filter(Boolean).join(" · ")}
          </p>
        )}
        {open && steps}
      </div>
    </section>
  );
}

/** A run that a person stopped (S3-08): the line saying who and when, and the director's reply with Carry on at its price
 *  and Start the plan again (a new run that plans the whole video again; its start card says its "up to" before Make it). */
/** The Stops a run carried on from (S3-08), as lines in the chat: "Reed stopped the director at 10:31 · carried on at 10:40". */
export const stopLines = (r: Progress) => (r.stops ?? []).map((x) => `${x.by} stopped the director at ${clock(x.at)} · carried on at ${clock(x.carried_at)}.`);

export function stoppedParts({ progress: r, onCarryOn, onPlanAgain, busy, planBusy, blocked, error }: { progress: Progress; onCarryOn: () => void; onPlanAgain: () => void; busy: boolean; planBusy: boolean; blocked: string | null; error: string | null }) {
  const s = r.stopped!;
  return {
    line: `${s.by} stopped the director at ${clock(s.at)}. Nothing more is being spent.`,
    reply: (
      <div className="flex flex-col gap-2">
        <p className="leading-[21px]">{`Stopped. ${s.made ? `The ${s.made} finished clip${s.made === 1 ? " is" : "s are"} kept.` : "Nothing was finished yet."} Tell me what to change, or carry on where I left off.`}</p>
        <div className="flex flex-wrap gap-2">
          {(s.carry_on || s.free) && ( // "": an editor's Carry on waits for the owner's OK, on its own card
            <Button busy={busy} disabled={!!blocked || planBusy} reason={blocked} onClick={onCarryOn}>
              {s.free ? "Carry on" : `Carry on · up to ${s.carry_on} more`}
            </Button>
          )}
          <Button variant="secondary" busy={planBusy} disabled={!!blocked || busy} reason={blocked} onClick={onPlanAgain}>
            Start the plan again
          </Button>
        </div>
        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      </div>
    ),
  };
}

/** A run that stopped on a problem (S3-11): what went wrong, in plain words, and its one-click fixes (never none): the
 *  failed clip again, carry on, split a clip too long for its model (free: the breakdown's own fix), or the video's
 *  settings, to pick a model that makes longer clips (`onSettings`: the Plan tab, the preview side on a phone). */
export function Failed({ progress: r, projectId, onCarryOn, onSettings, busy, blocked }: { progress: Progress; projectId: number; onCarryOn: () => void; onSettings: () => void; busy: boolean; blocked: string | null }) {
  const f = r.failed!;
  const queryClient = useQueryClient();
  const again = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/projects/{project_id}/clips/{clip_id}/generate", { params: { path: { project_id: projectId, clip_id: f.clip ?? 0 } } });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: () => Promise.all([refreshJobs(queryClient), queryClient.invalidateQueries({ queryKey: ["run-progress", projectId] })]),
  });
  const split = useMutation({
    mutationFn: async (problem: string) => {
      const { data, error } = await api.POST("/projects/{project_id}/breakdown/fix", { params: { path: { project_id: projectId } }, body: { problems: [problem] } });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: () => Promise.all([queryClient.invalidateQueries({ queryKey: ["run-progress", projectId] }), queryClient.invalidateQueries({ queryKey: ["breakdown", projectId] })]),
  });
  const press = (x: (typeof f.fixes)[number]) =>
    x.kind === "again" ? again.mutate() : x.kind === "split" ? split.mutate(x.problem) : x.kind === "model" ? onSettings() : onCarryOn(); // the video's settings: the Plan tab, on a phone too
  const then = f.fixes.find((x) => x.kind === "split")?.then;
  return (
    <section aria-label={f.title} className="overflow-hidden rounded-lg border border-[#f1c6c1] bg-surface">
      <p className="flex items-center gap-2 bg-danger-soft px-3 py-2.5 text-[13px] font-semibold text-danger">
        <TriangleAlert size={14} strokeWidth={1.75} aria-hidden />
        {f.title}
      </p>
      <div className="flex flex-col gap-3 px-3 pb-3 pt-2.5">
        <p className="text-[13px] leading-[19px]">{f.why}</p>
        {f.offer && <p className="text-[13px] leading-[19px]">{f.offer}</p>}
        <div className="flex flex-wrap gap-2">
          {f.fixes.map((x, i) => (
            <Button
              key={x.kind}
              variant={i === 0 ? "primary" : "secondary"}
              busy={x.kind === "again" ? again.isPending || making(r) : x.kind === "split" ? split.isPending : x.kind === "model" ? false : busy}
              disabled={x.kind === "carry_on" && !!blocked}
              reason={x.kind === "carry_on" ? blocked : undefined}
              onClick={() => press(x)}
            >
              {!x.price ? x.label : x.price === "free" ? `${x.label} · free` : `${x.label} · up to ${x.price}`}
            </Button>
          ))}
        </div>
        {then && <p className="text-xs text-muted">Its new clips are then made at their own price: up to {then}.</p>}
        {(again.isError || split.isError) && <p role="alert" className="text-sm text-danger">{(again.error ?? split.error)?.message}</p>}
      </div>
    </section>
  );
}

const money = (n: Note) => (n.spent_usd != null ? `$${n.spent_usd.toFixed(2)}` : `${Math.round(n.spent)} credits`);

/** The delivery note (S3-09, S3-10, P-08): Reed's three parts the director writes (5 Nov, #1340), What I made; What I
 *  watched and redid, the server's rows at their times (board S3-09, S5), shown when there are any; What remains uncertain, the director's words and what the server knows is still open; What I need from
 *  you, as the server says it ("ready to post" only when nothing is open); and what the video has cost so far, as its header says it (S3-12). `onWatch`: the changes it made, watched (the outline comes off). */
export function DeliveryNote({ note: n, onWatch, changes }: { note: Note; onWatch?: () => void; changes: number }) {
  const part = (title: string, body: ReactNode) => (
    <div className="flex flex-col gap-1">
      <h4 className="text-xs font-semibold text-muted">{title}</h4>
      {body}
    </div>
  );
  return (
    <section aria-label="Delivery note" className="rounded-lg border border-border bg-surface shadow-[0_1px_2px_rgb(28_27_25/0.06),0_2px_8px_rgb(28_27_25/0.04)]">
      <div className="flex items-center gap-2 px-3 py-2.5">
        <h3 className="text-[13px] font-semibold">Delivery note</h3>
        <span className="ml-auto inline-flex items-center gap-1.5 text-xs font-medium text-success">
          <span aria-hidden className="size-[7px] rounded-full bg-success" />
          Delivered
        </span>
      </div>
      <div className="flex flex-col gap-3 px-3 pb-3">
        {part("What I made", <p className="text-[13px] leading-[19px] max-lg:text-[15px] max-lg:leading-[22px]">{n.made}</p>)}
        {n.redid.length > 0 &&
          part(
            "What I watched and redid",
            <ul aria-label="What I watched and redid" className="flex flex-col gap-1 text-[13px] max-lg:text-[15px]">
              {n.redid.map((r, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="inline-flex h-5 shrink-0 items-center rounded-sm bg-accent-soft px-1.5 text-[11px] font-semibold tabular-nums text-accent-text">{mmss(r.at)}</span>
                  <span className="min-w-0">{r.text}</span>
                </li>
              ))}
            </ul>,
          )}
        {(n.unsure || n.open.length > 0) &&
          part(
            "What remains uncertain",
            <>
              {n.unsure && <p className="text-[13px] leading-[19px] max-lg:text-[15px] max-lg:leading-[22px]">{n.unsure}</p>}
              {n.open.length > 0 && (
                <ul className="flex list-disc flex-col gap-0.5 pl-4 text-[13px] leading-[19px] max-lg:text-[15px] max-lg:leading-[22px]">
                  {n.open.map((o, i) => (
                    <li key={i}>{o}</li>
                  ))}
                </ul>
              )}
            </>,
          )}
        {part("What I need from you", <p className="text-[13px] text-muted max-lg:text-[15px]">{n.needs}</p>)}
      </div>
      <div className="flex items-center gap-2 border-t border-border px-3 py-2.5 text-[13px]">
        <span className="tabular-nums text-muted">{n.cost}</span>
        {onWatch && changes > 0 && (
          <button type="button" onClick={onWatch} className="ml-auto font-medium text-accent-text hover:underline max-lg:min-h-control">
            Watch the changes
          </button>
        )}
      </div>
    </section>
  );
}

/** An earlier cut's note, folded to one line (S3-12): "Delivery note · Cut 1 · 0:58 · $9.84". */
export function PastNote({ note: n }: { note: Note }) {
  const [open, setOpen] = useState(false);
  return (
    <details onToggle={(e) => setOpen(e.currentTarget.open)} className="rounded-lg border border-border bg-surface px-3 py-2 text-[13px] text-muted">
      <summary className="cursor-pointer list-none tabular-nums max-lg:min-h-control max-lg:content-center">{["Delivery note", n.cut != null && `Cut ${n.cut}`, n.seconds > 0 && mmss(n.seconds), money(n)].filter(Boolean).join(" · ")}</summary>
      {open && (
        <div className="mt-2 text-text">
          <DeliveryNote note={n} changes={0} />
        </div>
      )}
    </details>
  );
}
