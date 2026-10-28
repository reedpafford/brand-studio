import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, CircleAlert, FileVideoCamera, Film, Link as LinkIcon, LoaderCircle, RotateCcw, Upload } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import { fileUrl } from "../api/upload";
import { Badge, Banner, Button, Card, Dialog, Field, Panel, TextArea, buttonClass, wholeCredits } from "../components";
import type { components } from "../api/schema";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { useRail } from "../useMedia";
import { useAllowanceStop } from "./useScript";

export const LINK = /^https?:\/\/(www\.)?instagram\.com\/(reel|reels|p)\/[\w-]+/i;
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
  const queryClient = useQueryClient();
  const made = async (id: number) => {
    await queryClient.invalidateQueries({ queryKey: ["scripts"] });
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
        <input ref={file} type="file" accept="video/mp4,video/quicktime,.mp4,.mov" aria-label="Choose a video file" className="sr-only" onChange={(e) => {
            const f = e.target.files?.[0];
            e.target.value = ""; // so the same file can be chosen again
            if (f) fromFile.mutate(f);
          }} />
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
  const queryClient = useQueryClient();
  const key = ["script-import", scriptId];
  return useQuery({
    queryKey: key,
    queryFn: async () => {
      const before = queryClient.getQueryData<{ status: string }>(key)?.status;
      const { data, response } = await api.GET("/scripts/{script_id}/import", { params: { path: { script_id: scriptId } } });
      if (response.status === 404) return null;
      if (!data) throw new Error("load");
      // The read has just finished: it wrote the script and the cast, so bring them in (an open Script step must not keep offering to write).
      if (data.status === "done" && before !== undefined && before !== "done") {
        void queryClient.invalidateQueries({ queryKey: ["script-lib", scriptId] });
        void queryClient.invalidateQueries({ queryKey: ["script-cast", scriptId] });
        void queryClient.invalidateQueries({ queryKey: ["scripts"] });
      }
      return data;
    },
    refetchInterval: (q) => (q.state.data?.status === "preparing" || q.state.data?.status === "reading" ? 2000 : false),
  });
}

/** The paid read's rows. The server's steps are watch, write and cast; "Got the reel" and "Listening" are the free preparation. */
const ROWS: { id: "got" | "heard" | "watch" | "write" | "cast"; label: string }[] = [
  { id: "got", label: "Got the reel" },
  { id: "heard", label: "Listening to the dialogue" },
  { id: "watch", label: "Finding the shots and writing the breakdown" },
  { id: "write", label: "Writing the script" },
  { id: "cast", label: "Filling in the cast" },
];

/** What the server says is left this week, if it says the read doesn't fit. The usual wording comes from the allowance itself. */
const notEnough = (e?: { credits: number; credits_left: number | null } | null) => (e && e.credits_left !== null && e.credits > e.credits_left ? "That's more than the credits you have left this week. It resets on Monday." : null);

/** Read this reel · N credits (or Try again after a failed step): the one amber button of a prepared reel. On a phone it sits in the action bar, on desktop in the card. */
export function ReadReelButton({ scriptId, createdById, className }: { scriptId: number; createdById: number | null; className?: string }) {
  const reel = useReelImport(scriptId);
  const queryClient = useQueryClient();
  const r = reel.data;
  const allowanceStop = useAllowanceStop({ created_by_id: createdById }, r?.estimate?.credits);
  const read = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/scripts/{script_id}/import/read", { params: { path: { script_id: scriptId } } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (d) => queryClient.setQueryData(["script-import", scriptId], d),
  });
  if (!r || (r.status !== "ready" && r.status !== "failed") || r.failed_step === "prepare") return null;
  const stop = allowanceStop ?? notEnough(r.estimate);
  return (
    <div className="space-y-2">
      <Button className={className} busy={read.isPending} disabled={!r.estimate || stop !== null} reason={stop} price={r.estimate?.credits} onClick={() => read.mutate()}>
        {r.status === "failed" ? "Try again" : "Read this reel"}
      </Button>
      {read.isError && <p role="alert" className={errorClass}>{read.error.message}</p>}
    </div>
  );
}

type ReelRow = components["schemas"]["ReelRow"];
const SpinIcon = (p: { size?: number; strokeWidth?: number; className?: string; "aria-hidden"?: boolean }) => <LoaderCircle {...p} className={`${p.className ?? ""} animate-spin motion-reduce:animate-none`} />;
/** The chip a reel script wears in lists: "Reel · 45 s", "Reading the reel…", or why the reel couldn't be got. */
export function ReelChip({ reel }: { reel?: ReelRow | null }) {
  if (!reel) return <Badge icon={Film}>Reel</Badge>;
  if (reel.status === "failed") return <span title={reel.fetch_error ?? undefined}><Badge tone="danger" icon={CircleAlert}>Couldn't get the reel</Badge></span>;
  // An uploaded video is already here: it shows its length at once, and never "Getting the reel…".
  if (reel.source === "file" && reel.status !== "reading") return <Badge icon={FileVideoCamera}>{reel.seconds ? `Video · ${Math.round(reel.seconds)} s` : "Video"}</Badge>;
  if (reel.status === "preparing" || reel.status === "reading") return <Badge icon={SpinIcon}>{reel.status === "reading" ? "Reading the reel…" : "Getting the reel…"}</Badge>;
  if (reel.source === "file") return <Badge icon={FileVideoCamera}>{reel.seconds ? `Video · ${Math.round(reel.seconds)} s` : "Video"}</Badge>;
  return <Badge icon={Film}>{reel.seconds ? `Reel · ${Math.round(reel.seconds)} s` : "Reel"}</Badge>;
}

/** Read it again (reel-import.md §5): what did it get wrong? The note can fix who speaks, the shots and the camera, never the words said. */
function ReadAgain({ scriptId, createdById, credits, onClose }: { scriptId: number; createdById: number | null; credits?: number | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  // Past an editor's week it can't be pressed; the reason says so and when it resets.
  const stop = useAllowanceStop({ created_by_id: createdById }, credits ?? undefined);
  const [note, setNote] = useState("");
  const again = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/scripts/{script_id}/import/read-again", { params: { path: { script_id: scriptId } }, body: { note: note.trim() } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (d) => {
      queryClient.setQueryData(["script-import", scriptId], d);
      onClose();
    },
  });
  return (
    <Panel title="Read it again" onClose={onClose}>
      <div className="space-y-4">
        <TextArea label="What did it get wrong? (optional)" rows={4} maxLength={500} placeholder="e.g. shot 3 is the groom, not the priest; the montage starts at 0:17" value={note} onChange={(e) => { setNote(e.target.value); again.reset(); }} />
        <p className="text-sm text-muted">The download and the dialogue are kept. Only the breakdown and the script are made again.</p>
        {again.isError && <p role="alert" className={errorClass}>{again.error.message}</p>}
        <Button busy={again.isPending} price={credits ?? undefined} icon={RotateCcw} disabled={stop !== null} reason={stop} onClick={() => again.mutate()} className="w-full">
          Read it again
        </Button>
      </div>
    </Panel>
  );
}

/** "New breakdown ready. Your script edits are kept.": the reel was read again after the script was edited. */
function FillAgain({ scriptId }: { scriptId: number }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [asking, setAsking] = useState(false);
  const bring = () => Promise.all([queryClient.invalidateQueries({ queryKey: ["script-lib", scriptId] }), queryClient.invalidateQueries({ queryKey: ["script-cast", scriptId] })]);
  const fill = useMutation({
    mutationFn: async () => {
      // What the script says now, so Undo can write it back (the old words also stay in the version's history).
      const before = queryClient.getQueryData<{ versions: { slot: number; text: string }[] }>(["script-lib", scriptId])?.versions.find((v) => v.slot === 0)?.text;
      const { data, error } = await api.POST("/scripts/{script_id}/fill-from-reel", { params: { path: { script_id: scriptId } } });
      if (!data) throw new Error(errorText(error));
      return { data, before };
    },
    onSuccess: async ({ data, before }) => {
      queryClient.setQueryData(["script-import", scriptId], data);
      setAsking(false);
      toast("Script filled from the reel again.", before?.trim() ? async () => {
        await api.PUT("/scripts/{script_id}/drafts/{slot}", { params: { path: { script_id: scriptId, slot: 0 } }, body: { text: before } });
        await bring();
      } : undefined);
      await bring();
    },
  });
  return (
    <>
      <Banner tone="info" title="New breakdown ready. Your script edits are kept." action={<Button variant="ghost" onClick={() => { fill.reset(); setAsking(true); }}>Fill the script again</Button>} />
      {asking && (
        <Dialog danger title="Replace your script with the reel's?" cancelLabel="Keep my script" actionLabel="Replace" busy={fill.isPending} onCancel={() => setAsking(false)} onConfirm={() => fill.mutate()}>
          Your current words move to this version's history.
          {fill.isError && <span role="alert" className={`${errorClass} mt-2 block`}>{fill.error.message}</span>}
        </Dialog>
      )}
    </>
  );
}

/** On the Description step: getting the reel, the price to read it, the read's progress, and what came of it. */
export function ReelBlock({ scriptId, published, createdById }: { scriptId: number; published: boolean; createdById: number | null }) {
  const reel = useReelImport(scriptId);
  const file = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const toast = useToast();
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
  const rail = useRail();
  const [reading, setReading] = useState(false);
  const brandId = Number(useParams().brandId);
  const r = reel.data;
  // The read finished while this page was open: say so and bring the script in.
  const was = useRef(r?.status);
  useEffect(() => {
    if (was.current === "reading" && r?.status === "done") {
      toast("Reel read. Check the script and the cast.");
      void queryClient.invalidateQueries({ queryKey: ["script-lib", scriptId] });
      void queryClient.invalidateQueries({ queryKey: ["script-cast", scriptId] });
      void queryClient.invalidateQueries({ queryKey: ["scripts"] });
    }
    was.current = r?.status;
  }, [r?.status]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!r) return null;
  const lines = r.transcript.length;
  const facts = [r.seconds ? `${Math.round(r.seconds)} s` : null, r.shots ? `${r.shots} shot${r.shots === 1 ? "" : "s"}` : null, lines > 0 ? `${lines} line${lines === 1 ? "" : "s"} of dialogue` : "No dialogue (music only)"].filter(Boolean).join(" · ");
  const thumb = (
    <span aria-hidden className="grid h-32 w-[72px] shrink-0 place-items-center overflow-hidden rounded-md bg-surface-2 text-muted">
      {r.contact_file_id ? <img src={fileUrl(r.contact_file_id)} alt="" className="size-full object-cover" /> : <Film size={20} strokeWidth={1.75} />}
    </span>
  );
  const chooser = (button: string) => (
    <>
      <input ref={file} type="file" accept="video/mp4,video/quicktime,.mp4,.mov" aria-label="Choose a video file" className="sr-only" onChange={(e) => {
          const f = e.target.files?.[0];
          e.target.value = ""; // so the same file can be chosen again
          if (f) again.mutate(f);
        }} />
      <Button variant="secondary" icon={Upload} busy={again.isPending} onClick={() => file.current?.click()}>
        {button}
      </Button>
    </>
  );
  if (r.status === "preparing")
    return (
      <Card className="max-w-[680px]">
        <p role="status" className="flex items-center gap-2">
          <LoaderCircle size={20} strokeWidth={1.75} aria-hidden className="animate-spin motion-reduce:animate-none" />
          Getting the reel…
        </p>
      </Card>
    );
  const step = r.failed_step;
  if (r.status === "failed" && (!step || step === "prepare")) {
    // The server says what is wrong (a silent video, one over the size, a link it was refused); our words are only for when it says nothing. The code picks the button.
    const known = PROBLEMS[r.problem_code ?? ""];
    const p = { text: r.problem || known?.text || "We couldn't get that reel. Upload the video instead.", button: known?.button ?? "Upload a video" };
    return (
      <Card className="max-w-[680px] space-y-3">
        <p role="alert" className="flex items-start gap-2 text-danger">
          <CircleAlert size={20} strokeWidth={1.75} aria-hidden className="mt-0.5 shrink-0" />
          {p.text}
        </p>
        {!published && chooser(p.button)}
        {again.isError && <p role="alert" className={errorClass}>{again.error.message}</p>}
      </Card>
    );
  }
  if (r.status === "ready" || r.status === "failed") {
    // The server says which step didn't finish and what was charged; ours is only for when it says nothing.
    const failedText = r.problem || (step === "watch" ? "The shots couldn't be found. Credits for the rest were returned." : step === "write" ? "The script didn't finish. Credits for this step were returned." : "The cast didn't finish. Credits for this step were returned.");
    const tried = r.estimate?.tries ?? 0;
    return (
      <Card className="max-w-[680px] space-y-3">
        <div className="flex gap-4">
          {thumb}
          <div className="min-w-0 space-y-1">
            <p className="flex items-center gap-1 font-medium">
              <Check size={20} strokeWidth={1.75} aria-hidden className="text-success" />
              Got the reel
            </p>
            <p className="text-sm text-muted">{facts}</p>
            {r.url && <p className="truncate text-sm text-muted">{r.url.replace(/^https?:\/\/(www\.)?/, "")}</p>}
            {r.estimate && <p className="text-sm text-muted">{r.status === "failed" ? `Trying again costs about ${wholeCredits(r.estimate.credits)} credits. A step that is run again is charged again.${tried >= 2 ? ` It has been tried ${tried} times already.` : ""}` : `Reading it costs about ${wholeCredits(r.estimate.credits)} credits.`}</p>}
          </div>
        </div>
        {r.status === "failed" && (
          <p role="alert" className="flex items-start gap-2 text-danger">
            <CircleAlert size={20} strokeWidth={1.75} aria-hidden className="mt-0.5 shrink-0" />
            {failedText}
          </p>
        )}
        {!published && rail && <ReadReelButton scriptId={scriptId} createdById={createdById} />}
      </Card>
    );
  }
  if (r.status === "reading") {
    const done = new Set(["got", "heard", ...r.steps_done]);
    const current = ROWS.find((row) => !done.has(row.id))?.id;
    return (
      <Card className="max-w-[680px] space-y-2">
        <p className="font-medium">Reading the reel</p>
        <ul aria-label="Reading the reel" className="space-y-1">
          {ROWS.map((row) => (
            <li key={row.id} className={`flex items-center gap-2 ${done.has(row.id) ? "" : row.id === current ? "" : "text-muted"}`}>
              {done.has(row.id) ? <Check size={20} strokeWidth={1.75} aria-hidden className="text-success" /> : row.id === current ? <LoaderCircle size={20} strokeWidth={1.75} aria-hidden className="animate-spin motion-reduce:animate-none" /> : <span aria-hidden className="size-5 rounded-full border border-border" />}
              <span>{row.label}</span>
              <span className="sr-only">{done.has(row.id) ? "done" : row.id === current ? "now" : "next"}</span>
            </li>
          ))}
        </ul>
        <p className="text-sm text-muted">It keeps going if you leave this page.</p>
      </Card>
    );
  }
  return (
    <div className="max-w-[680px] space-y-3">
      {r.new_fill_ready && r.edited_since_fill && !published && <FillAgain scriptId={scriptId} />}
      <Card className="flex gap-4">
        {thumb}
        <div className="min-w-0 space-y-1">
          <p className="flex items-center gap-1 font-medium">
            <Check size={20} strokeWidth={1.75} aria-hidden className="text-success" />
            Reel read
          </p>
          <p className="text-sm text-muted">Imported · {facts}</p>
          <p className="text-sm text-muted">The script and the cast are filled in. Check them, then approve.</p>
          <div className="flex flex-wrap items-center gap-2">
            <Link to={`/b/${brandId}/scripts/${scriptId}/reel`} className={buttonClass("secondary")}>
              Review the breakdown
            </Link>
            {!published && (
              <Button variant="ghost" dense icon={RotateCcw} onClick={() => setReading(true)}>
                Read it again
              </Button>
            )}
          </div>
        </div>
      </Card>
      {reading && <ReadAgain scriptId={scriptId} createdById={createdById} credits={r.read_again_credits} onClose={() => setReading(false)} />}
    </div>
  );
}
