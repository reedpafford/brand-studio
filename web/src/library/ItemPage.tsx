import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import { fileUrl, uploadFile } from "../api/upload";
import type { components } from "../api/schema";
import { useBrands } from "../shell/useBrands";
import { btnPrimary, btnSecondary, card, errorText as errorClass, input, linkText, pageTitle } from "../ui";
import { CharacterExtras } from "./CharacterExtras";
import { KINDS, isKindSlug } from "./kinds";

type Item = components["schemas"]["ItemOut"];

const day = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });

export function ItemPage() {
  const { brandId, kindSlug, itemId } = useParams();
  const slug = isKindSlug(kindSlug) ? kindSlug : null;
  const kind = slug ? KINDS[slug].kind : "character";
  const item_id = Number(itemId);
  const item = useQuery({
    enabled: !!slug,
    queryKey: ["library", kind, "item", item_id],
    queryFn: async () => (await api.GET("/library/{kind}/{item_id}", { params: { path: { kind, item_id } } })).data ?? null,
  });
  if (!slug) return <p className="p-6">That library doesn't exist.</p>;
  if (item.isPending) return <p className="p-6 text-muted">Loading…</p>;
  if (!item.data) return <p className="p-6">That {KINDS[slug].one} doesn't exist, or it was archived.</p>;
  return <ItemEditor key={`${item.data.id}-${item.data.version}`} item={item.data} slug={slug} brandId={Number(brandId)} />;
}

function ItemEditor({ item, slug, brandId }: { item: Item; slug: keyof typeof KINDS; brandId: number }) {
  const { kind, one, title } = KINDS[slug];
  const { data: brands } = useBrands();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const start = { name: item.name, notes: item.notes ?? "", brand_ids: item.brand_ids ?? [], image_file_ids: item.image_file_ids ?? [],
    outfits: item.outfits ?? [],
    voice_file_id: item.voice_file_id ?? null,
  };
  const [form, setForm] = useState(start);
  const changed = JSON.stringify(form) !== JSON.stringify(start);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["library", kind] });
  const path = { kind, item_id: item.id };
  const others = (item.brand_ids ?? []).filter((id) => id !== brandId).map((id) => brands?.find((b) => b.id === id)?.name).filter(Boolean);
  const currentName = brands?.find((b) => b.id === brandId)?.name;

  const save = useMutation({
    mutationFn: async () => {
      const { error, response } = await api.PATCH("/library/{kind}/{item_id}", { params: { path }, body: kind === "character" ? form : { name: form.name, notes: form.notes, brand_ids: form.brand_ids, image_file_ids: form.image_file_ids } });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: refresh,
  });
  const archive = useMutation({
    mutationFn: () => api.DELETE("/library/{kind}/{item_id}", { params: { path } }),
    onSuccess: async () => {
      await refresh();
      navigate(`/b/${brandId}/library/${slug}`);
    },
  });
  const addImage = useMutation({
    mutationFn: uploadFile,
    onSuccess: (f) => setForm((s) => ({ ...s, image_file_ids: [...s.image_file_ids, f.id] })),
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate();
  };
  const toggleBrand = (id: number) =>
    setForm({ ...form, brand_ids: form.brand_ids.includes(id) ? form.brand_ids.filter((b) => b !== id) : [...form.brand_ids, id] });

  return (
    <main className="mx-auto max-w-4xl space-y-6 p-4 sm:p-6">
      <Link to={`/b/${brandId}/library/${slug}`} className={linkText}>
        ← {title}
      </Link>
      <h1 className={pageTitle}>{item.name}</h1>
      {others.length > 0 && <p className="text-sm text-muted">Shared with {others.join(", ")}. Changes apply there too.</p>}
      <form onSubmit={submit} className={`${card} space-y-4`}>
        <div className="space-y-2">
          <div className="text-sm font-medium">Images</div>
          <ul className="flex flex-wrap gap-3">
            {form.image_file_ids.map((id, n) => (
              <li key={id} className="space-y-1 text-sm">
                <img src={fileUrl(id)} alt={`${item.name} ${n + 1}`} className="size-24 rounded-md border border-border bg-surface-2 object-cover" />
                <button
                  type="button"
                  className={linkText}
                  aria-label={`Remove image ${n + 1}`}
                  onClick={() => setForm({ ...form, image_file_ids: form.image_file_ids.filter((x) => x !== id) })}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
          <label className={`inline-block cursor-pointer text-sm ${linkText}`}>
            Add image
            <input type="file" accept="image/*" className="sr-only" aria-label="Add image" onChange={(e) => e.target.files?.[0] && addImage.mutate(e.target.files[0])} />
          </label>
          {addImage.isError && <p role="alert" className={errorClass}>{addImage.error.message}</p>}
        </div>
        <label className="block text-sm">
          Name
          <input className={input} required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </label>
        <fieldset className="space-y-1 text-sm">
          <legend className="font-medium">Brands</legend>
          {brands?.map((b) => (
            <label key={b.id} className="mr-4 inline-flex items-center gap-2">
              <input type="checkbox" checked={form.brand_ids.includes(b.id)} onChange={() => toggleBrand(b.id)} />
              {b.name}
            </label>
          ))}
        </fieldset>
        <label className="block text-sm">
          Notes
          <textarea className={input} rows={4} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </label>
        {kind === "character" && (
          <CharacterExtras
            outfits={form.outfits}
            voiceFileId={form.voice_file_id}
            onOutfits={(outfits) => setForm({ ...form, outfits })}
            onVoice={(voice_file_id) => setForm({ ...form, voice_file_id })}
          />
        )}
        {save.isError && <p role="alert" className={errorClass}>{save.error.message}</p>}
        <div className="flex flex-wrap items-center gap-3">
          <button className={btnPrimary} disabled={save.isPending || !changed || form.brand_ids.length === 0}>
            Save
          </button>
          {form.brand_ids.length === 0 && <span className="text-sm text-muted">Pick at least one brand.</span>}
          {form.brand_ids.length > 0 && item.brand_ids?.includes(brandId) && !form.brand_ids.includes(brandId) && (
            <span className="text-sm text-warning">This will remove {form.name} from {currentName}'s library.</span>
          )}
        </div>
      </form>
      <History kind={kind} item={item} onRestored={refresh} />
      <button
        className={btnSecondary}
        onClick={() => window.confirm(`Archive ${item.name}? You can bring it back from "Show archived".`) && archive.mutate()}
      >
        Archive {one}
      </button>
    </main>
  );
}

function History({ kind, item, onRestored }: { kind: "character" | "place" | "prop"; item: Item; onRestored: () => void }) {
  const versions = useQuery({
    queryKey: ["library", kind, "versions", item.id, item.version],
    queryFn: async () => (await api.GET("/library/{kind}/{item_id}/versions", { params: { path: { kind, item_id: item.id } } })).data ?? [],
  });
  const members = useQuery({
    queryKey: ["team", "members"],
    queryFn: async () => (await api.GET("/team/members")).data ?? [],
  });
  const restore = useMutation({
    mutationFn: (version: number) => api.POST("/library/{kind}/{item_id}/versions/{version}/restore", { params: { path: { kind, item_id: item.id, version } } }),
    onSuccess: onRestored,
  });
  const who = (id: number | null) => members.data?.find((m) => m.id === id)?.name ?? "someone";
  return (
    <section className="space-y-2">
      <h2 className="text-[length:var(--text-md)] font-semibold">History</h2>
      <ul className="divide-y divide-border text-sm">
        {versions.data?.map((v) => (
          <li key={v.version} className="flex items-center gap-3 py-2">
            <span className="flex-1">
              v{v.version} · {day(v.created_at)} by {who(v.saved_by_id)}
            </span>
            {v.version !== item.version && (
              <button className={linkText} aria-label={`Restore v${v.version}`} onClick={() => restore.mutate(v.version)}>
                Restore
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
