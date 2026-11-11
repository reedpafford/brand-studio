import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import { Dialog, Skeleton } from "../components";
import { SaveButton, SettingRow, type SettingsTop } from "./SettingRow";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";

const whole = (s: string) => /^\d+$/.test(s.trim());

/** v5 D_Settings › Limits: the limit Reed sets (each editor's own week), then two
 *  facts: editors' new videos always wait for him, and what the director's own time cost this month (in dollars: owner only). */
export function CreditLimits({ top }: { top: SettingsTop }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const limits = useQuery({ queryKey: ["credit-limits"], queryFn: async () => (await api.GET("/credits/limits")).data ?? null });
  const director = useQuery({ queryKey: ["usage", "summary", "month"], queryFn: async () => (await api.GET("/usage/summary", { params: { query: { period: "month" } } })).data ?? null });
  const allowances = useQuery({ queryKey: ["allowances"], queryFn: async () => (await api.GET("/credits/allowances")).data ?? [] });
  const [edit, setEdit] = useState<string | null>(null);
  const [asking, setAsking] = useState<string | null>(null);
  const saved = limits.data;
  const weekly = edit ?? String(saved?.weekly_quick_clip_credits ?? "");
  const weeklyError = !whole(weekly) ? "Use a whole number of credits." : null;
  const changed = !!saved && Number(weekly) !== saved.weekly_quick_clip_credits;
  const reason = !changed ? "No changes yet" : weeklyError ? "Fix the number above first" : null;

  const put = useMutation({
    mutationFn: async (body: { weekly_quick_clip_credits: number }) => {
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
      { weekly_quick_clip_credits: Number(weekly) },
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

  if (limits.isPending)
    return (
      <>
        {top()}
        <Skeleton className="h-40" />
      </>
    );
  if (!saved) return <>{top()}</>;
  const field = (id: string, label: string, value: string, set: (v: string) => void, error: string | null, help: string, unit: string) => (
    <SettingRow htmlFor={id} label={label} help={help}>
      <span className="flex items-center gap-2">
        <input id={id} inputMode="numeric" aria-invalid={!!error || undefined} value={value} onChange={(e) => set(e.target.value)} className="min-h-control w-[140px] rounded-md border border-border-strong bg-bg px-2.5 tabular-nums lg:min-h-control-dense" />
        <span className="text-xs text-muted">{unit}</span>
      </span>
      {error && <p role="alert" className={`mt-1 ${errorClass}`}>{error}</p>}
    </SettingRow>
  );
  const first = over[0];
  const spent = director.data?.director_spend_usd;
  return (
    <>
      {top(
        <SaveButton reason={reason} busy={put.isPending} onClick={press} />,
      )}
      <section aria-label="Limits" className="max-w-[900px]">
        {field("weekly-limit", "Each editor's own week", weekly, setEdit, weeklyError, "Small presses (another take, a redo) inside this go ahead; past it they wait for you.", "credits a week")}
        <SettingRow label="Freestyle and new videos from editors" help="Every editor's Make it and every change asked waits for your OK. This can't be turned off.">
          <p className="text-xs text-muted sm:pt-1.5">Always asks you</p>
        </SettingRow>
        <SettingRow label="The director's own time" help="Billed in dollars, outside the credit budget. Only you see it.">
          <p className="text-xs tabular-nums text-muted sm:pt-1.5">{spent === undefined ? "…" : `$${spent.toFixed(2)} this month`}</p>
        </SettingRow>
        {put.isError && <p role="alert" className={`pt-3 ${errorClass}`}>{put.error.message}</p>}
      </section>
      {asking && first && (
        <Dialog title="Lower the weekly allowance?" cancelLabel={`Keep ${saved.weekly_quick_clip_credits}`} actionLabel={`Save ${weekly}`} busy={put.isPending} onCancel={() => setAsking(null)} onConfirm={save}>
          {first.name} has used {Math.round(first.quick_clip_credits_used)} credits this week. With {weekly}, {first.name} can't make anything more until Monday.
          {over.length > 1 && ` ${over.length - 1} other${over.length > 2 ? "s are" : " is"} in the same position.`}
        </Dialog>
      )}
    </>
  );
}
