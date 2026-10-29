import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { Check, Ellipsis, MapPin, Pencil, Star, User } from "lucide-react";
import { api } from "../api/client";
import { Badge, Banner, Button, Card, Dialog, EmptyState, Field, Menu, MenuItem, Skeleton, TextArea } from "../components";
import { useToast } from "../toast";
import { editScene, joinNext, moveLine, splitAt, toPut, toggleStar, type PlanLine, type PlanScene } from "./planEdits";
import { serverTime } from "../time";
import { errorText as errorClass } from "../ui";

/** The video's scene plan (flows P1; Builder-Server-8's #893, to #876's names): the script's words grouped into scenes. The words never change (rule 19). */
type Line = PlanLine;
type Scene = PlanScene;
type Job = { id: number; status: "queued" | "running" | "failed"; reason: string | null; started_at: string | null };
export type Plan = {
  status: "ready" | "approved";
  approved_by?: { id: number; name: string } | null;
  approved_at?: string | null;
  source: "claude" | "owner" | "breakdown" | "hand";
  structure?: { label: string; from: "reel" | "study" | "pattern" } | null;
  cast: { ref_id: string; name: string }[];
  scenes: Scene[];
  summary?: string | null;
  advice: { scene_id: string; kind: string; text: string }[];
  job?: Job | null;
  estimate_credits: number;
  approve_credits?: number | null;
  stop?: string | null;
  out_of_date?: boolean;
  earlier?: { id: number; version: number; source: string; made_at: string | null }[];
  after?: { shots: number; clips: number } | null;
};
type Project = { id: number; plan_status?: "none" | "ready" | "approved" | null; plan_credits?: number | null };

// The plan routes are Builder-Server-8's (#893); until they are in the generated schema they are called with fetch.
async function call<T>(method: "GET" | "POST" | "PUT", path: string, body?: object): Promise<T> {
  const r = await fetch(`${location.origin}/api${path}`, { method, credentials: "include", ...(body ? { body: JSON.stringify(body), headers: { "Content-Type": "application/json" } } : {}) });
  if (!r.ok) {
    const detail = await r.json().then((j: { detail?: unknown }) => j.detail, () => null);
    throw Object.assign(new Error(typeof detail === "string" ? detail : "That didn't go through. Nothing was charged; try again."), { status: r.status });
  }
  return (r.status === 204 ? null : await r.json()) as T;
}

function usePlan(projectId: number, enabled: boolean) {
  return useQuery({
    enabled,
    queryKey: ["plan", projectId],
    queryFn: async () => {
      try {
        return await call<Plan>("GET", `/projects/${projectId}/plan`);
      } catch (e) {
        if ((e as { status?: number }).status === 404) return null; // no plan yet (E)
        throw e;
      }
    },
    refetchInterval: (q) => (q.state.data?.job && q.state.data.job.status !== "failed" ? 3000 : false),
  });
}

function Elapsed({ since }: { since: string | null | undefined }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  if (!since) return null;
  const s = Math.max(0, Math.round((now - Date.parse(since)) / 1000));
  return <span className="tabular-nums"> {Math.floor(s / 60)}:{String(s % 60).padStart(2, "0")}</span>;
}

const ago = (iso: string) => {
  const m = Math.round((Date.now() - serverTime(iso).getTime()) / 60000);
  return m < 1 ? "just now" : m < 60 ? `${m} min ago` : m < 1440 ? `${Math.round(m / 60)} h ago` : serverTime(iso).toLocaleDateString();
};

/** One scene: its part, one place and time, its lines read only with each line's action, ★ product marks, and who's in it.
 *  Each line has a "…" (a sheet at 390, PL1): Move to scene N−1 / N+1 (across its edge only), Start a new scene here, ★. The card's
 *  own "…" has Join with next, and Edit opens the place, time and actions to type. */
function SceneCard({ scene, si, count, cast, advice, change }: { scene: Scene; si: number; count: number; cast: Plan["cast"]; advice: Plan["advice"]; change?: (fn: (s: Scene[]) => Scene[], said: string, done?: () => void) => void }) {
  const who = scene.cast_ids.map((id) => cast.find((c) => c.ref_id === id)?.name ?? id);
  const [editing, setEditing] = useState<{ place: string; time: string; part: string; actions: string[] } | null>(null);
  const n = si + 1;
  const lineMenu = (l: Line, li: number) => {
    const first = li === 0;
    const last = li === scene.lines.length - 1;
    return (
      <Menu
        title={`Line ${l.n}`}
        align="right"
        trigger={(p) => (
          <button type="button" {...p} aria-label={`More for line ${l.n}`} className="grid size-control shrink-0 place-items-center rounded-md text-muted hover:bg-surface-2">
            <Ellipsis size={20} strokeWidth={1.75} aria-hidden />
          </button>
        )}
      >
        {(close) => (
          <>
            {first && si > 0 && <MenuItem onClick={() => { close(); change!((s) => moveLine(s, si, li, -1), `Line ${l.n} moved to scene ${n - 1}.`); }}>Move to scene {n - 1}</MenuItem>}
            {last && si < count - 1 && <MenuItem onClick={() => { close(); change!((s) => moveLine(s, si, li, 1), `Line ${l.n} moved to scene ${n + 1}.`); }}>Move to scene {n + 1}</MenuItem>}
            {!first && <MenuItem onClick={() => { close(); change!((s) => splitAt(s, si, li), `A new scene starts at line ${l.n}.`); }}>Start a new scene here</MenuItem>}
            <MenuItem onClick={() => { close(); change!((s) => toggleStar(s, si, li), l.star ? `Line ${l.n} no longer shows the product.` : `Line ${l.n} shows the product.`); }}>{l.star ? "Remove the ★" : "★ Show the product here"}</MenuItem>
          </>
        )}
      </Menu>
    );
  };
  if (editing && change)
    return (
      <Card className="space-y-3">
        <h3 className="type-card">Scene {n}</h3>
        <div className="grid gap-2 sm:grid-cols-3">
          <Field label="Part" value={editing.part} onChange={(e) => setEditing({ ...editing, part: e.target.value })} maxLength={60} />
          <Field label="Place" value={editing.place} onChange={(e) => setEditing({ ...editing, place: e.target.value })} maxLength={120} />
          <Field label="Time" value={editing.time} onChange={(e) => setEditing({ ...editing, time: e.target.value })} maxLength={60} />
        </div>
        {scene.lines.map((l, li) => (
          <div key={l.n} className="space-y-1">
            <p className="type-script">{l.text}</p>
            <TextArea label={`What we see on line ${l.n}`} rows={2} maxLength={400} value={editing.actions[li]} onChange={(e) => setEditing({ ...editing, actions: editing.actions.map((a, i) => (i === li ? e.target.value : a)) })} />
          </div>
        ))}
        <p className="text-sm text-muted">The words are the script's: change them in the script.</p>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => change((s) => editScene(s, si, editing), `Scene ${n} saved.`, () => setEditing(null))}>Save scene</Button>
          <Button variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
        </div>
      </Card>
    );
  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="type-card">Scene {n}</h3>
        {scene.part && <Badge>{scene.part}</Badge>}
        <span className="flex items-center gap-1 text-sm text-muted">
          <MapPin size={16} strokeWidth={1.75} aria-hidden />
          {[scene.place, scene.time].filter(Boolean).join(" · ")}
        </span>
        {change && (
          <span className="ml-auto flex items-center gap-1">
            <Button variant="ghost" dense icon={Pencil} aria-label={`Edit scene ${n}`} onClick={() => setEditing({ place: scene.place, time: scene.time, part: scene.part, actions: scene.lines.map((l) => l.action) })}>Edit</Button>
            {si < count - 1 && (
              <Menu
                title={`Scene ${n}`}
                align="right"
                trigger={(p) => (
                  <button type="button" {...p} aria-label={`More for scene ${n}`} className="grid size-control place-items-center rounded-md text-muted hover:bg-surface-2">
                    <Ellipsis size={20} strokeWidth={1.75} aria-hidden />
                  </button>
                )}
              >
                {(close) => <MenuItem onClick={() => { close(); change((s) => joinNext(s, si), `Scenes ${n} and ${n + 1} are one scene.`); }}>Join with scene {n + 1}</MenuItem>}
              </Menu>
            )}
          </span>
        )}
      </div>
      <ol className="space-y-2">
        {scene.lines.map((l, li) => (
          <li key={l.n} className="flex items-start gap-2">
            <div className="min-w-0 flex-1 space-y-1">
              <p className="type-script">
                {l.star && <Star size={16} strokeWidth={1.75} className="mr-1 inline text-accent" aria-label="Product" />}
                {l.text}
              </p>
              {l.action && <p className="text-sm text-muted">{l.action}</p>}
            </div>
            {change && lineMenu(l, li)}
          </li>
        ))}
      </ol>
      {who.length > 0 && (
        <p className="flex flex-wrap gap-2 text-xs">
          {who.map((w) => (
            <Badge key={w} icon={User}>{w}</Badge>
          ))}
        </p>
      )}
      {advice.map((a) => (
        <p key={a.kind + a.text} className="text-sm text-warning">{a.text}</p>
      ))}
    </Card>
  );
}

/** The Scenes view: every P1 state, editing with Undo, and the step's one amber, "Approve the plan · makes the shots". */
function Scenes({ projectId, planCredits, onApproved }: { projectId: number; planCredits?: number | null; onApproved: () => void }) {
  const plan = usePlan(projectId, true);
  const queryClient = useQueryClient();
  const toast = useToast();
  const [note, setNote] = useState("");
  // An approved plan asks "Change the plan?" first, for an edit or an earlier plan alike.
  const [asking, setAsking] = useState<{ next: Scene[]; said: string; done?: () => void } | { earlier: number } | null>(null);
  const refresh = () => Promise.all([queryClient.invalidateQueries({ queryKey: ["plan", projectId] }), queryClient.invalidateQueries({ queryKey: ["project", projectId] })]);
  const make = useMutation({ mutationFn: () => call("POST", `/projects/${projectId}/plan`, note.trim() ? { note: note.trim() } : {}), onSuccess: () => { setNote(""); return refresh(); } });
  // Stop works queued or running and is never charged (#893).
  const stopMaking = useMutation({ mutationFn: () => call("POST", `/projects/${projectId}/plan/stop`), onSettled: refresh });
  const byHand = useMutation({ mutationFn: () => call("POST", `/projects/${projectId}/plan/by-hand`), onSuccess: refresh });
  const useEarlier = useMutation({ mutationFn: (i: number) => call("POST", `/projects/${projectId}/plan/earlier/${i}/use`), onSuccess: refresh });
  const save = useMutation({ mutationFn: (scenes: Scene[]) => call<Plan>("PUT", `/projects/${projectId}/plan`, toPut(scenes)), onSuccess: refresh });
  const approve = useMutation({
    mutationFn: () => call("POST", `/projects/${projectId}/plan/approve`),
    onSuccess: async () => {
      await Promise.all([refresh(), queryClient.invalidateQueries({ queryKey: ["jobs"] })]);
      onApproved();
    },
  });
  // With no plan yet, the video carries the plan's price (#893); else it's one Claude call, priced from the rates.
  const rates = useQuery({ queryKey: ["rates"], queryFn: async () => (await api.GET("/credits/rates")).data ?? [] });
  const latest = [make, stopMaking, byHand, useEarlier, save, approve].reduce((a, m) => (m.submittedAt > a.submittedAt ? m : a));
  const refused = latest.isError ? latest.error.message : null;

  if (plan.isPending)
    return (
      <div role="status" aria-label="Loading the plan" className="space-y-3">
        <Skeleton className="h-6 w-2/3" />
        <Skeleton className="h-40" />
        <Skeleton className="h-40" />
      </div>
    );
  if (plan.isError)
    return (
      <Banner title="Couldn't load the plan." action={<Button variant="secondary" onClick={() => void plan.refetch()}>Try again</Button>}>
        Nothing was changed.
      </Banner>
    );
  const p = plan.data;
  const job = p?.job;
  if (job && job.status !== "failed")
    return (
      <div role="status" className="space-y-3">
        <p className="text-sm">
          {job.status === "queued" ? "Waiting to start" : "Making the plan…"}
          <Elapsed since={job.started_at} />
          {job.started_at ? "." : ""} You can leave this page.
        </p>
        <Button variant="ghost" busy={stopMaking.isPending} onClick={() => stopMaking.mutate()}>Stop</Button>
        <Skeleton className="h-40" />
      </div>
    );
  const stop = p?.stop ?? null;
  const price = p?.estimate_credits ?? planCredits ?? rates.data?.find((r) => r.kind === "write-claude")?.credits_per_unit ?? null;
  const makeButton = (label: string, primary = true) => (
    <Button variant={primary ? "primary" : "secondary"} price={price} disabled={!!stop} reason={stop} busy={make.isPending} onClick={() => make.mutate()}>
      {label}
    </Button>
  );
  if (!p || p.scenes.length === 0)
    return (
      <div className="space-y-3">
        {job?.status === "failed" && (
          <Banner title={job.reason ?? "The plan didn't finish."} action={makeButton("Try again", false)}>
            Nothing was charged. Or plan the scenes yourself.
          </Banner>
        )}
        {refused && <p role="alert" className={errorClass}>{refused}</p>}
        <EmptyState icon={MapPin} title="No plan yet" action={job?.status === "failed" ? undefined : makeButton("Make the plan")}>
          Turn the script into scenes: where each line happens and what we see.
        </EmptyState>
        <Button variant="ghost" busy={byHand.isPending} onClick={() => byHand.mutate()}>Write it myself · free</Button>
      </div>
    );

  const approved = p.status === "approved";
  const fromBreakdown = p.source === "breakdown";
  const lines = p.scenes.reduce((n, s) => n + s.lines.length, 0);
  const stars = p.scenes.reduce((n, s) => n + s.lines.filter((l) => l.star).length, 0);
  const summary = p.summary ?? `${p.scenes.length} scene${p.scenes.length === 1 ? "" : "s"} · ${lines} line${lines === 1 ? "" : "s"} · the product in ${stars}`;
  // Every edit saves at once (free) with Undo; an approved plan asks first, since its shots follow it.
  const commit = (next: Scene[], said: string) => {
    const before = p.scenes;
    // Undo puts the scenes back, not an approval: the plan waits for Approve again, and the toast says so.
    save.mutate(next, { onSuccess: () => toast(approved ? `${said} It waits for your approval again.` : said, () => save.mutate(before)) });
  };
  // `done` runs once the change goes ahead (an open editor closes then): Not yet keeps what was typed.
  const change = (fn: (s: Scene[]) => Scene[], said: string, done?: () => void) => {
    const next = fn(p.scenes);
    if (next === p.scenes) return done?.();
    if (approved) return setAsking({ next, said, done });
    commit(next, said);
    done?.();
  };
  const earlier = p.earlier ?? [];
  // What a change to an approved plan puts out of date (#893's `after`; null before there are shots): "3 shots and 2 clips".
  const outOfDate = [[p.after?.shots ?? 0, "shot"], [p.after?.clips ?? 0, "clip"]].filter(([k]) => (k as number) > 0).map(([k, w]) => `${k} ${w}${k === 1 ? "" : "s"}`).join(" and ");
  return (
    <div className="space-y-4">
      {p.structure && <p className="text-sm">{p.structure.from === "pattern" ? `Pattern: ${p.structure.label}` : `From the reference ${p.structure.from === "reel" ? "reel" : "study"}: ${p.structure.label}`}</p>}
      {p.cast.length > 0 && (
        <p className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted">Cast:</span>
          {p.cast.map((c) => (
            <Badge key={c.ref_id} icon={User}>{c.name}</Badge>
          ))}
        </p>
      )}
      <p className="text-sm text-muted">{summary}</p>
      {p.out_of_date && (
        <Banner tone="warning" title="Made for older words." action={makeButton("Make a new plan", false)}>
          The script's words changed since this plan was made. A new plan is made from the new words; this one is kept under Earlier plans.
        </Banner>
      )}
      {approved ? (
        <div className="space-y-1">
          <p className="flex items-center gap-2 text-sm">
            <Check size={16} strokeWidth={1.75} aria-hidden className="text-success" />
            {fromBreakdown ? "Approved · made from this video's breakdown" : p.source === "owner" ? "Approved · from the owner's plan" : `Approved${p.approved_by ? ` by ${p.approved_by.name}` : ""}${p.approved_at ? ` · ${ago(p.approved_at)}` : ""}`}
          </p>
          {fromBreakdown && <p className="text-sm text-muted">This video started before plans existed.</p>}
        </div>
      ) : p.source === "owner" ? (
        <p className="text-sm text-muted">From the owner's plan</p>
      ) : null}
      {refused && <p role="alert" className={errorClass}>{refused}</p>}
      <ul className="grid gap-3 [&>li]:min-w-0">
        {p.scenes.map((s, i) => (
          <li key={s.id} aria-label={`Scene ${i + 1}`}>
            <SceneCard scene={s} si={i} count={p.scenes.length} cast={p.cast} advice={p.advice.filter((a) => a.scene_id === s.id)} change={change} />
          </li>
        ))}
      </ul>
      {!approved && (
        <Button price={p.approve_credits ?? null} disabled={!!stop} reason={stop} busy={approve.isPending} onClick={() => approve.mutate()}>
          Approve the plan · makes the shots
        </Button>
      )}
      <details className="rounded-lg border border-border bg-surface px-4">
        <summary className="flex min-h-11 cursor-pointer items-center py-2 font-medium">Make a new plan</summary>
        <div className="space-y-2 pb-4">
          <TextArea label="What to change (optional)" rows={2} maxLength={500} placeholder="Make it funnier: he's a drama queen" value={note} onChange={(e) => setNote(e.target.value)} />
          {makeButton("Make a new plan", false)}
          <p className="text-sm text-muted">This plan is kept under Earlier plans; one press brings it back, free.</p>
        </div>
      </details>
      {earlier.length > 0 && (
        <details className="rounded-lg border border-border bg-surface px-4">
          <summary className="flex min-h-11 cursor-pointer items-center py-2 font-medium">Earlier plans · {earlier.length}</summary>
          <ul className="space-y-2 pb-4">
            {earlier.map((e, i) => (
              <li key={e.id} className="flex flex-wrap items-center gap-2 text-sm">
                <span className="min-w-0 flex-1">Plan {e.version}{e.made_at ? ` · ${ago(e.made_at)}` : ""}</span>
                <Button variant="secondary" dense busy={useEarlier.isPending && useEarlier.variables === i} onClick={() => (approved ? setAsking({ earlier: i }) : useEarlier.mutate(i))}>Use this one · free</Button>
              </li>
            ))}
          </ul>
        </details>
      )}
      {asking && (
        <Dialog title="Change the plan?" cancelLabel="Not yet" actionLabel="Change" busy={save.isPending || useEarlier.isPending} onCancel={() => setAsking(null)} onConfirm={() => { const a = asking; setAsking(null); if ("earlier" in a) useEarlier.mutate(a.earlier); else { commit(a.next, a.said); a.done?.(); } }}>
          It goes back to Ready to check, and its shots are made again from the new plan once you approve it.
          {outOfDate && ` This puts ${outOfDate} out of date.`} Your current final cut stays downloadable.
        </Dialog>
      )}
    </div>
  );
}

/** The Plan step (item 1b): Scenes (the scene plan) and Shots (what was the Breakdown step). Until the video carries its plan status
 *  (Builder-Server-8), it shows Shots alone, as Breakdown did. Shots is greyed until the plan is approved; with no view asked for, it
 *  opens on Scenes until then and on Shots after. */
export function PlanStep({ shots, project }: { shots: ReactNode; project?: Project }) {
  const [params, setParams] = useSearchParams();
  const status = project?.plan_status;
  if (!project || status == null) return <>{shots}</>;
  const approved = status === "approved";
  const asked = params.get("view");
  const view = asked === "shots" && approved ? "shots" : asked === "scenes" ? "scenes" : approved ? "shots" : "scenes";
  const go = (v: "scenes" | "shots") => {
    const next = new URLSearchParams(params);
    next.set("view", v);
    setParams(next, { replace: true });
  };
  const tab = (id: "scenes" | "shots", label: string, off: string | null) => (
    <button
      type="button"
      role="tab"
      aria-selected={view === id}
      aria-disabled={off ? true : undefined}
      aria-describedby={off ? `plan-${id}-why` : undefined}
      onClick={() => !off && go(id)}
      className={`-mb-px inline-flex min-h-control items-center gap-2 border-b-2 px-3 font-medium ${view === id ? "border-accent text-text" : "border-transparent text-muted"} ${off ? "cursor-not-allowed opacity-60" : "hover:text-text"}`}
    >
      {label}
      {off && <span id={`plan-${id}-why`} className="sr-only">{off}</span>}
    </button>
  );
  return (
    <div className="space-y-4">
      <div role="tablist" aria-label="Plan views" className="flex items-center gap-1 border-b border-border">
        {tab("scenes", "Scenes", null)}
        {tab("shots", "Shots", approved ? null : "Approve the plan first")}
        {!approved && <span className="ml-2 text-sm text-muted">Shots: approve the plan first</span>}
      </div>
      {view === "scenes" ? <Scenes projectId={project.id} planCredits={project.plan_credits} onApproved={() => go("shots")} /> : shots}
    </div>
  );
}
