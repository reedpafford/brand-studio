import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ChevronLeft, ChevronRight, CircleStop, Download, Ellipsis, Folder, Inbox, Lock, Pencil, SlidersHorizontal, X } from "lucide-react";
import { Link } from "react-router-dom";
import { api, must, polled } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { Button, Dialog, Field, Menu, MenuItem, Skeleton, useToast } from "../components";
import { flatten, said, StatusDot, useRefreshIdeas, useTree, type Status } from "../folders/ideas";
import { useLocks } from "./locks";

export type Head = components["schemas"]["Head"];
type Money = components["schemas"]["Money"];

/** One video's header (S3, P-04), read from the server: its status with the reason, used, up to, budget, folder. */
export function useHead(projectId: number) {
  return useQuery({
    queryKey: ["idea", projectId],
    enabled: projectId > 0,
    refetchInterval: (q) => (q.state.data?.status.kind === "working" ? 10_000 : false),
    queryFn: () => polled(api.GET("/projects/{project_id}/idea", { params: { path: { project_id: projectId } } }), null),
  });
}

/** A download's file name, from the video's title. */
export const mp4 = (title: string) => `${title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "video"}.mp4`;

const dollars = (m: Money) => `$${(m.usd ?? 0).toFixed(2)}`;
const credits = (m: Money, upTo = false) => (upTo ? Math.ceil(m.credits - 1e-9) : Math.round(m.credits));

/** The money in the header (S3): the owner's in dollars, an editor's in credits and % of the budget (rule 4). The last part
 *  is the figure that matters, in the text colour: "$6.12 spent · up to $16.86", "96 of up to 164 credits". `short`: the
 *  phone's line (P-04), the most only. */
export function moneyOf(h: Head, short = false, started = h.spent.credits > 0): [string, string] {
  const owner = h.spent.usd != null;
  const spent = started; // before Make it: "No generation started" (Reed, 4 Nov: the treatment is a small planning spend, in Usage)
  // While it plans before the OK (right after New video's Make it), "Working" beside "No generation started" read as a
  // contradiction (MAIN's Claymation run): it says what it's doing, and still that nothing is generated.
  const none = h.status.kind === "working" ? "Planning, no generation yet ·" : "No generation started ·";
  const top = h.up_to;
  if (h.actual) {
    // The owner's uncapped test site (Reed, 6 Nov): what the providers really charged, and the likely cost; no budget.
    // The whole video's spend beside one run's estimate, each said for what it is (QA on #1396).
    const more = [h.listed_usd ? `$${h.listed_usd.toFixed(2)} of it at list price` : "", h.unreported ? "more not reported yet" : ""].filter(Boolean).join(", ");
    const real = `This video so far ${dollars(h.spent)}${more ? ` (${more})` : ""}`;
    const going = ["working", "waiting", "needs_you"].includes(h.status.kind); // else the estimate is for the next run
    const about = h.expected ? `${going ? "this run" : "next run"} about ${dollars(h.expected)} (estimate)` : "estimating…";
    if (short) return ["", spent ? `${dollars(h.spent)} so far` : `About ${dollars(h.expected ?? h.spent)} (estimate)`];
    return [spent ? `${real} ·` : none, about];
  }
  // Past the budget mid-run (S3-06, S3-07); a start card waiting has spent nothing (S3-02). Never a "budget" below what's
  // spent (Flow-QA S7): then it's the whole video's spent against its "up to", as any other time.
  if (h.status.kind === "waiting" && spent && h.budget && h.budget.credits >= h.spent.credits) {
    if (owner) return [`${dollars(h.spent)} spent ·`, `budget ${dollars(h.budget)}`];
    const pct = h.budget.credits > 0 ? Math.round((100 * h.spent.credits) / h.budget.credits) : 0;
    return [`${credits(h.spent)} credits ·`, `${pct}% of the budget`];
  }
  if (!top) return short ? ["", "estimating…"] : [spent ? (owner ? `${dollars(h.spent)} spent ·` : `${credits(h.spent)} credits used ·`) : none, "estimating…"];
  const most = owner ? `up to ${dollars(top)}` : `up to ${credits(top, true)} credits`;
  if (h.status.kind === "delivered") return [owner ? `${dollars(h.spent)} of` : `${credits(h.spent)} of`, most];
  if (short) return ["", most];
  return [spent ? (owner ? `${dollars(h.spent)} spent ·` : `${credits(h.spent)} credits used ·`) : none, most];
}

/** The status in the header: the dot, the words and the reason (S-gaps-01). While it works the reason is where the run is
 *  ("starting", "revising"); the clip count is the progress card's. */
export function headStatus(status: Status, working?: string | null): Status {
  return status.kind === "working" ? { ...status, reason: working ?? null } : status;
}

const WORDS: Record<Status["kind"], string> = { working: "text-accent-text", needs_you: "text-warning", waiting: "text-muted", needs_fix: "text-danger", delivered: "text-success", stopped: "text-muted", archived: "text-muted" };
function StatusWords({ status }: { status: Status }) {
  return (
    <span className={`inline-flex min-w-0 items-center gap-1.5 text-xs font-medium ${WORDS[status.kind]}`}>
      <StatusDot status={status} />
      <span className="truncate">{said(status)}</span>
    </span>
  );
}

const chip = "inline-flex h-[26px] shrink-0 items-center gap-[5px] whitespace-nowrap rounded-sm border border-border-button bg-surface px-[9px] text-xs font-medium text-text";

/** The chips under the title (S3-01): Format · Style, Cast, Length, then Locks +N, whose menu turns each lock on or off
 *  (S-gaps-03 1). The first three are labels; a lock icon says that choice is locked. */
function Chips({ projectId, head, cast, lookOnly }: { projectId: number; head: Head; cast: string[]; lookOnly: boolean }) {
  const { locks, save } = useLocks(projectId);
  const on = locks?.locks;
  const castWords = cast.length > 2 ? `${cast.slice(0, 2).join(", ")} +${cast.length - 2}` : cast.join(", ");
  const length = head.seconds ? (head.seconds >= 120 ? `about ${Math.round(head.seconds / 60)} min` : `about ${head.seconds} s`) : null;
  const screens = on?.screens?.length ?? 0;
  // The End line lock waits on Reed's answer (the brand's end line is gone, #1315): not offered for now.
  const more = (on?.song ? 1 : 0) + (screens ? 1 : 0);
  const icon = (locked?: boolean) => locked && <Lock size={12} strokeWidth={1.75} aria-hidden className="text-muted" />;
  const rows: { id: "cast" | "look" | "length" | "song"; label: string; value: string; off?: boolean }[] = [
    { id: "cast", label: "Cast", value: castWords || "Not cast yet" },
    { id: "look", label: "Style", value: head.style },
    { id: "length", label: "Length", value: length ?? "Not planned yet" },
    { id: "song", label: "Song", value: head.song ? "Its song" : head.format ? `Not in a${/^[AEIOU]/.test(head.format) ? "n" : ""} ${head.format} video` : "Not in this video", off: !head.song },
  ];
  return (
    <div className="flex flex-wrap gap-1.5" aria-label="What it builds around">
      <span className={chip}>
        {icon(on?.look)}
        {head.format ? `${head.format} · ${head.style}` : head.style}
      </span>
      {castWords && (
        <span className={chip}>
          {icon(on?.cast)}
          <span className="font-normal text-muted">Cast</span>
          {castWords}
        </span>
      )}
      {length && (
        <span className={chip}>
          {icon(on?.length)}
          <span className="font-normal text-muted">Length</span>
          {length}
        </span>
      )}
      <Menu
        title="Locks"
        trigger={(p) => (
          <button type="button" {...p} className={`${chip} ${p["aria-expanded"] ? "border-[#c9ccf6] bg-accent-soft text-accent-text" : "hover:bg-surface-2"}`}>
            <SlidersHorizontal size={12} strokeWidth={1.75} aria-hidden />
            {more ? `Locks +${more}` : "Locks"}
          </button>
        )}
      >
        {() =>
          !locks ? (
            <Skeleton className="h-40 w-80" />
          ) : (
            <div className="w-full lg:w-[316px]">
              <p className="flex items-center px-2.5 pb-1.5 pt-1 text-xs">
                <span className="font-semibold text-muted">Locks</span>
                <span className="ml-auto text-muted">one press each</span>
              </p>
              {rows.map((r) => (
                <label key={r.id} className={`flex min-h-control items-center gap-3 px-2.5 lg:min-h-[32px] ${r.off || lookOnly ? "" : "cursor-pointer"}`}>
                  <span className="w-[70px] shrink-0 text-sm font-medium">{r.label}</span>
                  <span className="min-w-0 flex-1 truncate text-sm text-muted">{r.value}</span>
                  <input
                    type="checkbox"
                    role="switch"
                    aria-label={`Lock the ${r.label.toLowerCase()}`}
                    checked={!!on?.[r.id]}
                    disabled={r.off || lookOnly || save.isPending}
                    onChange={() => save.mutate({ ...locks, locks: { ...locks.locks, [r.id]: !on?.[r.id] } })}
                    className="peer sr-only"
                  />
                  <span aria-hidden className={`relative h-[18px] w-[30px] shrink-0 rounded-full transition-colors peer-focus-visible:outline-2 peer-focus-visible:outline-focus ${on?.[r.id] ? "bg-accent" : "bg-border-button"} ${r.off ? "opacity-50" : ""}`}>
                    <i className={`absolute top-[2px] size-[14px] rounded-full bg-white shadow-[0_1px_2px_rgb(0_0_0/0.2)] ${on?.[r.id] ? "right-[2px]" : "left-[2px]"}`} />
                  </span>
                </label>
              ))}
              <p className="mt-1 flex min-h-control items-center gap-3 border-t border-border px-2.5 lg:min-h-[32px]">
                <span className="w-[70px] shrink-0 text-sm font-medium">Screens</span>
                <span className="min-w-0 flex-1 text-sm text-muted">{screens ? `${screens} · picked in the plan` : "Picked in the plan"}</span>
                <Lock size={14} strokeWidth={1.75} aria-hidden className="text-muted" />
              </p>
            </div>
          )
        }
      </Menu>
    </div>
  );
}

/** The video's ⋯ menu (S-gaps-03 2): Move to folder…, Download MP4 once a cut exists, then Release this version while it's
 *  being made or Archive once it's done. On a phone it also holds Stop, as its top bar has no room for the button. */
export function VideoMenu({ title, cut, onMove, onRename, onRelease, onArchive, onStop }: { title: string; cut?: { file: number; name: string } | null; onMove?: () => void; onRename?: () => void; onRelease?: () => void; onArchive?: () => void; onStop?: () => void }) {
  if (!onMove && !onRename && !cut && !onRelease && !onArchive && !onStop) return null;
  const run = (close: () => void, go: () => void) => () => (close(), go());
  return (
    <Menu
      title={`More for ${title}`}
      align="right"
      trigger={(p) => (
        <button type="button" {...p} aria-label={`More for ${title}`} className="grid size-control place-items-center rounded-md text-muted hover:bg-surface-2 lg:size-8">
          <Ellipsis size={20} strokeWidth={1.75} aria-hidden className="lg:size-4" />
        </button>
      )}
    >
      {(close) => (
        <>
          {onStop && (
            <MenuItem onClick={run(close, onStop)}>
              <CircleStop size={16} strokeWidth={1.75} aria-hidden /> Stop the director
            </MenuItem>
          )}
          {onRename && (
            <MenuItem onClick={run(close, onRename)}>
              <Pencil size={16} strokeWidth={1.75} aria-hidden /> Rename…
            </MenuItem>
          )}
          {onMove && (
            <MenuItem onClick={run(close, onMove)}>
              <Folder size={16} strokeWidth={1.75} aria-hidden /> Move to folder…
            </MenuItem>
          )}
          {cut && (
            <a role="menuitem" href={fileUrl(cut.file)} download={cut.name} onClick={close} className="flex min-h-control items-center gap-3 rounded-md px-3 text-base text-text hover:bg-surface-2 lg:min-h-9 lg:text-sm">
              <Download size={16} strokeWidth={1.75} aria-hidden /> Download MP4
            </a>
          )}
          {(onRelease || onArchive) && <div className="my-1 h-px bg-border" />}
          {onRelease && (
            <MenuItem danger onClick={run(close, onRelease)}>
              <X size={16} strokeWidth={1.75} aria-hidden /> Release this version
            </MenuItem>
          )}
          {onArchive && (
            <MenuItem onClick={run(close, onArchive)}>
              <Archive size={16} strokeWidth={1.75} aria-hidden /> Archive
            </MenuItem>
          )}
        </>
      )}
    </Menu>
  );
}

/** Move to folder…: the brand's folders in tree order, or Unsorted. Free, and the tree shows it at once. */
export function MoveDialog({ brandId, projectId, title, now, onClose }: { brandId: number; projectId: number; title: string; now: number | null; onClose: () => void }) {
  const tree = useTree(brandId).data;
  const refresh = useRefreshIdeas();
  const client = useQueryClient();
  const again = () => Promise.all([refresh(), client.invalidateQueries({ queryKey: ["idea", projectId] }), client.invalidateQueries({ queryKey: ["project", projectId] })]); // the tree and the header's crumb
  const toast = useToast();
  const [to, setTo] = useState<number | null>(now);
  const move = useMutation({
    mutationFn: () => must(api.POST("/folders/file", { body: { kind: "video", ids: [projectId], folder_id: to } })),
    onSuccess: async () => {
      await again();
      onClose();
      const back = () => must(api.POST("/folders/file", { body: { kind: "video", ids: [projectId], folder_id: now } })).then(again, (e: Error) => toast(e.message, undefined, "error"));
      toast(`Moved "${title}".`, () => void back());
    },
  });
  const places = [{ id: null as number | null, name: "Unsorted", depth: 0 }, ...flatten(tree?.folders ?? [])];
  return (
    <Dialog title={`Move ${title} to…`} cancelLabel="Not now" actionLabel="Move" busy={move.isPending} holdReason={to === now ? "Pick another folder" : (move.error?.message ?? null)} onCancel={onClose} onConfirm={() => move.mutate()}>
      <div role="radiogroup" aria-label="Move to" className="-mx-2 max-h-80 overflow-y-auto">
        {places.map((f) => (
          <button key={f.id ?? "none"} type="button" role="radio" aria-checked={to === f.id} onClick={() => (setTo(f.id), move.reset())} style={{ paddingLeft: 8 + f.depth * 16 }} className={`flex min-h-control w-full items-center gap-2 rounded-md pr-2 text-left text-sm text-text lg:min-h-[30px] ${to === f.id ? "bg-surface-2 font-medium" : "hover:bg-surface-2"}`}>
            {f.id === null ? <Inbox size={14} strokeWidth={1.75} aria-hidden /> : <Folder size={14} strokeWidth={1.75} aria-hidden />}
            {f.name}
          </button>
        ))}
      </div>
    </Dialog>
  );
}

/** The chat's header (S3-01, S3-09; P-04 on a phone): the crumb, Stop and ⋯; the title, status and money; the chips. */
export function VideoHead({ brand, projectId, head, status, cast, lookOnly, phone, menu, stop, started }: { brand: { id: number; name: string }; projectId: number; head: Head; status: Status; cast: string[]; lookOnly: boolean; phone: boolean; menu: ReactNode; stop?: { busy: boolean; onPress: () => void } | null; started?: boolean }) {
  const [lead, most] = moneyOf(head, phone, started);
  if (phone)
    return (
      <header role="banner" className="flex min-h-[52px] items-center gap-2 border-b border-border bg-surface px-3">
        <Link to={`/b/${brand.id}/videos${head.folder ? `?folder=${head.folder.id}` : ""}`} aria-label={`Back to ${head.folder?.name ?? brand.name}`} className="grid size-control shrink-0 place-items-center rounded-md text-muted">
          <ChevronLeft size={20} strokeWidth={1.75} aria-hidden />
        </Link>
        <div className="flex min-w-0 flex-1 flex-col">
          <h1 className="truncate font-semibold">{head.title}</h1>
          <p className="flex min-w-0 items-center gap-1 text-xs tabular-nums text-muted">
            <StatusWords status={status} />
            {most && <span className="shrink-0">· {lead ? `${lead} ` : ""}{most}</span>}
          </p>
        </div>
        {menu}
      </header>
    );
  return (
    <header role="banner" className="flex flex-col gap-2 border-b border-border px-5 py-2.5">
      <div className="flex min-h-8 items-center gap-2">
        <nav aria-label="Where it is" className="flex min-w-0 items-center gap-1.5 whitespace-nowrap text-sm text-muted">
          <Link to={`/b/${brand.id}/videos`} className="hover:text-text">
            {brand.name}
          </Link>
          <ChevronRight size={12} strokeWidth={1.75} aria-hidden />
          <Link to={`/b/${brand.id}/videos?folder=${head.folder?.id ?? "none"}`} className="truncate hover:text-text">
            {head.folder?.name ?? "Unsorted"}
          </Link>
        </nav>
        <span className="flex-1" />
        {stop && (
          <Button variant="secondary" dense icon={CircleStop} busy={stop.busy} onClick={stop.onPress}>
            Stop
          </Button>
        )}
        {menu}
      </div>
      <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
        {/* beside the cut editor the chat is 400px: the status and the money go under the title (S7) */}
        <h1 className="min-w-0 max-w-[300px] shrink-0 truncate text-lg font-semibold">{head.title}</h1>
        <StatusWords status={status} /> {/* its reason gives way before the title does (a question's words are long) */}
        <span className="flex-1" />
        {/* the owner's full line can be long (H20): it wraps under the title, never past the column */}
        <p className="min-w-0 max-w-full text-sm tabular-nums text-muted">
          {lead && `${lead} `}
          <b className="whitespace-nowrap font-medium text-text">{most}</b>
        </p>
      </div>
      <Chips projectId={projectId} head={head} cast={cast} lookOnly={lookOnly} />
    </header>
  );
}

/** Rename… (Reed, 4 Nov: the old page's rename lives in the video's ⋯ menu): a made-from-chat video's title, else the video's
 *  name. Free, with Undo. */
export function RenameDialog({ projectId, freestyleId, title, onClose }: { projectId: number; freestyleId: number | null; title: string; onClose: () => void }) {
  const client = useQueryClient();
  const toast = useToast();
  const refreshIdeas = useRefreshIdeas(); // the tree, the folder's cards and lists show the new name too
  const [name, setName] = useState(title);
  const again = () => Promise.all([refreshIdeas(), ...[["idea", projectId], ["project", projectId], ["freestyle", freestyleId]].map((queryKey) => client.invalidateQueries({ queryKey }))]);
  const save = async (to: string): Promise<void> => {
    if (freestyleId) await must(api.PATCH("/freestyles/{freestyle_id}", { params: { path: { freestyle_id: freestyleId } }, body: { title: to } }));
    else await must(api.PATCH("/projects/{project_id}", { params: { path: { project_id: projectId } }, body: { name: to } }));
  };
  const rename = useMutation({
    mutationFn: () => save(name.trim()),
    onSuccess: () => {
      void again();
      onClose();
      toast(`Renamed to “${name.trim()}”.`, () => void save(title).then(again, (e: Error) => toast(e.message, undefined, "error")));
    },
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  return (
    <Dialog title="Rename this video" actionLabel="Rename" busy={rename.isPending} onCancel={onClose} onConfirm={() => name.trim() && name.trim() !== title && rename.mutate()}>
      <Field label="Name" value={name} maxLength={120} autoFocus onChange={(e) => setName(e.target.value)} />
    </Dialog>
  );
}
