import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import { Button, Dialog, Skeleton } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { useSummary } from "../usage/useUsage";
import { money } from "../usage/parts";

type Limits = { weekly_quick_clip_credits: number; per_video_max_credits: number };

const whole = (s: string) => /^\d+$/.test(s.trim());

/** Reed's two limits: each editor's weekly free allowance, and the most one video can cost. */
export function CreditLimits() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const limits = useQuery({ queryKey: ["credit-limits"], queryFn: async () => (await api.GET("/credits/limits")).data ?? null });
  const month = useSummary("month"); // the director's own time this month (#1208)
  const allowances = useQuery({ queryKey: ["allowances"], queryFn: async () => (await api.GET("/credits/allowances")).data ?? [] });
  const [edit, setEdit] = useState<{ weekly: string; cap: string } | null>(null);
  const [asking, setAsking] = useState<string | null>(null);
  const saved = limits.data;
  const weekly = edit?.weekly ?? String(saved?.weekly_quick_clip_credits ?? "");
  const cap = edit?.cap ?? String(saved?.per_video_max_credits ?? "");
  const weeklyError = !whole(weekly) ? "Use a whole number of credits." : null;
  const capError = !whole(cap) ? "Use a whole number of credits." : Number(cap) < 1 ? "The cap needs to be at least 1 credit." : null;
  const changed = !!saved && (Number(weekly) !== saved.weekly_quick_clip_credits || Number(cap) !== saved.per_video_max_credits);
  const reason = !changed ? "No changes yet" : weeklyError || capError ? "Fix the number above first" : null;

  const put = useMutation({
    mutationFn: async (body: Limits) => {
      const { data, error } = await api.PUT("/credits/limits", { body });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: async (data) => {
      queryClient.setQueryData(["credit-limits"], data);
      await queryClient.invalidateQueries({ queryKey: ["allowances"] });
    },
  });
  const save = () => {
    if (!saved) return;
    const before = { ...saved };
    put.mutate(
      { weekly_quick_clip_credits: Number(weekly), per_video_max_credits: Number(cap) },
      {
        onSuccess: () => {
          setEdit(null);
          setAsking(null);
          toast("Limits saved.", () => put.mutate(before));
        },
      },
    );
  };
  // An editor who has already used more than the new allowance can't make anything more until Monday: say so first.
  const over = (allowances.data ?? []).filter((a) => a.quick_clip_credits_used > Number(weekly));
  const press = () => (over.length > 0 && Number(weekly) < (saved?.weekly_quick_clip_credits ?? 0) ? setAsking(over[0].name) : save());

  if (limits.isPending) return <Skeleton className="h-40" />;
  if (!saved) return null;
  // v5 D_Settings: each limit is a row, its name and what it does on the left, the number on the right.
  const row = "grid gap-2 border-b border-border py-4 sm:grid-cols-[280px_minmax(0,1fr)] sm:gap-6";
  const field = (id: string, label: string, value: string, set: (v: string) => void, error: string | null, help: string, unit = "credits") => (
    <div className={row}>
      <div className="space-y-1">
        <label htmlFor={id} className="font-medium">{label}</label>
        <p id={`${id}-help`} className="text-sm text-muted">{help}</p>
      </div>
      <div className="space-y-1">
        <span className="flex items-center gap-3">
          <input id={id} inputMode="numeric" aria-invalid={!!error || undefined} aria-describedby={`${id}-help`} value={value} onChange={(e) => set(e.target.value)} className="min-h-control w-[140px] rounded-md border border-border-strong bg-surface px-3 text-right tabular-nums lg:min-h-control-dense" />
          <span className="text-sm text-muted">{unit}</span>
        </span>
        {error && <p role="alert" className={errorClass}>{error}</p>}
      </div>
    </div>
  );
  const first = over[0];
  return (
    <section aria-label="Credit limits" className="space-y-3">
      <h2 className="sr-only">Credit limits</h2>
      <div>
        {field("video-cap", "Most one video can cost", cap, (v) => setEdit({ weekly, cap: v }), capError, "For everyone, the owner too. A video's budget is twice its estimate, up to this.")}
        {field("weekly-limit", "Editors' weekly allowance", weekly, (v) => setEdit({ weekly: v, cap }), weeklyError, "Each editor's Quick clips only; scripts and videos run on their budgets. Resets on Monday.", "credits a week")}
        <div className={row}>
          <div className="space-y-1">
            <p className="font-medium">Editors' Freestyle sends</p>
            <p className="text-sm text-muted">Every Freestyle send from an editor waits for your OK in Needs you. This can't be turned off.</p>
          </div>
          <p className="text-sm text-muted sm:pt-1.5">Always asks you</p>
        </div>
        {month.data && (
          <div className={row}>
            <div className="space-y-1">
              <p className="font-medium">The director's own time</p>
              <p className="text-sm text-muted">Billed in dollars, outside the credit budgets. Only you see it.</p>
            </div>
            <p className="text-sm tabular-nums text-muted sm:pt-1.5">{money(month.data.director_spend_usd ?? 0)} this month</p>
          </div>
        )}
      </div>
      {put.isError && <p role="alert" className={errorClass}>{put.error.message}</p>}
      <div className="sm:flex sm:justify-end">
        <Button variant="secondary" busy={put.isPending} disabled={reason !== null} reason={reason} onClick={press} className="w-full sm:w-auto">
          Save limits
        </Button>
      </div>
      {asking && first && (
        <Dialog title="Lower the weekly allowance?" cancelLabel={`Keep ${saved.weekly_quick_clip_credits}`} actionLabel={`Save ${weekly}`} busy={put.isPending} onCancel={() => setAsking(null)} onConfirm={save}>
          {first.name} has used {Math.round(first.quick_clip_credits_used)} credits this week. With {weekly}, {first.name} can't make anything more until Monday.
          {over.length > 1 && ` ${over.length - 1} other${over.length > 2 ? "s are" : " is"} in the same position.`}
        </Dialog>
      )}
    </section>
  );
}
