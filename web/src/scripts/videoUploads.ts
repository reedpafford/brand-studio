import { useCallback, useEffect, useRef, useState } from "react";

export const MAX_REELS = 20;
export const MAX_BYTES = 100 * 1024 * 1024;
export const MAX_SECONDS = 90;

/** What the server answers once a video is uploaded and checked. `problem` is its plain sentence when it refused the file. */
export type Uploaded = { id: number | null; seconds: number | null; problem?: string | null };
/** Uploads one file with progress (0–100); the signal stops it. */
export type Uploader = (file: File, onProgress: (percent: number) => void, signal: AbortSignal) => Promise<Uploaded>;

export type FileRow = {
  key: string;
  file: File;
  status: "uploading" | "ready" | "problem";
  percent: number;
  seconds: number | null;
  id: number | null; // the server's id for the uploaded video (none when it refused the file)
  problem: string | null;
  canRetry: boolean;
};

const isVideo = (f: File) => /^video\/(mp4|quicktime)$/.test(f.type) || /\.(mp4|mov)$/i.test(f.name);
const same = (a: File, b: File) => a.name === b.name && a.size === b.size;
export const megabytes = (bytes: number) => `${Math.max(1, Math.round(bytes / 1048576))} MB`;
/** "bo-tries-sal…mon.mp4": one line, cut in the middle. */
export const cutMiddle = (name: string, most = 24) => (name.length <= most ? name : `${name.slice(0, Math.ceil((most - 1) / 2))}…${name.slice(name.length - Math.floor((most - 1) / 2))}`);

/** Why a file can't be sent at all, checked before anything is uploaded. */
export function checkBeforeUpload(file: File): string | null {
  if (!isVideo(file)) return "Only MP4 or MOV videos can be read.";
  if (file.size > MAX_BYTES) return "This one is over 100 MB.";
  return null;
}

/** The files added to Bulk create: each uploads as soon as it is added, and can be removed, or tried again, at any time. `room` is how many reels there is still space for (links count too). */
export function useFileQueue(uploader: Uploader, room: number, forget?: (id: number) => void) {
  const [rows, setRows] = useState<FileRow[]>([]);
  const [notes, setNotes] = useState<string[]>([]);
  const stops = useRef(new Map<string, AbortController>());
  const seq = useRef(0);
  const patch = useCallback((key: string, p: Partial<FileRow>) => setRows((all) => all.map((r) => (r.key === key ? { ...r, ...p } : r))), []);

  const start = useCallback(
    (key: string, file: File) => {
      const stop = new AbortController();
      stops.current.set(key, stop);
      patch(key, { status: "uploading", percent: 0, problem: null, canRetry: false });
      uploader(file, (percent) => patch(key, { percent }), stop.signal)
        .then((r) => {
          stops.current.delete(key);
          if (r.problem) return patch(key, { status: "problem", problem: r.problem, id: null, canRetry: false }); // a refused upload has no id and is never sent
          if (r.id === null) return patch(key, { status: "problem", problem: "The upload didn't finish.", canRetry: true });
          if (r.seconds !== null && r.seconds > MAX_SECONDS) return patch(key, { status: "problem", problem: "This one is longer than 90 seconds.", seconds: r.seconds, id: r.id, canRetry: false });
          patch(key, { status: "ready", percent: 100, seconds: r.seconds, id: r.id });
        })
        .catch(() => {
          if (stop.signal.aborted) return;
          stops.current.delete(key);
          patch(key, { status: "problem", problem: "The upload didn't finish.", canRetry: true });
        });
    },
    [uploader, patch],
  );

  const add = (files: File[]) => {
    const said: string[] = [];
    let skipped = 0;
    let have = rows.filter((r) => r.status !== "problem").length; // a refused file takes no place out of the cap
    const next: FileRow[] = [];
    for (const file of files) {
      if ([...rows, ...next].some((r) => same(r.file, file))) {
        said.push(`${file.name} is already in the list.`);
        continue;
      }
      if (have >= room) {
        skipped += 1;
        continue;
      }
      have += 1;
      const problem = checkBeforeUpload(file);
      next.push({ key: `f${++seq.current}`, file, status: problem ? "problem" : "uploading", percent: 0, seconds: null, id: null, problem, canRetry: false });
    }
    if (skipped > 0) said.push(`Up to ${MAX_REELS} reels at once. ${skipped} file${skipped === 1 ? " wasn't" : "s weren't"} added.`);
    setNotes(said);
    setRows((all) => [...all, ...next]);
    for (const r of next) if (!r.problem) start(r.key, r.file);
  };

  const remove = (key: string) => {
    stops.current.get(key)?.abort();
    stops.current.delete(key);
    const gone = rows.find((r) => r.key === key);
    if (gone?.id != null) forget?.(gone.id);
    setRows((all) => all.filter((r) => r.key !== key));
  };
  const retry = (key: string) => {
    const row = rows.find((r) => r.key === key);
    if (row) start(key, row.file);
  };
  const stopAll = () => {
    stops.current.forEach((s) => s.abort());
    stops.current.clear();
  };
  useEffect(() => stopAll, []);

  return {
    rows,
    notes,
    add,
    remove,
    retry,
    stopAll,
    uploading: rows.filter((r) => r.status === "uploading").length,
    ready: rows.filter((r) => r.status === "ready"),
    problems: rows.filter((r) => r.status === "problem").length,
  };
}
