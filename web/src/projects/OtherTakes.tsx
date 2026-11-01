import { useState } from "react";
import { Download, Play } from "lucide-react";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { Button, buttonClass } from "../components";
import { useToast } from "../toast";

type Clip = components["schemas"]["ProjectClipOut"];
type Take = Clip["takes"][number];
// Agreed with Next-Server for M30, and read only when the server sends them: the texts of findings marked Looks fine, this
// clip's failed or refused tries, and who put the picked take in the cut.
type Try = { at: string; reason: string; refused?: boolean };
type More = { marked_fine?: string[] };
type ClipMore = { tries?: Try[]; picked_by?: "check" | "director" | "you" | null };

/** What the AI said about a take, in plain words (ux-audit §8.3): its first note, Marked fine once dismissed, or no notes. */
export function takeReason(t: Take): string {
  const said = [...(t.check?.findings ?? []), ...(t.words?.findings ?? [])][0]?.text;
  if (said) return `AI: ${said}`;
  const fine = (t as Take & More).marked_fine?.[0];
  if (fine) return `Marked fine: ${fine}`;
  if (t.verdict === "checking") return "AI: still checking";
  if (t.verdict === "clean") return "AI: no notes";
  return "Not checked";
}

/** Every earlier take stays reachable (Reed's condition on the four steps, ux-audit §8.3): each with the AI's reason, Play,
 *  Use this take (with Undo) and Download; failed and refused tries are listed with why, with nothing to play. */
export function OtherTakes({ clip: c, aspect, projectName, viewOnly, onPick }: { clip: Clip; aspect: string; projectName: string; viewOnly: boolean; onPick: (takeId: number) => void }) {
  const toast = useToast();
  const [playing, setPlaying] = useState<number | null>(null);
  const others = c.takes.filter((t) => t.id !== c.picked_take_id).reverse();
  const extra = c as Clip & ClipMore;
  const tries = extra.tries ?? [];
  const n = others.length + tries.length;
  if (n === 0) return null;
  const byCheck = extra.picked_by === "check" || extra.picked_by === "director" || c.takes.find((t) => t.id === c.picked_take_id)?.approved_by === "check";
  const use = (t: Take) => {
    const was = c.picked_take_id;
    onPick(t.id);
    toast(`Take ${t.number} is picked.`, was !== null ? () => onPick(was) : undefined);
  };
  return (
    <details open={byCheck} className="rounded-md border border-border">
      <summary className="flex min-h-11 cursor-pointer items-center px-3 text-sm font-medium">Other takes ({n})</summary>
      <ul className="divide-y divide-border" aria-label={`Other takes for clip ${c.clip_id}`}>
        {others.map((t) => (
          <li key={t.id} className="space-y-2 p-3" aria-label={`Take ${t.number}`}>
            <p className="break-words text-sm">
              <span className="font-medium">Take {t.number}</span> · <span className="text-muted">{takeReason(t)}</span>
            </p>
            {playing === t.id && <video controls autoPlay src={fileUrl(t.file_id)} className="max-h-80 w-full rounded-md bg-surface-2 object-contain" style={{ aspectRatio: aspect.replace(":", " / ") }} aria-label={`Take ${t.number}`} />}
            <div className="flex flex-wrap gap-2">
              <Button variant="ghost" dense icon={Play} onClick={() => setPlaying(playing === t.id ? null : t.id)} aria-label={`Play take ${t.number}`}>
                {playing === t.id ? "Hide" : "Play"}
              </Button>
              {!viewOnly && (
                <Button variant="secondary" dense onClick={() => use(t)} aria-label={`Use take ${t.number}`}>
                  Use this take
                </Button>
              )}
              <a className={buttonClass("ghost")} href={fileUrl(t.file_id)} download={`${projectName}-${c.clip_id}-take${t.number}.mp4`} aria-label={`Download take ${t.number}`}>
                <Download aria-hidden className="size-4" />
                Download
              </a>
            </div>
          </li>
        ))}
        {tries.map((t, i) => (
          <li key={`try-${i}`} className="p-3 text-sm" aria-label={t.refused ? "A refused try" : "A try that didn't finish"}>
            <span className="font-medium">{t.refused ? "Refused" : "Didn't finish"}</span> · <span className="text-muted">{t.reason}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}
