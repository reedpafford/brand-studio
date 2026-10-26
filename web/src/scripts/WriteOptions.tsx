import { useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { api, errorText } from "../api/client";
import { useJobs } from "../clip/History";
import { Button, Card } from "../components";
import { errorText as errorClass } from "../ui";
import { Link } from "react-router-dom";
import { ReadReelButton, useReelImport } from "./ReelImport";
import { useAllowanceStop, usePatchScript, type Script } from "./useScript";

/** An empty script's ways to get words: Claude writes it (from the reel, or from the description), or you paste it yourself. */
export function WriteOptions({ script: s, onOwn }: { script: Script; onOwn: () => void }) {
  const queryClient = useQueryClient();
  const hasReel = !!s.reference_id || s.reel_imported;
  const estimate = useQuery({ queryKey: ["write-estimate", s.id], queryFn: async () => (await api.GET("/scripts/{script_id}/write/estimate", { params: { path: { script_id: s.id } } })).data ?? null });
  const credits = estimate.data?.credits;
  const stop = useAllowanceStop(s, credits);
  const patch = usePatchScript(s.id);
  const reel = useReelImport(s.id);
  const jobs = useJobs();
  const last = jobs.data?.filter((j) => j.kind === "write-claude" && j.script_id === s.id).sort((a, b) => b.id - a.id)[0];
  const write = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/scripts/{script_id}/write", { params: { path: { script_id: s.id } } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });

  // Just started: it counts as writing until the job list has caught up and says otherwise.
  const startedId = write.data?.id;
  const writing = last?.status === "queued" || last?.status === "running" || (startedId !== undefined && (last?.id ?? 0) < startedId);
  // The words arrive with the job: bring them in.
  useEffect(() => {
    if (last?.status !== "succeeded") return;
    void queryClient.invalidateQueries({ queryKey: ["script-lib", s.id] });
    void queryClient.invalidateQueries({ queryKey: ["script-cast", s.id] }); // the write also found the roles
  }, [last?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  // An imported reel is read before anything is written: its lines become the script.
  if (reel.data && reel.data.status !== "done")
    return (
      <Card className="max-w-[680px] space-y-3">
        <h2 className="type-section">Read the reel first</h2>
        <p className="text-sm text-muted">Its lines become the script.</p>
        <ReadReelButton scriptId={s.id} createdById={s.created_by_id} />
        <Link to="?" className="block text-accent-text underline">See the reel on Description</Link>
        <div className="border-t border-border pt-3">
          <Button variant="ghost" onClick={onOwn}>
            Paste or write it yourself
          </Button>
        </div>
      </Card>
    );
  if (s.reel_imported && reel.isPending) return null;
  if (writing || write.isPending)
    return (
      <Card className="max-w-[680px]">
        <div role="status">
          <p className="flex items-center gap-2"><Sparkles size={20} strokeWidth={1.75} aria-hidden /> Claude is writing the script…</p>
          <p className="text-sm text-muted">It shows here when it's ready. You can leave this page.</p>
        </div>
      </Card>
    );
  const label = hasReel ? "Write from the reference" : "Write with Claude";
  return (
    <Card className="max-w-[680px] space-y-4">
      <div className="space-y-2">
        <h2 className="type-section">{label}</h2>
        <p className="text-sm text-muted">{hasReel ? (s.new_lines ? "Writes new lines in the reel's voice and pacing. The shots and beats still follow the reel." : "Keeps the reel's lines word for word and rewrites only what the brand swap needs.") : "Claude writes it from the description."}</p>
        {hasReel && (
          <label className="flex min-h-control items-center gap-3">
            <input type="checkbox" role="switch" className="size-5" checked={s.new_lines} disabled={patch.isPending} onChange={(e) => patch.mutate({ new_lines: e.target.checked })} />
            Write new lines in the same style
          </label>
        )}
        {last?.status === "failed" && (
          <p role="alert" className={errorClass}>
            The last try didn't finish. Credits were returned.
          </p>
        )}
        {write.isError && <p role="alert" className={errorClass}>{write.error.message}</p>}
        <Button icon={Sparkles} price={credits} disabled={credits === undefined || stop !== null || patch.isPending} reason={stop} onClick={() => write.mutate()}>
          {last?.status === "failed" ? "Try again" : label}
        </Button>
        {credits !== undefined && <p className="text-sm text-muted">Includes finding the roles.</p>}
      </div>
      <div className="border-t border-border pt-3">
        <Button variant="ghost" onClick={onOwn}>
          Paste or write it yourself
        </Button>
      </div>
    </Card>
  );
}
