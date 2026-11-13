import { useState } from "react";
import { Mic, Plus } from "lucide-react";
import { useMe } from "../auth/useMe";
import { upTo, useItems } from "../library/kinds";
import { SAMPLE_TYPES, sampleOf, useCloneVoice, useVoiceList, voiceLine, voiceNote, voiceOf, type Voice } from "../library/Voices";
import { lookName, useLooks } from "../scripts/Looks";
import { useBrands } from "../shell/useBrands";
import { Dialog } from "./Dialog";
import { Failed, FileRow, Head, ICON, Loading, PlayButton } from "./libraryParts";
import { useLock } from "./useLock";

const FIRST = 3; // the app's voices shown before "Show all"

/** Library › Voices: the brand's own voices (cloned or described for it), the looks' own, then the app's, each with
 *  a sample to play and who it is the voice of. New voice clones one from a recording. */
export function VoicesTab({ brandId }: { brandId: number }) {
  const list = useVoiceList(brandId);
  const people = useItems("character", brandId).data ?? [];
  const looks = useLooks().data;
  const brand = useBrands().data?.find((b) => b.id === brandId)?.name ?? "this brand";
  const [all, setAll] = useState(false);
  const [adding, setAdding] = useState(false);
  const voices = list.data?.voices ?? [];
  const own = voices.filter((v) => v.kind !== "stock" && !v.look);
  const ofLooks = voices.filter((v) => v.kind !== "stock" && v.look);
  const app = voices.filter((v) => v.kind === "stock").sort((a, b) => Number(!sampleOf(a)) - Number(!sampleOf(b))); // samples first
  const row = (v: Voice) => {
    const src = sampleOf(v);
    const note = voiceNote(v);
    const by = people.filter((p) => voiceOf(p, [v])).map((p) => p.name);
    return (
      <li key={v.id ?? v.stock_key ?? v.name} className="rowline">
        {src ? <PlayButton src={src} of={`${v.name}’s sample`} /> : <span aria-hidden />}
        <b className="clip">{v.name}</b>
        <span>
          {voiceLine(v)}
          {note && <em className={v.state === "expired" || v.state === "failed" ? "bad" : undefined}>{note}</em>}
        </span>
        <span className="r">{v.look ? `The ${lookName(looks, v.look)} look’s voice` : by.length ? `Voice of ${by.join(", ")}` : ""}</span>
      </li>
    );
  };
  return (
    <>
      <Head
        action={
          list.isSuccess && (
            <button type="button" className="btn go" onClick={() => setAdding(true)}>
              <Plus {...ICON} />
              New voice
            </button>
          )
        }
      />
      <div className="view">
        <div className="page lib">
          {list.isPending ? (
            <Loading />
          ) : list.isError ? (
            <Failed icon={Mic} what="the voices" error={list.error} again={() => void list.refetch()} />
          ) : (
            <div className="rows">
              <h3>{brand}’s voices</h3>
              {own.length ? <ul>{own.map(row)}</ul> : <p className="hint">None yet. Clone a voice from a recording to keep one for {brand}.</p>}
              {ofLooks.length > 0 && (
                <>
                  <h3>
                    The looks’ own voices <small>each look narrates in its own</small>
                  </h3>
                  <ul>{ofLooks.map(row)}</ul>
                </>
              )}
              <h3>
                The app’s voices <small>usable in any video</small>
              </h3>
              <ul>{(all ? app : app.slice(0, FIRST)).map(row)}</ul>
              {app.length > FIRST && (
                <button type="button" className="btn ghost" onClick={() => setAll(!all)}>
                  {all ? "Show fewer" : `Show all ${app.length}`}
                </button>
              )}
            </div>
          )}
        </div>
      </div>
      {adding && <NewVoice brandId={brandId} cost={upTo(list.data?.clone_credits, list.data?.clone_usd)} onClose={() => setAdding(false)} />}
    </>
  );
}

/** New voice: a recording of one clear voice and a name, then it is cloned (paid, the server's price on the press,
 *  one request a press). Exactly what the current site's Clone a voice sends. */
function NewVoice({ brandId, cost, onClose }: { brandId: number; cost: string; onClose: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const clone = useCloneVoice(brandId, useMe().data?.role === "owner", onClose);
  const lock = useLock(clone.isPending);
  return (
    <Dialog title="New voice" confirm={cost ? `Clone · ${cost}` : "Clone"} busy={!file || !name.trim() || clone.isPending} onClose={onClose} onConfirm={() => lock((done) => clone.mutate({ file: file!, name, description }, { onSettled: done }))}>
      <FileRow label="Pick a recording" note="At least 10 s of one clear voice." accept={SAMPLE_TYPES} file={file?.name ?? ""} onPick={([f]) => setFile(f)} />
      <label className="dlab">
        Name
        <input data-autofocus value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label className="dlab">
        How it sounds
        <input value={description} placeholder="Deep, fixed" onChange={(e) => setDescription(e.target.value)} />
      </label>
      {clone.isError && (
        <p className="dsub bad" role="alert">
          {clone.error.message}
        </p>
      )}
    </Dialog>
  );
}
