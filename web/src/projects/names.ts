import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Piece } from "../clip/BrandPieces";

/** Role names of the cast slots not cast yet, by their `slot:N` id (from the Assets list). */
export function useRoleNames(projectId: number) {
  const assets = useQuery({
    queryKey: ["assets", projectId],
    queryFn: async () => (await api.GET("/projects/{project_id}/assets", { params: { path: { project_id: projectId } } })).data ?? [],
  });
  return new Map((assets.data ?? []).filter((a) => a.ref.startsWith("slot:")).map((a) => [a.ref, a.role]));
}

const KIND: Record<string, string> = { char: "Character", character: "Character", place: "Place", prop: "Prop", screen: "Screen" };

/** What a chip says for a reference id. A raw id ("slot:28", "char:5", "frame:c1") is never shown. */
export function refName(id: string, pieces: Piece[], roles: Map<string, string>): string {
  if (id === "previous") return "previous frame";
  const [kind, n] = id.split(":");
  if (kind === "frame") return "First frame";
  if (kind === "slot") return `${roles.get(id) || "A role"} · cast at Assets`;
  return pieces.find((p) => p.key === `${kind === "char" ? "character" : kind}-${n}`)?.name ?? KIND[kind] ?? "Picture";
}
