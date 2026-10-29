import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

const NAMES: Record<string, string> = {
  script: "Script",
  breakdown: "Breakdown",
  storyboard: "Storyboard",
  clip_prompts: "Clip prompts",
  clips: "Clips",
  video: "Final video",
};
const credits = (n: number) => `${Math.round(n * 10) / 10} credits`;

/** Under the budget meter: what finishing this video still costs, stage by stage. Credits only, never dollars. */
export function EstimateNote({
  projectId,
  used,
  budget,
}: {
  projectId: number;
  used: number;
  budget: number;
}) {
  // Asked again whenever the credits used change, so it follows the work.
  const estimate = useQuery({
    queryKey: ["project-estimate", projectId, used],
    queryFn: async () =>
      (
        await api.GET("/projects/{project_id}/estimate", {
          params: { path: { project_id: projectId } },
        })
      ).data ?? null,
  });
  const e = estimate.data;
  if (!e) return null;
  const left = Math.max(0, budget - used);
  const short = e.remaining_credits > left;
  return (
    <details className="relative text-sm">
      <summary className="min-h-11 cursor-pointer py-2 sm:min-h-0 sm:py-0">
        {e.remaining_credits === 0
          ? "Nothing left to spend."
          : `To finish: up to ${credits(e.remaining_credits)}`}{" "}
        · {credits(left)} left in the budget
      </summary>
      {/* From sm up the list floats under the meter, so opening it doesn't push the workspace down. */}
      <div className="mt-1 space-y-1 sm:absolute sm:inset-x-0 sm:z-10 sm:rounded-md sm:border sm:border-border sm:bg-surface sm:p-3 sm:shadow-md">
        {short && (
          <p className="text-warning">
            That is more than is left. The owner has to approve the extra.
          </p>
        )}
        <ul className="space-y-1" aria-label="Credits left per stage">
          {e.stages.map((s) => (
            <li
              key={s.stage}
              className="flex flex-wrap justify-between gap-x-3"
            >
              <span>
                {s.done ? "✓ " : ""}
                {NAMES[s.stage] ?? s.stage}
                {s.note && (
                  <span className="block text-xs text-muted">{s.note}</span>
                )}
              </span>
              <span className="tabular-nums text-muted">
                {s.done
                  ? "done"
                  : s.credits === 0
                    ? "free"
                    : credits(s.credits)}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </details>
  );
}
