import { Clock, Film } from "lucide-react";
import { Link } from "react-router-dom";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { WaitingCount } from "../approvals/HeldRequests";
import type { Job } from "../approvals/useHeld";
import { buttonClass, Dot, StepBars, wholeCredits } from "../components";
import { letterOf } from "../scripts/status";
import { VIDEO_STEPS, videoAt, videoStatus, videoTo } from "./progress";

type Project = components["schemas"]["ProjectOut"];

// One grid for the header and every row on desktop (v5 C_Videos); on a phone a row is the name with its details wrapped under it.
const COLS = "lg:grid lg:grid-cols-[minmax(0,2.4fr)_9rem_minmax(0,1.6fr)_5rem_9rem] lg:items-center lg:gap-4";
const cell = "min-w-0 text-sm text-muted lg:text-text";
const credits = (n: number) => `${n} credit${n === 1 ? "" : "s"}`;
const day = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });

/** The director's own videos carry a chip (they began as a Freestyle). */
const Director = () => <span className="shrink-0 rounded-sm bg-accent-soft px-1.5 text-xs font-medium text-accent-text">Director</span>;

/** A video's title over its project, with the poster (or a clock, for a request). */
function Name({ poster, title, under, chip, to }: { poster?: number | null; title: string; under: string; chip?: React.ReactNode; to?: string }) {
  return (
    <div className="flex min-w-0 basis-full items-center gap-3">
      <span aria-hidden className="grid h-11 w-8 shrink-0 place-items-center overflow-hidden rounded-sm bg-surface-2 text-muted">
        {poster ? <img src={fileUrl(poster)} alt="" className="size-full object-cover" /> : chip === "request" ? <Clock size={16} strokeWidth={1.75} /> : <Film size={16} strokeWidth={1.75} />}
      </span>
      <div className="min-w-0">
        <p className="flex min-w-0 items-center gap-2">
          {to ? <Link to={to} className="min-h-control min-w-0 content-center truncate font-medium hover:underline lg:min-h-0">{title}</Link> : <span className="truncate font-medium">{title}</span>}
          {chip === "request" ? <span className="shrink-0 rounded-sm bg-warning-soft px-1.5 text-xs font-medium text-warning">Request</span> : chip}
        </p>
        <p className="truncate text-xs text-muted">{under}</p>
      </div>
    </div>
  );
}

/** A change waiting for the owner's OK: Reed opens it in Needs you; an editor is told it waits. */
function HeldChange({ owner }: { owner: boolean }) {
  return owner ? <Link to="/approvals" className={`${buttonClass("secondary")} min-h-control-dense px-3 text-xs`}>Open in Needs you</Link> : <Dot tone="warning">Waiting for the owner's OK</Dot>;
}

/** A video: poster, name over its project, four step bars, what it waits on, who made it, what it spent. */
export function VideoRow({ p, project, held, owner }: { p: Project; project: string; /** a change of this video waits for the owner's OK */ held?: boolean; owner: boolean }) {
  const at = videoAt(p);
  const status = videoStatus(p);
  const making = !p.needs_you && !p.finished_at;
  const waits = held ? <HeldChange owner={owner} /> : p.finished_at ? (p.final_out_of_date ? <Dot tone="warning">Finished · changes waiting</Dot> : <span className="text-muted">Delivered {day(p.finished_at)}</span>)
    : p.archived_at ? <Dot tone={status.tone}>{status.label}</Dot>
    : <Dot tone={p.needs_you ? "warning" : "accent"}>{p.waiting_on || (at !== null && at < VIDEO_STEPS.length ? `Making ${VIDEO_STEPS[at].toLowerCase()}` : status.label)}</Dot>;
  return (
    <li className={`flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 lg:py-2 ${COLS} ${p.archived_at ? "opacity-70" : ""}`}>
      <Name poster={p.poster_file_id} title={p.name} under={project} to={videoTo(p)} chip={p.freestyle_id != null ? <Director /> : undefined} />
      <div className={cell}>{at !== null && <StepBars steps={VIDEO_STEPS} at={at} attention={p.needs_you} />}</div>
      <div className={cell}>
        {waits}
        <WaitingCount projectId={p.id} className="block" />
      </div>
      <div className={cell}>{p.created_by_name || "Someone"}</div>
      <div className={`${cell} tabular-nums lg:text-right`}>{making || p.needs_you || p.finished_at ? `spent ${credits(wholeCredits(p.credits_used) || 0)}` : ""}</div>
    </li>
  );
}

/** A held send with no video yet: the editor's request (v5 C_Videos "Request" row). The owner can open it in Needs you. */
export function RequestRow({ job, project, owner, maker }: { job: Job; project: string; owner: boolean; maker: string }) {
  const fs = job.freestyle;
  const title = fs ? `${fs.script_title || "New video"}${fs.slot != null ? ` · ${letterOf(fs.slot)}` : ""}` : "Quick clip";
  return (
    <li className={`flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 lg:py-2 ${COLS}`}>
      <Name title={title} under={`${fs ? "New video" : "Quick clip"} from ${maker} · not made yet · ${project}`} chip="request" />
      <div className={cell}>{owner ? "Starts at your OK" : ""}</div>
      <div className={cell}>
        {owner ? <Link to="/approvals" className={`${buttonClass("secondary")} min-h-control-dense px-3 text-xs`}>Open in Needs you</Link> : "Waiting for the owner's OK"}
      </div>
      <div className={cell}>{maker}</div>
      <div className={`${cell} tabular-nums lg:text-right`}>up to {credits(wholeCredits(job.freestyle?.up_to ?? job.credits) || 0)}</div>
    </li>
  );
}

/** The table's header, once; each group is a bar with its dot and count over its rows. */
export function VideoHead() {
  return (
    <div aria-hidden className={`hidden border-b border-border px-4 py-2 text-xs font-medium text-muted ${COLS}`}>
      <span className="lg:pl-11">Video</span>
      <span>Steps</span>
      <span>Waits on</span>
      <span>Maker</span>
      <span className="text-right">Credits</span>
    </div>
  );
}
