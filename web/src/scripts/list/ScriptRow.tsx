import { Link } from "react-router-dom";
import type { components } from "../../api/schema";
import { Badge, Button, Dot } from "../../components";
import { serverTime } from "../../time";
import { ScriptMenu } from "../DeleteScript";
import { useFormatName } from "../useFormats";
import { ReelChip } from "../ReelImport";
import { finished } from "../../freestyle/FromScript";
import { age, beingMade, letterOf, statusOf } from "../status";

export type Row = components["schemas"]["ScriptRow"];

/** The script's format, named by the guides, unless it is the usual Dialogue. */
function FormatBadge({ row }: { row: Row }) {
  const name = useFormatName();
  return row.format === "dialogue" ? null : <Badge tone="accent">{name(row.format)}</Badge>;
}
type Version = Row["versions"][number];
type Project = components["schemas"]["ProjectOut"];

// v5 C_Scripts: checkbox 36 | Script | Versions 220 | Waits on 220 | Owner 120 | Updated 100, one 44 px line per row.
// E_EditorScripts: Script (title over its project, owner and age) | Versions 180 | Length 110 | Look 120 | press 140.
// On a phone a row is the title with its details wrapped under it.
export const COLS = "lg:grid lg:grid-cols-[36px_minmax(0,1fr)_220px_220px_120px_100px] lg:items-center lg:gap-x-3";
export const EDITOR_COLS = "lg:grid lg:grid-cols-[minmax(0,1fr)_180px_110px_120px_140px] lg:items-center lg:gap-x-4";

export function TableHead({ editor }: { editor?: boolean }) {
  if (editor)
    return (
      <div aria-hidden className={`hidden min-h-9 border-b border-border px-6 text-xs text-muted ${EDITOR_COLS}`}>
        <span>Script</span>
        <span>Versions</span>
        <span>Length</span>
        <span>Look</span>
        <span />
      </div>
    );
  return (
    <div aria-hidden className={`hidden h-[34px] border-b border-border px-6 text-xs text-muted ${COLS}`}>
      <span />
      <span>Script</span>
      <span>Versions</span>
      <span>Waits on</span>
      <span>Owner</span>
      <span className="text-right">Updated</span>
    </div>
  );
}

/** A version's word in the lists: "Writing", "Ready to make", "Making", "Finished". */
const wordOf = (status: string) => (beingMade(status) ? "Making" : statusOf(status).label);

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

/** Length as the editor's table says it: "0:32", or "0:32 – 0:38" across its versions. */
const clock = (n: number) => `${Math.floor(n / 60)}:${String(Math.round(n % 60)).padStart(2, "0")}`;
export const lengthRange = (versions: Version[]) => {
  const s = versions.map((v) => v.seconds).filter((n) => n > 0);
  if (s.length === 0) return "—";
  const lo = Math.min(...s);
  const hi = Math.max(...s);
  return Math.round(lo) === Math.round(hi) ? clock(lo) : `${clock(lo)} – ${clock(hi)}`;
};

/** One script as the owner's table row (C_Scripts): picker, title, its versions as "● A Finished", who it waits on, its
 *  owner, when, and its menu. A removed one shows how it was removed and Restore. */
export function ScriptRow({ row: r, brandName, narrow, mayOpen, ownScript, panelTo, ownVideo, meId, waiting, onDelete, removed, onRestore, restoring, selected, onSelect }: Props) {
  const brandId = r.brand_id;
  // A script archived because a video was made from it keeps its videos and is never removed for good.
  const kept = r.removed ? r.removed === "archived" : r.versions.some((v) => !!v.project_id);
  // Where a version goes: its panel (to make it, or to see who's making it), the video made from it, or its draft.
  const chipTo = (v: Version) => (removed ? null : beingMade(v.status) && !ownVideo(v) ? panelTo(r.id, v.slot) : v.status === "approved" ? panelTo(r.id, v.slot) : v.project_id ? `/b/${brandId}/projects/${v.project_id}` : v.status === "draft" && mayOpen ? `/b/${brandId}/scripts/${r.id}` : null);
  // An editor opening someone else's published script by its title lands where Make this version is (A12), on its first
  // version ready to make; with none ready, where that version goes: the editor's own video, say (QA-4 on #1018).
  const ready = !ownScript && r.published ? (r.versions.find((v) => v.status === "approved") ?? r.versions.find((v) => chipTo(v) !== null)) : undefined;
  const titleTo = (ready && chipTo(ready)) || `/b/${brandId}/scripts/${r.id}`;
  const cell = "min-w-0 text-sm text-muted lg:text-text";
  return (
    <li className={`flex flex-wrap items-center gap-x-4 gap-y-1.5 border-b border-border px-4 py-2 lg:min-h-11 lg:px-6 lg:py-0 ${COLS} ${selected ? "bg-surface-2" : "hover:bg-surface"}`}>
      <div className="contents lg:block">
        {onSelect ? (
          <label className="grid size-control shrink-0 place-items-center lg:size-6">
            <span className="sr-only">Select {r.title}</span>
            <input type="checkbox" checked={!!selected} onChange={(e) => onSelect(e.target.checked)} className="size-4 accent-(--accent)" />
          </label>
        ) : (
          <span aria-hidden className="hidden lg:block" />
        )}
      </div>
      <div className="flex min-w-0 flex-1 basis-[60%] items-center gap-2 lg:basis-auto">
        <h3 className="flex min-w-0 items-center gap-2 font-medium">
          {mayOpen ? (
            <Link to={titleTo} className="min-h-control min-w-0 content-center break-words hover:underline lg:min-h-0 lg:truncate">
              {r.title}
            </Link>
          ) : (
            <span className="min-w-0 break-words lg:truncate">{r.title}</span>
          )}
          <FormatBadge row={r} />
        </h3>
        {r.reel_imported && <ReelChip reel={r.reel} />}
        {brandName && <span className="shrink-0 text-sm text-muted">{brandName}</span>}
        {removed && <Badge>{kept || !r.removed_at ? "Archived" : `Deleted · ${age(r.removed_at)}`}</Badge>}
        {removed && <span className="text-xs text-muted">{kept || !r.purge_on ? "Its videos are kept" : `Removed for good on ${serverTime(r.purge_on).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}`}</span>}
      </div>
      <ul className={`${cell} flex min-w-0 flex-wrap gap-x-2.5 gap-y-1 basis-full lg:basis-auto`} aria-label="Versions">
        {r.versions.map((v) => {
          const s = statusOf(v.status);
          const letter = letterOf(v.slot);
          const by = beingMade(v.status) && v.editor ? (v.editor.id === meId ? "you" : v.editor.name) : null;
          const said = `Version ${letter}, ${s.label.toLowerCase()}${by ? ` by ${by}` : ""}`;
          const to = chipTo(v);
          const chip = <Dot tone={s.tone} hollow={v.status === "draft"}>{`${letter} ${wordOf(v.status)}`}</Dot>;
          return (
            <li key={v.slot}>
              {to ? (
                <Link to={to} aria-label={said} title={said} className={`inline-flex items-center rounded-md text-xs hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${narrow ? "min-h-control" : "min-h-7"}`}>
                  {chip}
                </Link>
              ) : (
                <span aria-label={said} title={said} className="inline-flex items-center text-xs">
                  {chip}
                </span>
              )}
            </li>
          );
        })}
      </ul>
      <div className={`${cell} lg:truncate`}>{waiting ? <Dot tone="warning">{waiting}</Dot> : <span className="text-muted">Nothing</span>}</div>
      <div className={`${cell} lg:truncate`}>{r.created_by_name}</div>
      <div className="ml-auto flex shrink-0 items-center justify-end gap-1 text-xs tabular-nums text-muted">
        {removed ? (
          <Button variant="secondary" dense busy={restoring} onClick={onRestore} aria-label={`Restore ${r.title}`}>
            Restore
          </Button>
        ) : (
          <span>{age(r.created_at)}</span>
        )}
        {onDelete && <ScriptMenu title={r.title} onDelete={onDelete} />}
      </div>
    </li>
  );
}

/** One script in the editor's table (E_EditorScripts): its title over project, owner and age, its versions as A B C boxes,
 *  its length, its look, and Make a video. A script with a video running says so; one with nothing ready yet is greyed. */
export function EditorRow({ row: r, project, look, video, onMakeVideo, onDelete }: { row: Row; project: string; look: string; video: boolean; onMakeVideo?: () => void; onDelete?: () => void }) {
  const done = r.versions.some(finished);
  return (
    <li className={`flex flex-wrap items-center gap-x-4 gap-y-1.5 border-b border-border px-4 py-2 lg:min-h-14 lg:px-6 ${EDITOR_COLS} ${done ? "" : "opacity-55"}`}>
      <div className="min-w-0 basis-full lg:basis-auto">
        <h3 className="flex flex-wrap items-center gap-2 text-sm font-medium">
          <Link to={`/b/${r.brand_id}/scripts/${r.id}`} className="inline-flex min-h-control items-center break-words hover:underline lg:min-h-0">
            {r.title}
          </Link>
          <FormatBadge row={r} />
        </h3>
        <p className="text-xs text-muted">{[project, r.created_by_name, done && `ready since ${age(r.created_at)}`].filter(Boolean).join(" · ")}</p>
      </div>
      <span className="inline-flex gap-1" aria-label={`Versions ${r.versions.map((v) => letterOf(v.slot)).join(" ")}`}>
        {r.versions.map((v) => (
          <span key={v.slot} aria-hidden className="rounded-sm border border-border px-1.5 text-[11px] leading-5 text-muted">
            {letterOf(v.slot)}
          </span>
        ))}
      </span>
      <span className="text-sm tabular-nums">{lengthRange(r.versions)}</span>
      <span className="text-sm">{look}</span>
      <span className="ml-auto flex items-center gap-1 lg:ml-0 lg:justify-self-end">
        {onDelete && <ScriptMenu title={r.title} onDelete={onDelete} />}
        {!done ? (
          <span className="text-xs text-muted">Still being written</span>
        ) : video ? (
          <Dot tone="accent">Video in production</Dot>
        ) : (
          onMakeVideo && (
            <Button variant="secondary" dense onClick={onMakeVideo} aria-label={`Make a video from ${r.title}`}>
              Make a video
            </Button>
          )
        )}
      </span>
    </li>
  );
}
