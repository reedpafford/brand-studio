import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pause, Play, Upload } from "lucide-react";
import { api, must } from "../api/client";
import type { components } from "../api/schema";
import { uploadFile, fileUrl } from "../api/upload";
import { useMe } from "../auth/useMe";
import { Button, creditsLabel } from "../components";
import { useBrands } from "../shell/useBrands";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";

export type Voice = components["schemas"]["VoiceOut"];

async function readVoices(brandId: number) {
  return (await must(api.GET("/brands/{brand_id}/voices", { params: { path: { brand_id: brandId } } }))).data!;
}
async function cloneVoice(brandId: number, body: { name: string; description: string; sample_file_id: number }) {
  return (await must(api.POST("/brands/{brand_id}/voices/clone", { params: { path: { brand_id: brandId } }, body }))).data!;
}

export function useVoiceList(brandId: number) {
  return useQuery({ queryKey: ["voices", brandId], queryFn: () => readVoices(brandId), enabled: brandId > 0 });
}

/** The brand's own voices (uploaded or cloned on purpose, and the styles' own) for the tab's count. */
export function useVoices(brandId: number) {
  return (useVoiceList(brandId).data?.voices ?? []).filter((v) => v.kind !== "stock");
}

/** A character's voice in the item routes (#1314): a saved or cloned voice's row, or an app voice's key; one at most. */
export const voiceFields = (v: Voice | null) => (!v ? {} : v.id !== null ? { voice_id: v.id, voice_stock_key: null } : { voice_id: null, voice_stock_key: v.stock_key });
export function voiceOf(i: { voice_id?: number | null; voice_stock_key?: string | null }, voices: Voice[]) {
  return voices.find((v) => (i.voice_id != null && v.id === i.voice_id) || (i.voice_stock_key != null && v.stock_key === i.voice_stock_key));
}

const PROVIDER: Record<string, string> = { elevenlabs: "ElevenLabs", minimax: "MiniMax", omni: "Omni" };
export const voiceLine = (v: Voice) => [v.description, v.kind === "cloned" ? `${PROVIDER[v.provider] ?? v.provider} clone` : PROVIDER[v.provider] ?? v.provider].filter(Boolean).join(" · ");
// A free sample's address is the server's own (…/voices/samples/Roger.mp3); the app reaches the server under /api.
const apiPath = (url: string) => {
  const path = new URL(url, window.location.origin).pathname;
  return path.startsWith("/api/") ? path : `/api${path}`;
};
export const sampleOf = (v: Voice) => (v.sample_url ? apiPath(v.sample_url) : v.sample_file_id ? fileUrl(v.sample_file_id) : v.preview_file_id ? fileUrl(v.preview_file_id) : null);
const BARS = [6, 10, 14, 8, 16, 12, 6, 10, 18, 12, 8, 14, 10, 6, 12, 16, 10, 8, 12, 6, 9, 13, 7, 11];

/** One voice (S8-04, S4-04): Play, its name and line, and its sample's bars. Samples play free. */
export function VoiceRow({ voice: v, picked, onPick }: { voice: Voice; picked?: boolean; onPick?: () => void }) {
  const audio = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const src = sampleOf(v);
  const why = v.state === "cloning" ? "Cloning…" : v.state === "expired" || v.state === "failed" ? v.error : v.state === "may_expire" ? v.error || "Unused for a while: MiniMax may delete it soon." : "";
  return (
    <div className={`flex min-h-13 items-center gap-3 rounded-md border px-2.5 py-2 ${picked ? "border-accent bg-accent-soft" : "border-border bg-surface"}`}>
      <button type="button" disabled={!src} title={src ? undefined : "No free sample yet"} aria-label={`${playing ? "Pause" : "Play"} ${v.name}`} onClick={() => (playing ? audio.current?.pause() : void audio.current?.play())} className="grid size-11 shrink-0 place-items-center rounded-md border border-border-button text-text disabled:text-faint lg:size-7">
        {playing ? <Pause size={12} strokeWidth={2} aria-hidden /> : <Play size={12} strokeWidth={2} aria-hidden />}
      </button>
      {src && <audio ref={audio} src={src} preload="none" onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} className="hidden" />}
      <button type="button" disabled={!onPick} onClick={onPick} className="flex min-w-0 flex-1 flex-col text-left disabled:cursor-default">
        <span className="truncate text-sm font-semibold">{v.name}{v.kind === "cloned" && !/clon/i.test(v.name) ? " (cloned)" : ""}</span>
        <span className="truncate text-xs text-muted">{voiceLine(v)}</span>
        {why && <span className={`text-xs ${v.state === "expired" || v.state === "failed" ? "text-danger" : "text-warning"}`}>{why}</span>}
      </button>
      <span aria-hidden className="hidden items-center gap-0.5 sm:flex">
        {BARS.map((h, i) => <i key={i} className={`inline-block w-0.5 rounded-[1px] ${picked ? "bg-accent" : "bg-[#b9bcc6]"}`} style={{ height: h }} />)}
      </span>
    </div>
  );
}

/** Voices on Presenters & voices (S8-04 as redrawn in S-gaps-05 L4): the brand's own voices (uploaded or cloned on
 *  purpose), then every app voice, each with a free sample; Clone a voice with its price first. */
export function Voices({ brandId }: { brandId: number }) {
  const list = useVoiceList(brandId);
  const brand = useBrands().data?.find((b) => b.id === brandId);
  const [all, setAll] = useState(false);
  const [cloning, setCloning] = useState(false);
  const owner = useMe().data?.role === "owner";
  const voices = list.data?.voices ?? [];
  const own = voices.filter((v) => v.kind !== "stock");
  const app = voices.filter((v) => v.kind === "stock").sort((a, b) => Number(!sampleOf(a)) - Number(!sampleOf(b))); // samples first
  const price = list.data ? (owner && list.data.clone_usd != null ? `up to $${list.data.clone_usd.toFixed(2)}` : `up to ${creditsLabel(list.data.clone_credits)}`) : "";
  return (
    <section aria-label="Voices" className="flex min-w-0 grow flex-col gap-3">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-semibold">Voices</h2>
        <span className="text-xs text-muted">every voice plays a free sample</span>
        <span className="flex-1" />
        <Button variant="secondary" icon={Upload} aria-expanded={cloning} onClick={() => setCloning(!cloning)}>
          Clone a voice{price && <>{" "}<span className="opacity-80">· {price}</span></>}
        </Button>
      </div>
      {cloning && <Clone brandId={brandId} price={price} owner={owner} onDone={() => setCloning(false)} />}
      <h3 className="text-xs font-semibold text-muted">{brand?.name}’s own · uploaded or cloned, saved on purpose</h3>
      {own.length ? <div className="flex flex-col gap-2">{own.map((v) => <VoiceRow key={`v${v.id}`} voice={v} />)}</div> : <p className="text-sm text-muted">None yet. Clone a voice to keep one for {brand?.name}.</p>}
      <h3 className="text-xs font-semibold text-muted">The app’s voices · {app.length} · usable in any video, never saved to a brand</h3>
      <div className="flex flex-col gap-2">
        {(all ? app : app.slice(0, 3)).map((v) => <VoiceRow key={v.stock_key ?? v.name} voice={v} />)}
      </div>
      {app.length > 3 && (
        <button type="button" className="inline-flex min-h-control items-center lg:min-h-0 self-start text-sm text-muted hover:text-text" onClick={() => setAll(!all)}>
          {all ? "Show fewer" : `+ ${app.length - 3} more`}
        </button>
      )}
    </section>
  );
}

/** Clone a voice (S-gaps-05 L4): a sample of at least 10 s of one clear voice and a name, then Clone with the price first.
 *  An editor's press waits for the owner's OK. */
function Clone({ brandId, price, owner, onDone }: { brandId: number; price: string; owner: boolean; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const queryClient = useQueryClient();
  const toast = useToast();
  const clone = useMutation({
    mutationFn: async () => cloneVoice(brandId, { name: name.trim(), description: description.trim(), sample_file_id: (await uploadFile(file!)).id }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["voices", brandId] });
      toast(owner ? `Cloning ${name.trim()}…` : `${name.trim()} waits for the owner's OK. Nothing is charged until then.`);
      onDone();
    },
  });
  const ready = !!file && !!name.trim();
  return (
    <div className="flex max-w-[280px] flex-col gap-2 rounded-lg border border-border bg-surface p-3">
      <h3 className="text-sm font-semibold">Clone a voice</h3>
      <label className="flex min-h-11 cursor-pointer items-center gap-2 rounded-md border border-dashed border-border-strong px-3 text-sm lg:min-h-9">
        <Upload size={14} strokeWidth={1.75} aria-hidden />
        <span className="truncate">{file ? file.name : "Pick a sample"}</span>
        <input type="file" accept="audio/mpeg,audio/wav,audio/x-wav,audio/mp4,audio/x-m4a,.mp3,.wav,.m4a" className="sr-only" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </label>
      <p className="text-xs text-muted">At least 10 s of one clear voice.</p>
      <input aria-label="Name" placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} className="h-control lg:h-9 rounded-md border border-border-strong bg-surface px-3 text-base lg:text-sm" />
      <input aria-label="How it sounds" placeholder="How it sounds: deep, fixed" value={description} onChange={(e) => setDescription(e.target.value)} className="h-control lg:h-9 rounded-md border border-border-strong bg-surface px-3 text-base lg:text-sm" />
      {clone.isError && <p role="alert" className={errorClass}>{clone.error.message}</p>}
      <Button disabled={!ready} busy={clone.isPending} onClick={() => clone.mutate()}>
        Clone{price && <>{" "}<span className="opacity-80">· {price}</span></>}
      </Button>
    </div>
  );
}
