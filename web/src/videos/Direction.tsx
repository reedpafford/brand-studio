import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { fileUrl } from "../api/upload";
import { lookFitNote } from "../library/sheets";
import { useBreakdown } from "../projects/BreakdownPane";
import { useCast } from "../projects/CastOk";
import { useDirectorRun } from "./director";
import { newestTreatment } from "./Treatment";

const Part = ({ title, children }: { title: string; children: ReactNode }) => (
  <section aria-label={title} className="space-y-1.5">
    <h4 className="text-xs font-semibold text-muted">{title}</h4>
    {children}
  </section>
);

/** The direction card's body (Reed, 8 Nov: "before any paid stills or takes, the director presents one card: concept,
 *  beats, the look, the clip plan and the estimate"): the start card, with what the director already made before it. Its
 *  treatment, the cast and places it drew (the look), and its plan's clips; the estimate is on Make it. Nothing new is
 *  asked for it. Refined in the chat; Make it is the go and the cast and places OK at once. */
export function Direction({ projectId }: { projectId: number }) {
  const t = newestTreatment(useDirectorRun(projectId).data?.thread);
  const looks = useCast(projectId).data?.items ?? [];
  const plan = useBreakdown(projectId, 0).data?.breakdown;
  const shots = new Map((plan?.scenes ?? []).flatMap((s) => s.shots).map((s) => [s.id, s]));
  const clips = plan?.clips ?? [];
  const seconds = clips.reduce((n, c) => n + c.seconds, 0);
  const approves = looks.some((i) => i.approval !== "approved") && looks.every((i) => i.readiness === "ready"); // as the server's go
  if (!t && !looks.length && !clips.length) return null;
  return (
    <div className="space-y-3 text-[13px]">
      {t && (
        <Part title="Concept">
          <p>{t.logline}</p>
          <p className="text-muted">
            <span className="font-medium text-text">Hook:</span> {t.hook}
          </p>
        </Part>
      )}
      {t && t.beats.length > 0 && (
        <Part title="Beats">
          <ol className="space-y-0.5">
            {t.beats.map((b, i) => (
              <li key={b.id ?? i} className="flex gap-1.5">
                <span className="shrink-0 tabular-nums text-muted">{i + 1}.</span>
                <span className="min-w-0">
                  <span className="font-medium">{b.name || b.purpose.charAt(0).toUpperCase() + b.purpose.slice(1)}</span>
                  <span className="text-muted"> · {b.picture}</span>
                </span>
              </li>
            ))}
          </ol>
        </Part>
      )}
      {looks.length > 0 && (
        <Part title="The look">
          <ul className="flex flex-wrap gap-2.5">
            {looks.map((i) => (
              <li key={i.ref} className="w-[72px] space-y-1">
                {i.preview_file_id ? <img src={fileUrl(i.preview_file_id)} alt={i.name} className="aspect-square w-full rounded-md object-cover" /> : <div aria-hidden className="aspect-square w-full rounded-md bg-surface-3" />}
                <p className="truncate text-xs">{i.name}</p>
                {i.look_fit && i.approval !== "approved" && <p className="text-xs text-warning">{lookFitNote(i.look_fit)}</p>}
                {i.readiness === "needs_look" && (
                  // It didn't draw (tried twice) or nothing describes it: Cast's Redo is its fix; Make it still goes
                  <Link to="?tab=cast" className="inline-flex min-h-control items-center text-xs text-warning underline-offset-2 hover:underline lg:min-h-0">
                    Didn't draw · redo in Cast
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </Part>
      )}
      {clips.length > 0 && (
        <Part title={`Clip plan · ${clips.length} clip${clips.length === 1 ? "" : "s"} · about ${seconds} s`}>
          <ol className="space-y-0.5">
            {clips.map((c, i) => (
              <li key={c.id} className="flex gap-1.5">
                <span className="shrink-0 tabular-nums text-muted">{`Clip ${i + 1} · ${c.seconds} s`}</span>
                <span className="min-w-0 truncate">{shots.get(c.shot_ids[0])?.action}</span>
              </li>
            ))}
          </ol>
        </Part>
      )}
      <p className="text-xs text-muted">{`Make it starts the stills and clips${approves ? " and approves this cast and places" : ""}. To change anything first, say it in the chat.`}</p>
    </div>
  );
}
