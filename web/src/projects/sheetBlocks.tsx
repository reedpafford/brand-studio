import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";
import { api } from "../api/client";
import { useBrandPieces, type Piece } from "../clip/BrandPieces";
import { linkText } from "../ui";

export type Blocker = Pick<Piece, "id" | "type" | "name">;

/** Characters and places a shot uses that have no approved house-style sheet yet. The server refuses to make anything with them. */
export function useSheetBlocks(projectId: number, brandId: number) {
  const { pieces } = useBrandPieces(brandId);
  const breakdown = useQuery({
    queryKey: ["breakdown-sheets", projectId],
    queryFn: async () => {
      const { data } = await api.GET("/projects/{project_id}/breakdown", { params: { path: { project_id: projectId } } });
      return data ?? null;
    },
  });
  const shots = (breakdown.data?.breakdown.scenes ?? []).flatMap((s) => s.shots);
  const forShots = (shotIds: string[]): Blocker[] => {
    const refs = shots.filter((s) => shotIds.includes(s.id)).flatMap((s) => [...s.character_ids, s.place_id ?? ""]);
    return [...new Set(refs)].flatMap((ref) => {
      const [tag, id] = ref.split(":");
      const type = tag === "char" ? "character" : tag === "place" ? "place" : null;
      const piece = type && pieces.find((p) => p.type === type && p.id === Number(id));
      return piece && piece.blocked ? [piece] : [];
    });
  };
  return {
    forShot: (shotId: string) => forShots([shotId]),
    forClip: (clipId: string) => forShots(breakdown.data?.breakdown.clips.find((c) => c.id === clipId)?.shot_ids ?? []),
  };
}

const names = (list: Blocker[]) => [...new Set(list.map((b) => b.name))].join(" and ");

/** "Mia needs an approved sheet. [Open Mia]", with a link that comes back to this stage. */
export function SheetWarning({ blockers, brandId }: { blockers: Blocker[]; brandId: number }) {
  const here = useLocation();
  if (blockers.length === 0) return null;
  return (
    <ul className="space-y-0.5 text-xs text-warning" aria-label="Needs a sheet">
      {blockers.map((b) => (
        <li key={`${b.type}-${b.id}`}>
          {b.name} needs an approved sheet.{" "}
          <Link
            className={`${linkText} inline-flex min-h-11 items-center sm:min-h-0`}
            to={`/b/${brandId}/library/${b.type === "character" ? "characters" : "places"}/${b.id}?back=${encodeURIComponent(here.pathname + here.search)}`}
          >
            Open {b.name}
          </Link>
        </li>
      ))}
    </ul>
  );
}

export { names as blockerNames };
