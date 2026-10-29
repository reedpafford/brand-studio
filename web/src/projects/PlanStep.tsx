import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { Check, MapPin, Star, User } from "lucide-react";
import { api } from "../api/client";
import { Badge, Banner, Button, Card, EmptyState, Skeleton } from "../components";
import { serverTime } from "../time";
import { errorText as errorClass } from "../ui";

/** The video's scene plan (flows P1; Builder-Server-8's fields, as agreed): the script's words grouped into scenes. The words never change (rule 19). */
type Line = { n: number; text: string; action: string; star: boolean };
type Scene = { id: string; part: string; place: string; time: string; cast_ids: string[]; lines: Line[] };
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
};
type Project = { id: number; plan_status?: "none" | "ready" | "approved" | null };

// The routes are Builder-Server-8's; until they are in the generated schema they are called with fetch.
async function call<T>(method: "GET" | "POST", path: string, body?: object): Promise<T> {
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

/** One scene: its part of the structure, one place and time, its lines read only, each line's action, ★ product marks, and who's in it. */
function SceneCard({ scene, n, cast, advice }: { scene: Scene; n: number; cast: Plan["cast"]; advice: Plan["advice"] }) {
  const who = scene.cast_ids.map((id) => cast.find((c) => c.ref_id === id)?.name ?? id);
  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="type-card">Scene {n}</h3>
        {scene.part && <Badge>{scene.part}</Badge>}
        <span className="flex items-center gap-1 text-sm text-muted">
          <MapPin size={16} strokeWidth={1.75} aria-hidden />
          {[scene.place, scene.time].filter(Boolean).join(" · ")}
        </span>
      </div>
      <ol className="space-y-2">
        {scene.lines.map((l) => (
          <li key={l.n} className="space-y-1">
            <p className="type-script">
              {l.star && <Star size={16} strokeWidth={1.75} className="mr-1 inline text-accent" aria-label="Product" />}
              {l.text}
            </p>
            {l.action && <p className="text-sm text-muted">{l.action}</p>}
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

/** The Scenes view: every P1 state, and the step's one amber, "Approve the plan · makes the shots". */
function Scenes({ projectId, onApproved }: { projectId: number; onApproved: () => void }) {
  const plan = usePlan(projectId, true);
  const queryClient = useQueryClient();
  const refresh = () => Promise.all([queryClient.invalidateQueries({ queryKey: ["plan", projectId] }), queryClient.invalidateQueries({ queryKey: ["project", projectId] })]);
  const make = useMutation({ mutationFn: () => call("POST", `/projects/${projectId}/plan`, {}), onSuccess: refresh });
  const cancel = useMutation({ mutationFn: (id: number) => call("POST", `/jobs/${id}/cancel`), onSuccess: refresh });
  const byHand = useMutation({ mutationFn: () => call("POST", `/projects/${projectId}/plan/by-hand`), onSuccess: refresh });
  const approve = useMutation({
    mutationFn: () => call("POST", `/projects/${projectId}/plan/approve`),
    onSuccess: async () => {
      await Promise.all([refresh(), queryClient.invalidateQueries({ queryKey: ["jobs"] })]);
      onApproved();
    },
  });
  // With no plan yet there's no plan to carry its price: it's one Claude call, priced from the rates as Breakdown is.
  const rates = useQuery({ queryKey: ["rates"], queryFn: async () => (await api.GET("/credits/rates")).data ?? [] });
  const latest = [make, cancel, byHand, approve].reduce((a, m) => (m.submittedAt > a.submittedAt ? m : a));
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
          <Elapsed since={job.started_at} />. You can leave this page.
        </p>
        {job.status === "queued" && <Button variant="ghost" busy={cancel.isPending} onClick={() => cancel.mutate(job.id)}>Cancel</Button>}
        <Skeleton className="h-40" />
      </div>
    );
  const stop = p?.stop ?? null;
  const makeButton = (label: string, primary = true) => (
    <Button variant={primary ? "primary" : "secondary"} price={p?.estimate_credits ?? rates.data?.find((r) => r.kind === "write-claude")?.credits_per_unit ?? null} disabled={!!stop} reason={stop} busy={make.isPending} onClick={() => make.mutate()}>
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
            <SceneCard scene={s} n={i + 1} cast={p.cast} advice={p.advice.filter((a) => a.scene_id === s.id)} />
          </li>
        ))}
      </ul>
      {!approved && (
        <Button price={p.approve_credits ?? null} disabled={!!stop} reason={stop} busy={approve.isPending} onClick={() => approve.mutate()}>
          Approve the plan · makes the shots
        </Button>
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
      {view === "scenes" ? <Scenes projectId={project.id} onApproved={() => go("shots")} /> : shots}
    </div>
  );
}
