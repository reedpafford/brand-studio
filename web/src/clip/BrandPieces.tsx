import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export type Piece = { key: string; type: "character" | "place" | "prop" | "screen"; id: number; name: string; fileId?: number; auto?: string; blocked?: string };


/** Everything this brand can put in a clip, one list per tab. */
export function useBrandPieces(brandId: number): { pieces: Piece[]; screens: { key: string; moments: string[] }[]; isPending: boolean } {
  const useLibrary = (kind: "character" | "place" | "prop") =>
    useQuery({
      queryKey: ["library", kind, brandId, false],
      queryFn: async () => (await api.GET("/library/{kind}", { params: { path: { kind }, query: { brand_id: brandId } } })).data ?? [],
    });
  const characters = useLibrary("character");
  const places = useLibrary("place");
  const props = useLibrary("prop");
  const screens = useQuery({
    queryKey: ["screens", brandId],
    enabled: brandId > 0, // not before the brand has loaded (no /brands/0/… 404s)
    queryFn: async () => (await api.GET("/brands/{brand_id}/screens", { params: { path: { brand_id: brandId } } })).data ?? [],
  });
  const lift = (type: Piece["type"], rows: { id: number; name: string; image_file_ids?: number[]; sheet_status?: string }[] = []): Piece[] =>
    rows.map((r) => ({
      key: `${type}-${r.id}`,
      type,
      id: r.id,
      name: r.name,
      fileId: r.image_file_ids?.[0],
      // Videos only use an approved sheet.
      blocked: (type === "character" || type === "place") && r.sheet_status !== "approved" ? "Approve its sheet first" : undefined,
    }));
  const screenPieces: Piece[] = (screens.data ?? []).map((s) => ({ key: `screen-${s.id}`, type: "screen", id: s.id, name: s.name, fileId: s.file_id }));
  return {
    pieces: [...lift("character", characters.data), ...lift("place", places.data), ...lift("prop", props.data), ...screenPieces],
    screens: (screens.data ?? []).map((s) => ({ key: `screen-${s.id}`, moments: s.default_for })),
    isPending: characters.isPending || places.isPending || props.isPending || screens.isPending,
  };
}
