import { useRef, useState, type ReactNode } from "react";
import { Pause, Play, Trash2, Upload, type LucideIcon } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { fileUrl } from "../api/upload";
import { length, useAddClip, useDescribePrice, useRemoveClip, type Footage } from "../library/FootageTab";
import { upTo, useItems } from "../library/kinds";
import { Dialog } from "./Dialog";
import { useLock } from "./useLock";

export const ICON = { size: 16, strokeWidth: 1.75, "aria-hidden": true } as const;
const TABS = { product: "Product", cast: "Cast", footage: "Footage", voices: "Voices" } as const;
export type Tab = keyof typeof TABS;

/** The Library's open tab, kept in the address (?tab=cast); Product when it says nothing. */
export function useTab() {
  const [params, setParams] = useSearchParams();
  const asked = params.get("tab") ?? "";
  const tab: Tab = asked in TABS ? (asked as Tab) : "product";
  return [tab, (t: Tab) => setParams(t === "product" ? {} : { tab: t })] as const;
}

/** The picked product or person, kept in the address (?p=179). */
export function usePick() {
  const [params, setParams] = useSearchParams();
  return [Number(params.get("p")) || null, (id: number) => setParams((p) => (p.set("p", String(id)), p), { replace: true })] as const;
}

/** The Library's header: its tabs, and the open tab's one main press. */
export function Head({ action }: { action?: ReactNode }) {
  const [tab, setTab] = useTab();
  return (
    <header className="head lhead">
      <h1>Library</h1>
      <div className="seg" role="group" aria-label="Kind">
        {(Object.keys(TABS) as Tab[]).map((t) => (
          <button key={t} type="button" aria-pressed={t === tab} onClick={() => setTab(t)}>
            {TABS[t]}
          </button>
        ))}
      </div>
      <span className="grow" />
      {action}
    </header>
  );
}

/** A tab with nothing in it yet, or that couldn't be read: what it is for, and the one next step. */
export function Hold({ icon: Icon, title, bad, action, children }: { icon: LucideIcon; title: string; bad?: boolean; action?: ReactNode; children: ReactNode }) {
  return (
    <div className={`hold bare${bad ? " bad" : ""}`} role={bad ? "alert" : undefined}>
      <Icon size={18} strokeWidth={1.75} aria-hidden />
      <b>{title}</b>
      <p>{children}</p>
      {action && <div className="offers">{action}</div>}
    </div>
  );
}

/** A read that failed: the server's own words when it gave any, and a way to try again. */
export function Failed({ icon, what, error, again }: { icon: LucideIcon; what: string; error: Error; again: () => void }) {
  return (
    <Hold
      bad
      icon={icon}
      title={`Couldn’t load ${what}`}
      action={
        <button type="button" className="btn soft" onClick={again}>
          Try again
        </button>
      }
    >
      {error.message === "load" ? "Check your connection." : error.message}
    </Hold>
  );
}

export const Loading = () => (
  <p className="none" role="status">
    Loading…
  </p>
);

/** Play or stop a sample. Samples play free. */
export function PlayButton({ src, of }: { src: string; of: string }) {
  const audio = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  return (
    <button type="button" className="btn soft square" aria-label={`${playing ? "Stop" : "Play"} ${of}`} onClick={() => (playing ? audio.current?.pause() : void audio.current?.play()?.catch(() => {}))}>
      {playing ? <Pause {...ICON} size={14} /> : <Play {...ICON} size={14} />}
      <audio ref={audio} src={src} preload="none" onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} />
    </button>
  );
}

/** A file to choose, as a row: what to choose, then its name once chosen. */
export function FileRow({ label, note, accept, file, multiple, disabled, onPick }: { label: string; note: string; accept: string; file: string; multiple?: boolean; disabled?: boolean; onPick: (files: File[]) => void }) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <button type="button" className="way filerow" disabled={disabled} onClick={() => input.current?.click()}>
        <Upload {...ICON} />
        <span>
          <b className="clip">{file || label}</b>
          <small>{note}</small>
        </span>
      </button>
      <input ref={input} type="file" hidden aria-label={label} accept={accept} multiple={multiple} onChange={(e) => (e.target.files?.length && onPick([...e.target.files]), (e.target.value = ""))} />
    </>
  );
}

/** A clip as a tile: its first frame whole, never cut, and how long it is. */
export function ClipTile({ clip, onOpen }: { clip: Footage; onOpen: () => void }) {
  const words = clip.description || "A clip";
  return (
    <button type="button" className="ac" aria-label={`${words}, ${length(clip.seconds)} long`} title={words} onClick={onOpen}>
      {clip.thumb_file_id != null && <img src={fileUrl(clip.thumb_file_id)} alt="" loading="lazy" />}
      <span className="len">{length(clip.seconds)}</span>
    </button>
  );
}

/** A clip opened larger: it plays, with what it shows, and Delete (free, with Undo in the toast). */
export function ClipOpen({ brandId, clip, onClose }: { brandId: number; clip: Footage; onClose: () => void }) {
  const remove = useRemoveClip(brandId, clip.id);
  const product = useItems("prop", brandId).data?.find((p) => p.id === clip.product_id)?.name;
  return (
    <Dialog title="A clip" confirm="Close" onClose={onClose} onConfirm={onClose}>
      <div className="lb">
        <video src={fileUrl(clip.file_id)} poster={clip.thumb_file_id != null ? fileUrl(clip.thumb_file_id) : undefined} controls preload="none" aria-label={clip.description || "A clip of the brand’s footage"} />
        <div>
          <p className="dsub">{clip.describing ? "Describing what it shows…" : clip.description || clip.note || "Not described yet. The director skips it until it is."}</p>
          <p className="hint">{[`${length(clip.seconds)} long`, clip.competitor ? "A competitor’s product" : (product ?? "No product"), clip.folder ? `in ${clip.folder}` : "not in a folder"].join(" · ")}</p>
          <button type="button" className="btn soft" disabled={remove.isPending} onClick={() => remove.mutate(undefined, { onSuccess: onClose })}>
            <Trash2 {...ICON} size={14} />
            Delete this clip
          </button>
        </div>
      </div>
    </Dialog>
  );
}

/** Add one clip: the file, what it shows, and its product. Left without words the AI describes it from two of its
 *  frames, which is paid: the price is on the press, and the press is one request (./useLock). */
export function AddClip({ brandId, folder, productId, file: dropped, onClose }: { brandId: number; folder: string; productId: number | null; file?: File | null; onClose: () => void }) {
  const [file, setFile] = useState<File | null>(dropped ?? null);
  const [words, setWords] = useState("");
  const [product, setProduct] = useState(productId);
  const products = useItems("prop", brandId).data ?? [];
  const price = useDescribePrice(brandId);
  const add = useAddClip(brandId, onClose);
  const lock = useLock(add.isPending);
  const cost = upTo(price.data?.credits, price.data?.usd);
  const ai = !words.trim();
  return (
    <Dialog title="Add a clip" confirm={ai && cost ? `Add clip · ${cost}` : "Add clip"} busy={!file || add.isPending} onClose={onClose} onConfirm={() => lock((done) => add.mutate({ file: file!, words, folder, product, competitor: false }, { onSettled: done }))}>
      <p className="dsub">To {folder || "All footage (the top)"}</p>
      <FileRow label="Choose a clip" note="An MP4 or WebM of up to 3 minutes." accept="video/mp4,video/webm" file={file?.name ?? ""} onPick={([f]) => setFile(f)} />
      <label className="dlab">
        What it shows
        <textarea rows={3} maxLength={500} value={words} placeholder="The small alarm opens, beeps and flashes red." onChange={(e) => (setWords(e.target.value), add.reset())} />
      </label>
      <p className="hint">{ai ? `Leave it empty and the AI describes it from two of its frames · ${cost || "…"}` : "Your words, as the director reads them."}</p>
      {products.length > 0 && (
        <label className="dlab">
          Product
          <select value={product ?? ""} onChange={(e) => setProduct(e.target.value ? Number(e.target.value) : null)}>
            <option value="">No product</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
      )}
      {add.isError && (
        <p className="dsub bad" role="alert">
          {add.error.message}
        </p>
      )}
    </Dialog>
  );
}
