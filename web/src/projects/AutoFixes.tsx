import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Undo2 } from "lucide-react";
import { Button } from "../components";
import { errorText as errorClass } from "../ui";
import { BeforeAfter } from "./BeforeAfter";

/** What the server did on its own for a clip (flows P3; Builder-Server-8's #862): said after the fact, never a press to start it. */
type Auto = { id: number; prompt: string; retrying?: "refused" | "busy" | null; retried?: "refused" | "busy" | null; auto_fix?: { fixed: string[]; undone: boolean; before?: string } | null };

const WHY = { refused: "the first try was refused", busy: "the service was busy" } as const;

/** While the retry runs: "Tried again on its own: the first try was refused." After it: "Tried again once on its own (refused)", muted, so it stays known (PL9). */
export function RetryLine({ clip }: { clip: object }) {
  const c = clip as Auto;
  if (c.retrying) return <p role="status" className="text-sm text-muted">Tried again on its own: {WHY[c.retrying]}.</p>;
  if (c.retried) return <p className="text-sm text-muted">Tried again once on its own ({c.retried}).</p>;
  return null;
}

const list = (xs: string[]) => (xs.length < 2 ? xs.join("") : `${xs.slice(0, -1).join(", ")} and ${xs.at(-1)}`);

/** "Fixed for you: removed "9:16"." on the card (not under the folded prompt), with See the change and Undo (free; PL10): the original words come back and the flag returns as Advice. */
export function AutoFixLine({ projectId, clip }: { projectId: number; clip: object }) {
  const c = clip as Auto;
  const queryClient = useQueryClient();
  const undo = useMutation({
    mutationFn: async () => {
      const r = await fetch(`${location.origin}/api/projects/${projectId}/clips/${c.id}/auto-fix/undo`, { method: "POST", credentials: "include" });
      if (!r.ok) {
        const detail = await r.json().then((j: { detail?: unknown }) => j.detail, () => null);
        throw new Error(typeof detail === "string" ? detail : "The undo didn't go through. Nothing changed; try again.");
      }
    },
    // Either way the clip is read again: a refused Undo (the prompt was edited since) is said in the server's words, and a stale line goes.
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["project-clips", projectId] }),
  });
  const [seeing, setSeeing] = useState(false);
  const fix = c.auto_fix;
  if (!fix || fix.undone || fix.fixed.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm" role="note" aria-label="Fixed for you">
      <p className="min-w-0 flex-1 text-muted">Fixed for you: {list(fix.fixed)}.</p>
      {fix.before !== undefined && (
        <Button variant="ghost" dense aria-expanded={seeing} onClick={() => setSeeing(!seeing)}>{seeing ? "Hide the change" : "See the change"}</Button>
      )}
      <Button variant="ghost" dense icon={Undo2} busy={undo.isPending} onClick={() => undo.mutate()}>Undo</Button>
      {seeing && fix.before !== undefined && <div className="w-full"><BeforeAfter before={fix.before} after={c.prompt} label="What the fix changed" /></div>}
      {undo.isError && <p role="alert" className={errorClass}>{undo.error.message}</p>}
    </div>
  );
}
