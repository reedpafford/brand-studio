import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { api, errorText } from "../api/client";
import { Button, useToast } from "../components";

type Skipped = { id: number | null; reason: string; label?: string };
export type ApproveAllResult = { approved: number[]; skipped: Skipped[] };

/** Scrolls to a card and outlines it for a moment. */
function show(label: string) {
  const card = document.querySelector<HTMLElement>(`[aria-label="${label}"]`);
  card?.scrollIntoView?.({ block: "center", behavior: "smooth" });
  card?.classList.add("outline", "outline-2", "outline-accent");
  setTimeout(() => card?.classList.remove("outline", "outline-2", "outline-accent"), 1500);
}

/** Approve all, for any list of things that are approved one by one: approves everything that can be, lists what couldn't with why, and Undo takes back exactly those.
 *  `ready` is how many it would approve now, `waiting` how many are not approved yet. `name` is how a skipped one is called (the card's own label). */
export function useApproveAllWith(opts: {
  noun: string;
  press: () => Promise<ApproveAllResult>;
  undo: (ids: number[]) => Promise<{ response: { ok: boolean }; error?: unknown } | undefined>;
  refresh: () => Promise<unknown>;
  name: (skipped: Skipped) => string;
  target?: (skipped: Skipped) => string; // the card to scroll to, when it is called something else
  ready: number;
  waiting: number;
}): { button: ReactNode; line: ReactNode } {
  const { noun } = opts;
  const toast = useToast();
  const [result, setResult] = useState<ApproveAllResult | null>(null);
  const run = useMutation({
    mutationFn: opts.press,
    onSuccess: async (r) => {
      setResult(r);
      await opts.refresh();
      if (r.approved.length === 0) return;
      toast(`Approved ${r.approved.length} ${noun}${r.approved.length === 1 ? "" : "s"}.`, async () => {
        // A failed Undo says why, in words.
        const back = await opts.undo(r.approved).catch((e: unknown) => ({ error: e, response: { ok: false } }));
        if (back && !back.response.ok) return toast(errorText(back.error) || "Couldn't undo that. Try again.", undefined, "error");
        setResult(null);
        await opts.refresh();
      });
    },
  });

  // The line stays until the next action on the page: a click or a key that presses a control (Enter, Space), anywhere but on the line itself. Tab and other navigation never clear it, so a keyboard user can reach the links.
  useEffect(() => {
    if (!result) return;
    const away = (e: Event) => {
      if (!(e.target as Element | null)?.closest?.("[data-approve-line]")) setResult(null);
    };
    document.addEventListener("click", away);
    return () => document.removeEventListener("click", away);
  }, [result]);

  const button =
    opts.ready > 0 ? (
      <Button variant="secondary" icon={Check} busy={run.isPending} className="w-full sm:w-auto" onClick={() => run.mutate()}>
        {opts.ready === opts.waiting ? "Approve all" : `Approve ${opts.ready}`}
      </Button>
    ) : null;

  const left = result?.skipped ?? [];
  const line = run.isError ? (
    <p role="alert" className="text-sm text-danger">{run.error.message}</p>
  ) : result && result.approved.length + left.length > 0 ? (
    <p className="text-sm text-muted" role="status" data-approve-line>
      Approved {result.approved.length}.
      {left.length > 0 && ` ${left.length} not approved: `}
      {left.map((s, i) => (
        <span key={`${s.id}-${s.label}`}>
          {i > 0 && " · "}
          <button type="button" className="inline-flex min-h-11 items-center underline sm:min-h-0" onClick={() => show(opts.target?.(s) ?? opts.name(s))}>
            {opts.name(s)}
          </button>
          : {s.reason}
        </span>
      ))}
    </p>
  ) : null;
  return { button, line };
}

type Row = { id: number; clip_id: string };

/** Approve all on Storyboard (frames) and Clips (clips). */
export function useApproveAll(opts: { projectId: number; kind: "storyboard" | "clips"; noun: "frame" | "clip"; rows: Row[]; ready: number; waiting: number }) {
  const { projectId, kind, noun, rows } = opts;
  const queryClient = useQueryClient();
  const path = { project_id: projectId };
  const card = noun === "frame" ? "Frame" : "Clip"; // the card's own label
  return useApproveAllWith({
    noun,
    ready: opts.ready,
    waiting: opts.waiting,
    press: async () => {
      const { data, error } = kind === "storyboard" ? await api.POST("/projects/{project_id}/storyboard/approve-all", { params: { path } }) : await api.POST("/projects/{project_id}/clips/approve-all", { params: { path } });
      if (!data) throw new Error(errorText(error));
      return data as ApproveAllResult;
    },
    undo: (ids) => (kind === "storyboard" ? api.POST("/projects/{project_id}/storyboard/approve-all/undo", { params: { path }, body: { ids } }) : api.POST("/projects/{project_id}/clips/approve-all/undo", { params: { path }, body: { ids } })),
    refresh: () => Promise.all([kind === "storyboard" ? "storyboard" : "project-clips", "project-video"].map((k) => queryClient.invalidateQueries({ queryKey: [k, projectId] }))),
    name: (s) => `${card} ${rows.find((r) => r.id === s.id)?.clip_id}`,
  });
}
