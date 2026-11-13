import { Fragment, useState, type DragEvent, type ReactNode } from "react";
import { Ellipsis, Film, Folder, FolderPlus, Pencil, Plus, Trash2, Upload } from "lucide-react";
import { Link } from "react-router-dom";
import { clips as clipsWord, countIn, inside, trail, useFolderActions, useFootageFolders } from "../library/FootageFolders";
import { useFootage, type Footage } from "../library/FootageTab";
import { useBrands } from "../shell/useBrands";
import { Dialog } from "./Dialog";
import { AddClip, ClipOpen, ClipTile, Failed, Head, Hold, ICON, Loading } from "./libraryParts";
import { Popover } from "./Popover";

const FIRST = 24; // a folder's clips shown before "Show all"

/** A folder's own clips as small tiles; a long folder shows its first two dozen until asked for the rest. */
function Strip({ clips, onOpen }: { clips: Footage[]; onOpen: (id: number) => void }) {
  const [all, setAll] = useState(false);
  return (
    <div className="fstrip">
      {(all ? clips : clips.slice(0, FIRST)).map((c) => (
        <ClipTile key={c.id} clip={c} onOpen={() => onOpen(c.id)} />
      ))}
      {!all && clips.length > FIRST && (
        <button type="button" className="btn ghost" onClick={() => setAll(true)}>
          Show all {clips.length}
        </button>
      )}
    </div>
  );
}

/** Library › Footage: the brand's real clips in their folders, each folder with its clips counted at any depth. A
 *  folder opens to show the folders and clips in it; a clip opens larger. A clip dropped on the page, or chosen, is
 *  added to the open folder. */
export function FootageTab({ brandId }: { brandId: number }) {
  const footage = useFootage(brandId);
  const folders = useFootageFolders(brandId);
  const brand = useBrands().data?.find((b) => b.id === brandId)?.name ?? "this brand";
  const [at, setAt] = useState<number | null>(null);
  const [asking, setAsking] = useState<"clip" | "new" | "rename" | "delete" | null>(null);
  const [name, setName] = useState("");
  const [dropped, setDropped] = useState<File | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const rows = folders.data ?? [];
  const all = footage.data ?? [];
  const { folder, make, rename, remove, gone, count, up } = useFolderActions(brandId, rows, all, at, setAt, () => setAsking(null));
  const path = trail(rows, at);
  const loose = all.filter((c) => c.folder_id == null);
  const shown = all.find((c) => c.id === open);
  const naming = asking === "new" ? make : rename;
  const ask = (what: "new" | "rename" | "delete") => {
    setName(what === "rename" ? (folder?.name ?? "") : "");
    [make, rename, remove].forEach((m) => m.reset());
    setAsking(what);
  };
  const add = (file: File | null) => (setDropped(file), setAsking("clip"));
  const drop = (e: DragEvent) => {
    e.preventDefault();
    const file = [...e.dataTransfer.files].find((f) => f.type.startsWith("video/"));
    if (file) add(file);
  };
  const addButton = (
    <button type="button" className="btn go" onClick={() => add(null)}>
      <Plus {...ICON} />
      Add footage
    </button>
  );
  const newFolder = (
    <button type="button" className="btn ghost" onClick={() => ask("new")}>
      <FolderPlus {...ICON} />
      {folder ? `New folder in ${folder.name}` : "New folder"}
    </button>
  );
  const list = (parent: number | null, depth: number): ReactNode =>
    rows
      .filter((f) => (f.parent_id ?? null) === parent)
      .map((f) => {
        const isOpen = path.some((p) => p.id === f.id);
        const own = all.filter((c) => c.folder_id === f.id);
        return (
          <Fragment key={f.id}>
            <div className="frow" style={{ paddingLeft: 8 + depth * 24 }}>
              <button type="button" className="rl" aria-expanded={isOpen} onClick={() => setAt(isOpen ? (f.parent_id ?? null) : f.id)}>
                <Folder {...ICON} />
                <b className="clip">{f.name}</b>
                <span className="r">{clipsWord(countIn(all, inside(rows, f.id)))}</span>
              </button>
              {f.id === at && f.can_manage && (
                <Popover
                  label={`More for ${f.name}`}
                  end
                  button={(p) => (
                    <button type="button" className="btn ghost square" aria-label={`More for ${f.name}`} {...p}>
                      <Ellipsis {...ICON} />
                    </button>
                  )}
                >
                  {(close) => (
                    <>
                      <button type="button" role="menuitem" onClick={() => (close(), ask("rename"))}>
                        <Pencil {...ICON} />
                        Rename…
                      </button>
                      <button type="button" role="menuitem" onClick={() => (close(), ask("delete"))}>
                        <Trash2 {...ICON} />
                        Delete folder…
                      </button>
                    </>
                  )}
                </Popover>
              )}
            </div>
            {isOpen && list(f.id, depth + 1)}
            {isOpen && (
              <div className="inside" style={{ paddingLeft: 8 + (depth + 1) * 24 }}>
                {own.length > 0 ? <Strip clips={own} onOpen={setOpen} /> : f.id === at && !rows.some((x) => x.parent_id === f.id) && <p className="hint">No clips in this folder yet.</p>}
              </div>
            )}
          </Fragment>
        );
      });
  return (
    <>
      <Head action={all.length + rows.length > 0 && addButton} />
      <div className="view">
        <div className="page lib" onDragOver={(e) => e.preventDefault()} onDrop={drop}>
          {footage.isPending || folders.isPending ? (
            <Loading />
          ) : footage.isError || folders.isError ? (
            <Failed icon={Film} what="the footage" error={(footage.error ?? folders.error)!} again={() => (void footage.refetch(), void folders.refetch())} />
          ) : all.length + rows.length === 0 ? (
            <Hold
              icon={Film}
              title={`No footage for ${brand} yet`}
              action={
                <>
                  {addButton}
                  {newFolder}
                </>
              }
            >
              Add real clips once, each with what it shows. The director sees how things look and work, and can cut one in.
            </Hold>
          ) : (
            <div className="rows">
              {list(null, 0)}
              {loose.length > 0 && (
                <section aria-label="Not in a folder">
                  <h3>
                    Not in a folder <small>{clipsWord(loose.length)}</small>
                  </h3>
                  <Strip clips={loose} onOpen={setOpen} />
                </section>
              )}
              <div className="drop">
                <Upload {...ICON} />
                <span>Drop a clip here to add it to {folder ? folder.name : "the top"}.</span>
                {newFolder}
              </div>
              <p className="hint also">
                Moving a clip or a folder, changing what a clip shows and marking a competitor’s clip are on <Link to={`/b/${brandId}/library/footage`}>the current site</Link>.
              </p>
            </div>
          )}
        </div>
      </div>
      {asking === "clip" && <AddClip brandId={brandId} folder={path.map((f) => f.name).join("/")} productId={null} file={dropped} onClose={() => setAsking(null)} />}
      {(asking === "new" || asking === "rename") && (
        <Dialog title={asking === "rename" ? `Rename ${folder?.name}` : folder ? `New folder inside ${folder.name}` : "New folder"} confirm={asking === "new" ? "Make the folder" : "Rename"} busy={!name.trim() || naming.isPending} onClose={() => setAsking(null)} onConfirm={() => naming.mutate(name)}>
          <input data-autofocus aria-label="Name" value={name} maxLength={120} placeholder="Product shots" onChange={(e) => (setName(e.target.value), naming.reset())} />
          {naming.isError && (
            <p className="dsub bad" role="alert">
              {naming.error.message}
            </p>
          )}
        </Dialog>
      )}
      {asking === "delete" && folder && (
        <Dialog title={`Delete ${folder.name}?`} confirm="Delete folder" busy={remove.isPending} onClose={() => setAsking(null)} onConfirm={() => remove.mutate()}>
          <p className="dsub">{count ? `Its ${clipsWord(count)} move up to ${up}${gone.size > 1 ? ", and the folders inside it go with it" : ""}. No clip is deleted, and Undo brings it all back.` : "Nothing is in it."}</p>
          {remove.isError && (
            <p className="dsub bad" role="alert">
              {remove.error.message}
            </p>
          )}
        </Dialog>
      )}
      {shown && <ClipOpen brandId={brandId} clip={shown} onClose={() => setOpen(null)} />}
    </>
  );
}
