import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2, Upload } from "lucide-react";
import { fileUrl } from "../api/upload";
import { Badge, Button, Card, Field } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { clock } from "./TakePlayer";
import type { Script } from "./useScript";

/** A song ad studied for its shape (flows S3a; Builder-Server-7's SongStudyOut, #851). */
type Section = { name: string; start: number; end: number; lines: string[]; guessed: boolean };
export type Study = {
  status: "studying" | "done" | "failed";
  job?: { id: number; status: "queued" | "running" | "failed"; started_at: string | null } | null;
  seconds?: number | null;
  bpm?: number | null;
  sections: Section[];
  lines: { text: string; start: number; end: number }[];
  frames: { file_id: number; t: number }[];
  use_as_guide: boolean;
  problem: string;
};

// The routes are Builder-Server-7's; until they are in the generated schema they are called with fetch.
async function send(method: "POST" | "PATCH" | "DELETE", path: string, body?: FormData | object) {
  const r = await fetch(`${location.origin}/api${path}`, {
    method,
    credentials: "include",
    ...(body instanceof FormData ? { body } : body ? { body: JSON.stringify(body), headers: { "Content-Type": "application/json" } } : {}),
  });
  if (!r.ok) {
    const detail = await r.json().then((j: { detail?: unknown }) => j.detail, () => null);
    throw new Error(typeof detail === "string" ? detail : "That didn't work. Nothing was charged; try again.");
  }
}

function Elapsed({ since }: { since: string | null | undefined }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  if (!since) return null;
  return <span className="tabular-nums"> {clock(Math.max(0, Math.round((now - Date.parse(since)) / 1000)))}</span>;
}

const bpmText = (bpm: number | null | undefined) => (bpm ? `${Math.round(bpm)} BPM` : "no steady beat");

/** S3a: Study a song ad, a third box above Write 2 song directions. Free. Its words never reach the lyrics (rule 19). */
export function SongStudy({ script: s }: { script: Script }) {
  const v = s.versions.find((x) => x.slot === 0) as unknown as Record<string, unknown> | undefined;
  const study = (v?.song_study ?? null) as Study | null;
  const queryClient = useQueryClient();
  const toast = useToast();
  const [url, setUrl] = useState("");
  const file = useRef<HTMLInputElement>(null);
  const base = `/scripts/${s.id}/drafts/0/song-study`;
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["script-lib", s.id] });
  const studying = study?.status === "studying";
  // While it's studied, the version is read again until the card is in.
  useEffect(() => {
    if (!studying) return;
    const t = setInterval(() => void refresh(), 3000);
    return () => clearInterval(t);
  }, [studying]); // eslint-disable-line react-hooks/exhaustive-deps

  const start = useMutation({
    mutationFn: (what: { url?: string; file?: File }) => {
      const form = new FormData();
      if (what.file) form.append("file", what.file);
      else form.append("url", what.url ?? "");
      return send("POST", base, form);
    },
    onSuccess: () => {
      setUrl("");
      return refresh();
    },
  });
  const cancel = useMutation({ mutationFn: (id: number) => send("POST", `/jobs/${id}/cancel`), onSuccess: refresh });
  const guide = useMutation({ mutationFn: (on: boolean) => send("PATCH", base, { use_as_guide: on }), onSuccess: refresh });
  const remove = useMutation({
    mutationFn: () => send("DELETE", base),
    onSuccess: async () => {
      await refresh();
      toast("The study is removed.", () => void send("POST", `${base}/restore`).then(refresh));
    },
  });
  // Only the latest press's refusal shows, until the next press.
  const latest = [start, cancel, guide, remove].reduce((a, m) => (m.submittedAt > a.submittedAt ? m : a));

  // Hidden until the server offers studies (the version carries song_study, null when there is none).
  if (s.published || !v || !("song_study" in v)) return null;

  const ask = (label: string) => (
    <div className="space-y-2">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <div className="min-w-0 flex-1">
          <Field label="Reel link" type="url" placeholder="https://www.instagram.com/reel/…" value={url} onChange={(e) => setUrl(e.target.value)} />
        </div>
        <Button variant="secondary" disabled={!url.trim()} reason={!url.trim() ? "Paste a link first" : null} busy={start.isPending && !!url} onClick={() => start.mutate({ url: url.trim() })}>
          {label} · free
        </Button>
      </div>
      <input ref={file} type="file" accept="video/mp4,video/quicktime" className="sr-only" aria-label="Upload the video" onChange={(e) => e.target.files?.[0] && start.mutate({ file: e.target.files[0] })} />
      <Button variant="ghost" icon={Upload} onClick={() => file.current?.click()}>Or upload the video</Button>
      <p className="text-sm text-muted">Up to 4 minutes, mp4 or mov.</p>
    </div>
  );

  return (
    <section aria-label="Study a song ad" className="max-w-[680px]">
      <Card className="space-y-3">
        <div>
          <h2 className="type-card">Study a song ad <span className="text-muted">(optional)</span></h2>
          {!study && <p className="text-sm text-muted">Paste a song ad to learn its shape: its words, beat and parts. Free.</p>}
        </div>
        {latest.isError && <p role="alert" className={errorClass}>{latest.error.message}</p>}
        {!study && ask("Study it")}
        {studying && (
          <div role="status" className="flex flex-wrap items-center gap-3">
            <p className="min-w-0 flex-1 text-sm">
              Studying the song ad…<Elapsed since={study.job?.started_at} />. You can leave this page.
            </p>
            {study.job?.status === "queued" && <Button variant="ghost" busy={cancel.isPending} onClick={() => cancel.mutate(study.job!.id)}>Cancel</Button>}
          </div>
        )}
        {study?.status === "failed" && (
          <>
            <p role="alert" className={errorClass}>We couldn't study it: {study.problem || "studying it didn't finish"}. Nothing was charged.</p>
            {ask("Try another")}
          </>
        )}
        {study?.status === "done" && (
          <details open>
            <summary className="flex min-h-11 cursor-pointer items-center font-medium">
              Song ad studied · {study.seconds != null ? clock(study.seconds) : "—"} · {bpmText(study.bpm)}
            </summary>
            <div className="space-y-3 pb-1">
              <ol className="space-y-2" aria-label="Sections">
                {study.sections.map((x, i) => (
                  <li key={i} className="space-y-1">
                    <p className="flex flex-wrap items-center gap-2 text-sm">
                      <span className="font-medium">{x.name}</span>
                      <span className="tabular-nums text-muted">{clock(x.start)}–{clock(x.end)}</span>
                      {x.guessed && <Badge>guessed</Badge>}
                    </p>
                    {x.lines.length > 0 && <p className="whitespace-pre-wrap break-words text-sm text-muted">{x.lines.join("\n")}</p>}
                  </li>
                ))}
              </ol>
              {study.lines.length > 0 && (
                <details>
                  <summary className="flex min-h-11 cursor-pointer items-center text-sm">The words with their times · {study.lines.length}</summary>
                  <ul className="space-y-1 text-sm">
                    {study.lines.map((l, i) => (
                      <li key={i} className="flex gap-3"><span className="w-10 shrink-0 tabular-nums text-muted">{clock(l.start)}</span><span className="min-w-0 break-words">{l.text}</span></li>
                    ))}
                  </ul>
                </details>
              )}
              {study.frames.length > 0 && (
                <ul className="grid grid-cols-4 gap-2 sm:grid-cols-8" aria-label="Frames">
                  {study.frames.map((f) => (
                    <li key={f.file_id} className="min-w-0">
                      <img src={fileUrl(f.file_id)} alt={`Frame at ${clock(f.t)}`} className="aspect-[9/16] w-full rounded-sm object-cover" loading="lazy" />
                      <span className="text-xs tabular-nums text-muted">{clock(f.t)}</span>
                    </li>
                  ))}
                </ul>
              )}
              <label className="flex min-h-11 items-center gap-3 text-sm">
                <input type="checkbox" className="size-5" checked={study.use_as_guide} disabled={guide.isPending} onChange={(e) => guide.mutate(e.target.checked)} />
                Use as a guide for the song directions
              </label>
              <p className="text-sm text-muted">A guide only: the directions copy its shape, never its words.</p>
              <Button variant="ghost" icon={Trash2} busy={remove.isPending} onClick={() => remove.mutate()}>Remove</Button>
            </div>
          </details>
        )}
      </Card>
    </section>
  );
}
