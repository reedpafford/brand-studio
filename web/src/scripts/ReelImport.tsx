import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, CircleAlert, Film, Link as LinkIcon, LoaderCircle, Upload } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api, errorText } from "../api/client";
import { fileUrl } from "../api/upload";
import { Button, Card, Field } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";

const LINK = /^https?:\/\/(www\.)?instagram\.com\/(reel|reels|p)\/[\w-]+/i;
const MAX_MB = 100;
const MAX_SECONDS = 90;

/** Why a reel couldn't be got, in words, and what to do about it. */
const PROBLEMS: Record<string, { text: string; button: string }> = {
  blocked: { text: "Instagram didn't let us download it. Upload the video instead.", button: "Upload a video" },
  gone: { text: "That reel is private or was removed.", button: "Upload a video" },
  bad_file: { text: `That file isn't a video we can read. Use an MP4 or MOV up to ${MAX_SECONDS} seconds.`, button: "Choose another file" },
  too_long: { text: `That video is longer than ${MAX_SECONDS} seconds. Reels up to ${MAX_SECONDS} seconds can be read.`, button: "Choose another file" },
};

function postUpload(path: "/scripts/import/upload", form: Record<string, string>, file: File) {
  return api.POST(path, {
    body: { file: file as unknown as string, brand_id: Number(form.brand_id) },
    bodySerializer: () => {
      const f = new FormData();
      for (const [k, v] of Object.entries(form)) f.append(k, v);
      f.append("file", file);
      return f;
    },
  });
}

/** New script, Import a reel: a link or a video file. Getting it is free; the script is made at once and opens at its Description while the reel is prepared. */
export function ReelPicker({ brandId }: { brandId: number }) {
  const [url, setUrl] = useState("");
  const [bad, setBad] = useState<string | null>(null);
  const [newLines, setNewLines] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const made = async (id: number) => {
    await queryClient.invalidateQueries({ queryKey: ["scripts"] });
    toast("Getting the reel…");
    navigate(`/b/${brandId}/scripts/${id}`);
  };
  const fromLink = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/scripts/import/link", { body: { brand_id: brandId, url: url.trim(), new_lines: newLines } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (d) => made(d.script_id),
  });
  const fromFile = useMutation({
    mutationFn: async (f: File) => {
      if (f.size > MAX_MB * 1024 * 1024) throw new Error(`That file is over ${MAX_MB} MB. Use a shorter video.`);
      const { data, error } = await postUpload("/scripts/import/upload", { brand_id: String(brandId), new_lines: String(newLines) }, f);
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (d) => made(d.script_id),
  });
  const err = fromLink.error ?? fromFile.error;
  return (
    <Card className="max-w-[680px] space-y-4">
      <form
        className="flex flex-col gap-3 sm:flex-row sm:items-end"
        onSubmit={(e) => {
          e.preventDefault();
          if (!LINK.test(url.trim())) return setBad("That isn't an Instagram reel link.");
          setBad(null);
          fromLink.mutate();
        }}
      >
        <div className="min-w-0 flex-1">
          <Field label="Paste an Instagram reel link" inputMode="url" placeholder="https://www.instagram.com/reel/…" value={url} error={bad} onChange={(e) => setUrl(e.target.value)} trailing={<LinkIcon size={20} strokeWidth={1.75} aria-hidden className="text-muted" />} />
        </div>
        <Button type="submit" variant="secondary" busy={fromLink.isPending} disabled={!url.trim() || fromFile.isPending} className="w-full sm:w-auto">
          Get the reel
        </Button>
      </form>
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-muted">or</span>
        <input ref={file} type="file" accept="video/mp4,video/quicktime,.mp4,.mov" aria-label="Choose a video file" className="sr-only" onChange={(e) => e.target.files?.[0] && fromFile.mutate(e.target.files[0])} />
        <Button variant="secondary" icon={Upload} busy={fromFile.isPending} disabled={fromLink.isPending} onClick={() => file.current?.click()} className="w-full sm:w-auto">
          Upload a video
        </Button>
        <span className="text-sm text-muted">MP4 or MOV, up to {MAX_SECONDS} seconds and {MAX_MB} MB</span>
      </div>
      <div className="space-y-1">
        <label className="flex min-h-control items-center gap-3">
          <input type="checkbox" role="switch" className="size-5" checked={newLines} onChange={(e) => setNewLines(e.target.checked)} />
          Write new lines in the same style
        </label>
        <p className="text-sm text-muted">Off: keep the reel's lines and rewrite only what the brand swap needs.</p>
      </div>
      {err && <p role="alert" className={errorClass}>{err.message}</p>}
    </Card>
  );
}

/** The reel's preparation for a script made from one; null when the script isn't. Polls while it is being got. */
export function useReelImport(scriptId: number) {
  return useQuery({
    queryKey: ["script-import", scriptId],
    queryFn: async () => {
      const { data, response } = await api.GET("/scripts/{script_id}/import", { params: { path: { script_id: scriptId } } });
      if (response.status === 404) return null;
      if (!data) throw new Error("load");
      return data;
    },
    refetchInterval: (q) => (q.state.data?.status === "preparing" ? 2000 : false),
  });
}

/** On the Description step: getting the reel, then what was found, or why it couldn't be got. */
export function ReelBlock({ scriptId, published }: { scriptId: number; published: boolean }) {
  const reel = useReelImport(scriptId);
  const file = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const again = useMutation({
    mutationFn: async (f: File) => {
      if (f.size > MAX_MB * 1024 * 1024) throw new Error(`That file is over ${MAX_MB} MB. Use a shorter video.`);
      const { data, error } = await api.POST("/scripts/{script_id}/import/upload", {
        params: { path: { script_id: scriptId } },
        body: { file: f as unknown as string },
        bodySerializer: () => {
          const form = new FormData();
          form.append("file", f);
          return form;
        },
      });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (d) => queryClient.setQueryData(["script-import", scriptId], d),
  });
  const r = reel.data;
  if (!r) return null;
  const lines = r.transcript.length;
  if (r.status === "preparing")
    return (
      <Card className="max-w-[680px]">
        <p role="status" className="flex items-center gap-2">
          <LoaderCircle size={20} strokeWidth={1.75} aria-hidden className="animate-spin motion-reduce:animate-none" />
          Getting the reel…
        </p>
      </Card>
    );
  if (r.status === "failed") {
    const p = PROBLEMS[r.problem_code ?? ""] ?? { text: r.problem || "We couldn't get that reel. Upload the video instead.", button: "Upload a video" };
    return (
      <Card className="max-w-[680px] space-y-3">
        <p role="alert" className="flex items-start gap-2 text-danger">
          <CircleAlert size={20} strokeWidth={1.75} aria-hidden className="mt-0.5 shrink-0" />
          {p.text}
        </p>
        {!published && (
          <>
            <input ref={file} type="file" accept="video/mp4,video/quicktime,.mp4,.mov" aria-label="Choose a video file" className="sr-only" onChange={(e) => e.target.files?.[0] && again.mutate(e.target.files[0])} />
            <Button variant="secondary" icon={Upload} busy={again.isPending} onClick={() => file.current?.click()}>
              {p.button}
            </Button>
          </>
        )}
        {again.isError && <p role="alert" className={errorClass}>{again.error.message}</p>}
      </Card>
    );
  }
  return (
    <Card className="flex max-w-[680px] gap-4">
      <span aria-hidden className="grid h-32 w-[72px] shrink-0 place-items-center overflow-hidden rounded-md bg-surface-2 text-muted">
        {r.contact_file_id ? <img src={fileUrl(r.contact_file_id)} alt="" className="size-full object-cover" /> : <Film size={20} strokeWidth={1.75} />}
      </span>
      <div className="min-w-0 space-y-1">
        <p className="flex items-center gap-1 font-medium">
          <Check size={20} strokeWidth={1.75} aria-hidden className="text-success" />
          Got the reel
        </p>
        <p className="text-sm text-muted">
          {[r.seconds ? `${Math.round(r.seconds)} s` : null, r.shots ? `${r.shots} shot${r.shots === 1 ? "" : "s"}` : null, lines > 0 ? `${lines} line${lines === 1 ? "" : "s"} of dialogue` : "No dialogue (music only)"].filter(Boolean).join(" · ")}
        </p>
        {r.url && <p className="truncate text-sm text-muted">{r.url.replace(/^https?:\/\/(www\.)?/, "")}</p>}
        <p className="text-sm text-muted">Reading it into a script comes next.</p>
      </div>
    </Card>
  );
}
