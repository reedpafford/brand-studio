import { Undo2 } from "lucide-react";
import { Button } from "../components";
import { BeforeAfter } from "./BeforeAfter";

/** What the video's look changes for you (flows ST2; Next-Server's #918). */
export type LookFixed = { fixed: string[]; before: string; after: string };

/** "Fixed for the style: stage → world." with what changed. Undo puts the earlier prompt back; it is only offered before the
 *  still is drawn, since saving a prompt over a drawn still draws it again (paid). */
export function LookFixedNote({ fix, onUndo, busy }: { fix: LookFixed; onUndo?: () => void; busy: boolean }) {
  return (
    <div className="space-y-1 rounded-md bg-surface-2 p-2 text-sm" role="note" aria-label="Fixed for the style">
      <p>Fixed for the style: {fix.fixed.join(", ")}.</p>
      <BeforeAfter before={fix.before} after={fix.after} label="What the style changed" />
      {onUndo && (
        <Button variant="ghost" dense icon={Undo2} busy={busy} onClick={onUndo}>
          Undo
        </Button>
      )}
    </div>
  );
}

/** The look's own fix for a refusal or a check's note, next to the press it names: "For this style: …". */
export const LookTip = ({ text }: { text: string | null | undefined }) => (text ? <p className="text-sm text-muted">For this style: {text}</p> : null);
