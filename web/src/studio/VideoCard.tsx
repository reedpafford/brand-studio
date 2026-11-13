import { useEffect, useState } from "react";
import { Archive, Ellipsis, Film, Pencil } from "lucide-react";
import { Link } from "react-router-dom";
import { fileUrl } from "../api/upload";
import { costText, said, type Idea } from "../folders/ideas";
import type { useVideoActions } from "../projects/ReleaseVideo";
import { age } from "../scripts/status";
import { dragIdea } from "../shell/FolderTree";
import { useToast } from "../toast";
import { useVideoProject } from "../videos/VideoChat";
import { useMove } from "../videos/VideoHead";
import { Popover } from "./Popover";
import { DOT } from "./StudioShell";
import { MoveTo, Rename } from "./VideoMenu";
import { once } from "./videoData";

const ICON = { size: 16, strokeWidth: 1.75, "aria-hidden": true } as const;
/** A length as the clock on a poster reads: 0:19, 6:38. */
const clock = (seconds: number) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

/** Rename from a card. The list doesn't say which request renames this video (one made from a paste is renamed by its
 *  send, an earlier one by its own name), so the video is read first, as its own page reads it, and then the same
 *  dialog opens. */
function RenameFromCard({ i, onClose }: { i: Idea; onClose: () => void }) {
  const project = useVideoProject(i.id);
  const toast = useToast();
  const unread = project.isError || project.data === null;
  useEffect(() => {
    if (!unread) return;
    toast("Couldn’t open that video to rename it. Try again.", undefined, "error");
    onClose();
  }, [unread]); // eslint-disable-line react-hooks/exhaustive-deps
  return project.data ? <Rename id={i.id} fsId={project.data.freestyle_id ?? null} title={i.title} onClose={onClose} /> : null;
}

/** One video as a poster card: its still whole (never cut off or stretched), its length, its title, where it stands
 *  when it isn't simply delivered (with the bar of clips made while it is being made), then its look, its cost and when
 *  it last changed, each as the list gives it (and how many versions it has, when its script had several openings). It opens the video. Its menu (on hover or focus; always there on a
 *  phone) renames, moves and archives, each the current site's own request; the card itself drags onto a folder in the
 *  rail. An archived one is dimmed and has Restore instead. */
export function VideoCard({ i, brandId, video }: { i: Idea; brandId: number; video: ReturnType<typeof useVideoActions> }) {
  const [renaming, setRenaming] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const move = useMove(i.id, i.title, i.folder_id, () => {});
  const { kind, made, total } = i.status;
  const archived = kind === "archived";
  const target = { id: i.id, name: i.title, creditsUsed: 0 }; // only a release reads what was used, and a list never releases
  return (
    <div className={archived ? "vcard gone" : "vcard"}>
      <Link className="vid" to={`/s/b/${brandId}/videos/${i.id}`} draggable={!archived && i.can_manage} onDragStart={(e) => dragIdea(e, i.id, i.title)}>
        <span className="pic">
          {i.still_file_id ? <img src={fileUrl(i.still_file_id)} alt="" loading="lazy" draggable={false} /> : <Film size={20} strokeWidth={1.75} aria-hidden />}
          {i.seconds != null && (
            <span className="len" title="Length">
              {clock(i.seconds)}
            </span>
          )}
          {kind === "working" && total > 0 && (
            <span className="prog" aria-hidden>
              <i style={{ width: `${Math.round((made / total) * 100)}%` }} />
            </span>
          )}
        </span>
        <b className="clip">{i.title}</b>
        {kind !== "delivered" && (
          <span className="st">
            <i aria-hidden className={`dot ${DOT[kind] ?? ""}`} />
            <span className="clip">{said(i.status)}</span>
          </span>
        )}
        <small>{[i.style, i.versions > 1 && `${i.versions} versions`, costText(i.cost), archived ? "" : age(i.updated_at)].filter(Boolean).join(" · ")}</small>
      </Link>
      {!i.can_manage ? null : archived ? (
        <button type="button" className="btn soft" disabled={restoring} onClick={once(() => (setRestoring(true), void video.restore(target).finally(() => setRestoring(false))))}>
          Restore
        </button>
      ) : (
        <Popover
          label={`More for ${i.title}`}
          end
          button={(b) => (
            <button type="button" className="vx" aria-label={`More for ${i.title}`} title="Rename, move or archive" {...b}>
              <Ellipsis {...ICON} />
            </button>
          )}
        >
          {(close) => (
            <>
              <button type="button" role="menuitem" onClick={() => (close(), setRenaming(true))}>
                <Pencil {...ICON} /> Rename…
              </button>
              <MoveTo brandId={brandId} folder={i.folder_id} move={move} close={close} />
              <button type="button" role="menuitem" className="sep" onClick={() => (close(), video.archive(target))}>
                <Archive {...ICON} /> Archive
              </button>
            </>
          )}
        </Popover>
      )}
      {renaming && <RenameFromCard i={i} onClose={() => setRenaming(false)} />}
    </div>
  );
}
