import { useEffect, useState, type ReactNode } from "react";
import { Bell, ChevronDown, Film, Plus, FileText, Images, Palette, Check, Sparkles, Users, type LucideIcon } from "lucide-react";
import { Link, Navigate, Outlet, useLocation, useMatch, useNavigate, useParams } from "react-router-dom";
import { useHeld } from "../approvals/useHeld";
import { useMe } from "../auth/useMe";
import { useProductionSummary } from "../production/useProduction";
import { Banner, EmptyState, Menu, MenuItem, Skeleton } from "../components";
import { useMedia } from "../useMedia";
import { AccountMenu, STUDIO } from "./AccountMenu";
import { ActionBarProvider, useActionBarSlot } from "./ActionBar";
import { lastBrand, rememberBrand, useBrands } from "./useBrands";

type Brand = { id: number; name: string; colours?: string[] };

// Phone tabs keep this order; the desktop rail groups them (Make, Library) in the order work happens (Reed, 2 Nov: nav A).
const SECTIONS: { to: string; also?: string; label: string; short: string; icon: LucideIcon; railOnly?: boolean }[] = [
  { to: "videos", also: "projects", label: "Videos", short: "Videos", icon: Film },
  { to: "scripts", label: "Scripts", short: "Scripts", icon: FileText },
  { to: "/freestyle", label: "Freestyle", short: "Freestyle", icon: Sparkles }, // not under a brand
  { to: "media", label: "Media", short: "Media", icon: Images, railOnly: true }, // on a phone: from the Videos header (five tabs)
  { to: "library", label: "Cast & places", short: "Cast", icon: Users },
  { to: "brand", label: "Brand", short: "Brand", icon: Palette },
];

/** Where a brand switch lands: the same section in the other brand; a video or an item goes to that section's list. */
function sectionOf(pathname: string) {
  const m = /^\/b\/\d+\/([^/]+)/.exec(pathname)?.[1];
  if (m === "kit" || m === "screens") return "brand";
  if (m === "projects") return "videos";
  return m && SECTIONS.some((s) => s.to === m) ? m : "";
}

const href = (to: string, brand: number) => (to.startsWith("/") ? to : `/b/${brand}/${to}`);
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

/** Desktop: one rail (brand switcher on top; Make, Library and, for Reed, Studio; the account at the bottom), no top bar.
 *  Phone: the top bar (switcher, Needs you, account) and the bottom tabs. */
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
  // Needs you counts all it lists (held requests, videos that need attention, changes waiting), from reads the shell makes anyway.
  const summary = useProductionSummary(held.owner).data;
  const attention = (summary?.needs_attention ?? 0) + (summary?.changes_waiting ?? 0);
  const { count, node, setNode } = useActionBarSlot();
  // The phone's action bar is as tall as what's in it (the cost bar is taller than one button): the page's bottom
  // padding and the toasts sit above its real height, so neither the work nor a toast hides behind or over it.
  useEffect(() => {
    if (!node || typeof ResizeObserver === "undefined") return;
    const root = document.documentElement.style;
    const fit = () => (node.offsetHeight ? root.setProperty("--actionbar-h", `${node.offsetHeight}px`) : root.removeProperty("--actionbar-h"));
    const watch = new ResizeObserver(fit);
    watch.observe(node);
    return () => {
      watch.disconnect();
      root.removeProperty("--actionbar-h");
    };
  }, [node]);
  // Inside one video on a phone, the video's own header line replaces the brand bar.
  const oldVideo = useMatch("/b/:brandId/projects/:projectId");
  const newVideo = useMatch("/b/:brandId/videos/:projectId");
  const video = newVideo ?? oldVideo;
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

  const waiting = held.owner ? held.count + attention : null;
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
          <EmptyState icon={Palette} title="No brands yet">The owner adds brands. fomo and Iron Paws come with the studio.</EmptyState>
        </div>
      ) : (
        <Outlet />
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-bg text-text">
      {!inVideo && !rail && <TopBar brands={brands ?? []} brand={brand} current={current} waiting={waiting} />}
      <div className="flex">
        {rail && <Rail brands={brands ?? []} brand={brand} current={current} wide={wide} owner={held.owner} waiting={waiting} />}
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
    <span className="ml-auto inline-flex items-center gap-1.5 text-xs text-warning tabular-nums">
      <span aria-hidden className="size-1.5 rounded-full bg-warning" />
      {n}
      <span className="sr-only"> waiting</span>
    </span>
  );
}

function TopBar({ brands, brand, current, waiting }: { brands: Brand[]; brand?: Brand; current: number | null; waiting: number | null }) {
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-2 border-b border-border bg-bg px-4">
      <BrandSwitcher brands={brands} brand={brand} current={current} />
      <div className="ml-auto flex items-center gap-2">
        {/* Needs you shows only while something waits (Reed, 30 Oct); the page itself stays at /approvals. */}
        {!!waiting && (
          <Link to="/approvals" aria-label={`Needs you, ${waiting} waiting`} className="relative grid size-control place-items-center rounded-full hover:bg-surface-2">
            <Bell size={20} strokeWidth={1.75} aria-hidden />
            <span aria-hidden className="absolute right-1 top-1 inline-grid min-w-5 place-items-center rounded-full bg-accent px-1 text-xs font-semibold text-on-accent tabular-nums">{waiting}</span>
          </Link>
        )}
        <AccountMenu />
      </div>
    </header>
  );
}

function BrandSwitcher({ brands, brand, current, inRail, iconOnly }: { brands: Brand[]; brand?: Brand; current: number | null; inRail?: boolean; iconOnly?: boolean }) {
  const navigate = useNavigate();
  const owner = useMe().data?.role === "owner";
  const { pathname } = useLocation();
  const go = (id: number) => {
    const section = sectionOf(pathname);
    navigate(section ? `/b/${id}/${section}` : `/b/${id}`);
  };
  return (
    <div className={inRail ? "min-w-0" : "min-w-0 flex-1 lg:flex-none"}>
      <Menu
        title="Brands"
        trigger={(p) => (
          <button
            type="button"
            {...p}
            aria-label={brand ? `Brand: ${brand.name}` : "Choose a brand"}
            className={inRail ? `flex min-h-control w-full items-center gap-2 rounded-md px-2 hover:bg-surface-2 ${iconOnly ? "justify-center" : ""}` : "inline-flex min-h-control w-full max-w-full items-center gap-2 rounded-md border border-border bg-surface-2 px-3 hover:bg-surface-3 lg:w-auto"}
          >
            {dot(brand)}
            {!iconOnly && <span className="min-w-0 flex-1 truncate text-left font-semibold">{brand ? brand.name : "Choose a brand"}</span>}
            {!iconOnly && <ChevronDown size={16} strokeWidth={1.75} aria-hidden className="text-muted" />}
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
            {owner && (
              <div className="mt-1 border-t border-border pt-1">
                <MenuItem
                  onClick={() => {
                    close();
                    navigate("/brands/new");
                  }}
                >
                  <Plus size={20} strokeWidth={1.75} aria-hidden />
                  New brand
                </MenuItem>
              </div>
            )}
          </>
        )}
      </Menu>
    </div>
  );
}

/** A nav link that knows when it is current, including for the pages that belong under it (a video sits under Scripts). */
function NavItem({ to, also, className, children, ...rest }: { to: string; also?: string; className: (active: boolean) => string; children: ReactNode; "aria-label"?: string; title?: string }) {
  const { pathname } = useLocation();
  const active = pathname === to || pathname.startsWith(`${to}/`) || (!!also && pathname.startsWith(`${to.replace(/[^/]+$/, "")}${also}`));
  return (
    <Link to={to} className={className(active)} aria-current={active ? "page" : undefined} {...rest}>
      {children}
    </Link>
  );
}

function Rail({ brands, brand, current, wide, owner, waiting }: { brands: Brand[]; brand?: Brand; current: number | null; wide: boolean; owner: boolean; waiting: number | null }) {
  const item = (isActive: boolean) => `flex min-h-control-dense items-center gap-2.5 rounded-md px-2 ${wide ? "" : "justify-center"} ${isActive ? "bg-surface-2 font-medium text-text" : "text-muted hover:bg-surface-2 hover:text-text"}`;
  const row = (to: string, label: string, Icon: LucideIcon, extra?: ReactNode, also?: string) => (
    <NavItem key={to} to={to} also={also} className={item} aria-label={wide ? undefined : label} title={wide ? undefined : label}>
      <Icon size={16} strokeWidth={1.75} aria-hidden />
      {wide && <span>{label}</span>}
      {wide && extra}
    </NavItem>
  );
  const section = (to: string) => SECTIONS.find((s) => s.to === to)!;
  const group = (label: string, rows: ReactNode) => (
    <div className="mt-4 flex flex-col gap-0.5">
      {wide && <p className="px-2 pb-1 text-xs text-muted">{label}</p>}
      {rows}
    </div>
  );
  return (
    <nav aria-label="Main" className={`sticky top-0 z-30 flex h-screen shrink-0 flex-col border-r border-border bg-surface p-2 ${wide ? "w-rail" : "w-[64px]"}`}>
      {/* Only the rows scroll: the brand and account menus are wider than the rail and must not be clipped by it. */}
      <BrandSwitcher brands={brands} brand={brand} current={current} inRail iconOnly={!wide} />
      <div className="-mx-2 min-h-0 flex-1 overflow-y-auto px-2">
        {current && group("Make", ["scripts", "videos", "/freestyle"].map((to) => { const s = section(to); return row(href(s.to, current), s.label, s.icon, undefined, s.also); }))}
        {current && group("Library", ["library", "media", "brand"].map((to) => { const s = section(to); return row(`/b/${current}/${s.to}`, s.label, s.icon, undefined, s.also); }))}
        {owner &&
          group(
            "Studio",
            <>
              {!!waiting && row("/approvals", "Needs you", Bell, <Badge n={waiting} />)}
              {STUDIO.map(([to, label, Icon]) => row(to, label, Icon))}
            </>,
          )}
      </div>
      <div className="pt-4">
        <AccountMenu inRail iconOnly={!wide} />
      </div>
    </nav>
  );
}

function Tabs({ current }: { current: number | null }) {
  const tab = (isActive: boolean) => `flex min-h-control flex-1 flex-col items-center justify-center gap-0.5 text-[11.5px] ${isActive ? "font-semibold text-accent-text" : "text-muted"}`;
  return (
    <nav aria-label="Tabs" style={{ height: "calc(var(--tabbar-h) + env(safe-area-inset-bottom))" }} className="fixed inset-x-0 bottom-0 z-20 flex border-t border-border bg-surface pb-[env(safe-area-inset-bottom)]">
      {current &&
        SECTIONS.filter((s) => !s.railOnly).map((s) => (
          <NavItem key={s.to} to={href(s.to, current)} also={s.also} className={tab}>
            <s.icon size={20} strokeWidth={1.75} aria-hidden />
            {s.short}
          </NavItem>
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

/** Where a brand opens: an editor's day starts from their videos; Reed's from the scripts (audit M6). */
export const HOME: Record<string, string> = { editor: "videos", owner: "scripts" };

export function BrandHome() {
  const { brandId } = useParams();
  const { data: brands } = useBrands();
  const { data: me } = useMe();
  if (!brands?.some((b) => b.id === Number(brandId))) return <p className="p-6">That brand doesn't exist.</p>;
  if (!me) return <p className="p-6 text-muted">Loading…</p>;
  return <Navigate to={`/b/${brandId}/${HOME[me.role] ?? "scripts"}`} replace />;
}

