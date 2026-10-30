import { useEffect } from "react";
import { Pencil } from "lucide-react";
import { Button, Card } from "../components";
import { EnhanceBar, MarkLine, Notes } from "../projects/Enhance";
import { ScriptText } from "../projects/ScriptTab";
import { useDirections } from "./useDirections";
import type { Script } from "./useScript";

/** Step 3: Claude suggests camera, movement, reaction and brand-screen lines for version A. The words never change; the step is optional. */
export function DirectionsStep({ script: s, onAccepted, onEditWords }: { script: Script; onAccepted: (n: number) => void; onEditWords: () => void }) {
  const text = s.versions.find((v) => v.slot === 0)?.text ?? "";
  const e = useDirections(s.id, text);
  const accepted = e.marks.filter((m) => m.status === "accepted").length;
  // Accepted but not added: Next still goes on, but asks once before dropping them.
  useEffect(() => onAccepted(accepted), [accepted]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => onAccepted(0), []); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="space-y-3">
      <Card className="max-w-[680px]">
        <p>Claude suggests camera moves, movement, reactions and where brand screens show. Your words never change.</p>
        <p className="text-sm text-muted">This step is optional. Press Next to skip it.</p>
        {!s.published && (
          <div className="mt-2 space-y-1">
            <Button variant="ghost" icon={Pencil} onClick={onEditWords}>
              Edit the script
            </Button>
            {e.shown.length > 0 && <p className="text-sm text-muted">Changing the words clears these suggestions; ask Claude again after.</p>}
          </div>
        )}
      </Card>
      <EnhanceBar e={e} />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <ScriptText text={text} around={(line, where) => e.shown.filter((m) => m.line === line && (m.placement === "before") === (where === "before")).map((m) => <MarkLine key={m.id} mark={m} e={e} />)} />
        <div className="hidden lg:block">
          <Notes e={e} />
        </div>
      </div>
    </div>
  );
}
