import { useEffect, useState } from "react";
import { Archive, Copy, Download, Ellipsis, FolderInput, Pencil, Receipt } from "lucide-react";
import { Link } from "react-router-dom";
import { fileUrl } from "../api/upload";
import { flatten, useRefreshIdeas, useTree } from "../folders/ideas";
import { ARCHIVES, type useVideoActions, type VideoTarget } from "../projects/ReleaseVideo";
import { UNMADE, useVariations } from "../videos/Variations";
import { mp4, useMove, useRename } from "../videos/VideoHead";
import { Dialog } from "./Dialog";
import { Choice, Popover } from "./Popover";
import { useLock } from "./useLock";

const ICON = { size: 16, strokeWidth: 1.75, "aria-hidden": true } as const;

/** Rename this video: one field. Free, with Undo in the toast. */
export function Rename({ id, fsId, title, onClose }: { id: number; fsId: number | null; title: string; onClose: () => void }) {
  const [name, setName] = useState(title);
  const rename = useRename(id, fsId, title, onClose);
  return (
    <Dialog title="Rename this video" confirm="Rename" busy={rename.isPending} onClose={onClose} onConfirm={() => name.trim() && name.trim() !== title && rename.mutate(name)}>
      <input data-autofocus aria-label="Name" value={name} maxLength={120} onChange={(e) => setName(e.target.value)} />
    </Dialog>
  );
}

/** Make variations: two or three new videos with another hook or ending; the director writes the ideas and each then
 *  waits on its own start card with its price. What was asked and how far it has got is read while this is open. */
function Variations({ id, brandId, onClose }: { id: number; brandId: number; onClose: () => void }) {
  const [count, setCount] = useState<2 | 3>(3);
  const [part, setPart] = useState<"hook" | "ending">("hook");
  const [note, setNote] = useState("");
  const [asked, setAsked] = useState(false);
  const refresh = useRefreshIdeas();
  const { read, make } = useVariations(id, () => setAsked(true));
  const lock = useLock(make.isPending); // writing the ideas is paid: one request a press, however fast it is pressed
  const out = read.data;
  const done = asked && out?.state === "done";
  useEffect(() => {
    if (done) void refresh(); // the folder shows them at once
  }, [done]); // eslint-disable-line react-hooks/exhaustive-deps
  const seg = <T extends string | number>(label: string, value: T, set: (v: T) => void, options: [T, string][]) => (
    <div className="drow">
      <span>{label}</span>
      <div className="seg" role="group" aria-label={label}>
        {options.map(([v, words]) => (
          <button key={String(v)} type="button" aria-pressed={v === value} onClick={() => set(v)}>
            {words}
          </button>
        ))}
      </div>
    </div>
  );
  if (asked)
    return (
      <Dialog title="Variations" confirm="Done" onClose={onClose} onConfirm={onClose}>
        {out?.state === "writing" || out?.state === "held" || read.isFetching ? (
          <p className="dsub" role="status">
            {out?.state === "held" ? "Waiting for the owner’s OK to write the ideas. Nothing is charged until then." : `The director is writing ${count} ideas for ${part === "hook" ? "the hook" : "the ending"}…`}
          </p>
        ) : out?.state === "done" ? (
          <>
            <p className="dsub">Each waits on its own card, with its price, before anything is made:</p>
            <ul className="dlinks">
              {(out.videos ?? []).map((v) => (
                <li key={v.id}>
                  <Link to={`/s/b/${brandId}/videos/${v.id}`} onClick={onClose}>
                    {v.title}
                  </Link>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="dsub" role="alert">
            {UNMADE[out?.state ?? "failed"] ?? UNMADE.failed}
          </p>
        )}
      </Dialog>
    );
  const blocked = out?.blocked || make.error?.message;
  return (
    <Dialog title="Make variations" confirm="Make variations" busy={make.isPending || read.isPending || !!out?.blocked} onClose={onClose} onConfirm={() => lock((done) => make.mutate({ count, part, note }, { onSettled: done }))}>
      <p className="dsub">New videos with another hook or ending. The cast, the look and every other clip stay; only the changed clips are made.</p>
      {seg("How many", count, setCount, [[2, "2"], [3, "3"]])}
      {seg("Change", part, setPart, [["hook", "The hook"], ["ending", "The ending"]])}
      <input aria-label="Note, if you have one" placeholder="Note, if you have one: “Open on the empty lot”" value={note} onChange={(e) => (setNote(e.target.value), make.reset())} />
      {blocked && (
        <p className="dsub" role="alert">
          {blocked}
        </p>
      )}
    </Dialog>
  );
}

/** "Move to": Unsorted, then the brand's folders in tree order, the one it is in ticked. Free, with Undo in the toast.
 *  `move` is held by what stays on the page once the menu has closed. */
export function MoveTo({ brandId, folder, move, close }: { brandId: number; folder: number | null; move: ReturnType<typeof useMove>; close: () => void }) {
  const tree = useTree(brandId).data;
  return (
    <>
      <h6>Move to</h6>
      {[{ id: null as number | null, name: "Unsorted", depth: 0 }, ...flatten(tree?.folders ?? [])].map((f) => (
        <Choice key={f.id ?? "none"} checked={f.id === folder} disabled={move.isPending} onPick={() => (close(), f.id !== folder && !move.isPending && move.mutate(f.id))}>
          <span style={{ paddingLeft: f.depth * 12 }}>{f.name}</span>
        </Choice>
      ))}
    </>
  );
}

/** Archive asks first: what it does, said before it is done, and the server's own words if it refuses. */
export function ArchiveAsk({ asking }: { asking: ReturnType<typeof useVideoActions>["asking"] }) {
  if (!asking) return null;
  return (
    <Dialog title={`Archive “${asking.target.name}”?`} confirm="Archive" busy={asking.busy} onClose={asking.no} onConfirm={asking.yes}>
      <p className="dsub">{ARCHIVES}</p>
      {asking.problem && (
        <p className="dsub" role="alert">
          Couldn’t do that. Nothing changed. {asking.problem}
        </p>
      )}
    </Dialog>
  );
}

/** A video's "…" menu: what it cost (opens "So far"), rename, move to a folder, make variations and download every
 *  clip once it is delivered, download the cut, and archive, which asks first and can be undone from its toast. Each
 *  is the current site's own request. `onCost`: only the owner's dollars open; `may`: what this video allows now. */
export function VideoMenu({ target, brandId, fsId, folder, film, may, onCost, video }: { target: VideoTarget; brandId: number; fsId: number | null; folder: number | null; film: number | null; may: { change: boolean; variations: boolean; zip: boolean; archive: boolean }; onCost?: () => void; video: ReturnType<typeof useVideoActions> }) {
  const { id, name: title } = target;
  const [open, setOpen] = useState<"" | "rename" | "variations">("");
  const [moving, setMoving] = useState(false);
  const move = useMove(id, title, folder, () => {});
  return (
    <>
      <Popover
        label={`More for ${title}`}
        end
        button={(b) => (
          <button type="button" className="btn ghost square" aria-label="More" title="More" {...b} onClick={() => (setMoving(false), b.onClick())}>
            <Ellipsis {...ICON} />
          </button>
        )}
      >
        {(close) =>
          moving ? (
            <MoveTo brandId={brandId} folder={folder} move={move} close={close} />
          ) : (
            <>
              {onCost && (
                <button type="button" role="menuitem" onClick={() => (close(), onCost())}>
                  <Receipt {...ICON} /> What it cost…
                </button>
              )}
              {may.change && (
                <>
                  <button type="button" role="menuitem" onClick={() => (close(), setOpen("rename"))}>
                    <Pencil {...ICON} /> Rename…
                  </button>
                  <button type="button" role="menuitem" onClick={() => setMoving(true)}>
                    <FolderInput {...ICON} /> Move to folder…
                  </button>
                </>
              )}
              {may.variations && (
                <button type="button" role="menuitem" onClick={() => (close(), setOpen("variations"))}>
                  <Copy {...ICON} /> Make variations…
                </button>
              )}
              {film != null && (
                <a role="menuitem" href={fileUrl(film)} download={mp4(title)} onClick={close}>
                  <Download {...ICON} /> Download MP4
                </a>
              )}
              {may.zip && (
                <a role="menuitem" href={`/api/projects/${id}/clips.zip`} download={mp4(title).replace(/\.mp4$/, "-clips.zip")} onClick={close}>
                  <Download {...ICON} /> Download every clip (.zip)
                </a>
              )}
              {may.archive && (
                <button type="button" role="menuitem" className="sep" onClick={() => (close(), video.archive(target))}>
                  <Archive {...ICON} /> Archive
                </button>
              )}
            </>
          )
        }
      </Popover>
      {open === "rename" && <Rename id={id} fsId={fsId} title={title} onClose={() => setOpen("")} />}
      {open === "variations" && <Variations id={id} brandId={brandId} onClose={() => setOpen("")} />}
      <ArchiveAsk asking={video.asking} />
    </>
  );
}
