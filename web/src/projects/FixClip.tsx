import { Undo2, Wand2 } from "lucide-react";
import { Button } from "../components";
import { BeforeAfter } from "./BeforeAfter";

/** The note the server leaves on a clip whose prompt "Fix this clip's prompt" rewrote. */
export const FIX_NOTE = "Fix this clip's prompt";

/** "Fix this clip's prompt": free for everyone (an editor past their week too), and it never makes a take. */
export function FixThisPrompt({ busy, onFix }: { busy: boolean; onFix: () => void }) {
  return (
    <span className="mt-1 flex flex-wrap items-center gap-2 text-base">
      <Button variant="secondary" dense icon={Wand2} busy={busy} onClick={onFix}>
        {busy ? "Fixing…" : "Fix this clip's prompt"}
      </Button>
      <span className="text-sm text-muted">Free</span>
    </span>
  );
}

/** What the fix changed, with Undo. Looks good was cleared, so the new prompt is read again. */
export function FixedNote({ before, after, onUndo, busy }: { before: string; after: string; onUndo: () => void; busy: boolean }) {
  return (
    <div className="space-y-1 rounded-md bg-surface-2 p-2 text-sm" role="note" aria-label="Prompt fixed">
      <p>Fixed. Read the new prompt, then mark it Looks good.</p>
      <BeforeAfter before={before} after={after} label="What the fix changed" />
      <Button variant="ghost" dense icon={Undo2} busy={busy} onClick={onUndo}>
        Undo
      </Button>
    </div>
  );
}
