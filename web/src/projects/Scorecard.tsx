import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { Button, TextArea, creditsText } from "../components";
import { useMe } from "../auth/useMe";

type Card = components["schemas"]["CardOut"];

const yesNo = (ok: boolean | null, good: string, bad: string) => (ok === null ? null : ok ? good : bad);

/** On the delivered cut: forecast against actual (credits only), the automatic checks, and the owner's 1-5 score. */
export function Scorecard({ projectId }: { projectId: number }) {
  const queryClient = useQueryClient();
  const { data: me } = useMe();
  const key = ["scorecard", projectId];
  const card = useQuery({
    queryKey: key,
    retry: false,
    queryFn: async () => (await api.GET("/projects/{project_id}/scorecard", { params: { path: { project_id: projectId } } })).data ?? null,
  });
  const [typed, setNote] = useState<string | null>(null); // null: what is saved
  const save = useMutation({
    mutationFn: async (body: { score: number | null; note: string }) => {
      const { data, error } = await api.PUT("/projects/{project_id}/score", { params: { path: { project_id: projectId } }, body });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data: Card) => (setNote(null), queryClient.setQueryData(key, data)),
  });
  const c = card.data;
  if (!c) return null;
  const note = typed ?? c.note ?? "";
  const checks = [yesNo(c.words_exact, "Words said exactly", "Some words differ"), yesNo(c.must_show_ok, "Must-show items right", "A must-show item may be wrong")].filter(Boolean);
  const own = c.director_credits > 0 ? ` (${creditsText(c.director_credits)} the director's own)` : "";
  return (
    <section aria-label="Scorecard" className="space-y-2 border-t border-border pt-3">
      <p className="text-sm text-muted tabular-nums">
        {c.forecast_credits === null ? "No forecast was made. " : `Forecast ${creditsText(c.forecast_credits)} (${c.forecast_basis}). `}
        Spent {creditsText(c.actual_credits)}{own}
        {c.within_forecast !== null && (c.within_forecast ? ", within the forecast." : ", over the forecast.")}
      </p>
      {checks.length > 0 && <p className="text-sm text-muted">{checks.join(" · ")}</p>}
      {me?.role === "owner" && (
        <div className="space-y-2">
          <div role="radiogroup" aria-label="Your score" className="flex gap-2">
            {[1, 2, 3, 4, 5].map((n) => (
              <button key={n} type="button" role="radio" aria-checked={c.score === n} aria-label={`${n} of 5`} disabled={save.isPending} onClick={() => save.mutate({ score: c.score === n ? null : n, note })} className={`min-h-control min-w-control rounded-md border font-medium lg:min-h-control-dense lg:min-w-control-dense ${c.score === n ? "border-accent-border bg-accent text-on-accent" : "border-border-button text-text hover:bg-surface-2"}`}>
                {n}
              </button>
            ))}
          </div>
          {c.score !== null && (
            <>
              <TextArea label="Note (optional)" rows={2} value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)} />
              <Button variant="secondary" busy={save.isPending} disabled={note === (c.note ?? "")} onClick={() => save.mutate({ score: c.score, note })}>
                Save note
              </Button>
            </>
          )}
          {save.isError && <p role="alert" className="text-sm text-danger">{save.error.message}</p>}
        </div>
      )}
    </section>
  );
}
