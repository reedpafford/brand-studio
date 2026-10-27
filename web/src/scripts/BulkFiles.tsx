import { useRef, useState } from "react";
import { Check, FileVideoCamera, Upload, X } from "lucide-react";
import { Button } from "../components";
import { useMedia } from "../useMedia";
import { errorText as errorClass } from "../ui";
import { cutMiddle, MAX_BYTES, megabytes, type FileRow } from "./videoUploads";

type Queue = { rows: FileRow[]; notes: string[]; add: (files: File[]) => void; remove: (key: string) => void; retry: (key: string) => void };

/** Video files for Bulk create: a drop zone (a plain Choose files button on a phone), then a row per file with its progress. */
export function BulkFiles({ queue }: { queue: Queue }) {
  const phone = useMedia("(max-width: 639px)");
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const choose = (
    <>
      <input
        ref={input}
        type="file"
        multiple
        accept=".mp4,.mov,video/mp4,video/quicktime"
        className="sr-only"
        aria-label="Video files"
        tabIndex={-1}
        onChange={(e) => {
          queue.add([...(e.target.files ?? [])]);
          e.target.value = "";
        }}
      />
      <Button type="button" variant={phone ? "secondary" : "ghost"} dense={!phone} icon={Upload} className={phone ? "w-full" : ""} onClick={() => input.current?.click()}>
        Choose files
      </Button>
    </>
  );
  return (
    <div className="space-y-2">
      {phone ? (
        <div className="space-y-1">{choose}</div>
      ) : (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setOver(false);
            queue.add([...e.dataTransfer.files]);
          }}
          className={`flex h-24 flex-wrap items-center justify-center gap-2 rounded-lg border border-dashed px-4 text-center ${over ? "border-accent bg-accent-soft" : "border-border"}`}
        >
          <span>{over ? "Drop to add them" : "Drop video files here, or"}</span>
          {!over && choose}
        </div>
      )}
      <p className="text-sm text-muted">MP4 or MOV, up to 90 s and {megabytes(MAX_BYTES)} each.</p>
      {queue.notes.map((n) => (
        <p key={n} role="status" className="text-sm text-muted">
          {n}
        </p>
      ))}
      {queue.rows.length > 0 && (
        <ul className="space-y-2" aria-label="Files added">
          {queue.rows.map((r) => (
            <li key={r.key} className={`space-y-1 rounded-lg border p-3 ${r.status === "problem" ? "border-danger" : "border-border"}`}>
              <div className="flex items-center gap-2">
                <FileVideoCamera size={20} strokeWidth={1.75} aria-hidden className="shrink-0 text-muted" />
                <span className="min-w-0 flex-1 truncate" title={r.file.name}>
                  {cutMiddle(r.file.name)}
                </span>
                <span className="shrink-0 text-sm text-muted tabular-nums">{r.seconds !== null ? `${Math.round(r.seconds)} s · ` : ""}{megabytes(r.file.size)}</span>
                <button type="button" aria-label={`Remove ${r.file.name}`} onClick={() => queue.remove(r.key)} className="grid size-control shrink-0 place-items-center rounded-md text-muted hover:bg-surface-2 lg:size-control-dense">
                  <X size={20} strokeWidth={1.75} aria-hidden />
                </button>
              </div>
              {r.status === "uploading" && (
                <div className="space-y-1">
                  <div className="h-1.5 overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-valuenow={r.percent} aria-valuemin={0} aria-valuemax={100} aria-label={`Uploading ${r.file.name}`}>
                    <div className="h-full bg-accent" style={{ width: `${r.percent}%` }} />
                  </div>
                  <p className="text-sm text-muted tabular-nums">Uploading… {Math.round(r.percent)}%</p>
                </div>
              )}
              {r.status === "ready" && (
                <p className="flex items-center gap-1 text-sm text-success">
                  <Check size={16} strokeWidth={1.75} aria-hidden /> Ready
                </p>
              )}
              {r.status === "problem" && (
                <div className="flex flex-wrap items-center gap-2">
                  <p role="alert" className={`flex-1 text-sm ${errorClass}`}>{r.problem}</p>
                  {r.canRetry && (
                    <Button type="button" variant="secondary" dense onClick={() => queue.retry(r.key)}>
                      Try again
                    </Button>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
