import { useState } from "react";
import { Download, Play } from "lucide-react";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { Badge, Button, buttonClass } from "../components";
import type { ItemCheck } from "./Checks";

type Take = components["schemas"]["ProjectClipOut"]["takes"][number];

/** Why the check picked or passed over a take, in its own words (Reed, 30 Oct: "and why"). */
export function takeReason(t: Take): string {
  const found = [(t.check as ItemCheck)?.findings ?? [], (t.words as ItemCheck)?.findings ?? []].flat().map((f) => f.text);
  if (found.length) return found.join(" · ");
  if (t.verdict === "checking") return "Checking…";
  if (t.verdict === "clean") return "Checked: nothing found";
  return "Not checked";
}

/** Every take of a clip stays reachable (DECISIONS rule 21, Reed 30 Oct): play it, see why the check passed it over, use it, download it. */
export function OtherTakes({ takes, pickedId, clipId, fileName, disabled, onPick }: { takes: Take[]; pickedId: number | null; clipId: string; fileName: (n: number) => string; disabled: boolean; onPick: (takeId: number) => void }) {
  const [playing, setPlaying] = useState<number | null>(null);
  if (takes.length < 2) return null;
  const others = [...takes].reverse().filter((t) => t.id !== pickedId);
  const flagged = others.some((t) => t.verdict === "flagged");
  return (
    <details open={flagged || undefined} className="rounded-md bg-surface-2 p-2">
      <summary className="flex min-h-11 cursor-pointer items-center text-muted sm:min-h-9">Other takes ({others.length})</summary>
      <ul className="space-y-2 pt-1" aria-label={`Other takes for clip ${clipId}`}>
        {others.map((t) => (
          <li key={t.id} className="space-y-1 border-t border-border pt-2" aria-label={`Take ${t.number}`}>
            <p className="flex flex-wrap items-center gap-2">
              <span className="font-medium">Take {t.number}</span>
              {t.verdict === "flagged" && <Badge tone="warning">Passed over</Badge>}
              <span className="text-muted">{takeReason(t)}</span>
            </p>
            {playing === t.id && <video controls autoPlay src={fileUrl(t.file_id)} className="max-h-64 w-full rounded-md bg-surface-3" aria-label={`Take ${t.number} of clip ${clipId}`} />}
            <span className="flex flex-wrap gap-2">
              <Button variant="ghost" dense icon={Play} aria-label={`Play take ${t.number}`} onClick={() => setPlaying(playing === t.id ? null : t.id)}>
                {playing === t.id ? "Hide" : "Play"}
              </Button>
              <Button variant="secondary" dense disabled={disabled} aria-label={`Use take ${t.number}`} onClick={() => onPick(t.id)}>
                Use this take
              </Button>
              <a className={buttonClass("ghost")} href={fileUrl(t.file_id)} download={fileName(t.number)} aria-label={`Download take ${t.number}`}>
                <Download size={20} strokeWidth={1.75} aria-hidden />
                Download
              </a>
            </span>
          </li>
        ))}
      </ul>
    </details>
  );
}
