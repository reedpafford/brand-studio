import { useMutation, useQueryClient } from "@tanstack/react-query";
import { MapPinOff, MonitorOff, Plus, RotateCcw, Trash2, UserMinus, Wand2 } from "lucide-react";
import type { ReactNode } from "react";
import { api, errorText } from "../api/client";
import { Button } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import type { Breakdown } from "./breakdownEdit";
import { clone } from "./breakdownEdit";

/** A free one-click fix the server offers for one problem. */
type Fix = { problem: string; kind: string; label: string };
const ICON: Record<string, typeof Plus> = { add_line: Plus, restore_line: RotateCcw, remove_shot: Trash2 };

/** One-click fixes for breakdown problems (no model call, no price): next to the problem, or one "Fix N problems" for all of them.
 *  `run` asks the server (all when no problems are named) and says what it did; Undo puts the breakdown that was there back. */
export function useBreakdownFixes(opts: {
  offered: unknown[] | undefined;
  open: string[]; // the blocking problems shown
  was: Breakdown; // the breakdown as it is now, which Undo puts back
  run: (problems: string[]) => Promise<{ fixed: string[] }>;
  put: (bd: Breakdown) => Promise<unknown>;
  refresh: () => Promise<unknown>;
}): { beside: (problem: string) => ReactNode; all: ReactNode } {
  const toast = useToast();
  const queryClient = useQueryClient();
  const offered = ((opts.offered ?? []) as Fix[]).filter((f) => opts.open.includes(f.problem));
  const fix = useMutation({
    mutationFn: (problems: string[]) => opts.run(problems),
    onSuccess: async (done) => {
      const back = clone(opts.was);
      await opts.refresh();
      toast(done.fixed.join(" ") || "Fixed.", async () => {
        await opts.put(back);
        await opts.refresh();
        queryClient.invalidateQueries({ queryKey: ["project-clips"] });
      });
    },
  });
  const beside = (problem: string) => {
    const f = offered.find((o) => o.problem === problem);
    if (!f) return null;
    const Icon = ICON[f.kind] ?? Wand2;
    return (
      <span className="flex flex-wrap items-center gap-2">
        <Button variant="secondary" dense icon={Icon} busy={fix.isPending} aria-label={`${f.label}: ${problem}`} onClick={() => fix.mutate([problem])}>
          {f.label}
        </Button>
        <span className="text-sm text-muted">Free</span>
      </span>
    );
  };
  const all =
    offered.length > 1 || fix.error ? (
      <div className="space-y-1 pt-2">
        {offered.length > 1 && (
          <span className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" icon={Wand2} busy={fix.isPending} onClick={() => fix.mutate(offered.map((o) => o.problem))}>
              Fix {offered.length} problems
            </Button>
            <span className="text-sm text-muted">Free</span>
          </span>
        )}
        {fix.error && <p role="alert" className={errorClass}>{fix.error.message}</p>}
      </div>
    ) : null;
  return { beside, all };
}

export type RefKind = "character" | "place" | "screen";
const REMOVE_ICON = { character: UserMinus, place: MapPinOff, screen: MonitorOff };

/** "Remove Nate from this shot": a name the video doesn't have, taken out of one shot for free. There is no Undo yet: the server can't put back a name the video doesn't have. */
export function useRemoveRef(opts: {
  run: (shotId: string, kind: RefKind, ref: string, name: string) => Promise<{ fixed: string[] }>;
  refresh: () => Promise<unknown>;
}) {
  const toast = useToast();
  const remove = useMutation({
    mutationFn: (a: { shotId: string; kind: RefKind; ref: string; name: string }) => opts.run(a.shotId, a.kind, a.ref, a.name),
    onSuccess: async (done) => {
      await opts.refresh();
      toast(done.fixed.join(" ") || "Removed.", undefined, "success", true); // no Undo, and a long line: it stays as long as one with Undo
    },
  });
  /** `ref` is the id the shot holds (it tells two unknown people apart); `name` is how people call them, or "a character" when it isn't known. */
  const button = (shotId: string, kind: RefKind, ref: string, name: string, disabled?: string) => {
    const Icon = REMOVE_ICON[kind];
    return (
      <div className="space-y-1">
        <span className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" dense icon={Icon} busy={remove.isPending} disabled={!!disabled} reason={disabled} onClick={() => remove.mutate({ shotId, kind, ref, name })}>
            Remove {name} from this shot
          </Button>
          {!disabled && <span className="text-sm text-muted">Free</span>}
        </span>
        {remove.error && remove.variables?.ref === ref && <p role="alert" className={errorClass}>{remove.error.message}</p>}
      </div>
    );
  };
  return { button };
}

type Changed = { shot_id: string; before: string[]; after: string[] };

/** "Put the right cast in each shot": free, no model call. Undo puts each changed shot's earlier cast back. */
export function useFixCast(opts: { projectId: number; preview?: () => Promise<{ changed_shots: Changed[] }>; was: Breakdown; putBack: (b: Breakdown) => Promise<unknown>; refresh: () => Promise<unknown> }) {
  const toast = useToast();
  return useMutation({
    mutationFn: async () => {
      if (opts.preview) return (await opts.preview()).changed_shots;
      const { data, error } = await api.POST("/projects/{project_id}/breakdown/fix-cast", { params: { path: { project_id: opts.projectId } } });
      if (!data) throw new Error(errorText(error));
      return data.changed_shots as Changed[];
    },
    onSuccess: async (changed) => {
      await opts.refresh();
      toast(`Cast fixed in ${changed.length} shot${changed.length === 1 ? "" : "s"}.`, async () => {
        const back = clone(opts.was); // the breakdown as it was before the fix (the view still holds it)
        for (const scene of back.scenes) for (const shot of scene.shots) {
          const was = changed.find((c) => c.shot_id === shot.id);
          if (was) shot.character_ids = was.before;
        }
        await opts.putBack(back);
        await opts.refresh();
      });
    },
  });
}
