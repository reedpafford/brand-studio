import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { input } from "../ui";

type Item = components["schemas"]["ItemOut"];
type Screen = components["schemas"]["ScreenOut"];

/** The brand's characters and the products that come in flavours, for the brief (new or edited). */
export function useBriefChoices(brandId: number, picks: Record<string, string>) {
  const characters = useQuery({
    queryKey: ["library", "character", brandId, false],
    queryFn: async () => (await api.GET("/library/{kind}", { params: { path: { kind: "character" }, query: { brand_id: brandId } } })).data ?? [],
  });
  const screens = useQuery({
    queryKey: ["screens", brandId],
    queryFn: async () => (await api.GET("/brands/{brand_id}/screens", { params: { path: { brand_id: brandId } } })).data ?? [],
  });
  // Screens that are one flavour of a product (a bag that comes in Chicken or Peanut butter) are picked here.
  const products = new Map<string, Screen[]>();
  for (const s of screens.data ?? []) if (s.product && s.variant) products.set(s.product, [...(products.get(s.product) ?? []), s]);
  // A flavour has to be chosen; a product with only one is chosen for you.
  const chosen = (product: string) => picks[product] ?? (products.get(product)?.length === 1 ? products.get(product)![0].variant : undefined);
  const unchosen = [...products.keys()].find((p) => !chosen(p));
  return { characters, products, chosen, unchosen, loading: screens.isPending };
}

export function useReferences() {
  return useQuery({ queryKey: ["references"], queryFn: async () => (await api.GET("/references")).data ?? [] });
}

/** "Adapt a reference reel": pick one of the reels the studio has taken apart, and say what to swap. Nothing is picked by default. */
export function ReferencePicker({ value, replace, onChange }: { value: string | null; replace: string; onChange: (id: string | null, replace: string) => void }) {
  const refs = useReferences();
  if (!refs.data || refs.data.length === 0) return null;
  return (
    <fieldset className="space-y-2 text-sm">
      <legend className="font-medium">Adapt a reference reel (optional)</legend>
      <div className="flex flex-wrap gap-3">
        {refs.data.map((r) => {
          const on = value === r.id;
          return (
            <button
              key={r.id}
              type="button"
              aria-pressed={on}
              className={`w-40 overflow-hidden rounded-md bg-surface text-left ${on ? "border-2 border-accent" : "border border-border-strong"}`}
              onClick={() => onChange(on ? null : r.id, on ? "" : replace)}
            >
              {r.has_thumbnail ? <img src={`/api/references/${r.id}/thumbnail`} alt="" className="aspect-video w-full object-cover" /> : <div className="grid aspect-video place-items-center bg-surface-2 text-muted">No picture</div>}
              <span className="block space-y-0.5 p-2">
                <span className="block font-medium">{r.name}</span>
                <span className="line-clamp-3 text-xs text-muted">{r.logline}</span>
                <span className="block text-xs text-muted">{Math.round(r.seconds)} s</span>
              </span>
            </button>
          );
        })}
      </div>
      {value && (
        <label className="block">
          What to replace
          <textarea className={input} rows={3} value={replace} onChange={(e) => onChange(value, e.target.value)} />
          <span className="block text-muted">For example: the reselling montage becomes a fomo trading montage. Claude keeps the rest of the reel's story.</span>
        </label>
      )}
    </fieldset>
  );
}

/** The longest video a brief may plan: half the per-video credit cap (the budget is twice the 480p seconds). */
export function useLongestSeconds() {
  const limits = useQuery({ queryKey: ["limits"], queryFn: async () => (await api.GET("/credits/limits")).data ?? null });
  return limits.data ? Math.floor(limits.data.per_video_max_credits / 2) : 364;
}

export function CastPicker({ characters, cast, onChange }: { characters: Item[] | undefined; cast: number[]; onChange: (cast: number[]) => void }) {
  return (
    <fieldset className="space-y-1 text-sm">
      <legend className="font-medium">Who's in it</legend>
      {characters?.length === 0 && <p className="text-muted">No characters for this brand yet. Add them in the Library.</p>}
      {characters?.map((c) => (
        <label key={c.id} className="mr-4 inline-flex min-h-11 items-center gap-2 sm:min-h-0">
          <input type="checkbox" disabled={c.sheet_status !== "approved" && !cast.includes(c.id)} checked={cast.includes(c.id)} onChange={() => onChange(cast.includes(c.id) ? cast.filter((x) => x !== c.id) : [...cast, c.id])} />
          {c.name}
          {c.sheet_status !== "approved" && <span className="text-muted"> · Approve its sheet first</span>}
        </label>
      ))}
    </fieldset>
  );
}

export function FlavourPicker({ products, chosen, onPick }: { products: Map<string, Screen[]>; chosen: (product: string) => string | undefined; onPick: (product: string, variant: string) => void }) {
  return (
    <>
      {[...products].map(([product, list]) => (
        <fieldset key={product} className="space-y-1 text-sm">
          <legend className="font-medium">{product.charAt(0).toUpperCase() + product.slice(1)}</legend>
          <div className="flex flex-wrap gap-3">
            {list.map((s) => {
              const on = chosen(product) === s.variant;
              return (
                <button
                  key={s.id}
                  type="button"
                  aria-pressed={on}
                  className={`w-28 overflow-hidden rounded-md bg-surface text-left ${on ? "border-2 border-accent" : "border border-border-strong"}`}
                  onClick={() => onPick(product, s.variant)}
                >
                  <img src={fileUrl(s.file_id)} alt="" className="aspect-square w-full object-cover" />
                  <span className="block min-h-11 p-2 sm:min-h-0">{s.variant}</span>
                </button>
              );
            })}
          </div>
        </fieldset>
      ))}
    </>
  );
}
