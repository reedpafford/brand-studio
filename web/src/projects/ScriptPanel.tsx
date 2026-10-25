import { Pencil } from "lucide-react";
import { Button, Sheet, SidePanel } from "../components";
import { ScriptText, useLatestScript } from "./ScriptTab";

/** The working script, read only, from Shots on: a side panel on desktop, a sheet on a phone. */
export function ScriptPanel({ projectId, rail, highlight, onLineClick, onEdit, onClose }: { projectId: number; rail: boolean; highlight: number[]; onLineClick?: (line: number) => void; onEdit: () => void; onClose: () => void }) {
  const script = useLatestScript(projectId);
  const body = (
    <div className="space-y-3">
      {highlight.length > 0 && <p className="text-sm text-muted">Lines for this step are highlighted.</p>}
      {script.data ? <ScriptText text={script.data.text} highlight={highlight} onLineClick={onLineClick} /> : <p className="text-muted">No script yet.</p>}
      <Button variant="ghost" dense icon={Pencil} onClick={onEdit}>
        Edit in Script
      </Button>
    </div>
  );
  return rail ? (
    <SidePanel title="Script" onClose={onClose}>
      {body}
    </SidePanel>
  ) : (
    <Sheet title="Script" onClose={onClose}>
      {body}
    </Sheet>
  );
}
