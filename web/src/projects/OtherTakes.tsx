import { useState } from "react";
import { Download, Play } from "lucide-react";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { Button, buttonClass } from "../components";
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

/** The status dot and its words, as the clip list and the takes show them. */
export function Dot({ tone, children }: { tone: "ok" | "need" | "run" | "none"; children: string }) {
  const dot = tone === "ok" ? "border-success bg-success" : tone === "need" ? "border-warning bg-warning" : tone === "run" ? "border-accent" : "border-muted";
  return (
    <span className="inline-flex min-w-0 items-center gap-1.5 text-xs text-muted">
      <i aria-hidden className={`inline-block size-2 shrink-0 rounded-full border-[1.5px] ${dot}`} />
      <span className="min-w-0 break-words">{children}</span>
    </span>
  );
}

/** Every take of a clip stays reachable (DECISIONS rule 21, Reed 30 Oct), side by side with the picked one: play it, see
 *  why the check passed it over, use it, download it. */
export function OtherTakes({ takes, pickedId, clipId, fileName, disabled, onPick, poster, aspect }: { takes: Take[]; pickedId: number | null; clipId: string; fileName: (n: number) => string; disabled: boolean; onPick: (takeId: number) => void; poster?: string; aspect: string }) {
  const [playing, setPlaying] = useState<number | null>(null);
  const others = [...takes].reverse().filter((t) => t.id !== pickedId);
  if (takes.length < 2 || others.length === 0) return null;
  return (
    <ul className="flex flex-wrap gap-4" aria-label={`Other takes for clip ${clipId}`}>
      {others.map((t) => (
        <li key={t.id} className="flex w-40 flex-col gap-1.5 text-sm sm:w-44" aria-label={`Take ${t.number}`}>
          <div className="grid place-items-center overflow-hidden rounded-md bg-surface-2" style={{ aspectRatio: aspect.replace(":", " / ") }}>
            {playing === t.id ? (
              <video controls autoPlay src={fileUrl(t.file_id)} className="h-full w-full object-cover" aria-label={`Take ${t.number} of clip ${clipId}`} />
            ) : poster ? (
              <img src={poster} alt="" className="h-full w-full object-cover opacity-70" />
            ) : null}
          </div>
          <span className="font-medium">Take {t.number}</span>
          <Dot tone={t.verdict === "flagged" ? "need" : t.verdict === "clean" ? "ok" : "none"}>{t.verdict === "flagged" ? `Passed over: ${takeReason(t)}` : takeReason(t)}</Dot>
          <span className="flex flex-wrap gap-1">
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
  );
}
