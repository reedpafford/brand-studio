import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { Badge, Button } from "../components";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { Elapsed, useJobs } from "../clip/History";
import { btnPrimary, btnSecondary, card, errorText as errorClass, input, linkText } from "../ui";
import { blockerNames, SheetWarning, useSheetBlocks, type Blocker } from "./sheetBlocks";
import { useFrames } from "./StoryboardPane";
import { blocking } from "./problems";
import { KeepControl, useKeep } from "./Keep";

type Clip = components["schemas"]["ProjectClipOut"];
const GOING = ["queued", "running", "needs_owner_approval"];
const ratio = (a: string) => a.replace(":", " / ");

const hash = (t: string) => [...t].reduce((h, ch) => (h * 31 + ch.charCodeAt(0)) | 0, 7).toString(36);
/** Prompts the editor has read and marked "Looks good" (per browser; editing a prompt asks again). */
function useReviewed(projectId: number) {
  const key = `bs-prompts-ok-${projectId}`;
  const read = () => {
    try {
      return new Set<string>(JSON.parse(localStorage.getItem(key) ?? "[]"));
    } catch {
      return new Set<string>();
    }
  };
  const [ok, setOk] = useState(read);
  const id = (c: Clip) => `${c.id}:${hash(c.prompt)}`;
  const mark = (c: Clip) => {
    const next = new Set(ok).add(id(c));
    setOk(next);
    try {
      localStorage.setItem(key, JSON.stringify([...next]));
    } catch {
      /* private window: it just asks again next time */
    }
  };
  const unmark = (c: Clip) => {
    const next = new Set(ok);
    next.delete(id(c));
    setOk(next);
    try {
      localStorage.setItem(key, JSON.stringify([...next]));
    } catch {
      /* private window */
    }
  };
  return { has: (c: Clip) => ok.has(id(c)), mark, unmark };
}

/** The prompt as the editor reads it: script font, five lines with Show all, and each [ImageN] as the name of what it points at. */
function PromptText({ clip }: { clip: Clip }) {
  const [all, setAll] = useState(false);
  const images = clip.references.filter((r) => r.kind === "image");
  // A picture is named by what it is for; the first frame is "frame:<clip>", and an id with a colon is never shown.
  const name = (n: number) => {
    const ref = images[n - 1];
    if (!ref) return `Picture ${n}`;
    if (ref.role === "storyboard frame" || ref.id.startsWith("frame:") || ref.role.startsWith("frame:")) return "First frame";
    return ref.role && !ref.role.includes(":") ? ref.role : `Picture ${n}`;
  };
  const parts = clip.prompt.split(/(\[Image\d+\])/);
  return (
    <div className="space-y-1">
      <p className={`whitespace-pre-wrap rounded-md bg-surface-2 p-3 font-script leading-[1.6] [overflow-wrap:anywhere] ${all ? "" : "line-clamp-5"}`} aria-label={`Prompt for clip ${clip.clip_id}`}>
        {parts.map((t, i) => {
          const n = /^\[Image(\d+)\]$/.exec(t)?.[1];
          return n ? (
            <span key={i} className="mx-0.5 inline-block rounded-sm bg-accent-soft px-1.5 font-sans text-xs font-semibold text-accent-text">
              {name(Number(n))}
            </span>
          ) : (
            t
          );
        })}
      </p>
      <Button variant="ghost" dense onClick={() => setAll(!all)} aria-expanded={all}>
        {all ? "Show less" : "Show all"}
      </Button>
    </div>
  );
}

/** One video clip per breakdown clip: make takes, pick and approve one, then stitch them into the video. */
export function ClipsPane(props: { review?: boolean; projectId: number; brandId: number; aspect: string; projectName: string; used: number; budget: number }) {
  const { projectId } = props;
  const queryClient = useQueryClient();
  const path = { project_id: projectId };
  const jobs = useJobs();
  const frames = useFrames(projectId);
  const blocks = useSheetBlocks(projectId, props.brandId);
  const reviewed = useReviewed(projectId);
  const [writing, setWriting] = useState<number | null>(null);
  const jobOf = (id: number) => jobs.data?.find((j) => j.id === id);
  const going = (id: number | undefined) => id !== undefined && (!jobOf(id) || GOING.includes(jobOf(id)!.status));
  // The newest take job for a clip row (it survives a reload, since the job says which clip it is for).
  const takeJob = (clipRowId: number) =>
    (jobs.data ?? []).filter((j) => j.project_clip_id === clipRowId && j.step === "clip_take").sort((a, b) => b.id - a.id)[0];
  const serverGoing = (step: string) => (jobs.data ?? []).filter((j) => j.project_id === projectId && j.step === step && GOING.includes(j.status));
  const writingNow = going(writing ?? undefined) || serverGoing("clip_prompts").length > 0;
  const takesGoing = serverGoing("clip_take").length;
  const anyGoing = writingNow || takesGoing > 0;

  const clips = useQuery({
    queryKey: ["project-clips", projectId],
    queryFn: async () => (await api.GET("/projects/{project_id}/clips", { params: { path } })).data ?? [],
    refetchInterval: () => (anyGoing ? 3000 : false),
  });
  const rates = useQuery({ queryKey: ["rates"], queryFn: async () => (await api.GET("/credits/rates")).data ?? [] });
  const rate = (kind: string) => rates.data?.find((r) => r.kind === kind)?.credits_per_unit;
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["project-clips", projectId] });
    queryClient.invalidateQueries({ queryKey: ["project-video", projectId] });
  };
  // When a run or a take finishes, bring in what it made. The clips only refetch while a job is
  // going, so a job that finishes between two polls (or before it is ever seen running, like the
  // free stand-ins) would otherwise leave the card saying "Not made" until a reload.
  const finishedKey = (jobs.data ?? [])
    .filter((j) => j.project_id === projectId && (j.step === "clip_take" || j.step === "clip_prompts") && j.status === "succeeded")
    .map((j) => j.id)
    .join(",");
  useEffect(() => {
    if (!finishedKey) return;
    queryClient.invalidateQueries({ queryKey: ["project-clips", projectId] });
    queryClient.invalidateQueries({ queryKey: ["project-video", projectId] });
  }, [finishedKey, projectId, queryClient]);

  const write = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/projects/{project_id}/clips/prompts", { params: { path } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (job) => {
      setWriting(job.id);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
  const generate = useMutation({
    mutationFn: async ({ clip, note }: { clip: Clip; note?: string }) => {
      const { data, error } = await api.POST("/projects/{project_id}/clips/{clip_id}/generate", {
        params: { path: { ...path, clip_id: clip.id } },
        ...(note ? { body: { note } } : {}),
      });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });
  const review = useMutation({
    mutationFn: async (act: { clip: Clip; take?: number; undo?: boolean }) => {
      const args = { params: { path: { ...path, clip_id: act.clip.id } } };
      const { error, response } = act.undo
        ? await api.DELETE("/projects/{project_id}/clips/{clip_id}/approve", args)
        : act.take !== undefined
          ? await api.POST("/projects/{project_id}/clips/{clip_id}/takes/{take_id}/pick", { params: { path: { ...path, clip_id: act.clip.id, take_id: act.take } } })
          : await api.POST("/projects/{project_id}/clips/{clip_id}/approve", args);
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: refresh,
  });
  const edit = useMutation({
    mutationFn: async ({ clip, prompt }: { clip: Clip; prompt: string }) => {
      const { data, error } = await api.PUT("/projects/{project_id}/clips/{clip_id}", { params: { path: { ...path, clip_id: clip.id } }, body: { prompt, references: clip.references } });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: refresh,
  });
  const realImage = useMutation({
    mutationFn: async ({ clip, shot, on }: { clip: Clip; shot: string; on: boolean }) => {
      const { data, error } = await api.PUT("/projects/{project_id}/clips/{clip_id}/inserts/{shot_id}", {
        params: { path: { ...path, clip_id: clip.id, shot_id: shot } },
        body: { use_real_image: on },
      });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: refresh, // the take and its approval stay; only the finished video goes out of date
  });
  if (clips.isPending || frames.isPending) return <p className="text-muted">Loading…</p>;
  if (clips.isError) return <p role="alert" className={errorClass}>Could not load the clips. Try again.</p>;
  const list = clips.data;
  const over = (cost: number | undefined) => cost !== undefined && props.used + cost > props.budget;
  const price = (n: number | undefined) => (n === undefined ? "" : ` · ${Math.round(n)} credits`);
  const err = write.error ?? generate.error ?? review.error ?? edit.error ?? realImage.error;
  const takeCost = (c: Clip) => c.take_credits;
  const busyFor = (c: Clip) => going(takeJob(c.id)?.id);
  // In the new flow every prompt is read and marked "Looks good" before takes are paid for.
  const toRead = (c: Clip) => !!props.review && c.takes.length === 0 && !reviewed.has(c);
  const unread = list.filter(toRead).length;
  const missing = list.filter((c) => c.takes.length === 0 && !toRead(c) && blocking(c.problems).length === 0 && !c.stale && !busyFor(c) && blocks.forClip(c.clip_id).length === 0);
  const waitingForSheet = list.filter((c) => c.takes.length === 0 && blocks.forClip(c.clip_id).length > 0);
  const allCost = missing.reduce((n, c) => n + c.take_credits, 0);
  const approved = list.filter((c) => c.approved).length;
  const writeCost = rate("write-claude");

  if (writingNow)
    return (
      <section className={`${card} space-y-3`} aria-label="Clips">
        <p className="text-muted">Writing your clip prompts…</p>
        <div className="h-24 rounded-md bg-surface-2" aria-hidden />
      </section>
    );

  if (list.length === 0)
    return (
      <section className={`${card} space-y-3`} aria-label="Clips">
        <p className="text-[length:var(--text-xl)] font-semibold">No clips yet.</p>
        <p className="text-muted">Each clip is made from its storyboard frame and the breakdown.</p>
        <button className={`${btnPrimary} min-h-11 sm:min-h-9`} disabled={write.isPending} onClick={() => write.mutate()}>
          {over(writeCost) ? "Ask Reed to approve" : "Write clip prompts"}
          {price(writeCost)}
        </button>
        {err && <p role="alert" className={errorClass}>{err.message}</p>}
      </section>
    );

  return (
    <div className="space-y-4" aria-label="Clips">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[length:var(--text-md)] font-semibold">
          Clips <span className="font-normal text-muted">· {list.length} · {approved} approved</span>
        </h2>
        {missing.length > 0 && (
          <button
            className={`${btnPrimary} min-h-11 sm:min-h-9`}
            disabled={generate.isPending || unread > 0}
            onClick={async () => {
              for (const c of missing) await generate.mutateAsync({ clip: c }).catch(() => undefined);
            }}
          >
            {over(allCost) ? "Ask Reed to approve" : props.review ? "Make the takes" : "Make missing"}
            {price(allCost)}
          </button>
        )}
      </div>
      {unread > 0 && <p className="text-sm text-muted">Read each prompt and press Looks good before the takes are made ({unread} left).</p>}
      {err && <p role="alert" className={errorClass}>{err.message}</p>}
      {waitingForSheet.length > 0 && (
        <p className="text-sm text-warning">
          {waitingForSheet.length} clip{waitingForSheet.length === 1 ? " waits" : "s wait"} for a sheet ({blockerNames(waitingForSheet.flatMap((c) => blocks.forClip(c.clip_id)))}).
        </p>
      )}
      <ul className="space-y-4">
        {list.map((c) => {
          const job = takeJob(c.id);
          return (
            <ClipCard
              key={c.id}
              clip={c}
              projectId={projectId}
              aspect={props.aspect}
              poster={frames.data?.find((f) => f.clip_id === c.clip_id)?.file_id ?? null}
              projectName={props.projectName}
              job={job}
              busy={busyFor(c)}
              blockers={blocks.forClip(c.clip_id)}
              toRead={toRead(c)}
              onLooksGood={() => reviewed.mark(c)}
              onUndoLooksGood={() => reviewed.unmark(c)}
              showPrompt={!!props.review && c.takes.length === 0}
              brandId={props.brandId}
              cost={takeCost(c)}
              over={over(takeCost(c))}
              onGenerate={(note) => generate.mutate({ clip: c, note })}
              onPick={(take) => review.mutate({ clip: c, take })}
              onApprove={() => review.mutate({ clip: c })}
              onRealImage={(shot, on) => realImage.mutate({ clip: c, shot, on })}
              onUnapprove={() => review.mutate({ clip: c, undo: true })}
              onSave={(prompt) => edit.mutate({ clip: c, prompt })}
            />
          );
        })}
      </ul>
    </div>
  );
}

function ClipCard(props: {
  clip: Clip;
  projectId: number;
  aspect: string;
  poster: number | null;
  projectName: string;
  job: { status: string; created_at: string } | undefined;
  busy: boolean;
  blockers: Blocker[];
  toRead: boolean;
  showPrompt: boolean;
  onLooksGood: () => void;
  onUndoLooksGood: () => void;
  brandId: number;
  cost: number | undefined;
  over: boolean;
  onGenerate: (note?: string) => void;
  onPick: (takeId: number) => void;
  onApprove: () => void;
  onUnapprove: () => void;
  onRealImage: (shotId: string, on: boolean) => void;
  onSave: (prompt: string) => void;
}) {
  const { clip: c } = props;
  const keep = useKeep(props.projectId, { of: "clip", id: c.id });
  const [editing, setEditing] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const failed = props.job?.status === "failed";
  const status = c.approved ? "Approved" : props.busy ? null : failed ? "Failed · credits returned" : c.stale ? "Made for an older breakdown" : c.file_id ? "Ready" : "Not made";
  const verb = props.over ? "Ask Reed to approve" : c.takes.length === 0 ? "Make clip" : "Make another take";
  const price = props.cost === undefined ? "" : ` · ${Math.round(props.cost)} credits`;
  const picked = c.takes.find((t) => t.id === c.picked_take_id);
  return (
    <li className={`space-y-2 rounded-md bg-surface p-3 text-sm ${c.approved ? "border-2 border-success" : "border border-border"}`} aria-label={`Clip ${c.clip_id}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{c.clip_id} · {c.seconds} s</span>
        <span className={`ml-auto rounded-sm px-2 py-0.5 text-xs font-medium ${c.approved ? "bg-success-soft text-success" : failed ? "bg-danger-soft text-danger" : c.stale ? "bg-warning-soft text-warning" : "bg-surface-2"}`}>
          {status ?? (
            <>
              {props.job?.status === "queued" ? "Queued " : "Rendering "}
              {props.job && <Elapsed since={props.job.created_at} />}
            </>
          )}
        </span>
      </div>
      <div className="grid place-items-center overflow-hidden rounded-md bg-surface-2" style={{ aspectRatio: ratio(props.aspect), maxHeight: "24rem" }}>
        {c.file_id ? (
          <video controls muted src={fileUrl(c.file_id)} poster={props.poster ? fileUrl(props.poster) : undefined} className="h-full w-full object-cover" aria-label={`Video for clip ${c.clip_id}`} />
        ) : props.poster ? (
          <img src={fileUrl(props.poster)} alt={`Storyboard frame for clip ${c.clip_id}`} className="h-full w-full object-cover" />
        ) : (
          <span className="text-muted">No video yet</span>
        )}
      </div>
      <SheetWarning blockers={props.blockers} brandId={props.brandId} />
      {props.showPrompt && (
        <div className="space-y-1">
          {!props.toRead && <Badge tone="success" icon={Check}>Looks good</Badge>}
          <PromptText clip={c} />
        </div>
      )}
      {c.problems.length > 0 && (
        <ul className="text-xs text-danger" aria-label={`Problems for ${c.clip_id}`}>
          {c.problems.map((p) => (
            <li key={p} className="flex flex-wrap items-center gap-x-2">
              <span>{p}</span>
              <KeepControl problem={p} kept={c.kept} onKeep={keep.mutate} busy={keep.isPending} />
            </li>
          ))}
        </ul>
      )}
      {c.takes.length > 0 && (
        <fieldset className="flex flex-wrap items-center gap-3">
          <legend className="sr-only">Takes for clip {c.clip_id}</legend>
          <span className="text-muted">Takes:</span>
          {[...c.takes].reverse().map((t) => (
            <label key={t.id} className="inline-flex min-h-11 items-center gap-1 sm:min-h-0">
              <input type="radio" name={`takes-${c.id}`} className="size-5 sm:size-4" checked={t.id === c.picked_take_id} onChange={() => props.onPick(t.id)} />
              Take {t.number}
            </label>
          ))}
        </fieldset>
      )}
      {note !== null && (
        <div className="space-y-2">
          <label className="block">
            What's wrong?
            <textarea className={input} rows={3} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          <div className="flex gap-2">
            <button
              className={`${btnPrimary} min-h-11 sm:min-h-9`}
              disabled={props.busy || !note.trim()}
              onClick={() => {
                props.onGenerate(note.trim());
                setNote(null);
              }}
            >
              {props.over ? "Ask Reed to approve" : "Redo"}
              {price}
            </button>
            <button className={`${btnSecondary} min-h-11 sm:min-h-9`} onClick={() => setNote(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}
      {c.inserts.map((i) => (
        <label key={i.shot_id} className="flex min-h-11 w-full items-start gap-3 sm:min-h-0">
          <input type="checkbox" role="switch" className="mt-0.5 size-5 shrink-0 sm:size-4" checked={i.use_real_image} onChange={(e) => props.onRealImage(i.shot_id, e.target.checked)} />
          <span>
            Use the real image · {i.name} (shot {i.shot_id})
            <span className="block text-xs text-muted">Free. Shows the real picture at that moment.</span>
          </span>
        </label>
      ))}
      {editing !== null ? (
        <div className="space-y-2">
          <textarea className={input} rows={5} aria-label={`Prompt for ${c.clip_id}`} value={editing} onChange={(e) => setEditing(e.target.value)} />
          <div className="flex gap-2">
            <button className={btnPrimary} onClick={() => { props.onSave(editing); setEditing(null); }}>
              Save prompt
            </button>
            <button className={btnSecondary} onClick={() => setEditing(null)}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          {c.picked_take_id !== null && !c.approved && (
            <button className={`${btnSecondary} min-h-11 sm:min-h-9`} onClick={props.onApprove}>
              ✓ Looks good
            </button>
          )}
          {c.approved && (
            <button className={`${btnSecondary} min-h-11 sm:min-h-9`} onClick={props.onUnapprove}>
              Undo approval
            </button>
          )}
          {props.showPrompt && (
            <Button variant="secondary" icon={props.toRead ? Check : undefined} aria-label={`Prompt for ${c.clip_id} ${props.toRead ? "looks good" : "undo looks good"}`} onClick={props.toRead ? props.onLooksGood : props.onUndoLooksGood}>
              {props.toRead ? "Looks good" : "Undo"}
            </Button>
          )}
          {note === null && (
            <button className={`${btnSecondary} min-h-11 sm:min-h-9`} disabled={props.toRead || props.busy || blocking(c.problems).length > 0 || c.stale || props.blockers.length > 0} onClick={() => props.onGenerate()}>
            {verb}
            {price}
          </button>
          )}
          {c.takes.length > 0 && note === null && (
            <button className={`${linkText} min-h-11 sm:min-h-9`} onClick={() => setNote("")}>
              Needs a change
            </button>
          )}
          {picked && (
            <a className={`${linkText} inline-flex min-h-11 items-center sm:min-h-9`} href={fileUrl(picked.file_id)} download={`${props.projectName}-${c.clip_id}-take${picked.number}.mp4`}>
              Download
            </a>
          )}
          <button className={`${linkText} min-h-11 sm:min-h-9`} aria-label={`Edit the prompt for ${c.clip_id}`} onClick={() => setEditing(c.prompt)}>
            Edit prompt
          </button>
        </div>
      )}
    </li>
  );
}
