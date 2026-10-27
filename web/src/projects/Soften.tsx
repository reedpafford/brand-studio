import { Feather, Undo2 } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "../components";
import { BeforeAfter } from "./BeforeAfter";

export type Softened = { before: string; after: string };

/** "Soften it" for a frame whose prompt has a word the image model may refuse: free, nothing is drawn. */
export function SoftenIt({ busy, onSoften }: { busy: boolean; onSoften: () => void }): ReactNode {
  return (
    <span className="mt-1 flex flex-wrap items-center gap-2 text-base">
      <Button variant="secondary" dense icon={Feather} busy={busy} onClick={onSoften}>
        Soften it
      </Button>
      <span className="text-sm text-muted">Free</span>
    </span>
  );
}

/** A frame that was softened (by itself, or by Soften it): what changed, and Undo puts the earlier prompt back. */
export function SoftenedNote({ note, was, onUndo, busy }: { note: string; was: Softened; onUndo: () => void; busy: boolean }) {
  return (
    <div className="space-y-1 rounded-md bg-surface-2 p-2 text-sm" role="note" aria-label="Softened">
      <p>{note}</p>
      <BeforeAfter before={was.before} after={was.after} label="What was softened" />
      <Button variant="ghost" dense icon={Undo2} busy={busy} onClick={onUndo}>
        Undo
      </Button>
    </div>
  );
}
