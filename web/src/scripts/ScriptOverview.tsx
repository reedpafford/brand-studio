import type { ReactNode } from "react";
import { Download, FileText, Lock } from "lucide-react";
import { Link } from "react-router-dom";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { Button, Card, Dot, StepBars, wholeCredits } from "../components";
import { useProjectList } from "../projects/LegacyVideos";
import { VIDEO_STEPS, creditsOf, videoAt, videoStatus, videoTo } from "../videos/progress";
import { Who } from "../videos/VideoRows";
import { stepsFor } from "./flow";
import { beingMade, letterOf, statusOf } from "./status";
import type { Script } from "./useScript";
import { useStartCost } from "./VersionPanel";

type Version = Script["versions"][number];
type Project = components["schemas"]["ProjectOut"];

const COLS = "lg:grid lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1.6fr)_minmax(0,0.8fr)_6rem_minmax(0,1.4fr)] lg:items-center lg:gap-4";

/** A version's name: the original, or what the variation changes. */
const nameOf = (v: Version) => (v.slot === 0 ? "Original" : v.premise || (v.variation_of ? `Variation of ${v.variation_of}` : "Variation"));

function VersionRow({ v, video, onMake }: { v: Version; video?: Project; onMake: () => void }) {
  const cost = useStartCost(v.has_breakdown);
  const s = statusOf(v.status);
  const at = video ? videoAt(video) : null;
  const cell = "min-w-0 text-sm text-muted lg:text-base lg:text-text";
  return (
    <li aria-label={`Version ${letterOf(v.slot)}`} className={`flex flex-wrap items-center gap-x-4 gap-y-2 p-3 lg:px-4 lg:py-2 ${COLS}`}>
      <div className="flex min-w-0 basis-full items-center gap-3">
        <span aria-hidden className="grid h-12 w-8 shrink-0 place-items-center overflow-hidden rounded-sm bg-surface-2 text-muted">
          {video?.poster_file_id ? <img src={fileUrl(video.poster_file_id)} alt="" className="size-full object-cover" /> : <FileText size={16} strokeWidth={1.75} />}
        </span>
        <span className="font-semibold">{letterOf(v.slot)}</span>
        <span className="min-w-0 break-words lg:truncate">{nameOf(v)}</span>
      </div>
      <div className={`${cell} flex flex-wrap items-center gap-2`}>
        {video && at !== null && <StepBars steps={VIDEO_STEPS} at={at} />}
        {video && at !== null && at < VIDEO_STEPS.length ? (
          <span>
            {VIDEO_STEPS[at]}
            {video.waiting_on && <span className="text-warning"> · {video.waiting_on}</span>}
          </span>
        ) : video ? (
          <Dot tone={videoStatus(video).tone}>{videoStatus(video).label}</Dot>
        ) : (
          <Dot tone={s.tone}>{s.label}</Dot>
        )}
      </div>
      <div className={cell}>{v.editor ? <Who name={v.editor.name} /> : "—"}</div>
      <div className={`${cell} tabular-nums`}>{video ? creditsOf(video) : v.status === "approved" && v.estimate_credits > 0 ? `about ${wholeCredits(v.estimate_credits)} (planned)` : "—"}</div>
      <div className="flex flex-wrap items-center gap-2 lg:justify-end">
        {v.status === "approved" && (
          <Button dense charge="estimate" price={cost} onClick={onMake}>
            Make this version
          </Button>
        )}
        {video?.finished_at && (
          <Link to={`/b/${video.brand_id}/videos/${video.id}?step=downloads`} className="inline-flex min-h-control items-center gap-1 rounded-md px-2 text-accent-text hover:underline lg:min-h-control-dense">
            <Download size={16} strokeWidth={1.75} aria-hidden />
            Download
          </Link>
        )}
        {video && (
          <Link to={videoTo(video)} className="inline-flex min-h-control items-center rounded-md px-2 text-accent-text hover:underline lg:min-h-control-dense">
            Open video
          </Link>
        )}
        {!video && beingMade(v.status) && <span className="text-sm text-muted">{v.editor?.name ?? "Someone"} is making it</span>}
      </div>
    </li>
  );
}

function Side({ title, action, children }: { title: string; action?: { label: string; onClick: () => void }; children: ReactNode }) {
  return (
    <Card className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-semibold">{title}</h3>
        {action && (
          <Button variant="ghost" dense onClick={action.onClick}>
            {action.label}
          </Button>
        )}
      </div>
      {children}
    </Card>
  );
}

/** A published script's first tab: its versions as a table (each one's video, who makes it, its credits, and its press),
 *  with the words, cast and plan summed up beside it. */
export function ScriptOverview({ script: s, brandId, onStep, onMake }: { script: Script; brandId: number; onStep: (step: string) => void; onMake: (slot: number) => void }) {
  const videos = useProjectList(brandId);
  const byId = new Map((videos.data ?? []).map((p) => [p.id, p]));
  const versions = s.versions.filter((v) => v.text.trim() !== "" || v.status !== "draft");
  const ready = versions.filter((v) => v.status === "approved").length;
  const a = s.versions.find((v) => v.slot === 0);
  const words = (a?.text ?? "").split("\n").filter((l) => l.trim()).slice(0, 4);
  const song = s.kind === "song";
  const planned = s.versions.filter((v) => v.has_breakdown);
  const plan = stepsFor(s).find((x) => x.id === "breakdown")?.label ?? "Plan";
  const lengths = versions.map((v) => Math.round(v.seconds)).filter((n) => n > 0);
  return (
    <div className="space-y-4 lg:grid lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start lg:gap-6 lg:space-y-0">
      <section aria-label="Versions" className="space-y-3">
        {s.description && <p className="text-muted">{s.description}</p>}
        <h2 className="type-section">
          Versions{" "}
          <span className="font-normal text-muted tabular-nums">
            · {versions.length}
            {ready > 0 ? ` · ${ready} ready to make` : ""}
          </span>
        </h2>
        <Card className="p-0 sm:p-0">
          <div aria-hidden className={`hidden border-b border-border px-4 py-2 text-xs font-medium text-muted ${COLS}`}>
            <span className="pl-11">Version</span>
            <span>Video</span>
            <span>Made by</span>
            <span>Credits</span>
            <span />
          </div>
          <ul className="divide-y divide-border">
            {versions.map((v) => (
              <VersionRow key={v.slot} v={v} video={v.project_id ? byId.get(v.project_id) : undefined} onMake={() => onMake(v.slot)} />
            ))}
          </ul>
        </Card>
      </section>
      <aside className="space-y-3">
        <Side title={song ? "Lyrics" : "Words"} action={{ label: song ? "Open Song" : "Open Script", onClick: () => onStep(song ? "song" : "script") }}>
          {words.length ? <p className="whitespace-pre-wrap font-script text-sm leading-[1.6] [overflow-wrap:anywhere]">{words.join("\n")}</p> : <p className="text-sm text-muted">No words yet.</p>}
        </Side>
        <Side title="Cast" action={{ label: "Open Cast", onClick: () => onStep("cast") }}>
          {s.cast.length === 0 ? (
            <p className="text-sm text-muted">Everyone is made in Cast.</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {s.cast.map((c) => (
                <li key={c.id} className="flex items-center gap-2">
                  <Who name={c.role} />
                  {c.locked && <Lock size={16} strokeWidth={1.75} aria-label="Locked look" className="text-muted" />}
                </li>
              ))}
            </ul>
          )}
        </Side>
        <Side title={plan} action={{ label: `Open ${plan}`, onClick: () => onStep("breakdown") }}>
          <p className="text-sm">
            {planned.length === 0
              ? "The plan is made when an editor starts a version."
              : planned.map((v) => [letterOf(v.slot), v.clips ? `${v.clips} clip${v.clips === 1 ? "" : "s"}` : null, v.seconds ? `${Math.round(v.seconds)} s` : null].filter(Boolean).join(" · ")).join("; ")}
          </p>
        </Side>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 px-1 text-sm">
          <dt className="text-muted">Written by</dt>
          <dd>{s.created_by_name || "—"}</dd>
          <dt className="text-muted">Length</dt>
          <dd>{lengths.length ? `about ${Math.min(...lengths)}${Math.max(...lengths) !== Math.min(...lengths) ? `–${Math.max(...lengths)}` : ""} s` : "Set at Plan"}</dd>
        </dl>
      </aside>
    </div>
  );
}
