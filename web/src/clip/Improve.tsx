import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { creditsLabel } from "../components";
import { Sheet } from "../projects/Sheet";
import { btnPrimary, btnSecondary, errorText as errorClass, input } from "../ui";

type Body = components["schemas"]["ClipIn"];
const DIRECTIONS = ["Cinematic", "Realistic", "Funny", "Product ad"] as const;
const WAITING = ["queued", "running", "needs_owner_approval"];

/** Improve prompt: Claude turns the idea into a full prompt. Nothing is made until Generate is pressed. */
export function ImproveDialog(props: { body: Body; onUse: (prompt: string) => void; onClose: () => void }) {
  const [direction, setDirection] = useState<(typeof DIRECTIONS)[number]>("Cinematic");
  const [shots, setShots] = useState(2);
  const [text, setText] = useState<string | null>(null);
  const rates = useQuery({ queryKey: ["rates"], queryFn: async () => (await api.GET("/credits/rates")).data ?? [] });
  const cost = rates.data?.find((r) => r.kind === "write-claude")?.credits_per_unit;

  const start = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/clips/improve", { body: { ...props.body, improved: false, direction, shots } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: () => setText(null),
  });
  const jobId = start.data?.id;
  const result = useQuery({
    queryKey: ["improve", jobId],
    enabled: jobId !== undefined,
    refetchInterval: (q) => (!q.state.data || WAITING.includes(q.state.data.status) ? 2000 : false),
    queryFn: async () => {
      const { data, error } = await api.GET("/clips/improve/{job_id}", { params: { path: { job_id: jobId! } } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
  });
  const r = result.data;
  const working = start.isPending || (jobId !== undefined && (!r || WAITING.includes(r.status)));
  const ready = r?.status === "succeeded" && r.prompt !== null;
  const shown = text ?? r?.prompt ?? "";
  const failed = r?.status === "failed";

  return (
    <Sheet title="Improve prompt" onClose={props.onClose}>
      <p className="text-sm text-muted">Claude writes a full prompt from your idea. Nothing generates until you press Generate.</p>
      <p className="rounded-sm bg-surface-2 p-2 text-sm">{props.body.prompt || "Write an idea in the prompt box first."}</p>
      <fieldset className="space-y-1 text-sm">
        <legend className="font-medium">Direction</legend>
        <div className="flex flex-wrap gap-2">
          {DIRECTIONS.map((d) => (
            <button key={d} type="button" aria-pressed={d === direction} className={chip(d === direction)} onClick={() => setDirection(d)}>
              {d}
            </button>
          ))}
        </div>
      </fieldset>
      <fieldset className="space-y-1 text-sm">
        <legend className="font-medium">Shots</legend>
        <div className="flex gap-2">
          {[1, 2, 3, 4].map((n) => (
            <button key={n} type="button" aria-pressed={n === shots} className={chip(n === shots)} onClick={() => setShots(n)}>
              {n}
            </button>
          ))}
        </div>
      </fieldset>
      <button className={`${btnPrimary} min-h-11 w-full sm:min-h-9`} disabled={working || !props.body.prompt.trim()} onClick={() => start.mutate()}>
        {working ? "Writing…" : ready || failed ? "Improve again" : "Improve"}
        {cost !== undefined && !working ? ` · ${creditsLabel(cost)}` : ""}
      </button>
      {start.isError && <p role="alert" className={errorClass}>{start.error.message}</p>}
      {failed && <p role="alert" className={errorClass}>{r.error || "That did not work."} Credits returned.</p>}
      {ready && (
        <div className="space-y-2">
          <label className="block text-sm">
            Improved prompt
            <textarea className={input} rows={9} value={shown} onChange={(e) => setText(e.target.value)} />
          </label>
          {r.problems.length > 0 && (
            <ul className="list-disc pl-5 text-xs text-warning" aria-label="Checks">
              {r.problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          )}
          <div className="flex gap-2">
            <button className={`${btnPrimary} min-h-11 sm:min-h-9`} disabled={!shown.trim()} onClick={() => props.onUse(shown.trim())}>
              Use this
            </button>
            <button className={`${btnSecondary} min-h-11 sm:min-h-9`} onClick={props.onClose}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </Sheet>
  );
}

const chip = (on: boolean) => `min-h-11 rounded-sm border px-3 sm:min-h-9 ${on ? "border-accent bg-accent-soft text-accent-text" : "border-border-strong bg-surface"}`;
