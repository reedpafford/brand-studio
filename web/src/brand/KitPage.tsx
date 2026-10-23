import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { useBrands } from "../shell/useBrands";
import { btnPrimary, card, errorText as errorClass, input, linkText, pageTitle } from "../ui";
import { ImagePicker } from "./ImagePicker";

type Brand = components["schemas"]["BrandOut"];

const HEX = /^#[0-9a-fA-F]{6}$/;
const lines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);

export function KitPage() {
  const { brandId } = useParams();
  const { data: brands } = useBrands();
  const brand = brands?.find((b) => b.id === Number(brandId));
  if (!brand) return <p className="p-6">That brand doesn't exist.</p>;
  return <KitForm key={brand.id} brand={brand} />;
}

function KitForm({ brand }: { brand: Brand }) {
  const start = {
    name: brand.name,
    logo_file_id: brand.logo_file_id ?? null,
    style_board_file_id: brand.style_board_file_id ?? null,
    end_card_file_id: brand.end_card_file_id ?? null,
    colours: brand.colours ?? [],
    fonts: (brand.fonts ?? []).join("\n"),
    tone_notes: brand.tone_notes ?? "",
    never_say: (brand.never_say ?? []).join("\n"),
    legal_line: brand.legal_line ?? "",
  };
  const [kit, setKit] = useState(start);
  const [saved, setSaved] = useState(JSON.stringify(start));
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
    onSuccess: () => {
      setSaved(JSON.stringify(kit));
      return queryClient.invalidateQueries({ queryKey: ["brands"] });
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate();
  };
  const box = input;
  const changed = JSON.stringify(kit) !== saved;

  return (
    <main className="mx-auto max-w-2xl p-6">
      <h1 className={`${pageTitle} mb-4`}>Brand kit · {brand.name}</h1>
      <form onSubmit={submit} className={`${card} space-y-5`}>
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
          <p className="text-sm text-muted">The first colour marks this brand across the app.</p>
          <div className="flex flex-wrap gap-3">
            {kit.colours.map((c, i) => (
              <span key={i} className="flex flex-col gap-1">
                <span className="flex items-center gap-1">
                  <input
                    type="color"
                    aria-label={`Colour ${i + 1} picker`}
                    value={HEX.test(c) ? c : "#000000"}
                    onChange={(e) => set("colours", kit.colours.map((x, j) => (j === i ? e.target.value : x)))}
                  />
                  <input
                    className={`${input} w-28 font-mono`}
                    aria-label={`Colour ${i + 1}`}
                    placeholder="#12A150"
                    value={c}
                    onChange={(e) => set("colours", kit.colours.map((x, j) => (j === i ? e.target.value : x)))}
                  />
                  <button type="button" className={`text-sm ${linkText}`} aria-label={`Remove colour ${i + 1}`} onClick={() => set("colours", kit.colours.filter((_, j) => j !== i))}>
                    Remove
                  </button>
                </span>
                {c !== "" && !HEX.test(c) && <span className={errorClass}>Use a colour like #12A150.</span>}
              </span>
            ))}
          </div>
          <button type="button" className={`text-sm ${linkText}`} onClick={() => set("colours", [...kit.colours, kit.colours.at(-1) ?? ""])}>
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
          <p role="alert" className={errorClass}>
            {save.error.message}
          </p>
        )}
        <div className="flex items-center gap-3">
          <button className={btnPrimary} disabled={save.isPending || !changed || !kit.colours.every((c) => HEX.test(c))}>
            Save changes
          </button>
          {save.isSuccess && !changed && <span role="status" className="text-sm text-muted">Saved.</span>}
        </div>
      </form>
    </main>
  );
}
