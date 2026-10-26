import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ellipsis, RotateCcw, Sparkles, Trash2 } from "lucide-react";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { Elapsed } from "../clip/History";
import { useBrandPieces } from "../clip/BrandPieces";
import { useMe } from "../auth/useMe";
import { Banner, Button, Card, Dialog, Menu, MenuItem, Skeleton, Tabs, useToast, wholeCredits } from "../components";
import { BreakdownView } from "../projects/BreakdownView";
import { refName } from "../projects/names";
import { errorText as errorClass } from "../ui";
import { useCast } from "./useCast";
import { useAllowanceStop, type Script } from "./useScript";

type Breakdown = components["schemas"]["Breakdown"];
const LETTER = ["A", "B", "C"];

/** Step 6 (optional): plan a version's shots before publishing. The editor starts from the saved plan. */
export function BreakdownStep({ script, brandId, readOnly }: { script: Script; brandId: number; readOnly: boolean }) {
  const versions = script.versions.filter((v) => v.text.trim() !== "");
  const [slot, setSlot] = useState(versions[0]?.slot ?? 0);
  const at = versions.find((v) => v.slot === slot) ?? versions[0];
  if (!at) return <p className="text-muted">Write the script first.</p>;
  return (
    <div className="space-y-4">
      <Tabs
        label="Versions"
        value={String(at.slot)}
        onChange={(id) => setSlot(Number(id))}
        tabs={versions.map((v) => ({ id: String(v.slot), label: `${LETTER[v.slot] ?? v.slot + 1}${v.has_breakdown ? " · Planned" : ""}` }))}
      />
      <Plan key={at.slot} script={script} slot={at.slot} brandId={brandId} readOnly={readOnly} />
    </div>
  );
}


function Plan({ script, slot, brandId, readOnly }: { script: Script; slot: number; brandId: number; readOnly: boolean }) {
  const scriptId = script.id;
  const letter = LETTER[slot] ?? String(slot + 1);
  const queryClient = useQueryClient();
  const toast = useToast();
  const path = { script_id: scriptId, slot };
  const { pieces } = useBrandPieces(brandId);
  const cast = useCast(scriptId);
  const [started, setStarted] = useState<string | null>(null); // when this tab's run was pressed
  const [mountedAt] = useState(() => new Date().toISOString()); // when a run seen on arrival is counted from
  const [asking, setAsking] = useState(false);
  const [removing, setRemoving] = useState(false);
  const owner = useMe().data?.role === "owner";
  const preview = useQuery({
    queryKey: ["preview", scriptId, slot],
    queryFn: async () => (await api.GET("/scripts/{script_id}/drafts/{slot}/breakdown", { params: { path } })).data ?? null,
    refetchInterval: (q) => (q.state.data?.running ? 3000 : false),
  });
  const estimate = useQuery({
    queryKey: ["preview-estimate", scriptId, slot],
    queryFn: async () => (await api.GET("/scripts/{script_id}/drafts/{slot}/breakdown/estimate", { params: { path } })).data?.credits,
  });
  const price = estimate.data;
  const stop = useAllowanceStop(script, price);
  const run = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/scripts/{script_id}/drafts/{slot}/breakdown", { params: { path } });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: async () => {
      setStarted(new Date().toISOString());
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      await queryClient.invalidateQueries({ queryKey: ["preview", scriptId, slot] }); // the server now says it is running
    },
  });
  const p = preview.data;
  // Remove the plan (the owner, before publishing): an editor's video will plan its shots when they start. Undo puts the plan held here back.
  const keep = useMutation({
    mutationFn: async ({ problem, undo }: { problem: string; undo?: boolean }) => {
      const { response, error } = undo
        ? await api.DELETE("/scripts/{script_id}/drafts/{slot}/breakdown/keep", { params: { path, query: { problem } } })
        : await api.POST("/scripts/{script_id}/drafts/{slot}/breakdown/keep", { params: { path }, body: { problem } });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["preview", scriptId, slot] }),
  });
  const remove = useMutation({
    mutationFn: async (held: Breakdown) => {
      const { response, error } = await api.DELETE("/scripts/{script_id}/drafts/{slot}/breakdown", { params: { path } });
      if (!response.ok) throw new Error(errorText(error));
      return held;
    },
    onSuccess: async (held) => {
      setRemoving(false);
      setStarted(null); // a removed plan is not a failed run
      await queryClient.invalidateQueries({ queryKey: ["preview", scriptId, slot] });
      await queryClient.invalidateQueries({ queryKey: ["script-lib", scriptId] });
      toast(`Plan removed for version ${letter}.`, async () => {
        await api.PUT("/scripts/{script_id}/drafts/{slot}/breakdown", { params: { path }, body: held });
        await queryClient.invalidateQueries({ queryKey: ["preview", scriptId, slot] });
        await queryClient.invalidateQueries({ queryKey: ["script-lib", scriptId] });
      });
    },
  });
  const running = !!p?.running || run.isPending;
  const failed = started !== null && !running && !p?.breakdown; // pressed, finished, and nothing came of it
  const roles = new Map((cast.data ?? []).map((c) => [`slot:${c.id}`, c.role]));
  const planned = !!p?.breakdown;
  // A run that just finished (the server stops saying "running") brings the new plan and the picker's tick in.
  const wasRunning = p?.running ?? false;
  useEffect(() => {
    if (!wasRunning && started !== null) void queryClient.invalidateQueries({ queryKey: ["script-lib", scriptId] });
  }, [wasRunning, started, queryClient, scriptId]);

  const makeLabel = planned ? "Make it again" : "Make the breakdown";
  const button = (
    <Button
      variant={planned ? "ghost" : "secondary"}
      icon={planned ? RotateCcw : Sparkles}
      price={price}
      busy={run.isPending}
      disabled={running || readOnly || stop !== null}
      reason={stop ?? undefined}
      onClick={() => (planned ? setAsking(true) : run.mutate())}
    >
      {failed ? "Try again" : makeLabel}
    </Button>
  );

  if (preview.isPending)
    return (
      <div role="status" aria-label="Loading" className="space-y-2">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-12" />
        ))}
      </div>
    );
  if (running)
    return (
      <div className="space-y-3" role="status">
        <p className="text-sm text-muted">
          Planning shots… {started && <Elapsed since={started ?? mountedAt} />}
        </p>
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-12" />
        ))}
      </div>
    );
  if (!planned)
    return (
      <div className="space-y-3">
        {failed && (
          <Banner title="The breakdown didn't finish." action={button}>
            Nothing was charged.
          </Banner>
        )}
        {!failed && (
          <Card className="space-y-3">
            <p>Plan the shots now, or let it happen when an editor starts this version.</p>
            <p className="text-sm text-muted">Sees the length, scenes and shots, and lets you edit them.</p>
            {!readOnly && button}
          </Card>
        )}
        {run.error && <p role="alert" className={errorClass}>{run.error.message}</p>}
      </div>
    );

  const plan = p!.breakdown as Breakdown;
  const row = { id: 0, script_version: 0, source: "claude", breakdown: plan, problems: p!.problems, kept: p!.kept, stale: p!.stale } as components["schemas"]["BreakdownOut"];
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted tabular-nums">
        Planned · {p!.seconds} s · {plan.clips.length} clip{plan.clips.length === 1 ? "" : "s"}
        {script.versions.find((v) => v.slot === slot)?.estimate_credits ? ` · about ${wholeCredits(script.versions.find((v) => v.slot === slot)!.estimate_credits)} credits to make` : ""}
      </p>
      {!readOnly && (
        <div className="flex flex-wrap items-center gap-2">
          {!p!.stale && button /* a stale plan has its Make it again in the banner */}
          {owner && (
            <Menu
              title="More for this plan"
              trigger={(t) => (
                <button type="button" {...t} aria-label="More for this plan" className="grid size-control place-items-center rounded-md text-muted hover:bg-surface-2 lg:size-9">
                  <Ellipsis size={20} strokeWidth={1.75} aria-hidden />
                </button>
              )}
            >
              {(close) => (
                <MenuItem
                  danger
                  onClick={() => {
                    close();
                    setRemoving(true);
                  }}
                >
                  <Trash2 size={20} strokeWidth={1.75} aria-hidden />
                  Remove the plan
                </MenuItem>
              )}
            </Menu>
          )}
        </div>
      )}
      {remove.error && <p role="alert" className={errorClass}>{remove.error.message}</p>}
      {run.error && <p role="alert" className={errorClass}>{run.error.message}</p>}
      <BreakdownView
        key={JSON.stringify(plan)}
        row={row}
        projectId={scriptId}
        brandId={brandId}
        scriptVersion={0}
        plannedSeconds={p!.seconds}
        makeButton={() => null}
        failed={false}
        problem={null}
        name={(id) => (id ? refName(id, pieces, roles) : "")}
        line={null}
        preview={{
          keep: (problem, undo) => keep.mutate({ problem, undo }),
          keepBusy: keep.isPending,
          again: readOnly ? null : (
            <Button variant="secondary" icon={RotateCcw} price={price} disabled={running || stop !== null} reason={stop ?? undefined} onClick={() => setAsking(true)}>
              Make it again
            </Button>
          ),
          save: async (bd) => {
            const { data, error } = await api.PUT("/scripts/{script_id}/drafts/{slot}/breakdown", { params: { path }, body: bd });
            if (!data) throw new Error(errorText(error));
            toast(`Plan saved for version ${letter}.`);
            return data;
          },
        }}
      />
      {removing && (
        <Dialog title="Remove this plan?" cancelLabel="Keep it" actionLabel="Remove" danger busy={remove.isPending} onCancel={() => setRemoving(false)} onConfirm={() => remove.mutate(plan)}>
          An editor's video will plan its shots when they start.
        </Dialog>
      )}
      {asking && (
        <Dialog title="Make the breakdown again?" cancelLabel="Keep my plan" actionLabel="Make again" onCancel={() => setAsking(false)} onConfirm={() => { setAsking(false); run.mutate(); }}>
          Your edits to this plan will be lost.
        </Dialog>
      )}
    </div>
  );
}
