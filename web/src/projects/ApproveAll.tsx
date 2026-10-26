import { useState, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { api, errorText } from "../api/client";
import { Button, useToast } from "../components";

type Row = { id: number; clip_id: string };
type Result = { approved: number[]; skipped: { id: number; reason: string }[] };

/** "Clip c3" + the server's reason: "has no still yet", "was made for an older breakdown", "has a problem to fix". */
const because = (reason: string) => (/^(has|was|is) /.test(reason) ? reason : /^no /.test(reason) ? `has ${reason}` : `was ${reason}`);

/** Scrolls to a card and outlines it for a moment. */
function show(label: string) {
  const card = document.querySelector<HTMLElement>(`[aria-label="${label}"]`);
  card?.scrollIntoView?.({ block: "center", behavior: "smooth" });
  card?.classList.add("outline", "outline-2", "outline-accent");
  setTimeout(() => card?.classList.remove("outline", "outline-2", "outline-accent"), 1500);
}

/** Approve all (Storyboard and Clips): approves everything that can be, lists what couldn't with why, and Undo takes back exactly those.
 *  `ready` is how many it would approve now; `waiting` how many are not approved yet. */
export function useApproveAll(opts: { projectId: number; kind: "storyboard" | "clips"; noun: "frame" | "clip"; rows: Row[]; ready: number; waiting: number }): { button: ReactNode; line: ReactNode } {
  const { projectId, kind, noun, rows } = opts;
  const toast = useToast();
  const queryClient = useQueryClient();
  const [result, setResult] = useState<Result | null>(null);
  const path = { project_id: projectId };
  const refresh = () => Promise.all([kind === "storyboard" ? "storyboard" : "project-clips", "project-video"].map((k) => queryClient.invalidateQueries({ queryKey: [k, projectId] })));
  const run = useMutation({
    mutationFn: async () => {
      const { data, error } = kind === "storyboard" ? await api.POST("/projects/{project_id}/storyboard/approve-all", { params: { path } }) : await api.POST("/projects/{project_id}/clips/approve-all", { params: { path } });
      if (!data) throw new Error(errorText(error));
      return data as Result;
    },
    onSuccess: async (r) => {
      setResult(r);
      await refresh();
      if (r.approved.length === 0) return;
      toast(`Approved ${r.approved.length} ${noun}${r.approved.length === 1 ? "" : "s"}.`, async () => {
        const body = { ids: r.approved };
        if (kind === "storyboard") await api.POST("/projects/{project_id}/storyboard/approve-all/undo", { params: { path }, body });
        else await api.POST("/projects/{project_id}/clips/approve-all/undo", { params: { path }, body });
        setResult(null);
        await refresh();
      });
    },
  });

  const button =
    opts.ready > 0 ? (
      <Button variant="secondary" icon={Check} busy={run.isPending} className="w-full sm:w-auto" onClick={() => run.mutate()}>
        {opts.ready === opts.waiting ? "Approve all" : `Approve ${opts.ready}`}
      </Button>
    ) : null;

  const label = (id: number) => rows.find((r) => r.id === id)?.clip_id;
  const left = result?.skipped ?? [];
  const line =
    run.isError ? (
      <p role="alert" className="text-sm text-danger">{run.error.message}</p>
    ) : result && result.approved.length + left.length > 0 ? (
      <p className="text-sm text-muted" role="status">
        Approved {result.approved.length}.
        {left.length > 0 && ` ${left.length} not approved: `}
        {left.map((s, i) => {
          const clip = label(s.id);
          return (
            <span key={s.id}>
              {i > 0 && ", "}
              <button type="button" className="underline" onClick={() => show(`${noun === "frame" ? "Frame" : "Clip"} ${clip}`)}>
                Clip {clip}
              </button>{" "}
              {because(s.reason)}
            </span>
          );
        })}
      </p>
    ) : null;
  return { button, line };
}
