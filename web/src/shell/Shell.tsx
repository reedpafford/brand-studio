import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { NavLink, Navigate, Outlet, useLocation, useMatch, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useHeld } from "../approvals/useHeld";
import { useMe } from "../auth/useMe";
import { applyTheme, getTheme, nextTheme } from "../theme";
import { lastBrand, rememberBrand, useBrands } from "./useBrands";

const link = ({ isActive }: { isActive: boolean }) =>
  `whitespace-nowrap rounded-sm px-3 py-2 ${isActive ? "bg-accent-soft font-medium text-accent-text" : "text-muted"}`;

/** Top bar (switcher + account) over a 3px stripe in the brand's colour, then the section links. */
export function Shell() {
  const { data: brands, isPending } = useBrands();
  const { brandId } = useParams();
  const subPage = useMatch("/b/:brandId/*")?.params["*"] ?? "";
  const navigate = useNavigate();
  const held = useHeld();
  const fromUrl = Number(brandId) || null;
  // Off brand pages (e.g. /team) you stay "in" the brand you were last in.
  const current = fromUrl ?? (brands?.some((b) => b.id === lastBrand()) ? lastBrand() : null);
  const brand = brands?.find((b) => b.id === current);

  useEffect(() => {
    if (fromUrl) rememberBrand(fromUrl);
  }, [fromUrl]);

  useEffect(() => {
    const root = document.documentElement.style;
    if (brand?.colours?.[0]) root.setProperty("--brand", brand.colours[0]);
    else root.removeProperty("--brand");
    return () => void root.removeProperty("--brand");
  }, [brand]);

  if (isPending) return <p className="p-6 text-muted">Loading…</p>;
  if (!brands) return <p className="p-6 text-danger">Could not load brands.</p>;

  return (
    <div className="min-h-screen pb-[calc(4rem+env(safe-area-inset-bottom))] md:pb-0">
      <header className="flex h-14 items-center gap-3 border-b-[3px] border-brand bg-surface px-4">
        <span aria-hidden className="size-2.5 shrink-0 rounded-full bg-brand" />
        <label className="min-w-0 flex-1 sm:flex-none">
          <span className="sr-only">Brand</span>
          <select
            aria-label="Brand"
            className="min-h-11 w-full rounded-sm border border-border-strong bg-surface px-2 text-base text-text sm:min-h-9"
            value={brand ? current! : ""}
            onChange={(e) => navigate(subPage ? `/b/${e.target.value}/${subPage}` : `/b/${e.target.value}`)}
          >
            {!brand && <option value="">Choose a brand</option>}
            {brands.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </label>
        <AccountMenu />
      </header>
      <nav aria-label="Main" className="hidden gap-1 overflow-x-auto border-b border-border bg-surface px-3 py-1 text-sm md:flex">
        {current && (
          <>
            <NavLink to={`/b/${current}/projects`} className={link}>
              Projects
            </NavLink>
            <NavLink to={`/b/${current}/clip`} className={link}>
              Quick clip
            </NavLink>
            <NavLink to={`/b/${current}/library`} className={link}>
              Library
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
        {held.owner && (
          <NavLink to="/approvals" className={link}>
            Approvals <Badge n={held.count} />
          </NavLink>
        )}
      </nav>
      <Outlet />
      <TabBar brandId={current} waiting={held.owner ? held.count : null} />
    </div>
  );
}

/** A count in a small pill, said in words for screen readers. */
function Badge({ n }: { n: number }) {
  if (n === 0) return null;
  return (
    <span className="ml-1 inline-block min-w-5 rounded-full bg-warning-soft px-1.5 text-center text-xs font-medium text-warning">
      {n}
      <span className="sr-only"> waiting</span>
    </span>
  );
}

const tab = ({ isActive }: { isActive: boolean }) =>
  `grid min-h-16 flex-1 place-items-center text-sm ${isActive ? "font-medium text-accent-text" : "text-muted"}`;
const row = ({ isActive }: { isActive: boolean }) =>
  `flex min-h-12 items-center rounded-sm px-3 ${isActive ? "bg-accent-soft font-medium text-accent-text" : ""}`;
const BAR = "calc(4rem + env(safe-area-inset-bottom))"; // tab bar height plus the phone's home-bar space

/** Phone navigation: four tabs along the bottom; "More" holds the rest. */
function TabBar({ brandId, waiting }: { brandId: number | null; waiting: number | null }) {
  const [more, setMore] = useState(false);
  const [theme, setTheme] = useState(getTheme);
  const signOut = useSignOut();
  const { pathname } = useLocation();
  const inMore = /\/(kit|screens)$|^\/(team|approvals)/.test(pathname);
  const close = () => setMore(false);

  useEffect(() => {
    if (!more) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMore(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [more]);

  return (
    <>
      {more && (
        <>
          <button type="button" aria-label="Close menu" className="fixed inset-0 z-10 bg-[var(--scrim)] md:hidden" onClick={close} />
          <div style={{ bottom: BAR }} className="fixed inset-x-0 z-20 border-t border-border bg-surface p-2 shadow-md md:hidden">
            {brandId && (
              <>
                <NavLink to={`/b/${brandId}/kit`} onClick={close} className={row}>
                  Brand kit
                </NavLink>
                <NavLink to={`/b/${brandId}/screens`} onClick={close} className={row}>
                  Brand screens
                </NavLink>
              </>
            )}
            <NavLink to="/team" onClick={close} className={row}>
              Team
            </NavLink>
            {waiting !== null && (
              <NavLink to="/approvals" onClick={close} className={row}>
                Approvals <Badge n={waiting} />
              </NavLink>
            )}
            <button
              type="button"
              className="flex min-h-12 w-full items-center px-3 text-left"
              onClick={() => {
                const next = nextTheme(theme);
                applyTheme(next);
                setTheme(next);
              }}
            >
              Theme: {theme[0].toUpperCase() + theme.slice(1)}
            </button>
            <button type="button" className="flex min-h-12 w-full items-center px-3 text-left" onClick={() => signOut.mutate()}>
              Sign out
            </button>
          </div>
        </>
      )}
      <nav aria-label="Tabs" style={{ height: BAR }} className="fixed inset-x-0 bottom-0 z-20 flex border-t border-border bg-surface pb-[env(safe-area-inset-bottom)] md:hidden">
        {brandId && (
          <>
            <NavLink to={`/b/${brandId}/projects`} className={tab} onClick={close}>
              Projects
            </NavLink>
            <NavLink to={`/b/${brandId}/clip`} className={tab} onClick={close}>
              Clip
            </NavLink>
            <NavLink to={`/b/${brandId}/library`} className={tab} onClick={close}>
              Library
            </NavLink>
          </>
        )}
        <button type="button" aria-expanded={more} className={`grid min-h-16 flex-1 place-items-center text-sm ${more || inMore ? "font-medium text-accent-text" : "text-muted"}`} onClick={() => setMore(!more)}>
          More {waiting ? <Badge n={waiting} /> : null}
        </button>
      </nav>
    </>
  );
}
function useSignOut() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.POST("/auth/logout"),
    onSuccess: () => {
      queryClient.clear(); // nothing from this person stays for the next one
      navigate("/login", { replace: true });
    },
  });
}

function AccountMenu() {
  const { data: me } = useMe();
  const [open, setOpen] = useState(false);
  const signOut = useSignOut();
  const initials = (me?.name ?? "?").split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  return (
    <div className="relative ml-auto" onKeyDown={(e) => e.key === "Escape" && setOpen(false)}>
      <button
        aria-label="Account menu"
        aria-expanded={open}
        className="grid size-11 place-items-center rounded-full bg-accent-soft text-sm font-medium text-accent-text sm:size-9"
        onClick={() => setOpen(!open)}
      >
        {initials}
      </button>
      {open && (
        <div className="absolute right-0 top-full z-10 mt-2 w-56 space-y-2 rounded-md border border-border bg-surface p-3 shadow-md">
          <div>
            <div className="font-medium">{me?.name}</div>
            <div className="text-sm text-muted">{me?.role}</div>
          </div>
          <button className="min-h-11 w-full rounded-sm text-left text-text underline sm:min-h-9" onClick={() => signOut.mutate()}>
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}

/** "/" goes to the brand you were last in, else the first one. */
export function GoToBrand() {
  const { data: brands, isPending } = useBrands();
  if (isPending) return <p className="p-6 text-muted">Loading…</p>;
  const last = lastBrand();
  const target = brands?.find((b) => b.id === last) ?? brands?.[0];
  return target ? <Navigate to={`/b/${target.id}`} replace /> : <Navigate to="/team" replace />;
}

/** A brand's home is its Projects list. */
export function BrandHome() {
  const { brandId } = useParams();
  const { data: brands } = useBrands();
  if (!brands?.some((b) => b.id === Number(brandId))) return <p className="p-6">That brand doesn't exist.</p>;
  return <Navigate to={`/b/${brandId}/projects`} replace />;
}
