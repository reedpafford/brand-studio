import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell, ChevronDown, Clapperboard, LogOut, Palette, Check, UserPlus, Users, Zap, type LucideIcon } from "lucide-react";
import { Link, NavLink, Navigate, Outlet, useLocation, useMatch, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useHeld } from "../approvals/useHeld";
import { useMe } from "../auth/useMe";
import { Banner, EmptyState, Menu, MenuItem, Skeleton } from "../components";
import { applyTheme, getTheme, type Theme } from "../theme";
import { useMedia } from "../useMedia";
import { ActionBarProvider, useActionBarSlot } from "./ActionBar";
import { lastBrand, rememberBrand, useBrands } from "./useBrands";

type Brand = { id: number; name: string; colours?: string[] };

const SECTIONS: { to: string; label: string; short: string; icon: LucideIcon }[] = [
  { to: "projects", label: "Videos", short: "Videos", icon: Clapperboard },
  { to: "clip", label: "Quick clip", short: "Quick clip", icon: Zap },
  { to: "library", label: "Cast & places", short: "Cast", icon: Users },
  { to: "brand", label: "Brand", short: "Brand", icon: Palette },
];

/** Where a brand switch lands: the same section in the other brand; a video or an item goes to that section's list. */
function sectionOf(pathname: string) {
  const m = /^\/b\/\d+\/([^/]+)/.exec(pathname)?.[1];
  if (m === "kit" || m === "screens") return "brand";
  return m && SECTIONS.some((s) => s.to === m) ? m : "";
}

const dot = (brand?: Brand) => <span aria-hidden className="size-3 shrink-0 rounded-full bg-brand" style={brand?.colours?.[0] ? { background: brand.colours[0] } : undefined} />;

function useOnline() {
  const [online, setOnline] = useState(() => navigator.onLine !== false);
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  return online;
}

/** Top bar (switcher, Approvals, account), the four brand sections (side rail or bottom tabs), and a studio group for Reed. */
export function Shell() {
  return (
    <ActionBarProvider>
      <Frame />
    </ActionBarProvider>
  );
}

function Frame() {
  const { data: brands, isPending, isError } = useBrands();
  const { brandId } = useParams();
  const fromUrl = Number(brandId) || null;
  // Off brand pages (e.g. /team) you stay "in" the brand you were last in.
  const current = fromUrl ?? (brands?.some((b) => b.id === lastBrand()) ? lastBrand() : null);
  const brand = brands?.find((b) => b.id === current);
  const rail = useMedia("(min-width: 1024px)");
  const wide = useMedia("(min-width: 1280px)");
  const online = useOnline();
  const held = useHeld();
  const { count, setNode } = useActionBarSlot();
  // Inside one video on a phone, the video's own header line replaces the brand bar.
  const video = useMatch("/b/:brandId/projects/:projectId");
  const inVideo = !rail && video !== null && /^\d+$/.test(video.params.projectId ?? "");

  useEffect(() => {
    if (fromUrl) rememberBrand(fromUrl);
  }, [fromUrl]);

  useEffect(() => {
    const root = document.documentElement.style;
    if (brand?.colours?.[0]) root.setProperty("--brand", brand.colours[0]);
    else root.removeProperty("--brand");
    return () => void root.removeProperty("--brand");
  }, [brand]);

  const waiting = held.owner ? held.count : null;
  const work = (
    <div className="min-w-0 flex-1" style={rail ? undefined : { paddingBottom: `calc(var(--tabbar-h) + env(safe-area-inset-bottom)${count > 0 ? " + var(--actionbar-h)" : ""})` }}>
      {!online && (
        <div className="mx-auto max-w-content px-4 pt-4 sm:px-8">
          <Banner tone="warning" title="You're offline.">
            Reconnect to keep working; nothing was lost.
          </Banner>
        </div>
      )}
      {isPending ? (
        <div className="mx-auto max-w-content space-y-4 p-4 sm:p-8" role="status" aria-label="Loading">
          <Skeleton className="h-10 w-1/3" />
          <Skeleton className="h-40" />
        </div>
      ) : isError || !brands ? (
        <p role="alert" className="p-6 text-danger">Could not load brands.</p>
      ) : brands.length === 0 ? (
        <div className="mx-auto max-w-content p-4 sm:p-8">
          <EmptyState icon={Palette} title="No brands yet">Reed adds brands. fomo and Iron Paws come with the studio.</EmptyState>
        </div>
      ) : (
        <Outlet />
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-bg text-text">
      {!inVideo && <TopBar brands={brands ?? []} brand={brand} current={current} waiting={waiting} rail={rail} />}
      <div className="flex">
        {rail && <Rail brand={brand} current={current} wide={wide} owner={held.owner} waiting={waiting} />}
        {work}
      </div>
      {!rail && (
        <>
          <div ref={setNode} className="fixed inset-x-0 z-20 bg-surface empty:hidden" style={{ bottom: "calc(var(--tabbar-h) + env(safe-area-inset-bottom))" }} />
          <Tabs current={current} />
        </>
      )}
    </div>
  );
}

function Badge({ n }: { n: number | null }) {
  if (!n) return null;
  return (
    <span className="ml-auto inline-grid min-w-5 place-items-center rounded-full bg-accent px-1.5 text-xs font-semibold text-on-accent tabular-nums">
      {n}
      <span className="sr-only"> waiting</span>
    </span>
  );
}

function TopBar({ brands, brand, current, waiting, rail }: { brands: Brand[]; brand?: Brand; current: number | null; waiting: number | null; rail: boolean }) {
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-2 border-b border-border bg-bg px-4 lg:h-topbar lg:px-6">
      <BrandSwitcher brands={brands} brand={brand} current={current} />
      <div className="ml-auto flex items-center gap-2">
        {waiting !== null &&
          (rail ? (
            <Link to="/approvals" className="inline-flex min-h-control items-center gap-2 rounded-full border border-border bg-surface-2 px-4 text-base hover:bg-surface-3">
              <Bell size={20} strokeWidth={1.75} aria-hidden />
              Approvals
              {waiting > 0 && (
                <span className="inline-grid min-w-5 place-items-center rounded-full bg-accent px-1.5 text-xs font-semibold text-on-accent tabular-nums">
                  {waiting}
                  <span className="sr-only"> waiting</span>
                </span>
              )}
            </Link>
          ) : (
            <Link to="/approvals" aria-label={waiting > 0 ? `Approvals, ${waiting} waiting` : "Approvals"} className="relative grid size-control place-items-center rounded-full hover:bg-surface-2">
              <Bell size={20} strokeWidth={1.75} aria-hidden />
              {waiting > 0 && <span aria-hidden className="absolute right-1 top-1 inline-grid min-w-5 place-items-center rounded-full bg-accent px-1 text-xs font-semibold text-on-accent tabular-nums">{waiting}</span>}
            </Link>
          ))}
        <AccountMenu />
      </div>
    </header>
  );
}

function BrandSwitcher({ brands, brand, current }: { brands: Brand[]; brand?: Brand; current: number | null }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const go = (id: number) => {
    const section = sectionOf(pathname);
    navigate(section ? `/b/${id}/${section}` : `/b/${id}`);
  };
  return (
    <div className="min-w-0 flex-1 lg:flex-none">
      <Menu
        title="Brands"
        trigger={(p) => (
          <button type="button" {...p} aria-label={brand ? `Brand: ${brand.name}` : "Choose a brand"} className="inline-flex min-h-control w-full max-w-full items-center gap-2 rounded-md border border-border bg-surface-2 px-3 hover:bg-surface-3 lg:w-auto">
            {dot(brand)}
            <span className="min-w-0 flex-1 truncate text-left font-bold">{brand ? brand.name : "Choose a brand"}</span>
            <ChevronDown size={20} strokeWidth={1.75} aria-hidden />
          </button>
        )}
      >
        {(close) => (
          <>
            {brands.map((b) => (
              <MenuItem
                key={b.id}
                checked={b.id === current}
                onClick={() => {
                  close();
                  go(b.id);
                }}
              >
                {dot(b)}
                <span className="flex-1">{b.name}</span>
                {b.id === current && <Check size={20} strokeWidth={1.75} aria-hidden />}
              </MenuItem>
            ))}
            <p className="px-3 pb-2 pt-3 text-sm text-muted">Brands are set up by Reed.</p>
          </>
        )}
      </Menu>
    </div>
  );
}

const THEMES: { id: Theme; label: string }[] = [
  { id: "dark", label: "Dark" },
  { id: "light", label: "Light" },
  { id: "system", label: "Match my device" },
];

function AccountMenu() {
  const { data: me } = useMe();
  const signOut = useSignOut();
  const [theme, setTheme] = useState<Theme>(getTheme);
  const initials = (me?.name ?? "?").split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  return (
    <Menu
      title="Account"
      align="right"
      trigger={(p) => (
        <button type="button" {...p} aria-label="Account menu" className="grid size-control place-items-center rounded-full bg-accent-soft text-sm font-semibold text-accent-text">
          {initials}
        </button>
      )}
    >
      {(close) => (
        <>
          <div className="px-3 pb-2 pt-1">
            <div className="font-semibold">{me?.name}</div>
            <div className="text-sm text-muted">{me?.email}</div>
          </div>
          {me?.role === "owner" && (
            <Link to="/team" onClick={close} className="flex min-h-control items-center gap-3 rounded-md px-3 hover:bg-surface-2">
              <UserPlus size={20} strokeWidth={1.75} aria-hidden />
              Team
            </Link>
          )}
          <div role="group" aria-label="Theme" className="mt-1 border-t border-border pt-1">
            <p className="px-3 pt-2 text-xs font-bold uppercase tracking-[0.12em] text-muted">Theme</p>
            {THEMES.map((t) => (
              <MenuItem
                key={t.id}
                checked={theme === t.id}
                onClick={() => {
                  applyTheme(t.id);
                  setTheme(t.id);
                }}
              >
                <span className="flex-1">{t.label}</span>
                {theme === t.id && <Check size={20} strokeWidth={1.75} aria-hidden />}
              </MenuItem>
            ))}
          </div>
          <div className="mt-1 border-t border-border pt-1">
            <MenuItem onClick={() => signOut.mutate()}>
              <LogOut size={20} strokeWidth={1.75} aria-hidden />
              Sign out
            </MenuItem>
          </div>
        </>
      )}
    </Menu>
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

function Rail({ brand, current, wide, owner, waiting }: { brand?: Brand; current: number | null; wide: boolean; owner: boolean; waiting: number | null }) {
  const item = ({ isActive }: { isActive: boolean }) =>
    `relative flex min-h-control items-center gap-3 rounded-md px-3 ${wide ? "" : "justify-center"} ${isActive ? "bg-surface-2 text-text before:absolute before:inset-y-2 before:left-0 before:w-[3px] before:rounded-full before:bg-accent" : "text-muted hover:bg-surface-2 hover:text-text"}`;
  const row = (to: string, label: string, Icon: LucideIcon, extra?: ReactNode) => (
    <NavLink key={to} to={to} className={item} aria-label={wide ? undefined : label} title={wide ? undefined : label}>
      <Icon size={20} strokeWidth={1.75} aria-hidden />
      {wide && <span>{label}</span>}
      {wide && extra}
    </NavLink>
  );
  return (
    <nav aria-label="Main" className={`sticky top-topbar h-[calc(100vh-var(--topbar-h))] shrink-0 overflow-y-auto border-r border-border bg-bg p-3 ${wide ? "w-rail" : "w-[72px]"}`}>
      {wide && brand && <p className="px-3 pb-2 pt-3 text-xs font-bold uppercase tracking-[0.12em] text-muted">{brand.name}</p>}
      {current && <div className="flex flex-col gap-1">{SECTIONS.map((s) => row(`/b/${current}/${s.to}`, s.label, s.icon))}</div>}
      {owner && (
        <div className="mt-4 border-t border-border pt-2">
          {wide && <p className="px-3 pb-2 pt-3 text-xs font-bold uppercase tracking-[0.12em] text-muted">Studio</p>}
          <div className="flex flex-col gap-1">
            {row("/approvals", "Approvals", Bell, <Badge n={waiting} />)}
            {row("/team", "Team", UserPlus)}
          </div>
        </div>
      )}
    </nav>
  );
}

function Tabs({ current }: { current: number | null }) {
  const tab = ({ isActive }: { isActive: boolean }) => `flex min-h-control flex-1 flex-col items-center justify-center gap-0.5 text-[11.5px] ${isActive ? "font-semibold text-accent-text" : "text-muted"}`;
  return (
    <nav aria-label="Tabs" style={{ height: "calc(var(--tabbar-h) + env(safe-area-inset-bottom))" }} className="fixed inset-x-0 bottom-0 z-20 flex border-t border-border bg-surface pb-[env(safe-area-inset-bottom)]">
      {current &&
        SECTIONS.map((s) => (
          <NavLink key={s.to} to={`/b/${current}/${s.to}`} className={tab}>
            <s.icon size={20} strokeWidth={1.75} aria-hidden />
            {s.short}
          </NavLink>
        ))}
    </nav>
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

/** A brand's home is its Videos list. */
export function BrandHome() {
  const { brandId } = useParams();
  const { data: brands } = useBrands();
  if (!brands?.some((b) => b.id === Number(brandId))) return <p className="p-6">That brand doesn't exist.</p>;
  return <Navigate to={`/b/${brandId}/projects`} replace />;
}

