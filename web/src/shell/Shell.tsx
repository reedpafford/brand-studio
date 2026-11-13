import { useEffect, useRef, type ReactNode } from "react";
import { Archive, ChevronDown, Clock, Ellipsis, Film, Inbox, Plus, Palette, Check, Users, type LucideIcon } from "lucide-react";
import { Navigate, Outlet, useLocation, useMatch, useNavigate, useParams } from "react-router-dom";
import { WORDS_ID } from "../home/Words";
import { useMyRequests } from "../approvals/HeldRequests";
import { useArchiveBrand } from "../brand/ArchiveBrand";
import { useNeedsYou } from "../approvals/NeedsYouPage";
import { useMe } from "../auth/useMe";
import { Banner, EmptyState, Menu, MenuItem, Skeleton } from "../components";
import { useMedia, useOnline } from "../useMedia";
import { HOME, NavItem, Rail } from "./Rail";
import { ActionBarProvider, useActionBarSlot } from "./ActionBar";
import { lastBrand, rememberBrand, useBrands } from "./useBrands";
import { newLook } from "../studio/look";

type Brand = { id: number; name: string; colours?: string[] };

const SECTIONS = ["videos", "scripts", "media", "brand"];

/** Where a brand switch lands: the same section in the other brand (the library's same tab: Products, Cast); a video or
 *  an item goes to that section's list, and Home (at either address) stays Home. */
function sectionOf(pathname: string) {
  if (HOME.test(pathname)) return "";
  const tab = /^\/b\/\d+\/library\/([a-z]+)/.exec(pathname)?.[1];
  if (tab) return `library/${tab}`;
  const m = /^\/b\/\d+\/([^/]+)/.exec(pathname)?.[1];
  if (m === "kit" || m === "screens") return "brand";
  if (m === "projects") return "videos";
  return m && SECTIONS.includes(m) ? m : "";
}

const href = (to: string, brand: number) => `/b/${brand}/${to}`;
const typing = (t: EventTarget | null) => t instanceof HTMLElement && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName));
// v5 A_Shell/A_Account: a brand is a small colour square.
const dot = (brand?: Brand) => <span aria-hidden className="size-3.5 shrink-0 rounded-[3px]" style={{ background: brand?.colours?.[0] || "var(--accent)" }} />; // no colour: the accent, as the Brand page;

/** Desktop: one rail (`Rail`: the brand switcher on top; Home, All videos, Assets, Projects; the account at the bottom), no top bar.
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
  // Off brand pages (e.g. /team) you stay "in" the brand you were last in, or the first one: the rail keeps the brand's
  // rows on every page, Studio ones and an editor's My credits included (v5 A_Shell; audit lane 2).
  const current = fromUrl ?? (brands?.some((b) => b.id === lastBrand()) ? lastBrand() : (brands?.[0]?.id ?? null));
  const brand = brands?.find((b) => b.id === current);
  const rail = useMedia("(min-width: 1024px)");
  const wide = useMedia("(min-width: 1280px)");
  const online = useOnline();
  const owner = useMe().data?.role === "owner";
  const needsYou = useNeedsYou(null, owner).data; // Needs you's count is everything it lists, every brand (S9-01)
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
  const inVideo = !rail && ((newVideo !== null && /^\d+$/.test(newVideo.params.projectId ?? "")) || newProject !== null);
  const folderPage = useMatch("/b/:brandId/videos");
  const needsYouPage = useMatch("/approvals");
  const onFolders = !rail && (folderPage !== null || needsYouPage !== null); // P-01, P-02 and P-14 draw their own header
  // The video page (v6 S3) fills the screen: its own offline line, and on a phone no tabs under its message box (P-04).
  const onVideo = newVideo !== null && /^\d+$/.test(newVideo.params.projectId ?? "");

  useEffect(() => {
    if (fromUrl) rememberBrand(fromUrl);
  }, [fromUrl]);

  // N opens Home, on its words box, from anywhere but a box being typed in or an open dialog (A_Shell's keys).
  const navigate = useNavigate();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() !== "n" || e.metaKey || e.ctrlKey || e.altKey || typing(e.target) || !current || document.querySelector("[aria-modal]")) return;
      e.preventDefault();
      navigate(`/b/${current}`);
      document.getElementById(WORDS_ID)?.focus(); // already Home: straight to the words (a fresh Home focuses them itself)
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

  // The panel is the same element from page to page: each page opens at its top. It is `relative`, so what a page places
  // absolutely (a screen reader's hidden words too) scrolls inside it and never makes the window itself scroll.
  const panel = useRef<HTMLDivElement>(null);
  const { pathname: at } = useLocation();
  useEffect(() => {
    if (panel.current) panel.current.scrollTop = 0;
  }, [at]);

  const waiting = owner ? (needsYou?.total ?? null) : null; // no count until it's read: never a 0 that isn't so
  const work = (
    <div ref={panel} className={`min-w-0 flex-1 ${rail ? "relative my-2 mr-2 overflow-y-auto rounded-2xl border border-border bg-bg shadow-soft" : ""}`} style={rail || onVideo ? undefined : { paddingBottom: `calc(var(--tabbar-h) + env(safe-area-inset-bottom)${count > 0 ? " + var(--actionbar-h)" : ""})` }}>
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
    // On a desktop the rail sits on the canvas and the page is one rounded panel beside it, which scrolls on its own.
    <div className={`text-text ${rail ? "h-screen overflow-hidden bg-canvas" : "min-h-screen bg-bg"}`}>
      {!inVideo && !onFolders && !rail && <TopBar brands={brands ?? []} brand={brand} current={current} />}
      <div className={rail ? "flex h-full" : "flex"}>
        {rail && <Rail switcher={<BrandSwitcher brands={brands ?? []} brand={brand} current={current} inRail iconOnly={!wide} />} current={current} wide={wide} owner={owner} waiting={waiting} />}
        {work}
      </div>
      {!rail && (
        <>
          <div ref={setNode} className="fixed inset-x-0 z-20 bg-surface empty:hidden" style={{ bottom: onVideo ? "env(safe-area-inset-bottom)" : "calc(var(--tabbar-h) + env(safe-area-inset-bottom))" }} />
          {!onVideo && <Tabs current={current} owner={owner} waiting={waiting} />}
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

/** "/" goes to the brand you were last in, else the first one. `studio`: in the new look at /s/ (its own "/"). This
 *  one opens the new look for the owner, unless this computer was sent back to the current site; an editor's pages
 *  are the current site's. */
export function GoToBrand({ studio }: { studio?: boolean }) {
  const { data: brands, isPending } = useBrands();
  const me = useMe();
  if (isPending || (studio === undefined && me.isPending)) return <p className="p-6 text-muted">Loading…</p>;
  studio ??= newLook() && me.data?.role === "owner";
  const last = lastBrand();
  const target = brands?.find((b) => b.id === last) ?? brands?.[0];
  return target ? <Navigate to={`${studio ? "/s" : ""}/b/${target.id}`} replace /> : <Navigate to="/team" replace />;
}
