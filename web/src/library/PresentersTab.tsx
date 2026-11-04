import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Mic, Plus, Upload, Users } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import { fileUrl, uploadFile } from "../api/upload";
import { Button, Menu, MenuItem } from "../components";
import { errorText as errorClass } from "../ui";
import { useRail } from "../useMedia";
import { LibraryCard, Picture } from "./Cards";
import { LibraryFrame, useSearch } from "./LibraryFrame";
import { usePreview } from "./NewItem";
import { Voices, useVoiceList, voiceFields, voiceOf, type Voice } from "./Voices";
import { cover, useItems, videos } from "./kinds";

/** Presenters & voices (S8-04): the brand's presenters (characters who present, by how they appear) beside its voices,
 *  whose samples play free. New presenter opens the S-gaps-05 L3 form. */
export function PresentersTab({ brandId }: { brandId: number }) {
  const [params, setParams] = useSearchParams();
  const adding = params.get("new") === "1";
  const setAdding = (on: boolean) => setParams((p) => (on ? p.set("new", "1") : p.delete("new"), p), { replace: true });
  const characters = useItems("character", brandId);
  const all = useVoiceList(brandId).data?.voices ?? [];
  const [q] = useSearch();
  const rail = useRail();
  const shown = (characters.data ?? []).filter((c) => c.presenter && c.name.toLowerCase().includes(q.trim().toLowerCase()));
  const action = !adding && (
    <Button icon={Plus} onClick={() => setAdding(true)}>
      New presenter
    </Button>
  );
  return (
    <LibraryFrame brandId={brandId} tab="presenters" action={action} onAdd={() => setAdding(true)} addLabel="New presenter">
      {adding ? (
        <NewPresenter brandId={brandId} onClose={() => setAdding(false)} />
      ) : (
        <div className="flex flex-col gap-8 lg:flex-row lg:items-start">
          <section aria-label="Presenters" className="flex flex-col gap-3">
            <h2 className="text-lg font-semibold">Presenters</h2>
            {characters.data && shown.length === 0 && <p className="text-sm text-muted">{q ? `Nothing called “${q}”.` : "No presenters yet. A presenter is a face and a voice; each video picks how they appear."}</p>}
            <ul className="grid grid-cols-2 gap-3 lg:flex lg:flex-wrap lg:gap-4">
              {shown.map((c) => (
                <LibraryCard key={c.id} to={`/b/${brandId}/library/characters/${c.id}`} size={rail ? "h-[200px] w-[150px]" : "aspect-[175/230] w-full"} width="lg:w-[150px]" picture={<Picture id={cover(c)} alt={c.name} className="size-full" />} name={c.name} line={<span className="block lg:w-[150px]">{[voiceOf(c, all)?.name, c.used_in_count ? `in ${videos(c.used_in_count)}` : ""].filter(Boolean).join(" · ") || "No voice yet"}</span>} />
              ))}
            </ul>
          </section>
          <Voices brandId={brandId} />
        </div>
      )}
    </LibraryFrame>
  );
}

/** New presenter (S-gaps-05 L3): a face (a photo, or a saved character) and a voice, nothing else. How they appear is each
 *  video's choice in its Cast tab. Saving is free. */
function NewPresenter({ brandId, onClose }: { brandId: number; onClose: () => void }) {
  const characters = useItems("character", brandId);
  const voices = useVoiceList(brandId).data?.voices ?? [];
  const [name, setName] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [saved, setSaved] = useState<number | null>(null);
  const [voice, setVoice] = useState<Voice | null>(null);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const picked = characters.data?.find((c) => c.id === saved);
  const preview = usePreview(photo);
  const face = preview ?? (picked && cover(picked) ? fileUrl(cover(picked)!) : null);
  const save = useMutation({
    mutationFn: async () => {
      if (picked) {
        const { error, response } = await api.PATCH("/library/{kind}/{item_id}", { params: { path: { kind: "character", item_id: picked.id } }, body: { presenter: true, ...voiceFields(voice) } });
        if (!response.ok) throw new Error(errorText(error));
        return picked.id;
      }
      const source = photo ? (await uploadFile(photo)).id : null;
      const { data, error } = await api.POST("/library/{kind}", { params: { path: { kind: "character" } }, body: { name: name.trim(), notes: "", brand_ids: [brandId], image_file_ids: [], outfits: [], source_photo_file_id: source, presenter: true, ...voiceFields(voice) } });
      if (!data) throw new Error(errorText(error));
      return data.id;
    },
    onSuccess: async (id) => {
      await queryClient.invalidateQueries({ queryKey: ["library", "character"] });
      navigate(`/b/${brandId}/library/characters/${id}`);
    },
  });
  const ready = !!picked || !!name.trim();
  return (
    <section aria-label="New presenter" className="flex max-w-[600px] flex-col gap-3">
      <h2 className="text-lg font-semibold">New presenter</h2>
      <div className="flex gap-3">
        {face ? <img src={face} alt="The face" className="h-[86px] w-[64px] shrink-0 rounded-md object-cover" /> : <span aria-hidden className="h-[86px] w-[64px] shrink-0 rounded-md border border-dashed border-border-strong bg-surface-2" />}
        <div className="flex min-w-0 flex-col gap-2">
          <label className="w-full lg:w-[200px]">
            <span className="sr-only">Name</span>
            <input value={picked ? picked.name : name} disabled={!!picked} onChange={(e) => setName(e.target.value)} placeholder="Name" className="h-9 w-full rounded-md border border-border-strong bg-surface px-3 text-base text-text placeholder:text-muted disabled:text-muted lg:text-sm" />
          </label>
          <div className="flex flex-wrap gap-2">
            <label className="inline-flex min-h-control cursor-pointer items-center gap-1.5 rounded-md border border-border-button px-3 text-sm font-medium lg:min-h-control-dense">
              <Upload size={16} strokeWidth={1.75} aria-hidden />
              {photo ? "Another photo" : "Upload a photo"}
              <input type="file" accept="image/*" className="sr-only" onChange={(e) => e.target.files?.[0] && (setPhoto(e.target.files[0]), setSaved(null))} />
            </label>
            <Menu title="Pick a saved character" trigger={(p) => <Button variant="secondary" icon={Users} {...p}>{picked ? `Saved: ${picked.name}` : "Pick a saved character"}</Button>}>
              {(close) => (characters.data ?? []).filter((c) => !c.presenter).map((c) => (
                <MenuItem key={c.id} checked={saved === c.id} onClick={() => (close(), setSaved(c.id), setPhoto(null))}>{c.name}</MenuItem>
              ))}
            </Menu>
          </div>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="w-14 text-muted">Voice</span>
        {voice && (
          <span className="inline-flex h-7 items-center gap-1.5 rounded-md border border-border px-2 text-xs font-medium">
            <Mic size={12} strokeWidth={1.75} aria-hidden />
            {voice.name}{voice.description && ` · ${voice.description.split(",")[0].toLowerCase()}`}
          </span>
        )}
        <Menu title="Voice" trigger={(p) => <button type="button" {...p} className="min-h-control text-accent-text hover:underline lg:min-h-0">{voice ? "Change" : "Pick a voice"}</button>}>
          {(close) => voices.filter((v) => v.state !== "expired" && v.state !== "failed").map((v) => (
            <MenuItem key={v.id ?? v.stock_key ?? v.name} checked={voice === v} onClick={() => (close(), setVoice(v))}>{v.name}</MenuItem>
          ))}
        </Menu>
      </div>
      {save.isError && <p role="alert" className={errorClass}>{save.error.message}</p>}
      <div className="flex flex-wrap items-center gap-3">
        <Button disabled={!ready} busy={save.isPending} reason={ready ? null : "Name it, or pick a saved character"} onClick={() => save.mutate()}>Save presenter</Button>
        <span className="text-sm text-muted">A face and a voice, nothing else.</span>
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
      </div>
    </section>
  );
}
