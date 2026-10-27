import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, RotateCcw, Trash2, Wand2 } from "lucide-react";
import type { ReactNode } from "react";
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
