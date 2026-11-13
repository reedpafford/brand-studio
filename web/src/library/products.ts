import { api, errorText } from "../api/client";
import { uploadFile } from "../api/upload";
import type { Item } from "./kinds";

/** Adds a real photo to a product (S8-06): it becomes one of the brand's product pictures, linked to the product, used
 *  as it is whenever a shot shows the product. A second photo is a second picture (a flavour once it's named). */
export async function addPicture(brandId: number, item: Item, file: File, variant = "", named?: string) {
  const stored = await uploadFile(file);
  const taken = new Set((item.pictures ?? []).map((p) => p?.name));
  // A picture's name is its own in the brand, deleted ones included: after one is removed, the next number may be
  // taken, so a refused name is asked again with the number after it (the upload is not sent twice).
  let n = (item.pictures ?? []).length;
  for (let tries = 0; ; tries++) {
    const name = named ?? (variant ? `${item.name} (${variant})` : n ? `${item.name} (${n + 1})` : item.name);
    if (!named && !variant && taken.has(name) && ++n) continue;
    const { error, response } = await api.POST("/brands/{brand_id}/screens", {
      params: { path: { brand_id: brandId } },
      body: { name, file_id: stored.id, tags: named ? [] : ["product"], default_for: named ? [] : ["product"], product_id: item.id, variant },
    });
    if (response.ok) return stored.id;
    if (response.status !== 409 || named || variant || tries >= 8) throw new Error(errorText(error));
    n++;
  }
}
