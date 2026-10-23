import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export function useBrands() {
  return useQuery({
    queryKey: ["brands"],
    queryFn: async () => {
      const { data } = await api.GET("/brands");
      if (!data) throw new Error("Could not load brands");
      return data;
    },
  });
}

const LAST_BRAND = "bs.lastBrand";

export function rememberBrand(id: number) {
  try {
    localStorage.setItem(LAST_BRAND, String(id));
  } catch {
    /* private mode: not remembering is fine */
  }
}

export function lastBrand(): number | null {
  try {
    return Number(localStorage.getItem(LAST_BRAND)) || null;
  } catch {
    return null;
  }
}
