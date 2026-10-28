import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { Lock, Pencil, X } from "lucide-react";
import { api, errorText } from "../api/client";
import { Badge, Button, Card, Dialog, Field, TextArea } from "../components";
import { useBrands } from "../shell/useBrands";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import type { Script } from "./useScript";
import { useSongs } from "./useSongs";

export const MAX_LYRICS = 5000; // the music service's limits (app/music.py)
const MAX_STYLE = 1000;
const SUNG_PER_SECOND = 2.5; // about how fast a song is sung

/** The sung words: section tags like [Verse] are not sung and don't count. */
export const sungWords = (lyrics: string) => lyrics.replace(/\[[^\]]*\]/g, " ").split(/\s+/).filter(Boolean).length;
const words = (s: string) => s.split(/\s+/).filter(Boolean);
const n = (x: number) => x.toLocaleString("en-GB");

type Song = { text: string; style_line: string; spoken_end_line: string };

/** Save the lyrics, style line and spoken end line of a song script's version (slot 0). */
function useSaveSong(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Song) => {
      const { data, error } = await api.PUT("/scripts/{script_id}/drafts/{slot}", { params: { path: { script_id: id, slot: 0 } }, body });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["script-lib", id], data);
      void queryClient.invalidateQueries({ queryKey: ["songs", id] }); // takes of other words are now out of date
      return queryClient.invalidateQueries({ queryKey: ["scripts"] });
    },
  });
}

/** Advice under saved lyrics (flows S2): never blocks; each has its free fix, with Undo. */
function Advice({ song, brand, save }: { song: Song; brand?: { name: string; end_line: string }; save: (next: Song, said: string) => void }) {
  const styleWords = words(song.style_line);
  const sung = sungWords(song.text);
  const endLine = brand?.end_line.trim() ?? "";
  const named = !!brand && song.text.toLowerCase().includes(brand.name.toLowerCase());
  const items: { text: string; fix?: ReactNode }[] = [];
  if (!song.style_line.trim()) items.push({ text: "No style yet: the song will be upbeat pop by default." });
  if (styleWords.length > 25)
    items.push({
      text: "Music models follow short styles better. Keep it under 25 words.",
      fix: <Button variant="secondary" onClick={() => save({ ...song, style_line: styleWords.slice(0, 25).join(" ") }, "Style cut to 25 words.")}>Shorten it · free</Button>,
    });
  if (sung > 150) items.push({ text: `About ${Math.round(sung / SUNG_PER_SECOND)} s sung. That's a long ad: the video will be about that long too.` });
  if (brand && !named && !song.spoken_end_line)
    items.push({
      text: `The song doesn't say ${brand.name} or where to find it.`,
      fix: endLine ? (
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => save({ ...song, text: `${song.text.trimEnd()}\n\n[Outro]\n${endLine}` }, "The end line is sung at the end.")}>Sing the end line · free</Button>
          <Button variant="secondary" onClick={() => save({ ...song, spoken_end_line: endLine }, "The end line is spoken over the end.")}>Speak it over the end · free</Button>
        </div>
      ) : (
        <p className="text-sm text-muted">Add a line to the lyrics that names {brand.name} and where to find it.</p>
      ),
    });
  if (items.length === 0) return null;
  return (
    <details className="max-w-[680px] rounded-lg border border-border bg-surface px-4">
      <summary className="flex min-h-11 cursor-pointer items-center py-2 font-medium">Advice · {items.length}</summary>
      <ul className="space-y-3 pb-4">
        {items.map((x) => (
          <li key={x.text} className="space-y-2">
            <p className="text-sm">{x.text}</p>
            {x.fix}
          </li>
        ))}
      </ul>
    </details>
  );
}

/** "Spoken at the end: '…'" with Edit and Remove (rule 18, flows S2). */
function SpokenLine({ song, readOnly, save }: { song: Song; readOnly: boolean; save: (next: Song, said: string) => void }) {
  const [editing, setEditing] = useState<string | null>(null);
  if (!song.spoken_end_line) return null;
  if (editing !== null)
    return (
      <form
        className="flex max-w-[680px] flex-col gap-2 sm:flex-row sm:items-end"
        onSubmit={(e) => {
          e.preventDefault();
          if (editing.trim()) save({ ...song, spoken_end_line: editing.trim() }, "Saved.");
          setEditing(null);
        }}
      >
        <div className="min-w-0 flex-1">
          <Field label="Spoken at the end" value={editing} onChange={(e) => setEditing(e.target.value)} maxLength={300} autoFocus />
        </div>
        <Button type="submit" variant="secondary" disabled={!editing.trim()}>Save</Button>
        <Button variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
      </form>
    );
  return (
    <div className="flex max-w-[680px] flex-wrap items-center gap-2">
      <p className="min-w-0 flex-1 text-sm">Spoken at the end: "{song.spoken_end_line}"</p>
      {!readOnly && (
        <>
          <Button variant="ghost" icon={Pencil} onClick={() => setEditing(song.spoken_end_line)}>Edit</Button>
          <Button variant="ghost" icon={X} onClick={() => save({ ...song, spoken_end_line: "" }, "The spoken end line is removed.")}>Remove</Button>
        </>
      )}
    </div>
  );
}

/** Step 1 of a song script: the lyrics (sung word for word; the AI never changes them) and the style line (flows S2). */
export function SongStep({ script: s, brandId, onDirty }: { script: Script; brandId: number; onDirty: (dirty: boolean) => void }) {
  const v = s.versions.find((x) => x.slot === 0);
  const saved: Song = { text: v?.text ?? "", style_line: v?.style_line ?? "", spoken_end_line: v?.spoken_end_line ?? "" };
  const brand = useBrands().data?.find((b) => b.id === brandId);
  const takes = useSongs(s.id).data?.takes.length ?? 0;
  const put = useSaveSong(s.id);
  const toast = useToast();
  // The boxes while editing; null shows the saved lyrics. Kept for this tab, so no way out of the page loses them.
  const memory = `song-words-${s.id}`;
  // "Edit lyrics or style" from a refused take opens the boxes at once (no lock, no confirm: it already knows).
  const [params, setParams] = useSearchParams();
  const asked = params.get("edit") === "1" && !s.published;
  const [draft, setDraftNow] = useState<{ text: string; style: string } | null>(() => {
    try {
      const kept = sessionStorage.getItem(memory);
      if (kept) return JSON.parse(kept);
    } catch {
      /* private window */
    }
    return (saved.text.trim() || s.published) && !asked ? null : { text: saved.text, style: saved.style_line };
  });
  const setDraft = (d: { text: string; style: string } | null) => {
    setDraftNow(d);
    try {
      if (d === null || (d.text === saved.text && d.style === saved.style_line)) sessionStorage.removeItem(memory);
      else sessionStorage.setItem(memory, JSON.stringify(d));
    } catch {
      /* private window: just not kept */
    }
  };
  const [asking, setAsking] = useState(false);
  useEffect(() => {
    if (asked) setParams({}, { replace: true }); // done: a reload shows the step as usual
  }, [asked]); // eslint-disable-line react-hooks/exhaustive-deps
  const dirty = draft !== null && (draft.text !== saved.text || draft.style !== saved.style_line);
  useEffect(() => onDirty(dirty), [dirty]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => onDirty(false), []); // eslint-disable-line react-hooks/exhaustive-deps

  // A free fix from Advice or the spoken line: saved at once, with Undo back to what was there.
  const fix = (next: Song, said: string) => {
    const before = saved;
    put.mutate(next, { onSuccess: () => toast(said, () => put.mutate(before)) });
  };

  if (draft === null) {
    return (
      <div className="space-y-4">
        <Card className="max-w-[680px] space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge icon={Lock}>{s.published ? "Published · final" : "Sung word for word"}</Badge>
            {!s.published && (
              <Button variant="secondary" icon={Pencil} onClick={() => (takes > 0 ? setAsking(true) : setDraft({ text: saved.text, style: saved.style_line }))}>
                Edit lyrics
              </Button>
            )}
          </div>
          <pre className="whitespace-pre-wrap break-words type-script">{saved.text}</pre>
          <p className="text-sm text-muted">{saved.style_line ? `Style: ${saved.style_line}` : "No style yet"} · About {Math.round(sungWords(saved.text) / SUNG_PER_SECOND)} s sung · {n(sungWords(saved.text))} words</p>
        </Card>
        {put.isError && <p role="alert" className={errorClass}>{put.error.message}</p>}
        <SpokenLine song={saved} readOnly={s.published} save={fix} />
        {!s.published && <Advice song={saved} brand={brand} save={fix} />}
        {asking && (
          <Dialog title="Edit the lyrics?" cancelLabel="Cancel" actionLabel="Edit lyrics" onCancel={() => setAsking(false)} onConfirm={() => { setAsking(false); setDraft({ text: saved.text, style: saved.style_line }); }}>
            Your {takes === 1 ? "take" : `${takes} takes`} will be out of date. They're kept, and you can make new ones.
          </Dialog>
        )}
      </div>
    );
  }

  const over = draft.text.length - MAX_LYRICS;
  const sung = sungWords(draft.text);
  const reason = over > 0 ? `Cut ${n(over)} characters first` : !draft.text.trim() ? "Write or paste the lyrics first" : !dirty ? "Nothing changed yet" : null;
  return (
    <div className="space-y-4">
      <Card className="max-w-[680px] space-y-3">
        <TextArea
          label="Lyrics"
          rows={12}
          placeholder={"[Verse]\nPaste or write the lyrics here"}
          value={draft.text}
          onChange={(e) => setDraft({ ...draft, text: e.target.value })}
          counter={over > 0 ? `Cut ${n(over)} characters` : `${n(draft.text.length)} / ${n(MAX_LYRICS)}`}
          hint={`Sung exactly as written. [Verse] and [Chorus] tags are fine. About ${Math.round(sung / SUNG_PER_SECOND)} s sung · ${n(sung)} words`}
          error={over > 0 ? `That's ${n(over)} characters over the music model's ${n(MAX_LYRICS)}. Your words stay here; cut some, then save.` : null}
        />
        <TextArea
          label="Style"
          rows={Math.min(4, Math.max(1, Math.ceil(draft.style.length / 45)))}
          maxLength={MAX_STYLE}
          placeholder="pop, female lead, 120 BPM, upbeat, modern polished"
          value={draft.style}
          onChange={(e) => setDraft({ ...draft, style: e.target.value })}
          counter={`${n(draft.style.length)} / ${n(MAX_STYLE)}`}
          hint="Genre, voice, speed and feel. Empty is fine: the song will be upbeat pop."
        />
        {put.isError && <p role="alert" className={errorClass}>{put.error.message}</p>}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            busy={put.isPending}
            disabled={reason !== null}
            reason={reason}
            onClick={() => put.mutate({ ...saved, text: draft.text, style_line: draft.style.trim() }, { onSuccess: () => { setDraft(null); toast("Saved."); } })}
          >
            Save lyrics
          </Button>
          {dirty && <span className="text-sm text-warning">Not saved yet</span>}
          {(dirty || saved.text.trim()) && (
            <Button variant="ghost" onClick={() => setDraft(saved.text.trim() ? null : { text: "", style: saved.style_line })}>
              {dirty ? "Discard changes" : "Cancel"}
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}
