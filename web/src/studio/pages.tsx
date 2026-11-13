import { Clapperboard, Library, Plus, Wallet } from "lucide-react";
import { Link, useLocation, useParams } from "react-router-dom";
import { useMe } from "../auth/useMe";

/** The studio's four pages: the rail's word for each, its title, and where the same page is on the current site
 *  (an editor's spend is their own credits). */
export const PAGES = [
  { page: "", label: "Create", title: "New video", icon: Plus, current: (brand: number) => `/b/${brand}` },
  { page: "videos", label: "Videos", title: "Videos", icon: Clapperboard, current: (brand: number) => `/b/${brand}/videos` },
  { page: "library", label: "Library", title: "Library", icon: Library, current: (brand: number) => `/b/${brand}/library` },
  { page: "spend", label: "Spend", title: "Spend", icon: Wallet, current: (brand: number, owner: boolean) => (owner ? `/usage/brands/${brand}` : "/usage/mine") },
] as const;

/** A page of the studio that isn't built yet: its header in the new look, and the way to the same page on the current
 *  site (a folder picked in the rail goes with it). Each later step of the redesign replaces one of these. */
export function StudioPage({ page }: { page: (typeof PAGES)[number]["page"] }) {
  const { brandId } = useParams();
  const { search } = useLocation();
  const owner = useMe().data?.role === "owner";
  const p = PAGES.find((x) => x.page === page)!;
  return (
    <>
      <header className="head">
        <h1>{p.title}</h1>
      </header>
      <div className="view" key={page}>
        <div className="page">
          <p className="quiet">
            This screen arrives in a later step of the new look. For now, <Link to={`${p.current(Number(brandId), owner)}${search}`}>open {p.title} on the current site</Link>.
          </p>
        </div>
      </div>
    </>
  );
}
