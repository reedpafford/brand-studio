import { Link } from "react-router-dom";
import { useBrandPieces } from "../clip/BrandPieces";
import { aboutMissingLook, plainWords, refName, useRoleNames } from "./names";

/** Problem lines in words (no "char:3"), and the link to Assets for the ones about a look that isn't approved. */
export function useProblemWords(projectId: number, brandId: number) {
  const { pieces } = useBrandPieces(brandId);
  const roles = useRoleNames(projectId);
  const words = (p: string) => plainWords(p, (id) => refName(id, pieces, roles));
  const fix = (p: string) =>
    aboutMissingLook(p) ? (
      <Link to={`/b/${brandId}/videos/${projectId}?step=assets`} className="ml-2 whitespace-nowrap text-accent-text underline">
        Approve a look in Assets
      </Link>
    ) : null;
  return { words, fix };
}
