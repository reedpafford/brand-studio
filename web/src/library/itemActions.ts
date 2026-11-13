import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText, must } from "../api/client";
import { uploadFile } from "../api/upload";
import { refreshJobs } from "../jobs/refresh";
import { useToast } from "../toast";
import { voiceFields, type Voice } from "./Voices";
import type { Item, Kind } from "./kinds";
import { addPicture } from "./products";
import { SHEET_MODEL } from "./sheets";

/** A saved item's reads and presses, each one request: the library's pages (the current site's, and the new look's
 *  studio/Library*.tsx) send the same things through these. */
const useRefresh = (kind: Kind) => {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["library", kind] });
};

/** One saved item with the videos it is in, read again every 3 s while its sheet is drawn or waits for the owner.
 *  `null`: gone or archived. Nothing is read without an id. */
export function useItem(kind: Kind, id: number | null) {
  return useQuery({
    enabled: id !== null,
    queryKey: ["library", kind, "item", id],
    queryFn: async () => {
      const { data, response } = await api.GET("/library/{kind}/{item_id}", { params: { path: { kind, item_id: id! } } });
      if (response.status === 404) return null; // gone or archived
      if (!data) throw new Error("load");
      return data;
    },
    refetchInterval: (q) => (["drawing", "waiting_for_owner"].includes(q.state.data?.sheet_status ?? "") ? 3000 : false),
  });
}

/** An item's words as its form holds them. */
export const itemWords = (item: Item) => ({
  name: item.name,
  notes: item.notes ?? "",
  brand_ids: item.brand_ids ?? [],
  outfits: item.outfits ?? [],
  voice_file_id: item.voice_file_id ?? null,
  short_description: item.short_description ?? "",
  main_claim: item.main_claim ?? "",
});

/** Save an item's words (free): the fields its kind has, each as the form holds it. */
export function useSaveItem(kind: Kind, itemId: number) {
  const refresh = useRefresh(kind);
  const toast = useToast();
  return useMutation({
    mutationFn: async (form: ReturnType<typeof itemWords>) => {
      const body = kind === "character" ? { name: form.name, notes: form.notes, brand_ids: form.brand_ids, outfits: form.outfits, voice_file_id: form.voice_file_id } : { name: form.name, notes: form.notes, brand_ids: form.brand_ids, ...(kind === "prop" ? { short_description: form.short_description, main_claim: form.main_claim } : {}) };
      const { error, response } = await api.PATCH("/library/{kind}/{item_id}", { params: { path: { kind, item_id: itemId } }, body });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: () => {
      void refresh();
      toast("Saved.");
    },
  });
}

/** Archive an item (free), with Undo in the toast. `onGone` runs once the lists have been read again. */
export function useArchive(kind: Kind, item: Item, onGone: () => void) {
  const refresh = useRefresh(kind);
  const toast = useToast();
  const path = { kind, item_id: item.id };
  return useMutation({
    mutationFn: () => must(api.DELETE("/library/{kind}/{item_id}", { params: { path } })),
    onSuccess: async () => {
      await refresh();
      onGone();
      toast(`${item.name} archived.`, async () => {
        await api.POST("/library/{kind}/{item_id}/unarchive", { params: { path } });
        void refresh();
      });
    },
  });
}

/** Draw the item's sheet (paid): from its words when `change` is "", else the last sheet with that change. */
export function useDrawSheet(kind: Kind, itemId: number, onAsked: () => void) {
  const refresh = useRefresh(kind);
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (change: string) => {
      const { data, error } = await api.POST("/library/{kind}/{item_id}/sheet", { params: { path: { kind, item_id: itemId } }, body: { model_id: SHEET_MODEL, change } });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: () => {
      onAsked();
      refreshJobs(queryClient);
      void refresh();
    },
  });
}

/** Approve the item's sheet (free), with Undo in the toast. */
export function useApproveSheet(kind: Kind, item: Item) {
  const refresh = useRefresh(kind);
  const toast = useToast();
  const path = { kind, item_id: item.id };
  return useMutation({
    mutationFn: () => must(api.POST("/library/{kind}/{item_id}/sheet/approve", { params: { path } })),
    onSuccess: () => {
      void refresh();
      toast(`${item.name}'s sheet approved.`, async () => {
        await api.DELETE("/library/{kind}/{item_id}/sheet/approve", { params: { path } });
        void refresh();
      });
    },
  });
}

/** Give a character a voice, or none (free). */
export function usePickVoice(itemId: number) {
  const refresh = useRefresh("character");
  return useMutation({
    mutationFn: (v: Voice | null) => must(api.PATCH("/library/{kind}/{item_id}", { params: { path: { kind: "character", item_id: itemId } }, body: v ? voiceFields(v) : { voice_id: null, voice_stock_key: null } })),
    onSuccess: refresh,
  });
}

/** A product's own picture list (`image_file_ids`), which the director uses instead of the brand's pictures whenever it
 *  holds any: kept in step with the photos shown, so a photo added is given to the director and one removed is not. */
const setOwnPictures = async (item: Item, ids: number[]) => {
  const { error, response } = await api.PATCH("/library/{kind}/{item_id}", { params: { path: { kind: "prop", item_id: item.id } }, body: { image_file_ids: ids } });
  if (!response.ok) throw new Error(errorText(error));
};

/** Add a real photo to a product (free): it is shown as it is whenever a shot shows the product. */
export function useAddPicture(brandId: number, item: Item) {
  const refresh = useRefresh("prop");
  return useMutation({
    mutationFn: async (file: File) => {
      const id = await addPicture(brandId, item, file);
      if (item.image_file_ids?.length) await setOwnPictures(item, [...item.image_file_ids, id]);
    },
    onSettled: refresh,
  });
}

/** Remove one of a product's photos (free): the director is no longer given it (new videos, and new takes of
 *  existing ones), and Undo in the toast brings it back. Takes already made keep the picture they were made with. */
export function useRemovePicture(brandId: number, item: Item) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const refresh = () => Promise.all([queryClient.invalidateQueries({ queryKey: ["screens", brandId] }), queryClient.invalidateQueries({ queryKey: ["library", "prop"] })]);
  const at = (id: number) => ({ params: { path: { brand_id: brandId, screen_id: id } } });
  const own = item.image_file_ids ?? [];
  return useMutation({
    mutationFn: async (p: { screen_id: number; file_id: number }) => {
      if (own.includes(p.file_id)) await setOwnPictures(item, own.filter((f) => f !== p.file_id)); // first: were the next step refused, the photo is still the brand's
      const { error, response } = await api.DELETE("/brands/{brand_id}/screens/{screen_id}", at(p.screen_id));
      if (!response.ok) throw new Error(errorText(error));
    },
    onSettled: refresh,
    onSuccess: (_gone, p) =>
      toast("Photo removed. The director won’t be given it again; clips already made keep it.", async () => {
        try {
          const { error, response } = await api.POST("/brands/{brand_id}/screens/{screen_id}/restore", at(p.screen_id));
          if (!response.ok) throw new Error(errorText(error));
          if (own.includes(p.file_id)) await setOwnPictures(item, own);
        } catch (e) {
          toast((e as Error).message, undefined, "error");
        }
        await refresh();
      }),
  });
}

/** "order-tracking.png" reads "Order tracking". */
const screenName = (file: string) => {
  const words = file.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
};

/** Make a new item in this brand: a character or place is saved (its photo first, when it has one) and its sheet is
 *  drawn (paid); a product is saved with its pictures (free). A press after a later step failed (a held sheet, an
 *  upload) goes on from there, never a second item; `locked` says the item is made, so its words can't change here. */
export function useCreateItem(brandId: number, kind: Kind, onMade: (id: number) => void) {
  const queryClient = useQueryClient();
  const product = kind === "prop";
  const done = useRef<{ item: Item | null; pictures: number }>({ item: null, pictures: 0 });
  const [locked, setLocked] = useState(false);
  const create = useMutation({
    mutationFn: async ({ name, words, photo, more, type }: { name: string; words: string; photo: File | null; more: File[]; type: "app" | "physical" }) => {
      let data = done.current.item;
      if (!data) {
        const source = photo && !product ? (await uploadFile(photo)).id : null;
        const made = await api.POST("/library/{kind}", {
          params: { path: { kind } },
          body: { name: name.trim(), notes: words.trim(), brand_ids: [brandId], image_file_ids: [], outfits: [], source_photo_file_id: source, presenter: false, product_type: product ? type : null },
        });
        if (!made.data) throw new Error(errorText(made.error));
        data = done.current.item = made.data;
        setLocked(true);
      }
      if (product) {
        const files = [photo, ...more].filter((f): f is File => !!f);
        for (let n = done.current.pictures; n < files.length; n++) {
          await addPicture(brandId, { ...data, pictures: Array(n).fill(null) } as Item, files[n], "", type === "app" ? screenName(files[n].name) : undefined);
          done.current.pictures = n + 1;
        }
        return data.id;
      }
      const sheet = await api.POST("/library/{kind}/{item_id}/sheet", { params: { path: { kind, item_id: data.id } }, body: { model_id: SHEET_MODEL, change: "" } });
      if (!sheet.data) throw new Error(errorText(sheet.error));
      return data.id;
    },
    onSuccess: (id) => {
      void queryClient.invalidateQueries({ queryKey: ["library", kind] });
      if (!product) refreshJobs(queryClient);
      onMade(id);
    },
  });
  return { create, locked };
}
