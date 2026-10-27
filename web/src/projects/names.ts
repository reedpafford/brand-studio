import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Piece } from "../clip/BrandPieces";

/** Role names by the id the shots use for them (from the Assets list): `slot:N` for a role not cast yet, `char:N` for a look made for this video. */
export function useRoleNames(projectId: number) {
  const assets = useQuery({
    queryKey: ["assets", projectId],
    queryFn: async () => (await api.GET("/projects/{project_id}/assets", { params: { path: { project_id: projectId } } })).data ?? [],
  });
  return new Map((assets.data ?? []).filter((a) => a.role && (a.ref.startsWith("slot:") || a.ref.startsWith("char:"))).map((a) => [a.ref, a.role]));
}

const KIND: Record<string, string> = { char: "Character", character: "Character", place: "Place", prop: "Prop", screen: "Screen" };

/** What a chip says for a reference id. A raw id ("slot:28", "char:5", "frame:c1") is never shown. */
export function refName(id: string, pieces: Piece[], roles: Map<string, string>): string {
  if (id === "previous") return "previous frame";
  const [kind, n] = id.split(":");
  if (kind === "frame") return "First frame";
  if (kind === "slot") return `${roles.get(id) || "A role"} · cast at Assets`;
  return pieces.find((p) => p.key === `${kind === "char" ? "character" : kind}-${n}`)?.name ?? (kind === "char" ? roles.get(id) : undefined) ?? KIND[kind] ?? "Picture";
}

const REF = /\b(?:char|place|prop|screen|slot|frame):\w+/g;

/** A problem line in words: "c3: char:5 is in the clip…" reads "Clip c3: Mia is in the clip…". A raw id is never shown. `nameOf` is refName for the page's pieces and roles. */
export function plainWords(text: string, nameOf: (id: string) => string): string {
  return text
    .replace(/^(c\d+): /, "Clip $1: ")
    .replace(REF, (id) => (id.startsWith("frame:") ? "the first frame" : nameOf(id).replace(" · cast at Assets", "")));
}

/** A problem about a character with no approved look: the fix is on Assets. */
export const aboutMissingLook = (text: string) => /sheet isn't attached|no approved (sheet|look)|needs an approved (sheet|look)|has no look/i.test(text);
