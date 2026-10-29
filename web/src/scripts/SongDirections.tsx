import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Check, Sparkles, Trash2 } from "lucide-react";
import { api, errorText } from "../api/client";
import { Badge, Button, Card, Dialog, Field, TextArea } from "../components";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { lengthNote, type Song } from "./SongStep";
import { useAllowanceStop, type Script } from "./useScript";

/** One song direction Claude wrote (flows S3): a suggestion only; nothing reaches the lyrics without Use this one (rule 19). */
export type Direction = { id: number; title: string; concept: string; lyrics: string; style_line: string; visual_concept: string; recommended: boolean; left_out: string[]; unchecked_claims: string[] };
type Job = { id: number; status: "queued" | "running" | "failed" | "refused"; reason: string | null; started_at: string };
/** The S3 fields on a song script's version (Next-Server's directions route). */
export type DirectionsDraft = { song_directions: Direction[]; directions_job: Job | null; directions_estimate_credits: number; directions_stop: string | null; claims_to_check: string[] };

export const directionsOf = (v: unknown): DirectionsDraft => {
  const d = (v ?? {}) as Partial<DirectionsDraft>;
  return { song_directions: d.song_directions ?? [], directions_job: d.directions_job ?? null, directions_estimate_credits: d.directions_estimate_credits ?? 0, directions_stop: d.directions_stop ?? null, claims_to_check: d.claims_to_check ?? [] };
};

// The routes are Next-Server's; until they are in the generated schema they are called untyped.
const call = async (method: "POST" | "DELETE", path: string, body?: object) => {
  const { data, error, response } = await (api as unknown as Record<string, (p: string, o: object) => Promise<{ data?: unknown; error?: unknown; response: Response }>>)[method](path, body ? { body } : {});
  if (!response.ok) throw new Error(errorText(error));
  return data;
};

function Elapsed({ since }: { since: string }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const s = Math.max(0, Math.round((now - Date.parse(since)) / 1000));
  return <span className="tabular-nums">{Math.floor(s / 60)}:{String(s % 60).padStart(2, "0")}</span>;
}

/** "Not checked: '…'" under the lyrics after a direction is used: the owner vouches (Keep it) or edits (flows S3). Advice, never a block. */
export function ClaimsNote({ script: s, claims, onEdit }: { script: Script; claims: string[]; onEdit: () => void }) {
  const queryClient = useQueryClient();
  const keep = useMutation({ mutationFn: () => call("POST", `/scripts/${s.id}/drafts/0/claims/keep`), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["script-lib", s.id] }) });
  if (claims.length === 0 || s.published) return null;
  return (
    <Card className="max-w-[680px] space-y-2">
      <p className="text-sm">Not checked against the brand's facts: {claims.map((c) => `"${c}"`).join(", ")}. Keep it only if it's true.</p>
      {keep.isError && <p role="alert" className={errorClass}>{keep.error.message}</p>}
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" icon={Check} busy={keep.isPending} onClick={() => keep.mutate()}>Keep it</Button>
        <Button variant="ghost" onClick={onEdit}>Edit lyrics</Button>
      </div>
    </Card>
  );
}

/** S3: Write 2 song directions (optional). From a script and Sounds like boxes, the two cards, Use this one (Undo), Write 2 more. */
export function SongDirections({ script: s, brandId, saved, hasWords, onUsed }: { script: Script; brandId: number; saved: Song; hasWords: boolean; onUsed: () => void }) {
  const v = s.versions.find((x) => x.slot === 0);
  const d = directionsOf(v);
  const queryClient = useQueryClient();
  const toast = useToast();
  const [source, setSource] = useState("");
  const [soundsLike, setSoundsLike] = useState("");
  const [asking, setAsking] = useState<Direction | null>(null);
  const stop = useAllowanceStop(s, d.directions_estimate_credits) ?? d.directions_stop;
  const job = d.directions_job;
  const busy = job?.status === "queued" || job?.status === "running";
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["script-lib", s.id] });
  // While Claude writes, the version is read again until the cards are in.
  useEffect(() => {
    if (!busy) return;
    const t = setInterval(() => void refresh(), 3000);
    return () => clearInterval(t);
  }, [busy]); // eslint-disable-line react-hooks/exhaustive-deps

  const base = `/scripts/${s.id}/drafts/0/directions`;
  const write = useMutation({ mutationFn: () => call("POST", base, { source: source.trim() || undefined, sounds_like: soundsLike.trim() || undefined }), onSuccess: refresh });
  const cancel = useMutation({ mutationFn: (id: number) => call("POST", `/jobs/${id}/cancel`), onSuccess: refresh });
  const use = useMutation({
    mutationFn: (x: Direction) => call("POST", `${base}/${x.id}/use`) as Promise<{ was_text: string; was_style_line: string }>,
    onSuccess: async (r, x) => {
      setAsking(null);
      onUsed();
      await refresh();
      void queryClient.invalidateQueries({ queryKey: ["songs", s.id] });
      const before: Song = { ...saved, text: r?.was_text ?? saved.text, style_line: r?.was_style_line ?? saved.style_line };
      toast(`"${x.title}" is in. The lyrics are yours now: the AI won't change them.`, () =>
        void api.PUT("/scripts/{script_id}/drafts/{slot}", { params: { path: { script_id: s.id, slot: 0 } }, body: before }).then(refresh),
      );
    },
  });
  const remove = useMutation({
    mutationFn: (x: Direction) => call("DELETE", `${base}/${x.id}`),
    onSuccess: async (_r, x) => {
      await refresh();
      toast(`"${x.title}" removed.`, () => void call("POST", `${base}/${x.id}/restore`).then(refresh));
    },
  });
  // Only the latest press's refusal shows, until the next press.
  const latest = [write, cancel, use, remove].reduce((a, m) => (m.submittedAt > a.submittedAt ? m : a));
  const pick = (x: Direction) => (hasWords ? setAsking(x) : use.mutate(x));
  // Hidden until the server offers directions (its route sends the price): never a press with nothing behind it.
  if (s.published || !(v && "directions_estimate_credits" in v)) return null;
  const any = d.song_directions.length > 0;

  return (
    <section aria-label="Song directions" className="space-y-3">
      <Card className="max-w-[680px] space-y-3">
        <div>
          <h2 className="type-card">Write 2 song directions <span className="text-muted">(optional)</span></h2>
          <p className="text-sm text-muted">Claude writes 2 songs from the brand. Nothing goes into your lyrics until you pick one.</p>
        </div>
        <TextArea label="From a script (optional)" rows={3} maxLength={20000} placeholder="Paste a script or voice-over to turn into a song" value={source} onChange={(e) => setSource(e.target.value)} hint="Its lines stay in order, as close to word for word as the rhyme allows, and no claims are added." />
        <Field label="Sounds like (optional)" maxLength={200} placeholder="A song or an artist" value={soundsLike} onChange={(e) => setSoundsLike(e.target.value)} hint="The style describes the sound and never names it: Suno won't take names." />
        {busy && job ? (
          <div role="status" className="flex flex-wrap items-center gap-3">
            <p className="min-w-0 flex-1 text-sm">
              {job.status === "queued" ? "Waiting to start" : "Writing 2 directions…"} <Elapsed since={job.started_at} />. It shows here when it's ready. You can leave this page.
            </p>
            {job.status === "queued" && (
              <Button variant="ghost" busy={cancel.isPending} onClick={() => cancel.mutate(job.id)}>Cancel</Button>
            )}
          </div>
        ) : (
          <>
            {job?.status === "failed" && <p role="alert" className={errorClass}>The directions didn't finish. Nothing was charged.</p>}
            {job?.status === "refused" && <p role="alert" className={errorClass}>Claude won't write this: {job.reason ?? "it didn't say why"}. Change the boxes above and try again, or write your own lyrics.</p>}
            {latest.isError && <p role="alert" className={errorClass}>{latest.error.message}</p>}
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="secondary" icon={Sparkles} price={d.directions_estimate_credits} disabled={stop !== null} reason={stop} busy={write.isPending} onClick={() => write.mutate()}>
                {job?.status === "failed" || job?.status === "refused" ? "Try again" : any ? "Write 2 more" : "Write 2 song directions for me"}
              </Button>
              {d.directions_stop && stop === d.directions_stop && <Link to={`/b/${brandId}/brand`} className="text-sm underline">Open the brand page</Link>}
            </div>
          </>
        )}
      </Card>
      {any && (
        <details open={!saved.text.trim()} className="rounded-lg border border-border bg-surface px-4">
          <summary className="flex min-h-11 cursor-pointer items-center py-2 font-medium">Directions · {d.song_directions.length}</summary>
          <ul className="grid gap-3 pb-4 lg:grid-cols-2 [&>li]:min-w-0">
            {d.song_directions.map((x) => (
              <li key={x.id}>
                <Card className="h-full space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="type-card">{x.title}</h3>
                    {x.recommended && <Badge tone="accent">Recommended</Badge>}
                  </div>
                  <p className="text-sm">{x.concept}</p>
                  <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap break-words rounded-md bg-surface-2 p-3 type-script">{x.lyrics}</pre>
                  <p className="text-sm text-muted">{lengthNote(x.lyrics)}</p>
                  <p className="text-sm">Style: {x.style_line}</p>
                  <p className="text-sm text-muted">On screen: {x.visual_concept}</p>
                  {x.left_out.length > 0 && <p className="text-sm">Leaves out: {x.left_out.join(", ")}</p>}
                  {x.unchecked_claims.length > 0 && <p className="text-sm text-warning">Not checked: {x.unchecked_claims.map((c) => `"${c}"`).join(", ")}</p>}
                  <div className="flex flex-wrap gap-2 pt-1">
                    <Button variant="secondary" busy={use.isPending && use.variables?.id === x.id} onClick={() => pick(x)}>Use this one</Button>
                    <Button variant="ghost" icon={Trash2} busy={remove.isPending && remove.variables?.id === x.id} onClick={() => remove.mutate(x)} aria-label={`Remove "${x.title}"`}>Remove</Button>
                  </div>
                </Card>
              </li>
            ))}
          </ul>
          <p className="pb-4 text-sm text-muted">Neither fits? Write 2 more above, or write your own lyrics.</p>
        </details>
      )}
      {asking && (
        <Dialog title={`Replace your lyrics with "${asking.title}"?`} cancelLabel="Not yet" actionLabel="Replace" busy={use.isPending} onCancel={() => setAsking(null)} onConfirm={() => use.mutate(asking)}>
          Your words are kept in Undo.
        </Dialog>
      )}
    </section>
  );
}
