import { Film } from "lucide-react";
import { Link } from "react-router-dom";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { WaitingCount } from "../approvals/HeldRequests";
import { Card, Dot, StepBars } from "../components";
import { age, letterOf } from "../scripts/status";
import { VIDEO_STEPS, creditsOf, videoAt, videoStatus, videoTo } from "./progress";

type Project = components["schemas"]["ProjectOut"];
/** The script and version a video was made from, when the scripts list has it. */
export type MadeFrom = { scriptId: number; title: string; slot: number };

// One grid for the header and every row on desktop; on a phone a row is the name with its details wrapped under it.
const COLS = "lg:grid lg:grid-cols-[minmax(0,2fr)_minmax(0,1.5fr)_minmax(0,1.1fr)_minmax(0,1.5fr)_minmax(0,0.9fr)_5.5rem_5.5rem] lg:items-center lg:gap-4";

/** The person's first letter in a small circle, then the name. */
export function Who({ name }: { name: string }) {
  return (
    <span className="inline-flex min-w-0 items-center gap-2">
      <span aria-hidden className="grid size-5 shrink-0 place-items-center rounded-full bg-surface-3 text-xs font-semibold text-muted">
        {(name || "?").charAt(0).toUpperCase()}
      </span>
      <span className="truncate">{name}</span>
    </span>
  );
}

function Row({ p, from }: { p: Project; from?: MadeFrom }) {
  const at = videoAt(p);
  const status = videoStatus(p);
  const cell = "min-w-0 text-sm text-muted lg:text-base lg:text-text";
  return (
    <li className={`flex flex-wrap items-center gap-x-4 gap-y-2 p-3 lg:px-4 lg:py-2 ${COLS} ${p.archived_at ? "opacity-70" : ""}`}>
      <div className="flex min-w-0 basis-full items-center gap-3">
        <span aria-hidden className="grid h-12 w-8 shrink-0 place-items-center overflow-hidden rounded-sm bg-surface-2 text-muted">
          {p.poster_file_id ? <img src={fileUrl(p.poster_file_id)} alt="" className="size-full object-cover" /> : <Film size={16} strokeWidth={1.75} />}
        </span>
        <Link to={videoTo(p)} className="min-h-control min-w-0 content-center break-words font-medium hover:underline lg:min-h-0 lg:truncate">
          {p.name}
        </Link>
      </div>
      <div className={cell}>
        {!p.script_draft_id ? (
          "(earlier way)"
        ) : from ? (
          <Link to={`/b/${p.brand_id}/scripts/${from.scriptId}`} className="inline-flex min-h-control min-w-0 items-center text-accent-text hover:underline lg:min-h-0">
            <span className="truncate">{`${from.title} › ${letterOf(from.slot)}`}</span>
          </Link>
        ) : (
          <Link to={`/b/${p.brand_id}/scripts/${p.script_draft_id}`} className="inline-flex min-h-control items-center text-accent-text hover:underline lg:min-h-0">
            Its script
          </Link>
        )}
      </div>
      <div className={`${cell} flex items-center gap-2`}>
        {at !== null && <StepBars steps={VIDEO_STEPS} at={at} />}
        {at !== null && at < VIDEO_STEPS.length && !p.archived_at ? <span>{VIDEO_STEPS[at]}</span> : <Dot tone={status.tone}>{status.label}</Dot>}
      </div>
      <div className={cell}>
        {p.waiting_on && <span className={p.needs_you ? "font-medium text-warning" : ""}>{p.waiting_on}</span>}
        <WaitingCount projectId={p.id} className="block" />
      </div>
      <div className={cell}>
        <Who name={p.created_by_name || "Someone"} />
      </div>
      <div className={`${cell} tabular-nums`}>
        {creditsOf(p)}
        <span className="lg:sr-only"> credits</span>
      </div>
      <div className={`${cell} tabular-nums`}>{p.finished_at ? age(p.finished_at) : ""}</div>
    </li>
  );
}

/** Videos as a table: one header, then a row per video. */
export function VideoTable({ rows, madeFrom }: { rows: Project[]; madeFrom: Map<number, MadeFrom> }) {
  return (
    <Card className="p-0 sm:p-0">
      <div aria-hidden className={`hidden border-b border-border px-4 py-2 text-xs font-medium text-muted ${COLS}`}>
        <span>Video</span>
        <span>Script</span>
        <span>Step</span>
        <span>Waiting on</span>
        <span>Made by</span>
        <span>Credits</span>
        <span>Finished</span>
      </div>
      <ul className="divide-y divide-border">
        {rows.map((p) => (
          <Row key={p.id} p={p} from={madeFrom.get(p.id)} />
        ))}
      </ul>
    </Card>
  );
}
