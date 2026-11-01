import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Square, Wand2 } from "lucide-react";
import { Link } from "react-router-dom";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { useMe } from "../auth/useMe";
import { Badge, Banner, Button, Card, Dialog, buttonClass, creditsText } from "../components";
import { useToast } from "../toast";
import { useProjectVideo } from "./useProgress";

// What the run says (Next-Server #1087). `credits` (up to), `start_blocked` and an editor's null `spent_usd` are agreed and may land after.
type Run = components["schemas"]["DirectorOut"] & { credits?: number; start_blocked?: string; spent_usd?: number | null };
type Turn = Run["turns"][number];

/** The director on a video made from a script (director-chat.md, first slice): Make it, what it's doing as it goes, Stop,
 *  and the finished cut with its note. The step screens below stay as they are, to look inside. */
export function DirectorPanel({ projectId, aspect, name }: { projectId: number; aspect: string; name: string }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const owner = useMe().data?.role === "owner";
  const [stopping, setStopping] = useState(false);
  const run = useQuery({
    queryKey: ["director", projectId],
    queryFn: async () => (await api.GET("/projects/{project_id}/director", { params: { path: { project_id: projectId } } })).data as Run | undefined ?? null,
    refetchInterval: (q) => (q.state.data?.status === "running" ? 5_000 : false),
  });
  const r = run.data;
  const status = r?.status ?? "none";
  // When a move finishes, the steps below have new work: refresh them.
  const moves = r?.turns.length ?? 0;
  useEffect(() => {
    if (!moves) return;
    void queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "director" && q.queryKey.includes(projectId) });
    void queryClient.invalidateQueries({ queryKey: ["jobs"] }); // a held move shows in the waiting banner
  }, [moves, status, projectId, queryClient]);
  const after = (data: Run | undefined) => {
    if (data) queryClient.setQueryData(["director", projectId], data);
    return queryClient.invalidateQueries({ queryKey: ["jobs"] });
  };
  const start = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/projects/{project_id}/director", { params: { path: { project_id: projectId } } });
      if (!data) throw new Error(errorText(error));
      return data as Run;
    },
    onSuccess: after,
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  const stop = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/projects/{project_id}/director/stop", { params: { path: { project_id: projectId } } });
      if (!data) throw new Error(errorText(error));
      return data as Run;
    },
    onSuccess: (data) => {
      setStopping(false);
      toast("Stopped. What it already started still finishes.");
      return after(data);
    },
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  if (run.isPending) return null;
  if (run.isError) return <Banner tone="warning" title="Couldn't load the director." action={<Button variant="secondary" onClick={() => void run.refetch()}>Try again</Button>} />;
  const cost = r ? spent(r, owner) : "";
  const blocked = r?.start_blocked || null;
  const makeIt = (label: string) => (
    <Button icon={Wand2} busy={start.isPending} disabled={!!blocked} onClick={() => start.mutate()}>
      {label}
    </Button>
  );

  if (status === "running") {
    const held = r!.turns.some((t) => t.status === "needs_owner_approval");
    return (
      <Card className="space-y-3" aria-label="The director">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="type-section">{held ? "The director is waiting for approval" : "The director is making this video"}</h2>
            {cost && <p className="text-sm text-muted tabular-nums">{cost}</p>}
          </div>
          <Button variant="secondary" icon={Square} onClick={() => setStopping(true)}>
            Stop
          </Button>
        </div>
        <Moves turns={r!.turns} newest={5} />
        {stopping && (
          <Dialog title="Stop the director?" actionLabel="Stop" danger busy={stop.isPending} onCancel={() => setStopping(false)} onConfirm={() => stop.mutate()}>
            <p>It makes no more moves. What it already started still finishes, and nothing is undone. You can carry on in the steps below.</p>
          </Dialog>
        )}
      </Card>
    );
  }
  if (status === "delivered") return <Delivered run={r!} cost={cost} projectId={projectId} aspect={aspect} name={name} again={makeIt("Make it again")} blocked={blocked} />;
  if (status === "ended")
    return (
      <Banner tone="warning" title={`The director stopped${r!.ended ? `: ${r!.ended}` : "."}`} action={makeIt("Make it again")}>
        {cost} {blocked ?? "You can carry on in the steps below, or make it again."}
        <details className="mt-2">
          <summary className="min-h-11 cursor-pointer py-2 text-sm">What it did ({r!.turns.length})</summary>
          <Moves turns={r!.turns} />
        </details>
      </Banner>
    );
  return (
    <Card className="flex flex-wrap items-center justify-between gap-3" aria-label="The director">
      <div className="min-w-0 flex-1">
        <h2 className="type-section">Let the director make it</h2>
        <p className="text-sm text-muted">{blocked ?? "It makes every step from the script, checks each take, and gives you the finished cut. You can stop it any time."}</p>
      </div>
      {makeIt("Make it")}
    </Card>
  );
}

/** "Up to 42 credits so far", and for the owner only what the director's own thinking cost (rule 4: editors never see dollars). */
function spent(r: Run, owner: boolean) {
  const credits = r.credits != null ? `Up to ${creditsText(r.credits)}${r.status === "running" ? " so far" : ""}.` : "";
  const usd = owner && r.spent_usd != null ? ` The director's own time: $${r.spent_usd.toFixed(2)}.` : "";
  return (credits + usd).trim();
}

/** Each move as one plain line, what it did, with its reason under it. While it runs, only the newest few, with Show all. */
function Moves({ turns, newest }: { turns: Turn[]; newest?: number }) {
  const [all, setAll] = useState(false);
  const shown = newest && !all ? turns.slice(-newest) : turns;
  return (
    <>
      {shown.length < turns.length && (
        <Button variant="ghost" dense onClick={() => setAll(true)}>
          Show all {turns.length} moves
        </Button>
      )}
      <ol className="space-y-2" aria-label="What the director did">
        {shown.map((t) => (
          <li key={t.turn} className="min-w-0 border-l-2 border-line pl-3 text-sm">
            <p className="break-words">
              {t.result || (t.status === "needs_owner_approval" ? "Waiting for the owner's OK." : "Deciding what to do next…")}
            </p>
            {t.why && <p className="break-words text-muted">{t.why}</p>}
          </li>
        ))}
      </ol>
    </>
  );
}

function Delivered({ run, cost, projectId, aspect, name, again, blocked }: { run: Run; cost: string; projectId: number; aspect: string; name: string; again: ReactNode; blocked: string | null }) {
  const video = useProjectVideo(projectId);
  const v = video.data;
  const note = [...run.turns].reverse().find((t) => t.tool === "deliver")?.why ?? "";
  return (
    <Card className="grid gap-4 sm:grid-cols-[minmax(0,320px)_1fr]" aria-label="The director's cut">
      {v ? (
        <video controls src={fileUrl(v.file_id)} className="w-full rounded-lg bg-surface-2" style={{ aspectRatio: aspect.replace(":", " / ") }} aria-label="The finished video" />
      ) : (
        <p className="text-sm text-muted" role="status">The finished cut is on Final cut.</p>
      )}
      <div className="min-w-0 space-y-3">
        <Badge tone="success">Made by the director</Badge>
        {note && <p className="break-words">{note}</p>}
        {cost && <p className="text-sm text-muted tabular-nums">{cost}</p>}
        {blocked && <p className="text-sm text-muted">{blocked}</p>}
        <div className="flex flex-wrap gap-2">
          {v && (
            <a className={buttonClass("primary")} href={fileUrl(v.file_id)} download={`${name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "video"}.mp4`}>
              <Download aria-hidden className="size-4" />
              Download MP4
            </a>
          )}
          <Link className={buttonClass("secondary")} to="?step=clips">
            Look inside
          </Link>
          {again}
        </div>
        <details>
          <summary className="min-h-11 cursor-pointer py-2 text-sm">What it did ({run.turns.length})</summary>
          <Moves turns={run.turns} />
        </details>
      </div>
    </Card>
  );
}
