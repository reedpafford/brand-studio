import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronLeft, Ellipsis, MapPin, Pencil, RotateCcw, Sparkles, Trash2 } from "lucide-react";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { Elapsed } from "../clip/History";
import { useBrandPieces } from "../clip/BrandPieces";
import { useMe } from "../auth/useMe";
import { Banner, Button, Dialog, Dot, Menu, MenuItem, Skeleton, useToast, wholeCredits } from "../components";
import { BreakdownView } from "../projects/BreakdownView";
import { Scenes, call, usePlan } from "../projects/PlanStep";
import { plainWords, refName } from "../projects/names";
import { useBreakdownFixes } from "../projects/BreakdownFixes";
import { errorText as errorClass } from "../ui";
import { useCast } from "./useCast";
import type { Script } from "./useScript";
import { ClipTable, sceneGroups } from "./BreakdownTable";
import { PickLabel, pickClass } from "./ScriptFrame";
import { refreshJobs } from "../jobs/refresh";

type Breakdown = components["schemas"]["Breakdown"];
const LETTER = ["A", "B", "C"];

/** The version a Breakdown shows: ?v=1 is version B. Shared with the page's Version picker in the settings row. */
export const breakdownSlot = (script: Script, v: string | null) => {
  const versions = script.versions.filter((x) => x.text.trim() !== "");
  return (versions.find((x) => String(x.slot) === v) ?? versions[0])?.slot ?? 0;
};

/** v5's "Version A ▾" in the settings row (C_Breakdown). */
export function VersionPick({ script, value, onChange }: { script: Script; value: number; onChange: (slot: number) => void }) {
  const versions = script.versions.filter((x) => x.text.trim() !== "");
  const letter = (slot: number) => LETTER[slot] ?? String(slot + 1);
  // v5 C_Breakdown: the app's picker chip, "Version C ▾", like the other pickers in the row (44 px on a phone).
  return (
    <Menu
      title="Version"
      trigger={(t) => (
        <Button variant="ghost" dense trailing={ChevronDown} className={`min-w-11 ${pickClass}`} aria-label={`Version: ${letter(value)}`} {...t}>
          <PickLabel label="Version">{letter(value)}</PickLabel>
        </Button>
      )}
    >
      {(close) => (
        <>
          {versions.map((v) => (
            <MenuItem key={v.slot} onClick={() => { close(); onChange(v.slot); }}>
              {`Version ${letter(v.slot)}${v.has_breakdown ? " · planned" : ""}${v.slot === value ? " ✓" : ""}`}
            </MenuItem>
          ))}
        </>
      )}
    </Menu>
  );
}

/** Step 4 (optional, v5 C_Breakdown): a version's shots as a clip table grouped by scene, with Plan again and Approve the
 *  plan. The scene plan and the shot editor are still a press away (the ⋯ menu, or a row), so nothing is lost. */
export function BreakdownStep({ script, brandId, readOnly, slot }: { script: Script; brandId: number; readOnly: boolean; slot: number }) {
  const at = script.versions.find((v) => v.slot === slot && v.text.trim() !== "");
  if (!at) return <p className="text-muted">Write the script first.</p>;
  return <Plan key={at.slot} script={script} slot={at.slot} brandId={brandId} readOnly={readOnly} />;
}

function Plan({ script, slot, brandId, readOnly }: { script: Script; slot: number; brandId: number; readOnly: boolean }) {
  // The table, or one of the editors it opens: the shots (a row, or Edit the shots) or the scene plan (Edit the scenes).
  const [mode, setMode] = useState<"table" | "shots" | "scenes">("table");
  const home = { base: `/scripts/${script.id}/drafts/${slot}/plan`, key: ["draft-plan", script.id, slot], refresh: [["script-lib", script.id]], script: true };
  const scenePlan = usePlan(home.base, home.key);
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
  const run = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/scripts/{script_id}/drafts/{slot}/breakdown", { params: { path } });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: async () => {
      setStarted(new Date().toISOString());
      refreshJobs(queryClient);
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
  const older = !!script.versions.find((v) => v.slot === slot)?.preview_older_plan; // S6: made before the owner's plan
  // A run that just finished (the server stops saying "running") brings the new plan and the picker's tick in.
  const wasRunning = p?.running ?? false;
  useEffect(() => {
    if (!wasRunning && started !== null) void queryClient.invalidateQueries({ queryKey: ["script-lib", scriptId] });
  }, [wasRunning, started, queryClient, scriptId]);



  const fixes = useBreakdownFixes({
    offered: (p as { fixes?: unknown[] } | null | undefined)?.fixes,
    open: (p?.problems ?? []).filter((x) => !(p?.kept ?? []).includes(x)),
    was: (p?.breakdown ?? { hook: "", scenes: [], clips: [] }) as Breakdown,
    run: async (problems) => {
      const { data, error } = await api.POST("/scripts/{script_id}/drafts/{slot}/breakdown/fix", { params: { path }, body: { problems } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    put: async (bd) => api.PUT("/scripts/{script_id}/drafts/{slot}/breakdown", { params: { path }, body: bd }),
    refresh: () => Promise.all([queryClient.invalidateQueries({ queryKey: ["preview", scriptId, slot] }), queryClient.invalidateQueries({ queryKey: ["script-lib", scriptId] })]),
  });
  const approvePlan = useMutation({
    mutationFn: () => call("POST", `${home.base}/approve`),
    onSuccess: async () => {
      refreshJobs(queryClient);
      await Promise.all([queryClient.invalidateQueries({ queryKey: home.key }), queryClient.invalidateQueries({ queryKey: ["preview", scriptId, slot] }), queryClient.invalidateQueries({ queryKey: ["script-lib", scriptId] })]);
      toast(`Plan approved for version ${letter}.`);
    },
  });
  const back = (
    <Button variant="ghost" icon={ChevronLeft} onClick={() => setMode("table")}>
      Back to the breakdown
    </Button>
  );
  if (mode === "scenes")
    return (
      <div className="space-y-4">
        {back}
        <Scenes home={home} onApproved={() => setMode("table")} />
      </div>
    );

  if (preview.isPending)
    return (
      <div role="status" aria-label="Loading" className="space-y-2">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-12" />
        ))}
      </div>
    );
  const scenes = scenePlan.data;
  const sceneReady = !!scenes && scenes.scenes.length > 0 && scenes.status === "ready";
  const sceneApproved = scenes?.status === "approved";
  const v = script.versions.find((x) => x.slot === slot);
  const title = <h2 className="type-card">Breakdown · version {letter}</h2>;
  const menu = !readOnly && (
    <Menu
      title="More for this plan"
      align="right"
      trigger={(t) => (
        <button type="button" {...t} aria-label="More for this plan" className="grid size-control place-items-center rounded-md text-muted hover:bg-surface-2 lg:size-control-dense">
          <Ellipsis size={20} strokeWidth={1.75} aria-hidden />
        </button>
      )}
    >
      {(close) => (
        <>
          {planned && (
            <MenuItem onClick={() => { close(); setMode("shots"); }}>
              <Pencil size={20} strokeWidth={1.75} aria-hidden /> Edit the shots
            </MenuItem>
          )}
          <MenuItem onClick={() => { close(); setMode("scenes"); }}>
            <MapPin size={20} strokeWidth={1.75} aria-hidden /> {scenes?.scenes.length ? "Edit the scenes" : "Plan the scenes first"}
          </MenuItem>
          {planned && owner && (
            <MenuItem danger onClick={() => { close(); setRemoving(true); }}>
              <Trash2 size={20} strokeWidth={1.75} aria-hidden /> Remove the plan
            </MenuItem>
          )}
        </>
      )}
    </Menu>
  );
  const approveButton = !readOnly && sceneReady && (
    <Button busy={approvePlan.isPending} disabled={running} onClick={() => approvePlan.mutate()}>
      Approve the plan
    </Button>
  );
  const errors = [run.error, remove.error, approvePlan.error].filter(Boolean) as Error[];

  if (running)
    return (
      <div className="space-y-3" role="status">
        {title}
        <p className="text-xs text-muted">
          Planning… {started && <Elapsed since={started ?? mountedAt} />}
        </p>
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-12" />
        ))}
      </div>
    );
  if (!planned)
    return (
      <section aria-label="Breakdown" className="mx-auto flex max-w-[1000px] flex-col gap-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            {title}
            <p className="text-xs text-muted">{readOnly ? "Not planned: each video plans its own shots." : "Not planned yet. Plan the shots now, or let each video plan its own when it starts."}</p>
          </div>
          {!readOnly && (
            <div className="flex items-center gap-2">
              <Button variant="secondary" dense icon={failed ? RotateCcw : Sparkles} charge="estimate" price={price} busy={run.isPending} onClick={() => run.mutate()}>
                {failed ? "Try again" : "Plan the shots"}
              </Button>
              {menu}
              {approveButton}
            </div>
          )}
        </div>
        {failed && <Banner title="The breakdown didn't finish.">Nothing was charged.</Banner>}
        {sceneReady && <p className="text-sm text-muted">The scene plan is ready. Approve it and the shots are planned from it.</p>}
        {errors.map((e) => <p key={e.message} role="alert" className={errorClass}>{e.message}</p>)}
      </section>
    );

  const plan = p!.breakdown as Breakdown;
  const row = { id: 0, script_version: 0, source: "claude", breakdown: plan, problems: p!.problems, kept: p!.kept, stale: p!.stale } as components["schemas"]["BreakdownOut"];
  if (mode === "shots")
    return (
      <div className="space-y-4">
        {back}
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
            fix: async (problems) => {
              const { data, error } = await api.POST("/scripts/{script_id}/drafts/{slot}/breakdown/fix", { params: { path }, body: { problems } });
              if (!data) throw new Error(errorText(error));
              return data;
            },
            fixCast: async () => {
              const { data, error } = await api.POST("/scripts/{script_id}/drafts/{slot}/breakdown/fix-cast", { params: { path } });
              if (!data) throw new Error(errorText(error));
              return data as unknown as { changed_shots: { shot_id: string; before: string[]; after: string[] }[] };
            },
            again: readOnly ? null : (
              <Button variant="secondary" icon={RotateCcw} charge="estimate" price={price} disabled={running} onClick={() => setAsking(true)}>
                Plan again
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
        {asking && (
          <Dialog title="Plan again?" cancelLabel="Keep my plan" actionLabel="Plan again" onCancel={() => setAsking(false)} onConfirm={() => { setAsking(false); setMode("table"); run.mutate(); }}>
            Your edits to this plan will be lost.
          </Dialog>
        )}
      </div>
    );

  const groups = sceneGroups(plan);
  const who = (ids: string[]) => [...new Set(ids.map((id) => (id.startsWith("slot:") ? roles.get(id) || "A role" : refName(id, pieces, roles))))].join(", ") || "—";
  // A problem that names a shot ("shot 2.1") sits under that shot's clip, with a warning dot on the row (C_Breakdown).
  const open = p!.problems.filter((x) => !p!.kept.includes(x));
  const clipOf = (problem: string) => {
    const shot = /\bshot (\d+(?:\.\d+)+)/i.exec(problem)?.[1];
    return shot ? plan.clips.find((c) => c.shot_ids.includes(shot))?.id : undefined;
  };
  const loose = open.filter((x) => !clipOf(x));
  const problemBox = (problem: string) => (
    <div key={problem} role="status" className="my-2 flex flex-wrap items-center gap-3 rounded-lg border border-warning/40 bg-warning-soft px-3.5 py-2.5">
      <span aria-hidden className="size-2 shrink-0 rounded-full bg-warning" />
      <span className="min-w-0 flex-1 basis-[calc(100%-1.25rem)] sm:basis-0">{plainWords(problem, (id) => (id.startsWith("slot:") ? roles.get(id) || "A role" : refName(id, pieces, roles)))}</span>
      {!readOnly && (
        // On a phone the presses sit under the words, side by side, so the words keep the full width (QA-12 on #1238).
        <span className="flex w-full flex-wrap gap-2 pl-5 sm:w-auto sm:pl-0">
          <Button variant="secondary" dense busy={keep.isPending} onClick={() => keep.mutate({ problem })}>
            Keep as is
          </Button>
          {fixes.beside(problem) ?? (
            <Button variant="secondary" dense onClick={() => setMode("shots")}>
              Open the shots
            </Button>
          )}
        </span>
      )}
    </div>
  );
  const credits = v?.estimate_credits ? ` · about ${wholeCredits(v.estimate_credits)} credits to make (planned)` : "";
  const by = v?.planned_by?.name ? ` · planned by ${v.planned_by.name}` : "";
  return (
    <section aria-label="Breakdown" className="mx-auto flex max-w-[1000px] flex-col gap-3.5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          {title}
          <p className="text-xs tabular-nums text-muted">
            Planned · {groups.length} scene{groups.length === 1 ? "" : "s"} · {plan.clips.length} clip{plan.clips.length === 1 ? "" : "s"} · {p!.seconds} s{credits}
            {by}
          </p>
        </div>
        {!readOnly && (
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" dense charge="estimate" price={price} disabled={running} onClick={() => setAsking(true)}>
              Plan again
            </Button>
            {menu}
            {approveButton}
            {sceneApproved && <Dot tone="success">Plan approved</Dot>}
          </div>
        )}
      </div>
      {older && !readOnly && (
        <Banner tone="warning" title="Made for an older plan." action={<Button variant="secondary" icon={RotateCcw} charge="estimate" price={price} busy={run.isPending} disabled={running} onClick={() => run.mutate()}>Plan again</Button>}>
          The scene plan changed after these shots were made, so a new video makes its own shots from the plan.
        </Banner>
      )}
      {p!.stale && !readOnly && (
        <Banner tone="warning" title="Made for an older script." action={<Button variant="secondary" icon={RotateCcw} charge="estimate" price={price} busy={run.isPending} disabled={running} onClick={() => run.mutate()}>Plan again</Button>}>
          The words changed after these shots were planned.
        </Banner>
      )}
      {loose.map(problemBox)}
      {fixes.all}
      {errors.map((e) => <p key={e.message} role="alert" className={errorClass}>{e.message}</p>)}
      <ClipTable plan={plan} who={who} readOnly={readOnly} onOpen={() => setMode("shots")} flagged={(id) => open.some((x) => clipOf(x) === id)} under={(id) => open.filter((x) => clipOf(x) === id).map(problemBox)} />
      {removing && (
        <Dialog title="Remove this plan?" cancelLabel="Keep it" actionLabel="Remove" danger busy={remove.isPending} onCancel={() => setRemoving(false)} onConfirm={() => remove.mutate(plan)}>
          Each video will plan its own shots when it starts.
        </Dialog>
      )}
      {asking && (
        <Dialog title="Plan again?" cancelLabel="Keep my plan" actionLabel="Plan again" onCancel={() => setAsking(false)} onConfirm={() => { setAsking(false); run.mutate(); }}>
          Your edits to this plan will be lost.
        </Dialog>
      )}
    </section>
  );
}
