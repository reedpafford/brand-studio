import { useRef, useState } from "react";
import { FileText, Film, Image, LoaderCircle, Plus, Upload, X } from "lucide-react";
import { fileUrl, uploadFile } from "../api/upload";
import { Button, Menu, MenuItem } from "../components";

type File_ = { id: number | null; name: string; video: boolean; local: string; error?: string };

/** Pictures or clips for this video only (S-gaps-01, 3): kept with the video, never added to the brand (rule 12). */
export function useAttachments() {
  const [files, setFiles] = useState<File_[]>([]);
  const add = (list: FileList | File[] | null) => {
    for (const f of Array.from(list ?? [])) {
      const local = URL.createObjectURL(f);
      const row: File_ = { id: null, name: f.name, video: f.type.startsWith("video/"), local };
      setFiles((xs) => [...xs, row]);
      uploadFile(f).then(
        (stored) => setFiles((xs) => xs.map((x) => (x.local === local ? { ...x, id: stored.id } : x))),
        (e: Error) => setFiles((xs) => xs.map((x) => (x.local === local ? { ...x, error: e.message } : x))),
      );
    }
  };
  const remove = (local: string) => {
    URL.revokeObjectURL?.(local);
    setFiles((xs) => xs.filter((x) => x.local !== local));
  };
  const ids = files.flatMap((f) => (f.id ? [f.id] : []));
  return { files, add, remove, ids, busy: files.some((f) => !f.id && !f.error) };
}
export type Attachments = ReturnType<typeof useAttachments>;

export const ACCEPT = "image/png,image/jpeg,image/webp,video/mp4,video/webm";

/** The box's + menu: pictures or clips for this video, or start from a saved script or a reel instead. */
export function Attach({ files, onScript, onReel }: { files: Attachments; onScript: () => void; onReel: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <input ref={input} type="file" multiple accept={ACCEPT} aria-label="Attach pictures or clips" tabIndex={-1} className="sr-only" onChange={(e) => (files.add(e.target.files), (e.target.value = ""))} />
      <Menu
        title="Add to this video"
        trigger={(p) => (
          <button type="button" {...p} aria-label="Add" title="Add pictures, a saved script or a reel" className="grid size-control shrink-0 place-items-center rounded-full border border-border-button text-muted transition-colors duration-(--dur-fast) ease-out hover:bg-surface-2 hover:text-text aria-expanded:bg-surface-2 lg:size-7">
            <Plus size={14} aria-hidden />
          </button>
        )}
      >
        {(close) => (
          <>
            <MenuItem onClick={() => (close(), input.current?.click())}>
              <Image size={14} aria-hidden />
              <span className="flex-1 whitespace-nowrap">Upload pictures or clips</span>
              <span className="whitespace-nowrap text-xs text-muted">for this video</span>
            </MenuItem>
            <MenuItem onClick={() => (close(), onScript())}>
              <FileText size={14} aria-hidden />
              Use a saved script
            </MenuItem>
            <MenuItem onClick={() => (close(), onReel())}>
              <Film size={14} aria-hidden />
              Use a reel
            </MenuItem>
          </>
        )}
      </Menu>
    </>
  );
}

/** The same upload as a press of its own (the Uploads tab). */
export function UploadPress({ files }: { files: Attachments }) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <input ref={input} type="file" multiple accept={ACCEPT} aria-label="Upload pictures or clips for this video" tabIndex={-1} className="sr-only" onChange={(e) => (files.add(e.target.files), (e.target.value = ""))} />
      <Button variant="secondary" icon={Upload} onClick={() => input.current?.click()}>
        Upload pictures or clips
      </Button>
    </>
  );
}

/** The attached files under the words, each with its picture and a remove, and what happens to them. */
export function Attached({ files }: { files: Attachments }) {
  if (!files.files.length) return null;
  return (
    <div className="flex flex-col gap-2 pt-2">
      <ul aria-label="Attached" className="flex flex-wrap gap-2">
        {files.files.map((f) => (
          <li key={f.local} className="flex items-center gap-2 rounded-md border border-border py-1 pl-1 pr-2">
            <span className="relative block h-[34px] w-[26px] overflow-hidden rounded-sm bg-surface-3">
              {f.video ? <video src={f.id ? fileUrl(f.id) : f.local} muted className="size-full object-cover" /> : <img src={f.local} alt="" className="size-full object-cover" />}
              {!f.id && !f.error && <LoaderCircle size={12} aria-hidden className="absolute inset-0 m-auto animate-spin text-white" />}
            </span>
            <span className={`text-xs ${f.error ? "text-danger" : ""}`}>{f.error ? `${f.name}: ${f.error}` : f.name}</span>
            <button type="button" aria-label={`Remove ${f.name}`} onClick={() => files.remove(f.local)} className="-my-1 -mr-2 grid size-control place-items-center text-muted hover:text-text lg:m-0 lg:size-auto">
              <X size={12} aria-hidden />
            </button>
          </li>
        ))}
      </ul>
      <span className="text-xs text-muted">Used for this video only. They aren’t added to the brand.</span>
    </div>
  );
}
