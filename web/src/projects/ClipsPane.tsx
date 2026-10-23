import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { Elapsed, useJobs } from "../clip/History";
import { btnPrimary, btnSecondary, card, errorText as errorClass, input, linkText } from "../ui";
import { useFrames } from "./StoryboardPane";

type Clip = components["schemas"]["ProjectClipOut"];
const GOING = ["queued", "running", "needs_owner_approval"];
const ratio = (a: string) => a.replace(":", " / ");

/** One video clip per breakdown clip: make takes, pick and approve one, then stitch them into the video. */
export function ClipsPane(props: { projectId: number; brandId: number; aspect: string; projectName: string; used: number; budget: number }) {
  const { projectId } = props;
  const queryClient = useQueryClient();
  const path = { project_id: projectId };
  const jobs = useJobs();
  const frames = useFrames(projectId);
  // The takes I started: clip row id → job id (jobs don't say which clip they are for yet).
  const [started, setStarted] = useState<Record<number, number>>({});
  const [writing, setWriting] = useState<number | null>(null);
  const jobOf = (id: number) => jobs.data?.find((j) => j.id === id);
  const going = (id: number | undefined) => id !== undefined && (!jobOf(id) || GOING.includes(jobOf(id)!.status));
  const serverGoing = (step: string) => (jobs.data ?? []).filter((j) => j.project_id === projectId && j.step === step && GOING.includes(j.status));
  const writingNow = going(writing ?? undefined) || serverGoing("clip_prompts").length > 0;
  const takesGoing = serverGoing("clip_take").length;
  const anyGoing = writingNow || takesGoing > 0 || Object.values(started).some((j) => going(j));

  const clips = useQuery({
    queryKey: ["project-clips", projectId],
    queryFn: async () => (await api.GET("/projects/{project_id}/clips", { params: { path } })).data ?? [],
    refetchInterval: () => (anyGoing ? 3000 : false),
  });
  const video = useQuery({
    queryKey: ["project-video", projectId],
    queryFn: async () => {
      const { data, response } = await api.GET("/projects/{project_id}/video", { params: { path } });
      if (response.status === 404) return null;
      if (!data) throw new Error("load");
      return data;
    },
  });
  const rates = useQuery({ queryKey: ["rates"], queryFn: async () => (await api.GET("/credits/rates")).data ?? [] });
  const rate = (kind: string) => rates.data?.find((r) => r.kind === kind)?.credits_per_unit;
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["project-clips", projectId] });
    queryClient.invalidateQueries({ queryKey: ["project-video", projectId] });
  };

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
    mutationFn: async (clip: Clip) => {
      const { data, error } = await api.POST("/projects/{project_id}/clips/{clip_id}/generate", { params: { path: { ...path, clip_id: clip.id } } });
      if (!data) throw new Error(errorText(error));
      return { clip, job: data };
    },
    onSuccess: ({ clip, job }) => {
      setStarted((s) => ({ ...s, [clip.id]: job.id }));
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
  const review = useMutation({
    mutationFn: async (act: { clip: Clip; take?: number }) => {
      const args = { params: { path: { ...path, clip_id: act.clip.id } } };
      const { error, response } =
        act.take !== undefined
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
  const stitch = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/projects/{project_id}/video", { params: { path } });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: refresh,
  });

  if (clips.isPending || frames.isPending) return <p className="text-muted">Loading…</p>;
  if (clips.isError) return <p role="alert" className={errorClass}>Could not load the clips. Try again.</p>;
  const list = clips.data;
  const over = (cost: number | undefined) => cost !== undefined && props.used + cost > props.budget;
  const price = (n: number | undefined) => (n === undefined ? "" : ` · ${Math.round(n)} credits`);
  const err = write.error ?? generate.error ?? review.error ?? edit.error ?? stitch.error;
  const videoRate = rate("video");
  const takeCost = (c: Clip) => (videoRate === undefined ? undefined : videoRate * c.seconds);
  const busyFor = (c: Clip) => going(started[c.id]);
  const missing = list.filter((c) => c.takes.length === 0 && c.problems.length === 0 && !c.stale && !busyFor(c));
  const allCost = videoRate === undefined ? undefined : missing.reduce((n, c) => n + videoRate * c.seconds, 0);
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
        <button className={btnPrimary} disabled={write.isPending} onClick={() => write.mutate()}>
          {over(writeCost) ? "Ask Reed to approve" : "Write clip prompts"}
          {price(writeCost)}
        </button>
        {err && <p role="alert" className={errorClass}>{err.message}</p>}
      </section>
    );

  const left = list.length - approved;
  const v = video.data;
  return (
    <div className="space-y-4" aria-label="Clips">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[length:var(--text-md)] font-semibold">
          Clips <span className="font-normal text-muted">· {list.length} · {approved} approved</span>
        </h2>
        {missing.length > 0 && (
          <button
            className={btnPrimary}
            disabled={generate.isPending}
            onClick={async () => {
              for (const c of missing) await generate.mutateAsync(c).catch(() => undefined);
            }}
          >
            {over(allCost) ? "Ask Reed to approve" : "Make missing"}
            {price(allCost)}
          </button>
        )}
      </div>
      {err && <p role="alert" className={errorClass}>{err.message}</p>}
      <ul className="space-y-4">
        {list.map((c) => {
          const job = started[c.id] !== undefined ? jobOf(started[c.id]) : undefined;
          return (
            <ClipCard
              key={c.id}
              clip={c}
              aspect={props.aspect}
              poster={frames.data?.find((f) => f.clip_id === c.clip_id)?.file_id ?? null}
              projectName={props.projectName}
              job={job}
              busy={busyFor(c)}
              cost={takeCost(c)}
              over={over(takeCost(c))}
              onGenerate={() => generate.mutate(c)}
              onPick={(take) => review.mutate({ clip: c, take })}
              onApprove={() => review.mutate({ clip: c })}
              onSave={(prompt) => edit.mutate({ clip: c, prompt })}
            />
          );
        })}
      </ul>
      <section className={`${card} space-y-2 text-sm`} aria-label="The video">
        <h3 className="font-semibold">The video</h3>
        {v ? (
          <>
            <video controls src={fileUrl(v.file_id)} className="max-h-96 rounded-sm" />
            <p className="text-muted">{Math.round(list.reduce((n, c) => n + c.seconds, 0))} s · {props.aspect}</p>
            <a className={`${btnSecondary} inline-block`} href={fileUrl(v.file_id)} download={`${props.projectName}.mp4`}>
              Download MP4
            </a>
            {v.out_of_date && <p className="text-warning">Out of date. A take or an approval changed since.</p>}
          </>
        ) : (
          <p className="text-muted">{left > 0 ? `${approved} of ${list.length} clips approved. Approve every clip to make the video (${left} left).` : "Every clip is approved."}</p>
        )}
        {(!v || v.out_of_date) && (
          <button className={btnPrimary} disabled={left > 0 || stitch.isPending} onClick={() => stitch.mutate()}>
            {stitch.isPending ? "Putting your clips together…" : v ? "Make the video again" : "Make the video"}
          </button>
        )}
        {!v && left === 0 && <p className="text-muted">Free: it uses no credits.</p>}
      </section>
    </div>
  );
}

function ClipCard(props: {
  clip: Clip;
  aspect: string;
  poster: number | null;
  projectName: string;
  job: { status: string; created_at: string } | undefined;
  busy: boolean;
  cost: number | undefined;
  over: boolean;
  onGenerate: () => void;
  onPick: (takeId: number) => void;
  onApprove: () => void;
  onSave: (prompt: string) => void;
}) {
  const { clip: c } = props;
  const [editing, setEditing] = useState<string | null>(null);
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
      {c.problems.length > 0 && (
        <ul className="list-disc pl-5 text-xs text-danger" aria-label={`Problems for ${c.clip_id}`}>
          {c.problems.map((p) => (
            <li key={p}>{p}</li>
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
          <button className={`${btnSecondary} min-h-11 sm:min-h-9`} disabled={props.busy || c.problems.length > 0 || c.stale} onClick={props.onGenerate}>
            {verb}
            {price}
          </button>
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
