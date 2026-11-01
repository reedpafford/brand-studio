import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Square, Wand2 } from "lucide-react";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { useMe } from "../auth/useMe";
import { Badge, Banner, Button, Card, Dialog, buttonClass, creditsText } from "../components";
import { useToast } from "../toast";
import { ReviewChip } from "./Checks";
import { useProjectClips, useProjectVideo } from "./useProgress";

type Run = components["schemas"]["DirectorOut"];
type Turn = Run["turns"][number];

// What it's doing, from its newest move (ux-audit §8.5's progress line).
const DOING: Record<string, string> = {
  plan: "Making the plan",
  make_looks: "Making the looks",
  storyboard: "Making the storyboard",
  stills: "Drawing the stills",
  clip_prompts: "Writing the clip prompts",
  make_take: "Making clips",
  pick_take: "Making clips",
  final_cut: "Making the cut",
  deliver: "Making the cut",
};

/** The Director view of a video (ux-audit §8.5, director-chat.md first slice): the cut, a progress line, the delivery card
 *  with what it redid and why, Make it and Stop. Look inside has the steps, as they are. Chat and locks come later: the right
 *  column on desktop is kept free for them. */
export function DirectorPanel({ projectId, aspect, name, onLookInside }: { projectId: number; aspect: string; name: string; onLookInside: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const owner = useMe().data?.role === "owner";
  const [stopping, setStopping] = useState(false);
  const run = useQuery({
    queryKey: ["director", projectId],
    queryFn: async () => (await api.GET("/projects/{project_id}/director", { params: { path: { project_id: projectId } } })).data ?? null,
    refetchInterval: (q) => (q.state.data?.status === "running" ? 5_000 : false),
  });
  const clips = useProjectClips(projectId);
  const video = useProjectVideo(projectId);
  const r = run.data;
  const status = r?.status ?? "none";
  // When a move finishes, the steps have new work: refresh them, and the waiting banner for a held move.
  const moves = r?.turns.length ?? 0;
  useEffect(() => {
    if (!moves) return;
    void queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "director" && q.queryKey.includes(projectId) });
    void queryClient.invalidateQueries({ queryKey: ["jobs"] });
  }, [moves, status, projectId, queryClient]);
  const after = (data: Run) => {
    queryClient.setQueryData(["director", projectId], data);
    return queryClient.invalidateQueries({ queryKey: ["jobs"] });
  };
  const start = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/projects/{project_id}/director", { params: { path: { project_id: projectId } } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: after,
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  const stop = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/projects/{project_id}/director/stop", { params: { path: { project_id: projectId } } });
      if (!data) throw new Error(errorText(error));
      return data;
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

  const turns = r?.turns ?? [];
  const running = status === "running";
  const held = running && turns.some((t) => t.status === "needs_owner_approval");
  const blocked = r?.start_blocked || null;
  const cut = video.data;
  const list = clips.data ?? [];
  const doing = [...turns].reverse().find((t) => t.tool && DOING[t.tool])?.tool;
  const made = list.filter((c) => c.takes.length > 0).length;
  const phase = held ? "Waiting for the owner's OK" : !doing ? "Starting" : DOING[doing] === "Making clips" && list.length ? `Making clips: ${made} of ${list.length}` : DOING[doing];
  const credits = r ? creditsText(r.credits) : null;
  const dollars = owner && r?.spent_usd != null ? `the director's own time $${r.spent_usd.toFixed(2)}` : null; // rule 4: the owner only
  const note = [...turns].reverse().find((t) => t.tool === "deliver")?.why ?? "";
  const firstTake = turns.findIndex((t) => t.tool === "make_take");
  const redid = turns.filter((t, i) => t.tool === "make_take" && i > firstTake && t.why);
  const line =
    status === "none" ? (blocked ?? "It makes every step from the script, checks each take, and delivers the finished cut. You can stop it any time.")
    : running ? [phase, credits && `up to ${credits} so far`, dollars, "you can leave this page"].filter(Boolean).join(" · ")
    : [status === "ended" && (r!.ended || "It stopped."), credits && `${credits} for this run`, dollars].filter(Boolean).join(" · ");
  const badge = running ? <Badge tone={held ? "warning" : "neutral"}>{held ? "Waiting for approval" : "Working…"}</Badge> : status === "delivered" ? <Badge tone="success">Delivered</Badge> : status === "ended" ? <Badge tone="warning">Stopped</Badge> : null;

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <Card className="min-w-0 space-y-3" aria-label="The director">
        {cut ? (
          <video controls src={fileUrl(cut.file_id)} className="mx-auto max-h-[70vh] w-full rounded-lg bg-surface-2 object-contain" style={{ aspectRatio: aspect.replace(":", " / ") }} aria-label="The finished video" />
        ) : (
          <div className="mx-auto grid max-h-[50vh] w-full place-items-center rounded-lg bg-surface-2 p-4 text-center text-sm text-muted" style={{ aspectRatio: aspect.replace(":", " / ") }}>
            {running ? `${phase}…` : "The cut shows here once it's made."}
          </div>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="type-section">{status === "none" ? "Let the director make it" : "The director's cut"}</h2>
          {badge}
          <span className="flex-1" />
          {cut && !running && (
            <a className={buttonClass("secondary")} href={fileUrl(cut.file_id)} download={`${name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "video"}.mp4`}>
              <Download aria-hidden className="size-4" />
              Download MP4
            </a>
          )}
          {running ? (
            <Button variant="secondary" icon={Square} onClick={() => setStopping(true)}>
              Stop
            </Button>
          ) : (
            <Button icon={Wand2} busy={start.isPending} disabled={!!blocked} onClick={() => start.mutate()}>
              {status === "none" ? "Make it" : "Make it again"}
            </Button>
          )}
        </div>
        {line && <p className="break-words text-sm text-muted tabular-nums">{line}</p>}
        {status !== "none" && !running && blocked && <p className="text-sm text-muted">{blocked}</p>}
        {note && <p className="break-words">{note}</p>}
        {redid.length > 0 && (
          <Section title={`What it redid (${redid.length})`}>
            <Moves turns={redid} />
          </Section>
        )}
        {status === "delivered" && <ReviewChip projectId={projectId} />}
        {turns.length > 0 && (
          <Section title={`Every move (${turns.length})`} open={running}>
            <Moves turns={turns} newest={running ? 5 : undefined} />
          </Section>
        )}
        <p className="text-sm text-muted">
          Advice it leaves stays on Review.{" "}
          <button type="button" className="min-h-11 font-medium text-accent underline" onClick={onLookInside}>
            Look inside
          </button>{" "}
          for every step.
        </p>
      </Card>
      {stopping && (
        <Dialog title="Stop the director?" actionLabel="Stop" danger busy={stop.isPending} onCancel={() => setStopping(false)} onConfirm={() => stop.mutate()}>
          <p>It makes no more moves. What it already started still finishes, and nothing is undone. You can carry on in Look inside.</p>
        </Dialog>
      )}
    </div>
  );
}

function Section({ title, open, children }: { title: string; open?: boolean; children: ReactNode }) {
  return (
    <details open={open} className="space-y-2">
      <summary className="min-h-11 cursor-pointer py-2 text-sm font-medium">{title}</summary>
      {children}
    </details>
  );
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
      <ol className="space-y-2">
        {shown.map((t) => (
          <li key={t.turn} className="min-w-0 border-l-2 border-line pl-3 text-sm">
            <p className="break-words">{t.result || (t.status === "needs_owner_approval" ? "Waiting for the owner's OK." : "Deciding what to do next…")}</p>
            {t.why && <p className="break-words text-muted">{t.why}</p>}
          </li>
        ))}
      </ol>
    </>
  );
}
