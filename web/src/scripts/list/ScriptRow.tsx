import { FileText } from "lucide-react";
import { Link } from "react-router-dom";
import type { components } from "../../api/schema";
import { fileUrl } from "../../api/upload";
import { Badge, Button, Dot } from "../../components";
import { serverTime } from "../../time";
import { Who } from "../../videos/VideoRows";
import { ScriptMenu } from "../DeleteScript";
import { isNarrated } from "../flow";
import { ReelChip } from "../ReelImport";
import { age, beingMade, letterOf, statusOf } from "../status";

export type Row = components["schemas"]["ScriptRow"];
type Version = Row["versions"][number];
type Project = components["schemas"]["ProjectOut"];

// One grid for the header and every row on desktop; on a phone a row is the title with its details wrapped under it.
export const COLS = "lg:grid lg:grid-cols-[minmax(0,2.4fr)_minmax(0,1.8fr)_minmax(0,1.5fr)_minmax(0,0.9fr)_6rem_2.25rem] lg:items-center lg:gap-4";

export function TableHead() {
  return (
    <div aria-hidden className={`hidden border-b border-border px-4 py-2 text-xs font-medium text-muted ${COLS}`}>
      <span className="pl-8">Script</span>
      <span>Versions</span>
      <span>Waiting on</span>
      <span>Written by</span>
      <span>Added</span>
      <span />
    </div>
  );
}

const lengthText = (versions: Version[]) => {
  const s = versions.map((v) => v.seconds).filter((n) => n > 0);
  if (s.length === 0) return "Length set at Breakdown";
  const lo = Math.round(Math.min(...s));
  const hi = Math.round(Math.max(...s));
  return lo === hi ? `about ${lo} s` : `about ${lo}–${hi} s`;
};

/** Who the script waits on and for what, from what the lists already know: a video's own Needs you, a draft's writer,
 *  a ready version nobody has started. Blank when nothing waits. */
export function waitingOn(r: Row, videos: Map<number, Project>, meId?: number): string {
  const who = (p: { id: number; name: string } | null | undefined) => (p?.id === meId ? "You" : (p?.name ?? "Someone"));
  for (const v of r.versions) {
    const p = v.project_id ? videos.get(v.project_id) : undefined;
    if (beingMade(v.status) && p?.waiting_on) return `${who(v.editor)}: ${p.waiting_on}`;
  }
  if (!r.published) return r.created_by_id === meId ? "You: finish writing" : `${r.created_by_name || "The writer"} to finish writing`;
  if (r.versions.some((v) => v.status === "approved")) return "An editor to pick it up";
  return "";
}

type Props = {
  row: Row;
  brandName?: string;
  refName?: string;
  refThumb?: boolean;
  narrow: boolean;
  mayOpen: boolean;
  ownScript?: boolean;
  panelTo: (id: number, slot: number) => string;
  ownVideo: (v: Version) => boolean;
  meId?: number;
  waiting: string;
  onDelete?: () => void;
  removed?: boolean;
  onRestore?: () => void;
  restoring?: boolean;
  selected?: boolean;
  onSelect?: (on: boolean) => void;
};

/** One script: picker, poster, title and format, its versions in words, who it waits on, who wrote it, when, and its menu. */
export function ScriptRow({ row: r, brandName, refName, refThumb, narrow, mayOpen, ownScript, panelTo, ownVideo, meId, waiting, onDelete, removed, onRestore, restoring, selected, onSelect }: Props) {
  const brandId = r.brand_id;
  // A script archived because a video was made from it keeps its videos and is never removed for good.
  const kept = r.removed ? r.removed === "archived" : r.versions.some((v) => !!v.project_id);
  const meta = [brandName, refName && `Ref: ${refName}`, lengthText(r.versions), r.published && r.versions_left > 0 && `${r.versions_left} version${r.versions_left === 1 ? "" : "s"} left to make`].filter(Boolean).join(" · ");
  // Where a version goes: its panel (to make it, or to see who's making it), the video made from it, or its draft.
  const chipTo = (v: Version) => (removed ? null : beingMade(v.status) && !ownVideo(v) ? panelTo(r.id, v.slot) : v.status === "approved" ? panelTo(r.id, v.slot) : v.project_id ? `/b/${brandId}/projects/${v.project_id}` : v.status === "draft" && mayOpen ? `/b/${brandId}/scripts/${r.id}` : null);
  // An editor opening someone else's published script by its title lands where Make this version is (A12), on its first
  // version ready to make; with none ready, where that version goes: the editor's own video, say (QA-4 on #1018).
  const ready = !ownScript && r.published ? (r.versions.find((v) => v.status === "approved") ?? r.versions.find((v) => chipTo(v) !== null)) : undefined;
  const titleTo = (ready && chipTo(ready)) || `/b/${brandId}/scripts/${r.id}`;
  const cell = "min-w-0 text-sm text-muted lg:text-base lg:text-text";
  return (
    <li className={`flex flex-wrap items-center gap-x-4 gap-y-2 p-3 lg:px-4 lg:py-2 ${COLS} ${selected ? "bg-accent-soft" : ""}`}>
      <div className="flex min-w-0 basis-full items-center gap-2">
        {onSelect ? (
          <label className="grid size-control shrink-0 place-items-center lg:size-6">
            <span className="sr-only">Select {r.title}</span>
            <input type="checkbox" checked={!!selected} onChange={(e) => onSelect(e.target.checked)} className="size-4 accent-(--accent)" />
          </label>
        ) : (
          <span aria-hidden className="hidden w-6 shrink-0 lg:block" />
        )}
        <span aria-hidden className="grid h-12 w-8 shrink-0 place-items-center overflow-hidden rounded-sm bg-surface-2 text-muted">
          {r.poster_file_id ? <img src={fileUrl(r.poster_file_id)} alt="" className="size-full object-cover" /> : refThumb ? <img src={`/api/references/${r.reference_id}/thumbnail`} alt="" className="size-full object-cover" /> : <FileText size={16} strokeWidth={1.75} />}
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="flex min-w-0 items-center gap-2 font-medium">
            {mayOpen ? (
              <Link to={titleTo} className="min-h-control min-w-0 content-center break-words hover:underline lg:min-h-0 lg:truncate">
                {r.title}
              </Link>
            ) : (
              <span className="min-w-0 break-words lg:truncate">{r.title}</span>
            )}
            {r.kind === "song" && <Badge tone="accent">Song</Badge>}
            {isNarrated(r) && <Badge tone="accent">Narrated</Badge>}
          </h3>
          <p className="flex min-w-0 flex-wrap items-center gap-x-2 text-sm text-muted">
            {r.reel_imported && <ReelChip reel={r.reel} />}
            <span className="min-w-0 lg:truncate">{meta}</span>
          </p>
          {removed && (
            <p className="flex flex-wrap items-center gap-2 text-sm text-muted">
              <Badge>{kept || !r.removed_at ? "Archived" : `Deleted · ${age(r.removed_at)}`}</Badge>
              {kept || !r.purge_on ? "Its videos are kept" : `Removed for good on ${serverTime(r.purge_on).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}`}
            </p>
          )}
        </div>
        {removed && (
          <Button variant="secondary" dense busy={restoring} onClick={onRestore} aria-label={`Restore ${r.title}`}>
            Restore
          </Button>
        )}
      </div>
      <ul className={`${cell} flex flex-wrap gap-x-3 gap-y-1`} aria-label="Versions">
        {r.versions.map((v) => {
          const s = statusOf(v.status);
          const letter = letterOf(v.slot);
          const by = beingMade(v.status) && v.editor ? (v.editor.id === meId ? "you" : v.editor.name) : null;
          const said = `Version ${letter}, ${s.label.toLowerCase()}${by ? ` by ${by}` : ""}`;
          const to = chipTo(v);
          const chip = (
            <>
              <span className="font-semibold text-text">{letter}</span>
              <Dot tone={s.tone}>{`${s.short}${by ? ` · ${by}` : ""}`}</Dot>
            </>
          );
          return (
            <li key={v.slot}>
              {to ? (
                <Link to={to} aria-label={said} title={said} className={`inline-flex items-center gap-2 rounded-md hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${narrow ? "min-h-control" : "min-h-7"}`}>
                  {chip}
                </Link>
              ) : (
                <span aria-label={said} title={said} className="inline-flex items-center gap-2">
                  {chip}
                </span>
              )}
            </li>
          );
        })}
      </ul>
      <div className={cell}>{waiting}</div>
      <div className={cell}>{r.created_by_name && <Who name={r.created_by_name} />}</div>
      <div className={`${cell} tabular-nums`}>{age(r.created_at)}</div>
      <div className="ml-auto flex shrink-0 items-center justify-end gap-2 lg:ml-0">
        {onDelete && <ScriptMenu title={r.title} onDelete={onDelete} />}
      </div>
    </li>
  );
}
