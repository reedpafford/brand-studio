import { useState } from "react";
import { CircleAlert, CircleCheck } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { Button, TextArea } from "../components";
import { useMe } from "../auth/useMe";
import { spentAsHeader, spent as money } from "../videos/money";
import { useHead } from "../videos/VideoHead";

type Card = components["schemas"]["CardOut"];

const yesNo = (ok: boolean | null, good: string, bad: string) => (ok === null ? null : ok ? good : bad);

/** On the delivered cut: forecast against actual (in the viewer's money: dollars to the owner, credits to an editor,
 *  rule 4), the automatic checks, and the owner's 1-5 score. */
export function Scorecard({ projectId }: { projectId: number }) {
  const queryClient = useQueryClient();
  const { data: me } = useMe();
  const head = useHead(projectId).data ?? undefined;
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
  const checks = [[c.words_exact, yesNo(c.words_exact, "Words said exactly", "Some words differ")], [c.must_show_ok, yesNo(c.must_show_ok, "Must-show items right", "A must-show item may be wrong")]].filter(([, w]) => w) as [boolean, string][];
  // The owner's uncapped site (Reed, 6 Nov): Spent is the providers' own, so no flat-credit figure beside it or set against it.
  const real = !!head?.actual;
  const own = c.director_credits > 0 && !real ? ` (${money(head, c.director_credits)} the director's own)` : "";
  return (
    <section aria-label="Scorecard" className="flex flex-col gap-5">
      {/* What it cost and what the checks found, each under its own label; then the owner's own score, said what it's for. */}
      <dl className="grid grid-cols-[96px_1fr] gap-x-3 gap-y-2 text-sm">
        <dt className="text-muted">Cost</dt>
        <dd className="tabular-nums">
        {c.forecast_credits === null ? "No forecast was made. " : `Forecast ${money(head, c.forecast_credits)} (${c.forecast_basis}). `}
        Spent {spentAsHeader(head, c.actual_credits)}{own}
        {real ? " (the providers' own charges)." : c.within_forecast !== null && (c.within_forecast ? ", within the forecast." : ", over the forecast.")}
        </dd>
        {checks.length > 0 && (
          <>
            <dt className="text-muted">Checks</dt>
            <dd className="flex flex-wrap gap-x-4 gap-y-1">
              {checks.map(([ok, words]) => (
                <span key={words} className="inline-flex items-center gap-1.5">
                  {ok ? <CircleCheck size={14} strokeWidth={1.75} aria-hidden className="text-success" /> : <CircleAlert size={14} strokeWidth={1.75} aria-hidden className="text-warning" />}
                  {words}
                </span>
              ))}
            </dd>
          </>
        )}
      </dl>
      {me?.role === "owner" && (
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-0.5">
            <h3 className="text-sm font-semibold">Your score for this cut</h3>
            <p className="text-xs text-muted">1 is poor, 5 is great. Usage shows your average score for each format and style.</p>
          </div>
          <div role="radiogroup" aria-label="Your score" className="flex gap-1.5">
            {[1, 2, 3, 4, 5].map((n) => (
              <button key={n} type="button" role="radio" aria-checked={c.score === n} aria-label={`${n} of 5`} disabled={save.isPending} onClick={() => save.mutate({ score: c.score === n ? null : n, note })} className={`min-h-control min-w-control rounded-md border text-sm font-medium tabular-nums transition-[background-color,border-color,color,transform] duration-(--dur-fast) ease-out active:scale-95 lg:min-h-control-dense lg:min-w-control-dense ${c.score === n ? "border-ink bg-ink text-white" : "border-border-button text-text hover:border-border-strong/50 hover:bg-surface-2"}`}>
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
