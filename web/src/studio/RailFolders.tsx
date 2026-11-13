import { useEffect, useRef, useState, type ReactNode } from "react";
import { useMutation } from "@tanstack/react-query";
import { Folder, Plus } from "lucide-react";
import { Link } from "react-router-dom";
import { folderWrites } from "../folders/FolderActions";
import { UNSORTED, useRefreshIdeas, useTree, type Branch } from "../folders/ideas";
import { IDEA, useDropIdea } from "../shell/FolderTree";
import { useToast } from "../toast";
import "./videos.css";

const ICON = { size: 16, strokeWidth: 1.75, "aria-hidden": true } as const;

/** A new folder, typed where it will sit: Enter makes it at the top of the brand's folders; Escape, an empty name or
 *  leaving the field puts it away. If the server refuses (a name already taken) its own words show and the field stays. */
export function NewFolder({ brandId, onDone }: { brandId: number; onDone: () => void }) {
  const [name, setName] = useState("");
  const field = useRef<HTMLInputElement>(null);
  useEffect(() => {
    field.current?.focus({ preventScroll: true }); // a phone's row of pills brings it into view sideways; the page stays put
    field.current?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
  }, []);
  const refresh = useRefreshIdeas();
  const toast = useToast();
  const make = useMutation({
    mutationFn: () => folderWrites.make(brandId, name, null),
    onSuccess: async ({ data }) => {
      await refresh();
      toast(`“${data!.name}” is ready. Drag a video onto it, or use “Move to” in a video’s menu.`);
      onDone();
    },
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  return (
    <label className="nf">
      <Folder {...ICON} />
      <input
        ref={field}
        aria-label="New folder name"
        placeholder="Folder name"
        maxLength={120}
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") onDone();
          else if (e.key === "Enter" && !name.trim()) onDone();
          else if (e.key === "Enter" && !make.isPending) make.mutate();
        }}
        onBlur={() => !make.isPending && onDone()}
      />
    </label>
  );
}

/** The rail's folders: each with how many videos are in it, Unsorted last, and a "+" that types a new one straight
 *  into the list. A video's card dragged onto one is filed there (the current site's own drop, with Undo). */
export function RailFolders({ brandId, base, folder }: { brandId: number; base: string; folder: string | null }) {
  const tree = useTree(brandId).data;
  const [adding, setAdding] = useState(false);
  const [over, setOver] = useState<string | null>(null);
  const [carrying, setCarrying] = useState(false); // a card is being dragged: every folder lights up as a place to drop it
  useEffect(() => {
    const on = (e: DragEvent) => setCarrying(!!e.dataTransfer?.types.includes(IDEA));
    const off = () => setCarrying(false);
    document.addEventListener("dragstart", on);
    document.addEventListener("dragend", off);
    document.addEventListener("drop", off);
    return () => {
      document.removeEventListener("dragstart", on);
      document.removeEventListener("dragend", off);
      document.removeEventListener("drop", off);
    };
  }, []);
  const toast = useToast();
  const fileIdea = useDropIdea((message, undo) => toast(message, undo, undo ? "success" : "error")); // no Undo: nothing moved, and the words are the server's
  const rows = (branches: Branch[], depth = 0): ReactNode =>
    branches.map((b) => {
      const key = b.id == null ? UNSORTED : String(b.id); // ?folder=: Unsorted has no id
      return [
        <Link
          key={key}
          to={`${base}/videos?folder=${key}`}
          aria-current={folder === key ? "page" : undefined}
          className={over === key ? "over" : undefined}
          style={depth ? { paddingLeft: 10 + depth * 16 } : undefined}
          onDragOver={(e) => {
            if (!e.dataTransfer.types.includes(IDEA)) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = "move";
            setOver(key);
          }}
          onDragLeave={(e) => !e.currentTarget.contains(e.relatedTarget as Node | null) && setOver(null)}
          onDrop={(e) => (setOver(null), void fileIdea(e, b))}
        >
          <Folder {...ICON} />
          <span className="clip">{b.name}</span>
          <span className="n" title={`${b.count} video${b.count === 1 ? "" : "s"}`}>
            {b.count}
          </span>
        </Link>,
        rows(b.folders ?? [], depth + 1),
      ];
    });
  return (
    <>
      <h6>
        <span id="studio-folders">Folders</span>
        <span className="grow" />
        <button type="button" className="btn ghost square" aria-label="New folder" title="New folder" onClick={() => setAdding(true)}>
          <Plus {...ICON} />
        </button>
      </h6>
      <div className={carrying ? "nav drop" : "nav"} role="group" aria-labelledby="studio-folders">
        {adding && <NewFolder brandId={brandId} onDone={() => setAdding(false)} />}
        {tree && rows([...tree.folders, tree.unsorted])}
      </div>
    </>
  );
}
