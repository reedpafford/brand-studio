import type { ReactNode } from "react";
import { Download } from "lucide-react";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import type { ItemCheck } from "./Checks";

type Take = components["schemas"]["ProjectClipOut"]["takes"][number];

/** Why the check picked or passed over a take, in its own words (Reed, 30 Oct: "and why"). */
export function takeReason(t: Take): string {
  const found = [(t.check as ItemCheck)?.findings ?? [], (t.words as ItemCheck)?.findings ?? []].flat().map((f) => f.text);
  if (found.length) return found.join(" · ");
  if (t.verdict === "checking") return "Checking…";
  if (t.verdict === "clean" || (t.check as ItemCheck)?.status === "ok") return "Check found nothing";
  return "Not checked";
}

/** The status dot and its words, as the clip list and the takes show them. */
export function Dot({ tone, children }: { tone: "ok" | "need" | "run" | "none"; children: string }) {
  const dot = tone === "ok" ? "border-success bg-success" : tone === "need" ? "border-warning bg-warning" : tone === "run" ? "border-accent" : "border-muted";
  return (
    <span className="inline-flex min-w-0 items-start gap-1.5 text-xs text-muted">
      <i aria-hidden className={`mt-1 inline-block size-2 shrink-0 rounded-full border-[1.5px] ${dot}`} />
      <span className="min-w-0 break-words">{children}</span>
    </span>
  );
}

/** The small mono label on a take or a still: "TAKE 2", "STILL". */
export function Tag({ children }: { children: ReactNode }) {
  return <span className="pointer-events-none absolute bottom-1.5 left-1.5 rounded-[2px] bg-black/55 px-1 py-0.5 font-mono text-[10px] uppercase leading-none text-on-media">{children}</span>;
}

/** Every take of a clip stays reachable (DECISIONS rule 21, Reed 30 Oct), side by side with the picked one (v5): it plays
 *  under the pointer, a press uses it (free; the earlier one is put back the same way), it downloads from its corner, and
 *  its line says why the check passed it over. `tile` is the takes' shared width. */
export function OtherTakes({ takes, pickedId, clipId, fileName, disabled, onPick, poster, aspect, tile }: { takes: Take[]; pickedId: number | null; clipId: string; fileName: (n: number) => string; disabled: boolean; onPick: (takeId: number) => void; poster?: string; aspect: string; tile: string }) {
  const others = [...takes].reverse().filter((t) => t.id !== pickedId);
  if (takes.length < 2 || others.length === 0) return null;
  const play = (el: HTMLElement, on: boolean) => {
    const v = el.querySelector("video");
    if (on) void v?.play?.()?.catch(() => undefined);
    else v?.pause?.();
  };
  return (
    <ul className="contents" aria-label={`Other takes for clip ${clipId}`}>
      {others.map((t) => (
        <li key={t.id} className={tile} aria-label={`Take ${t.number}`}>
          <div className="group relative overflow-hidden rounded-md bg-surface-2" style={{ aspectRatio: aspect.replace(":", " / ") }} onMouseEnter={(e) => play(e.currentTarget, true)} onMouseLeave={(e) => play(e.currentTarget, false)}>
            <video muted loop playsInline preload="metadata" src={fileUrl(t.file_id)} poster={poster} className="h-full w-full object-cover" aria-label={`Take ${t.number} of clip ${clipId}`} />
            <button type="button" disabled={disabled} title="Use this take" aria-label={`Use take ${t.number}`} onClick={() => onPick(t.id)} className="absolute inset-0 rounded-md hover:bg-white/5 disabled:cursor-not-allowed" />
            <Tag>Take {t.number}</Tag>
            <a href={fileUrl(t.file_id)} download={fileName(t.number)} aria-label={`Download take ${t.number}`} className="absolute right-1 top-1 grid size-11 place-items-center rounded-sm bg-black/55 text-on-media lg:size-8 [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover:opacity-100 [@media(hover:hover)]:focus-visible:opacity-100">
              <Download size={16} strokeWidth={1.75} aria-hidden />
            </a>
          </div>
          <Dot tone={t.verdict === "flagged" ? "need" : t.verdict === "clean" ? "ok" : "none"}>{t.verdict === "flagged" ? `Passed over: ${takeReason(t)}` : takeReason(t)}</Dot>
        </li>
      ))}
    </ul>
  );
}
