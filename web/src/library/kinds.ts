import { useQueries, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { creditsLabel } from "../components";
import { serverTime } from "../time";

export type Item = components["schemas"]["ItemOut"];
export type Kind = "character" | "place" | "prop";

/** The library's tabs (v6 S8, P-13): three kinds of saved item, the presenters and voices, and the brand kit. */
export const KINDS = {
  characters: { kind: "character", one: "character", title: "Characters" },
  places: { kind: "place", one: "place", title: "Places" },
  products: { kind: "prop", one: "product", title: "Products" },
} as const;
export type KindSlug = keyof typeof KINDS;
export const isKindSlug = (s: string | undefined): s is KindSlug => !!s && s in KINDS;
export const slugOf = (kind: Kind): KindSlug => (kind === "character" ? "characters" : kind === "place" ? "places" : "products");
export type TabSlug = KindSlug | "footage" | "presenters" | "kit";

/** A brand's saved items of one kind (the archive instead with `archived`). */
export function itemsQuery(kind: Kind, brandId: number, archived = false) {
  return {
    queryKey: ["library", kind, brandId, archived],
    queryFn: async () => {
      const { data } = await api.GET("/library/{kind}", { params: { path: { kind }, query: { brand_id: brandId, archived } } });
      if (!data) throw new Error("load");
      return data;
    },
    enabled: brandId > 0,
  };
}
export const useItems = (kind: Kind, brandId: number, archived = false) => useQuery(itemsQuery(kind, brandId, archived));

/** Each tab's count: characters, places, products, and presenters (characters who present). */
export function useCounts(brandId: number) {
  const [characters, places, products] = useQueries({ queries: (["character", "place", "prop"] as const).map((k) => itemsQuery(k, brandId)) });
  return {
    characters: characters.data?.length,
    places: places.data?.length,
    products: products.data?.length,
    presenters: characters.data?.filter((c) => c.presenter).length,
  };
}

/** What making a new character's or place's sheet costs at most ("Make one · up to $0.08"). */
export function useNewPrice(kind: Kind) {
  return useQuery({
    enabled: kind !== "prop",
    queryKey: ["library", kind, "price"],
    queryFn: async () => (await api.GET("/library/{kind}/price", { params: { path: { kind } } })).data ?? null,
  });
}

/** A price before a charge (rule 36): "up to $0.08" for the owner, "up to 1 credit" for an editor. */
export const upTo = (credits: number | undefined, usd: number | null | undefined) =>
  credits === undefined ? "" : usd != null ? `up to $${usd.toFixed(2)}` : `up to ${creditsLabel(credits)}`;

/** A product is an app (its pictures are its screens) or a physical thing (its photos) (S-gaps-05 L1). */
export const PRODUCT_TYPE = { app: "App", physical: "Physical" } as const;

/** The picture on a card: a product's first photo; a character's or place's sheet, else its source photo. */
export const cover = (i: Item) => i.pictures?.[0]?.file_id ?? i.sheet_file_id ?? i.source_photo_file_id ?? i.image_file_ids?.[0];

export const videos = (n: number) => `${n} video${n === 1 ? "" : "s"}`;
export const day = (iso: string) => serverTime(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
