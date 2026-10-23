import { useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { NavLink, Navigate, Outlet, useMatch, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useMe } from "../auth/useMe";
import { lastBrand, rememberBrand, useBrands } from "./useBrands";

const link = ({ isActive }: { isActive: boolean }) =>
  isActive ? "font-semibold underline" : "text-neutral-600";

/** Top bar: brand switcher, links, sign out. Everything below filters by the chosen brand. */
export function Shell() {
  const { data: me } = useMe();
  const { data: brands, isPending } = useBrands();
  const { brandId } = useParams();
  const subPage = useMatch("/b/:brandId/*")?.params["*"] ?? "";
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const current = Number(brandId) || null;

  useEffect(() => {
    if (current) rememberBrand(current);
  }, [current]);

  const signOut = useMutation({
    mutationFn: () => api.POST("/auth/logout"),
    onSuccess: async () => {
      queryClient.clear();
      navigate("/login", { replace: true });
    },
  });

  if (isPending) return <p className="p-6 text-neutral-600">Loading…</p>;
  if (!brands) return <p className="p-6 text-red-700">Could not load brands.</p>;

  return (
    <div className="min-h-screen">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-neutral-200 px-4 py-3">
        <label className="flex items-center gap-2 text-sm">
          <span className="sr-only">Brand</span>
          <select
            aria-label="Brand"
            className="rounded border border-neutral-300 px-2 py-1 text-base"
            value={current ?? ""}
            onChange={(e) => navigate(`/b/${e.target.value}/${subPage}`)}
          >
            {current === null && <option value="">Choose a brand</option>}
            {brands.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </label>
        <nav aria-label="Main" className="flex gap-4 text-sm">
          {current && (
            <>
              <NavLink end to={`/b/${current}`} className={link}>
                Brand
              </NavLink>
              <NavLink to={`/b/${current}/kit`} className={link}>
                Kit
              </NavLink>
              <NavLink to={`/b/${current}/screens`} className={link}>
                Screens
              </NavLink>
            </>
          )}
          <NavLink to="/team" className={link}>
            Team
          </NavLink>
        </nav>
        <div className="ml-auto flex items-center gap-3 text-sm">
          <span className="text-neutral-600">{me?.name}</span>
          <button className="underline" onClick={() => signOut.mutate()}>
            Sign out
          </button>
        </div>
      </header>
      <Outlet />
    </div>
  );
}

/** "/" goes to the brand you were last in, else the first one. */
export function GoToBrand() {
  const { data: brands, isPending } = useBrands();
  if (isPending) return <p className="p-6 text-neutral-600">Loading…</p>;
  const last = lastBrand();
  const target = brands?.find((b) => b.id === last) ?? brands?.[0];
  return target ? <Navigate to={`/b/${target.id}`} replace /> : <Navigate to="/team" replace />;
}

export function BrandHome() {
  const { brandId } = useParams();
  const { data: brands } = useBrands();
  const brand = brands?.find((b) => b.id === Number(brandId));
  if (!brand) return <p className="p-6">That brand doesn't exist.</p>;
  return (
    <main className="p-6">
      <h1 className="text-2xl font-semibold">{brand.name}</h1>
      <p className="text-neutral-600">Brand kit, screens and characters are coming next.</p>
    </main>
  );
}
