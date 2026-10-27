import type { Uploaded, Uploader } from "./videoUploads";

type Reply = { upload_id?: number | null; seconds?: number | null; problem?: string | null; detail?: unknown };

/** Uploads one video for a brand, with progress (a plain fetch can't report it). It is free and makes no draft. A refused file comes back as `problem`; a failed request throws. */
export const videoUploader =
  (brandId: number): Uploader =>
  (file, onProgress, signal) =>
    new Promise<Uploaded>((resolve, reject) => {
      const form = new FormData();
      form.append("file", file);
      form.append("brand_id", String(brandId));
      const req = new XMLHttpRequest();
      req.open("POST", `${location.origin}/api/uploads/video`);
      req.withCredentials = true;
      req.upload.onprogress = (e) => e.lengthComputable && onProgress((e.loaded / e.total) * 100);
      req.onload = () => {
        try {
          const body = JSON.parse(req.responseText) as Reply;
          if (req.status === 201) return resolve({ id: body.upload_id ?? null, seconds: body.seconds ?? null, problem: body.problem ?? null });
          if (typeof body.detail === "string") return resolve({ id: null, seconds: null, problem: body.detail }); // 413 / 415: the server's own sentence
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

/** Takes an uploaded video away again (free; nothing was charged or made from it). */
export const forgetVideo = (id: number) => void fetch(`${location.origin}/api/uploads/${id}`, { method: "DELETE", credentials: "include" }).catch(() => undefined);
