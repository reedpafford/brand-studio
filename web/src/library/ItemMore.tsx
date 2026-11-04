import { useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api, errorText, must } from "../api/client";
import { uploadFile } from "../api/upload";
import { useMe } from "../auth/useMe";
import { Button } from "../components";
import { useBrands } from "../shell/useBrands";
import { useToast } from "../toast";
import { errorText as errorClass } from "../ui";
import { CharacterExtras } from "./CharacterExtras";
import { LookSheets } from "./LookSheets";
import { SheetVersions } from "./SheetVersions";
import { day, slugOf, type Item, type Kind } from "./kinds";

const field = "h-9 w-full rounded-md border border-border-strong bg-surface px-3 text-base text-text lg:text-sm";

/** Everything S8-03 doesn't draw, folded under More (S-gaps-05 L5): the sheets in other styles, its words, photo,
 *  outfits and voice sample, the brands that share it, and its history with Restore and Delete forever. */
export function ItemMore({ item, kind, brandId, title }: { item: Item; kind: Kind; brandId: number; title: string }) {
  const [open, setOpen] = useState(false);
  return (
    <section aria-label="More" className="max-w-[972px] rounded-lg border border-border bg-surface">
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="flex min-h-11 w-full items-center justify-between px-4 text-sm font-semibold">
        More
        <ChevronDown size={16} strokeWidth={1.75} aria-hidden className={`text-muted transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="flex flex-col divide-y divide-border border-t border-border px-4">
          {kind !== "prop" && (
            <Row title="Sheets in other styles">
              <div className="flex flex-col gap-4">
                <SheetVersions item={item} kind={kind} />
                {kind === "character" && <LookSheets item={item} />}
              </div>
            </Row>
          )}
          <Row title="Words, photo and brands">
            <Edit key={`${item.id}-${item.version}`} item={item} kind={kind} brandId={brandId} title={title} />
          </Row>
          <Row title="History">
            <History item={item} kind={kind} brandId={brandId} />
          </Row>
        </div>
      )}
    </section>
  );
}

const Row = ({ title, children }: { title: string; children: ReactNode }) => (
  <div className="grid gap-2 py-4 lg:grid-cols-[162px_minmax(0,1fr)] lg:gap-4">
    <h3 className="text-sm font-semibold">{title}</h3>
    <div className="min-w-0">{children}</div>
  </div>
);

/** Its name and words (a product's line and claim too), its source photo, outfits and voice sample, and its brands. */
function Edit({ item, kind, brandId, title }: { item: Item; kind: Kind; brandId: number; title: string }) {
  const { data: brands } = useBrands();
  const queryClient = useQueryClient();
  const toast = useToast();
  const start = {
    name: item.name,
    notes: item.notes ?? "",
    brand_ids: item.brand_ids ?? [],
    outfits: item.outfits ?? [],
    voice_file_id: item.voice_file_id ?? null,
    short_description: item.short_description ?? "",
    main_claim: item.main_claim ?? "",
  };
  const [form, setForm] = useState(start);
  const changed = JSON.stringify(form) !== JSON.stringify(start);
  const path = { kind, item_id: item.id };
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["library", kind] });
  const save = useMutation({
    mutationFn: async () => {
      const body = kind === "character" ? { name: form.name, notes: form.notes, brand_ids: form.brand_ids, outfits: form.outfits, voice_file_id: form.voice_file_id } : { name: form.name, notes: form.notes, brand_ids: form.brand_ids, ...(kind === "prop" ? { short_description: form.short_description, main_claim: form.main_claim } : {}) };
      const { error, response } = await api.PATCH("/library/{kind}/{item_id}", { params: { path }, body });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: () => {
      void refresh();
      toast("Saved.");
    },
  });
  const photo = useMutation({
    mutationFn: async (file: File) => must(api.PATCH("/library/{kind}/{item_id}", { params: { path }, body: { source_photo_file_id: (await uploadFile(file)).id } })),
    onSuccess: refresh,
  });
  const toggle = (id: number) => setForm({ ...form, brand_ids: form.brand_ids.includes(id) ? form.brand_ids.filter((b) => b !== id) : [...form.brand_ids, id] });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (changed && form.brand_ids.length) save.mutate();
  };
  const leaving = item.brand_ids?.includes(brandId) && !form.brand_ids.includes(brandId);
  return (
    <form onSubmit={submit} className="flex max-w-[640px] flex-col gap-3 text-sm">
      <label className="flex flex-col gap-1">
        Name
        <input className={field} required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
      </label>
      <label className="flex flex-col gap-1">
        {kind === "prop" ? "Rules (what must read right)" : "Description"}
        <textarea className={`${field} h-auto py-2`} rows={3} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
      </label>
      {kind === "prop" && (
        <>
          <label className="flex flex-col gap-1">
            What it is, in a line
            <input className={field} maxLength={500} placeholder="Grain-free salmon kibble for picky dogs" value={form.short_description} onChange={(e) => setForm({ ...form, short_description: e.target.value })} />
          </label>
          <label className="flex flex-col gap-1">
            Main claim
            <input className={field} maxLength={500} placeholder="Dogs finish the bowl" value={form.main_claim} onChange={(e) => setForm({ ...form, main_claim: e.target.value })} />
          </label>
          {(item.advice ?? []).map((a) => <p key={a} className="text-warning">{a}</p>)}
        </>
      )}
      {kind !== "prop" && (
        <p className="flex flex-wrap items-center gap-2">
          <span className="text-muted">{item.source_photo_file_id ? "Made from an uploaded photo (not used in videos itself)." : "No photo: drawn from the description."}</span>
          <label className="cursor-pointer text-accent-text hover:underline">
            {item.source_photo_file_id ? "Replace the photo" : "Upload a photo"}
            <input type="file" accept="image/*" className="sr-only" onChange={(e) => e.target.files?.[0] && photo.mutate(e.target.files[0])} />
          </label>
        </p>
      )}
      {kind === "character" && (
        <CharacterExtras outfits={form.outfits} voiceFileId={form.voice_file_id} onOutfits={(outfits) => setForm({ ...form, outfits })} onVoice={(voice_file_id) => setForm({ ...form, voice_file_id })} />
      )}
      <fieldset className="flex flex-wrap gap-x-4">
        <legend className="mb-1 font-medium">Shared with brands</legend>
        {brands?.map((b) => (
          <label key={b.id} className="inline-flex min-h-11 items-center gap-2 lg:min-h-8">
            <input type="checkbox" checked={form.brand_ids.includes(b.id)} onChange={() => toggle(b.id)} />
            {b.name}
          </label>
        ))}
      </fieldset>
      {leaving && form.brand_ids.length > 0 && <p className="text-warning">This takes {form.name} out of this brand’s {title.toLowerCase()}.</p>}
      {(save.error ?? photo.error) && <p role="alert" className={errorClass}>{(save.error ?? photo.error)!.message}</p>}
      <div className="flex items-center gap-2">
        <Button type="submit" disabled={!changed || form.brand_ids.length === 0} reason={form.brand_ids.length === 0 ? "Pick at least one brand" : null} busy={save.isPending}>Save changes</Button>
        {changed && <Button variant="ghost" onClick={() => setForm(start)}>Undo changes</Button>}
      </div>
    </form>
  );
}

/** Its versions with who saved each and Restore (which can be undone), and the owner's Delete forever. */
function History({ item, kind, brandId }: { item: Item; kind: Kind; brandId: number }) {
  const owner = useMe().data?.role === "owner";
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();
  const path = { kind, item_id: item.id };
  const versions = useQuery({ queryKey: ["library", kind, "versions", item.id, item.version], queryFn: async () => (await api.GET("/library/{kind}/{item_id}/versions", { params: { path } })).data ?? [] });
  const members = useQuery({ queryKey: ["team", "members"], queryFn: async () => (await api.GET("/team/members")).data ?? [] });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["library", kind] });
  const restoreCall = (version: number) => must(api.POST("/library/{kind}/{item_id}/versions/{version}/restore", { params: { path: { ...path, version } } }));
  const restore = useMutation({
    mutationFn: restoreCall,
    onSuccess: ({ data }, version) => {
      void refresh();
      toast(`Restored v${version} as v${data?.version}.`, () => restoreCall(item.version).then(refresh));
    },
  });
  const purge = useMutation({
    mutationFn: async () => {
      await must(api.DELETE("/library/{kind}/{item_id}", { params: { path } }));
      await must(api.DELETE("/library/{kind}/{item_id}/permanent", { params: { path } }));
    },
    onSuccess: async () => {
      await refresh();
      navigate(`/b/${brandId}/library/${slugOf(kind)}`);
    },
  });
  const who = (id: number | null) => members.data?.find((m) => m.id === id)?.name ?? "someone";
  const old = (versions.data ?? []).filter((v) => v.version !== item.version);
  return (
    <div className="flex flex-col gap-2 text-sm">
      <p>v{item.version} is in use.</p>
      {old.length > 0 && (
        <ul className="divide-y divide-border">
          {old.map((v) => (
            <li key={v.version} className="flex min-h-10 items-center gap-3">
              <span className="flex-1">v{v.version} · {day(v.created_at)} by {who(v.saved_by_id)}</span>
              <button type="button" className="min-h-11 text-accent-text hover:underline lg:min-h-0" aria-label={`Restore v${v.version}`} onClick={() => restore.mutate(v.version)}>Restore</button>
            </li>
          ))}
        </ul>
      )}
      {owner && (
        <p>
          <button type="button" className="min-h-11 text-danger hover:underline lg:min-h-0" onClick={() => window.confirm(`Delete ${item.name} forever? This removes all versions and can't be undone.`) && purge.mutate()}>
            Delete forever
          </button>
        </p>
      )}
      {(restore.error ?? purge.error) && <p role="alert" className={errorClass}>{(restore.error ?? purge.error)!.message}</p>}
    </div>
  );
}
