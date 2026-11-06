import { useEffect, type ReactNode } from "react";
import { Archive, ChevronDown, Clock, Ellipsis, Film, Inbox, Plus, FileText, Images, Palette, Check, Users, type LucideIcon } from "lucide-react";
import { Link, Navigate, Outlet, useLocation, useMatch, useNavigate, useParams } from "react-router-dom";
import { useMyRequests } from "../approvals/HeldRequests";
import { useArchiveBrand } from "../brand/ArchiveBrand";
import { useHeld } from "../approvals/useHeld";
import { useMe } from "../auth/useMe";
import { useProductionSummary } from "../production/useProduction";
import { Banner, EmptyState, Menu, MenuItem, Skeleton } from "../components";
import { useMedia, useOnline } from "../useMedia";
import { AccountMenu, STUDIO } from "./AccountMenu";
import { FolderTree } from "./FolderTree";
import { QuickSearch } from "./QuickSearch";
import { ActionBarProvider, useActionBarSlot } from "./ActionBar";
import { lastBrand, rememberBrand, useBrands } from "./useBrands";

type Brand = { id: number; name: string; colours?: string[] };

// v6 S0-01: the rail's Library rows (Scripts first, S-gaps-04 R1); a brand switch keeps you in the same section.
export const NEW_VIDEO = "videos/new";
const SECTIONS: { to: string; also?: string; label: string; icon: LucideIcon }[] = [
  { to: "videos", also: "projects", label: "Videos", icon: Film },
  { to: "scripts", label: "Scripts", icon: FileText },
  { to: "library", label: "Cast & places", icon: Users },
  { to: "media", label: "Media", icon: Images },
  { to: "brand", label: "Brand kit", icon: Palette },
];
const LIBRARY = ["scripts", "library", "media", "brand"];

/** Where a brand switch lands: the same section in the other brand; a video or an item goes to that section's list. */
function sectionOf(pathname: string) {
  const m = /^\/b\/\d+\/([^/]+)/.exec(pathname)?.[1];
  if (m === "kit" || m === "screens") return "brand";
  if (m === "projects") return "videos";
  return m && SECTIONS.some((s) => s.to === m) ? m : "";
}

const href = (to: string, brand: number) => `/b/${brand}/${to}`;
const typing = (t: EventTarget | null) => t instanceof HTMLElement && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName));
// v5 A_Shell/A_Account: a brand is a small colour square.
const dot = (brand?: Brand) => <span aria-hidden className="size-3.5 shrink-0 rounded-[3px]" style={{ background: brand?.colours?.[0] || "var(--accent)" }} />; // no colour: the accent, as the Brand page;

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
  // Off brand pages (e.g. /team) you stay "in" the brand you were last in, or the first one: the rail keeps Make and
  // Library on every page, Studio ones and an editor's My credits included (v5 A_Shell; audit lane 2).
  const current = fromUrl ?? (brands?.some((b) => b.id === lastBrand()) ? lastBrand() : (brands?.[0]?.id ?? null));
  const brand = brands?.find((b) => b.id === current);
  const rail = useMedia("(min-width: 1024px)");
  const wide = useMedia("(min-width: 1280px)");
  const online = useOnline();
  const held = useHeld();
  // Needs you counts all it lists (held requests, videos that need attention, changes waiting), from reads the shell makes anyway.
  const summary = useProductionSummary(held.owner).data;
  const attention = (summary?.needs_attention ?? 0) + (summary?.changes_waiting ?? 0);
  const { count, node, setNode } = useActionBarSlot();
  // The phone's action bar is as tall as what's in it (it can be taller than one button): the page's bottom
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
  const newVideo = useMatch("/b/:brandId/videos/:projectId");
  const newProject = useMatch("/b/:brandId/projects/new");
  // New video has its own title bar on a phone too (B_PhoneNew).
  const inVideo = !rail && ((newVideo !== null && (/^\d+$/.test(newVideo.params.projectId ?? "") || newVideo.params.projectId === "new")) || newProject !== null);
  const folderPage = useMatch("/b/:brandId/videos");
  const onFolders = !rail && folderPage !== null; // P-01 and P-02 draw their own header
  // The video page (v6 S3) fills the screen: its own offline line, and on a phone no tabs under its message box (P-04).
  const onVideo = newVideo !== null && /^\d+$/.test(newVideo.params.projectId ?? "");

  useEffect(() => {
    if (fromUrl) rememberBrand(fromUrl);
  }, [fromUrl]);

  // N opens New video from anywhere but a box being typed in or an open dialog (A_Shell's keys).
  const navigate = useNavigate();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() !== "n" || e.metaKey || e.ctrlKey || e.altKey || typing(e.target) || !current || document.querySelector("[aria-modal]")) return;
      e.preventDefault();
      navigate(href(NEW_VIDEO, current));
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [current, navigate]);

  useEffect(() => {
    const root = document.documentElement.style;
    if (brand?.colours?.[0]) root.setProperty("--brand", brand.colours[0]);
    else root.removeProperty("--brand");
    return () => void root.removeProperty("--brand");
  }, [brand]);

  const waiting = held.owner ? held.count + attention : null;
  const work = (
    <div className="min-w-0 flex-1" style={rail || onVideo ? undefined : { paddingBottom: `calc(var(--tabbar-h) + env(safe-area-inset-bottom)${count > 0 ? " + var(--actionbar-h)" : ""})` }}>
      {!online && !onVideo && (
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
      {!inVideo && !onFolders && !rail && <TopBar brands={brands ?? []} brand={brand} current={current} />}
      <div className="flex">
        {rail && <Rail brands={brands ?? []} brand={brand} current={current} wide={wide} owner={held.owner} waiting={waiting} />}
        {work}
      </div>
      {!rail && (
        <>
          <div ref={setNode} className="fixed inset-x-0 z-20 bg-surface empty:hidden" style={{ bottom: onVideo ? "env(safe-area-inset-bottom)" : "calc(var(--tabbar-h) + env(safe-area-inset-bottom))" }} />
          {!onVideo && <Tabs current={current} owner={held.owner} waiting={waiting} />}
        </>
      )}
    </div>
  );
}

/** The brand menu on its own, for a phone page that draws its own header (P-01, and a new brand's set-up list). */
export function BrandMenu() {
  const { data: brands } = useBrands();
  const { brandId } = useParams();
  const current = Number(brandId) || null;
  return <BrandSwitcher brands={brands ?? []} brand={brands?.find((b) => b.id === current)} current={current} inRail />; // P-01: plain, as in the rail
}

/** A phone's top bar off the folder pages: the brand menu. Needs you and the account are tabs now (v6 P-01). */
function TopBar({ brands, brand, current }: { brands: Brand[]; brand?: Brand; current: number | null }) {
  return (
    <header aria-label="Top bar" className="sticky top-0 z-20 flex h-14 items-center gap-2 border-b border-border bg-bg px-4">
      <BrandSwitcher brands={brands} brand={brand} current={current} />
    </header>
  );
}

function BrandSwitcher({ brands, brand, current, inRail, iconOnly }: { brands: Brand[]; brand?: Brand; current: number | null; inRail?: boolean; iconOnly?: boolean }) {
  const navigate = useNavigate();
  const owner = useMe().data?.role === "owner";
  const { pathname } = useLocation();
  const archive = useArchiveBrand(brand, brands.filter((b) => b.id !== brand?.id)); // S-gaps-05: Archive is in this menu
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
            {inRail && <p className="px-3 pb-1 pt-1 text-xs font-medium text-muted">Brands</p>}
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
                {brand && (
                  <MenuItem danger onClick={() => (close(), archive.ask())}>
                    <Archive size={20} strokeWidth={1.75} aria-hidden />
                    Archive {brand.name}…
                  </MenuItem>
                )}
              </div>
            )}
          </>
        )}
      </Menu>
      {archive.dialog}
    </div>
  );
}

/** A nav link that knows when it is current, including for the pages that belong under it (a video sits under Scripts). */
function NavItem({ to, also, under, className, children, ...rest }: { to: string; also?: string; /** also current on these pages (the phone's Library tab) */ under?: RegExp; className: (active: boolean) => string; children: ReactNode; "aria-label"?: string; title?: string }) {
  const { pathname } = useLocation();
  const onNew = pathname.endsWith(`/${NEW_VIDEO}`); // under /videos, but its own place
  const active = pathname === to || !!under?.test(pathname) || (!onNew && (pathname.startsWith(`${to}/`) || (!!also && pathname.startsWith(`${to.replace(/[^/]+$/, "")}${also}`))));
  return (
    <Link to={to} className={className(active)} aria-current={active ? "page" : undefined} {...rest}>
      {children}
    </Link>
  );
}

function Rail({ brands, brand, current, wide, owner, waiting }: { brands: Brand[]; brand?: Brand; current: number | null; wide: boolean; owner: boolean; waiting: number | null }) {
  const mine = (useMyRequests().data ?? []).filter((j) => j.status === "needs_owner_approval").length;
  const item = (isActive: boolean) => `flex h-[30px] items-center gap-2 rounded-md px-2 text-sm font-medium ${wide ? "" : "justify-center"} ${isActive ? "bg-surface-3 text-text" : "text-muted hover:bg-surface-3/60 hover:text-text"}`;
  const row = (to: string, label: string, Icon: LucideIcon, extra?: ReactNode, also?: string) => (
    <NavItem key={to} to={to} also={also} className={item} aria-label={wide ? undefined : label} title={wide ? undefined : label}>
      <Icon size={14} strokeWidth={1.75} aria-hidden />
      {wide && <span>{label}</span>}
      {wide && extra}
    </NavItem>
  );
  const count = (n: number, tone: "need" | "n") => (
    <span className={`ml-auto inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-full px-1.5 text-[11px] font-semibold tabular-nums ${tone === "need" ? "bg-warning-soft text-warning" : "bg-surface-3 text-muted"}`}>
      {n}
      <span className="sr-only"> waiting</span>
    </span>
  );
  const section = (to: string) => SECTIONS.find((s) => s.to === to)!;
  const group = (label: string, rows: ReactNode) => (
    <div className="flex flex-col gap-0.5">
      {wide && <p className="mt-2.5 flex h-7 items-center px-2 text-xs font-medium text-muted">{label}</p>}
      {rows}
    </div>
  );
  return (
    <nav aria-label="Main" className={`sticky top-0 z-30 flex h-screen shrink-0 flex-col gap-0.5 border-r border-border bg-surface-2 px-2 py-2.5 ${wide ? "w-rail" : "w-[64px]"}`}>
      {/* Only the rows scroll: the brand and account menus are wider than the rail and must not be clipped by it. */}
      <BrandSwitcher brands={brands} brand={brand} current={current} inRail iconOnly={!wide} />
      {current && (
        <div className={`flex gap-2 pb-1.5 pt-0.5 ${wide ? "" : "flex-col"}`}>
          {/* v6 S0-01: outlined, with its key; the open folder's own New video is the page's indigo press. */}
          <Link to={href(NEW_VIDEO, current)} aria-label="New video" title="New video (N)" className={`inline-flex h-8 min-w-0 flex-1 items-center gap-1.5 rounded-md border border-border-button bg-surface px-3 text-sm font-medium text-text hover:bg-surface-2 ${wide ? "" : "justify-center"}`}>
            <Plus size={14} strokeWidth={1.75} aria-hidden />
            {wide && <span aria-hidden className="flex-1">New video</span>}
            {wide && <kbd aria-hidden className="rounded-sm border border-border-button px-1 font-sans text-[11px] leading-4 text-muted">N</kbd>}
          </Link>
          {wide && <QuickSearch brandId={current} />}
        </div>
      )}
      <div className="-mx-2 min-h-0 flex-1 overflow-y-auto px-2">
        {current && (wide ? <FolderTree brandId={current} /> : <div className="mt-2.5">{row(href("videos", current), "Videos", Film, undefined, "projects")}</div>)}
        {current && group("Library", LIBRARY.map((to) => { const s = section(to); return row(href(s.to, current), s.label, s.icon, undefined, s.also); }))}
        {owner
          ? group(
              "Studio",
              <>
                {row("/approvals", "Needs you", Inbox, count(waiting ?? 0, "need"))}
                {STUDIO.map(([to, label, Icon]) => row(to, label, Icon))}
              </>,
            )
          : group("Mine", row("/requests", "My requests", Clock, count(mine, "n")))}
      </div>
      <div className="pt-2">
        <AccountMenu inRail iconOnly={!wide} />
      </div>
    </nav>
  );
}

/** The phone's four tabs (v6 P-01, S-gaps-04 R3): Videos, Library, Needs you (an editor's My requests) and More. */
function Tabs({ current, owner, waiting }: { current: number | null; owner: boolean; waiting: number | null }) {
  const mine = (useMyRequests().data ?? []).filter((j) => j.status === "needs_owner_approval").length;
  const tab = (isActive: boolean) => `relative flex min-h-control flex-1 flex-col items-center justify-center gap-0.5 text-[11.5px] ${isActive ? "font-semibold text-text" : "text-muted"}`;
  const badge = (n: number | null) =>
    n ? (
      <span className="absolute left-[54%] top-1 inline-grid h-[18px] min-w-[18px] place-items-center rounded-full bg-warning-soft px-1 text-[11px] font-semibold text-warning tabular-nums">
        {n}
        <span className="sr-only"> waiting</span>
      </span>
    ) : null;
  const tabs: [string, string, LucideIcon, ReactNode?, string?, RegExp?][] = current
    ? [
        [href("videos", current), "Videos", Film, null, "projects"],
        [`/b/${current}/more/library`, "Library", Users, null, undefined, /^\/b\/\d+\/(scripts|library|media|brand)(\/|$)/],
        owner ? ["/approvals", "Needs you", Inbox, badge(waiting)] : ["/requests", "My requests", Clock, badge(mine)],
        ["/more", "More", Ellipsis],
      ]
    : [];
  return (
    <nav aria-label="Tabs" style={{ height: "calc(var(--tabbar-h) + env(safe-area-inset-bottom))" }} className="fixed inset-x-0 bottom-0 z-20 flex border-t border-border bg-surface pb-[env(safe-area-inset-bottom)]">
      {tabs.map(([to, label, Icon, extra, also, under]) => (
        <NavItem key={to} to={to} also={also} under={under} className={tab}>
          <Icon size={20} strokeWidth={1.75} aria-hidden />
          {label}
          {extra}
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

