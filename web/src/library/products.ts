import { api, errorText } from "../api/client";
import { uploadFile } from "../api/upload";
import type { Item } from "./kinds";

/** Adds a real photo to a product (S8-06): it becomes one of the brand's product pictures, linked to the product, used
 *  as it is whenever a shot shows the product. A second photo is a second picture (a flavour once it's named). */
export async function addPicture(brandId: number, item: Item, file: File, variant = "", named?: string) {
  const stored = await uploadFile(file);
  const n = (item.pictures ?? []).length;
  const name = named ?? (variant ? `${item.name} (${variant})` : n ? `${item.name} (${n + 1})` : item.name);
  const { error, response } = await api.POST("/brands/{brand_id}/screens", {
    params: { path: { brand_id: brandId } },
    body: { name, file_id: stored.id, tags: named ? [] : ["product"], default_for: named ? [] : ["product"], product_id: item.id, variant },
  });
  if (!response.ok) throw new Error(errorText(error));
}
