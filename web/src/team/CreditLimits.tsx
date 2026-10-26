import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import { Button, Card, Dialog, Skeleton } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { money } from "../usage/parts";

/** 1 credit = $0.1028 (ops/DECISIONS). Only Reed ever sees these dollars. */
const CREDIT_USD = 0.1028;
type Limits = { weekly_quick_clip_credits: number; per_video_max_credits: number };

const whole = (s: string) => /^\d+$/.test(s.trim());
const dollars = (s: string) => (whole(s) ? `≈ ${money(Number(s) * CREDIT_USD)}` : "");

/** Reed's two limits: each editor's weekly free allowance, and the most one video can cost. */
export function CreditLimits() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const limits = useQuery({ queryKey: ["credit-limits"], queryFn: async () => (await api.GET("/credits/limits")).data ?? null });
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
  const field = (id: string, label: string, value: string, set: (v: string) => void, error: string | null, help: string, usd: string) => (
    <div className="space-y-1">
      <div className="flex flex-wrap items-center gap-3">
        <label htmlFor={id} className="min-w-0 flex-1 font-medium">{label}</label>
        <input id={id} inputMode="numeric" aria-invalid={!!error || undefined} aria-describedby={`${id}-help`} value={value} onChange={(e) => set(e.target.value)} className="min-h-control w-[120px] rounded-md border border-border-strong bg-surface px-3 text-right tabular-nums" />
        <span className="w-24 text-sm text-muted">credits</span>
      </div>
      <p id={`${id}-help`} className="text-sm text-muted">{usd && <span className="tabular-nums">{usd}. </span>}{help}</p>
      {error && <p role="alert" className={errorClass}>{error}</p>}
    </div>
  );
  const first = over[0];
  return (
    <section aria-label="Credit limits" className="space-y-3">
      <h2 className="type-section">Credit limits</h2>
      <Card className="space-y-4">
        {field("weekly-limit", "Editors' weekly allowance", weekly, (v) => setEdit({ weekly: v, cap }), weeklyError, "Free generation for each editor's own scripts and quick clips. Resets on Monday.", dollars(weekly) && `${dollars(weekly)} a week`)}
        {field("video-cap", "Most one video can cost", cap, (v) => setEdit({ weekly, cap: v }), capError, "For everyone, Reed too. A video's budget is twice its estimate, up to this.", dollars(cap))}
        {put.isError && <p role="alert" className={errorClass}>{put.error.message}</p>}
        <div className="flex justify-end">
          <Button variant="secondary" busy={put.isPending} disabled={reason !== null} reason={reason} onClick={press} className="w-full sm:w-auto">
            Save limits
          </Button>
        </div>
      </Card>
      {asking && first && (
        <Dialog title="Lower the weekly allowance?" cancelLabel={`Keep ${saved.weekly_quick_clip_credits}`} actionLabel={`Save ${weekly}`} busy={put.isPending} onCancel={() => setAsking(null)} onConfirm={save}>
          {first.name} has used {Math.round(first.quick_clip_credits_used)} credits this week. With {weekly}, {first.name} can't make anything more until Monday.
          {over.length > 1 && ` ${over.length - 1} other${over.length > 2 ? "s are" : " is"} in the same position.`}
        </Dialog>
      )}
    </section>
  );
}
