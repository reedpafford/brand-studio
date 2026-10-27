import type { Uploaded, Uploader } from "./videoUploads";

/** Uploads one video to the server with progress (a plain fetch can't report it). Throws if the request itself fails; a refused file comes back as `problem`. */
export const uploadVideo: Uploader = (file, onProgress, signal) =>
  new Promise<Uploaded>((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);
    const req = new XMLHttpRequest();
    req.open("POST", `${location.origin}/api/uploads/video`);
    req.withCredentials = true;
    req.upload.onprogress = (e) => e.lengthComputable && onProgress((e.loaded / e.total) * 100);
    req.onload = () => {
      try {
        const body = JSON.parse(req.responseText) as { id?: string; seconds?: number | null; problem?: string | null; detail?: unknown };
        if (req.status >= 200 && req.status < 300 && body.id) return resolve({ id: body.id, seconds: body.seconds ?? null, problem: body.problem ?? null });
        if (typeof body.detail === "string") return resolve({ id: "", seconds: null, problem: body.detail }); // the server's own sentence
      } catch {
        /* not JSON: the upload didn't finish */
      }
      reject(new Error("upload failed"));
    };
    req.onerror = () => reject(new Error("upload failed"));
    signal.addEventListener("abort", () => {
      req.abort();
      reject(new DOMException("aborted", "AbortError"));
    });
    req.send(form);
  });

/** Takes an uploaded video away again (free; nothing was made from it). */
export const forgetVideo = (id: string) => void fetch(`${location.origin}/api/uploads/video/${encodeURIComponent(id)}`, { method: "DELETE", credentials: "include" }).catch(() => undefined);
