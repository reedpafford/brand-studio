import { useRef, useState } from "react";
import { Film, Image, LoaderCircle, Upload, X } from "lucide-react";
import { fileUrl, uploadFile } from "../api/upload";
import { Menu, MenuItem } from "../components";

type File_ = { id: number | null; name: string; video: boolean; local: string; error?: string };

/** Pictures or clips for this video only (S-gaps-01, 3): kept with the video, never added to the brand (rule 12). */
export function useAttachments() {
  const [files, setFiles] = useState<File_[]>([]);
  const add = (list: FileList | null) => {
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

/** The upload button's menu: attach pictures or clips for this video, or adapt a reel instead (Use a reel). */
export function Attach({ files, onReel }: { files: Attachments; onReel: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <input ref={input} type="file" multiple accept="image/png,image/jpeg,image/webp,video/mp4,video/webm" aria-label="Attach pictures or clips" tabIndex={-1} className="sr-only" onChange={(e) => (files.add(e.target.files), (e.target.value = ""))} />
      <Menu
        title="Add to this video"
        trigger={(p) => (
          <button type="button" {...p} aria-label="Upload" className="grid size-8 place-items-center rounded-md text-muted hover:bg-surface-2 aria-expanded:bg-surface-2">
            <Upload size={14} aria-hidden />
          </button>
        )}
      >
        {(close) => (
          <>
            <MenuItem onClick={() => (close(), input.current?.click())}>
              <Image size={14} aria-hidden />
              <span className="flex-1 whitespace-nowrap">Attach pictures or clips</span>
              <span className="whitespace-nowrap text-xs text-muted">for this video</span>
            </MenuItem>
            <MenuItem onClick={() => (close(), onReel())}>
              <Film size={14} aria-hidden />
              Adapt a reel instead…
            </MenuItem>
          </>
        )}
      </Menu>
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
            <button type="button" aria-label={`Remove ${f.name}`} onClick={() => files.remove(f.local)} className="text-muted hover:text-text">
              <X size={12} aria-hidden />
            </button>
          </li>
        ))}
      </ul>
      <span className="text-xs text-muted">Used for this video only. They aren’t added to the brand.</span>
    </div>
  );
}
