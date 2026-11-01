import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Clapperboard, Square } from "lucide-react";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { Banner, Button, Card, creditsText } from "../components";
import { videoQuery } from "./useProgress";

type Director = components["schemas"]["DirectorOut"];

/** The director's run on this video (null when the server has none for this person: not theirs, or not built there). */
export function useDirector(projectId: number) {
  return useQuery({
    queryKey: ["director", projectId],
    queryFn: async () => {
      const { data, response } = await api.GET("/projects/{project_id}/director", { params: { path: { project_id: projectId } } });
      if (!data) return response.status >= 500 ? Promise.reject(new Error("load")) : null;
      return data;
    },
    refetchInterval: (q) => (q.state.data?.status === "running" ? 3000 : false),
  });
}

const WORDS: Record<string, string> = { running: "Working", delivered: "Delivered", ended: "Stopped" };

/** The Director view (audit 8.5, first slice): start, the progress log, the delivery note, Stop and what it cost.
 *  The chat and the locks come once the server has them. "Look inside" is the steps, as before. */
export function DirectorView({ projectId, run }: { projectId: number; run: Director }) {
  const queryClient = useQueryClient();
  const video = useQuery(videoQuery(projectId));
  const press = useMutation({
    mutationFn: async (stop: boolean) => {
      const path = { project_id: projectId };
      const { data, error } = stop ? await api.POST("/projects/{project_id}/director/stop", { params: { path } }) : await api.POST("/projects/{project_id}/director", { params: { path } });
      if (!data) throw new Error((error as { detail?: string } | undefined)?.detail ?? "That didn't work. Try again.");
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["director", projectId], data);
      for (const key of ["project", "jobs", "project-video"]) void queryClient.invalidateQueries({ queryKey: [key] });
    },
  });
  const turns = [...run.turns].reverse(); // newest first
  const last = run.turns.at(-1);
  const cost = `${run.status === "delivered" ? "" : "up to "}${creditsText(run.credits)}${run.spent_usd != null ? ` · $${run.spent_usd.toFixed(2)} director time` : ""}`;
  return (
    <section className="space-y-4" aria-label="Director">
      {run.status === "none" ? (
        <Card className="space-y-3 p-4">
          <p>The director makes this video from its published script: the shots, the cast, the stills, the clips and the cut. You can stop it at any time, and look inside to change any step.</p>
          <Button icon={Clapperboard} busy={press.isPending} reason={run.start_blocked || undefined} disabled={!!run.start_blocked} onClick={() => press.mutate(false)}>
            Make it now
          </Button>
        </Card>
      ) : (
        <Card className="space-y-3 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p role="status">
              <span className="font-semibold">{WORDS[run.status] ?? run.status}</span>
              {last?.result && run.status === "running" && <span className="text-muted"> · {last.result}</span>}
              <span className="block text-sm text-muted tabular-nums">{cost}</span>
            </p>
            {run.status === "running" ? (
              <Button variant="secondary" icon={Square} busy={press.isPending} onClick={() => press.mutate(true)}>
                Stop
              </Button>
            ) : (
              <Button variant="secondary" icon={Clapperboard} busy={press.isPending} reason={run.start_blocked || undefined} disabled={!!run.start_blocked} onClick={() => press.mutate(false)}>
                Make it again
              </Button>
            )}
          </div>
          {run.status === "delivered" && video.data?.file_id && <video controls src={fileUrl(video.data.file_id)} className="max-h-96 w-full rounded-md bg-surface-3" aria-label="The cut" />}
          {run.status === "delivered" && last?.why && (
            <div>
              <h3 className="font-semibold">Delivery note</h3>
              <p className="whitespace-pre-line">{last.why}</p>
            </div>
          )}
          {run.status === "ended" && run.ended && <p>{run.ended} What it already made is kept.</p>}
        </Card>
      )}
      {press.error && <Banner title={press.error.message} />}
      {turns.length > 0 && (
        <div>
          <h3 className="type-section">What it did</h3>
          <ol className="divide-y divide-border" aria-label="What the director did">
            {turns.map((t) => (
              <li key={t.turn} className="py-2">
                <p>
                  <span className="tabular-nums text-muted">{t.turn}.</span> {t.result || (t.status === "needs_owner_approval" ? "Waiting for the owner's OK." : "Deciding…")}
                </p>
                {t.why && <p className="text-sm text-muted">{t.why}</p>}
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}
