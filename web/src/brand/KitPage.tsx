import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { useBrands } from "../shell/useBrands";
import { ImagePicker } from "./ImagePicker";

type Brand = components["schemas"]["BrandOut"];

const lines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);

export function KitPage() {
  const { brandId } = useParams();
  const { data: brands } = useBrands();
  const brand = brands?.find((b) => b.id === Number(brandId));
  if (!brand) return <p className="p-6">That brand doesn't exist.</p>;
  return <KitForm key={brand.id} brand={brand} />;
}

function KitForm({ brand }: { brand: Brand }) {
  const [kit, setKit] = useState({
    name: brand.name,
    logo_file_id: brand.logo_file_id ?? null,
    style_board_file_id: brand.style_board_file_id ?? null,
    end_card_file_id: brand.end_card_file_id ?? null,
    colours: brand.colours ?? [],
    fonts: (brand.fonts ?? []).join("\n"),
    tone_notes: brand.tone_notes ?? "",
    never_say: (brand.never_say ?? []).join("\n"),
    legal_line: brand.legal_line ?? "",
  });
  const set = <K extends keyof typeof kit>(k: K, v: (typeof kit)[K]) => setKit({ ...kit, [k]: v });
  const queryClient = useQueryClient();
  const save = useMutation({
    mutationFn: async () => {
      const { error, response } = await api.PATCH("/brands/{brand_id}", {
        params: { path: { brand_id: brand.id } },
        body: { ...kit, fonts: lines(kit.fonts), never_say: lines(kit.never_say) },
      });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["brands"] }),
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate();
  };
  const box = "w-full rounded border border-neutral-300 px-3 py-2 text-base";

  return (
    <main className="mx-auto max-w-2xl p-6">
      <h1 className="mb-4 text-2xl font-semibold">Brand kit</h1>
      <form onSubmit={submit} className="space-y-5">
        <label className="block text-sm">
          Name
          <input className={box} required value={kit.name} onChange={(e) => set("name", e.target.value)} />
        </label>
        <div className="grid gap-4 sm:grid-cols-3">
          <ImagePicker label="Logo" fileId={kit.logo_file_id} onChange={(id) => set("logo_file_id", id)} />
          <ImagePicker label="Style board" fileId={kit.style_board_file_id} onChange={(id) => set("style_board_file_id", id)} />
          <ImagePicker label="End card" fileId={kit.end_card_file_id} onChange={(id) => set("end_card_file_id", id)} />
        </div>
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">Colours</legend>
          <div className="flex flex-wrap gap-3">
            {kit.colours.map((c, i) => (
              <span key={i} className="flex items-center gap-1">
                <input
                  type="color"
                  aria-label={`Colour ${i + 1}`}
                  value={c}
                  onChange={(e) => set("colours", kit.colours.map((x, j) => (j === i ? e.target.value : x)))}
                />
                <button type="button" className="text-sm underline" aria-label={`Remove colour ${i + 1}`} onClick={() => set("colours", kit.colours.filter((_, j) => j !== i))}>
                  Remove
                </button>
              </span>
            ))}
          </div>
          <button type="button" className="text-sm underline" onClick={() => set("colours", [...kit.colours, "#000000"])}>
            Add colour
          </button>
        </fieldset>
        <label className="block text-sm">
          Fonts (one per line)
          <textarea className={box} rows={3} value={kit.fonts} onChange={(e) => set("fonts", e.target.value)} />
        </label>
        <label className="block text-sm">
          Tone of voice
          <textarea className={box} rows={4} value={kit.tone_notes} onChange={(e) => set("tone_notes", e.target.value)} />
        </label>
        <label className="block text-sm">
          Never say (one per line)
          <textarea className={box} rows={3} value={kit.never_say} onChange={(e) => set("never_say", e.target.value)} />
        </label>
        <label className="block text-sm">
          Legal line
          <textarea className={box} rows={2} value={kit.legal_line} onChange={(e) => set("legal_line", e.target.value)} />
        </label>
        {save.isError && (
          <p role="alert" className="text-sm text-red-700">
            {save.error.message}
          </p>
        )}
        <div className="flex items-center gap-3">
          <button className="rounded bg-neutral-900 px-4 py-2 text-white disabled:opacity-50" disabled={save.isPending}>
            Save kit
          </button>
          {save.isSuccess && <span role="status" className="text-sm text-neutral-600">Saved.</span>}
        </div>
      </form>
    </main>
  );
}
