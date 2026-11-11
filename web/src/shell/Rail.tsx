import type { ReactNode } from "react";
import { Clock, Film, House, Inbox, Package, Palette, Users, type LucideIcon } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { useMyRequests } from "../approvals/HeldRequests";
import { AccountMenu } from "./AccountMenu";
import { FolderTree } from "./FolderTree";
import { QuickSearch } from "./QuickSearch";
import { NewVideoRow, RailGroup, railRow } from "./RailParts";

/** Home's other address (New video's). */
export const HOME = /^\/b\/\d+\/videos\/new$/;

// Assets: what a brand is made of. Brand is also where its footage, media and scripts are reached from, so it is the
// current row on those pages; Cast is the library's characters, places and presenters.
const ASSETS: { to: string; label: string; icon: LucideIcon; under?: RegExp }[] = [
  { to: "brand", label: "Brand", icon: Palette, under: /^\/b\/\d+\/(scripts|media|library\/footage)(\/|$)/ },
  { to: "library/products", label: "Products", icon: Package },
  { to: "library/characters", label: "Cast", icon: Users, under: /^\/b\/\d+\/library\/(places|presenters)(\/|$)/ },
];

/** A nav link that knows when it is current, including for the pages that belong under it (a video sits under All videos). */
export function NavItem({ to, also, under, exact, className, children, ...rest }: { to: string; also?: string; /** also current on these pages (the phone's Library tab, Home's other address) */ under?: RegExp; /** not current on the pages under it (Home) */ exact?: boolean; className: (active: boolean) => string; children: ReactNode; "aria-label"?: string; title?: string }) {
  const { pathname } = useLocation();
  const onNew = HOME.test(pathname); // under /videos, but it is Home
  const active = pathname === to || !!under?.test(pathname) || (!exact && !onNew && (pathname.startsWith(`${to}/`) || (!!also && pathname.startsWith(`${to.replace(/[^/]+$/, "")}${also}`))));
  return (
    <Link to={to} className={className(active)} aria-current={active ? "page" : undefined} {...rest}>
      {children}
    </Link>
  );
}

/** The desktop rail, top to bottom: the brand switcher; Home and All videos (and what waits: the owner's Needs you only
 *  while something does, an editor's My requests); Assets; Projects (New video, Recent, the folders); the account, where
 *  the owner's Studio pages live. Between 1024 and 1279 px the same rows are icons. */
export function Rail({ switcher, current, wide, owner, waiting }: { switcher: ReactNode; current: number | null; wide: boolean; owner: boolean; waiting: number | null }) {
  const mine = (useMyRequests().data ?? []).filter((j) => j.status === "needs_owner_approval").length;
  const item = (isActive: boolean) => `${railRow} font-medium ${wide ? "" : "justify-center"} text-text ${isActive ? "bg-surface shadow-soft" : "hover:bg-surface-3"}`;
  const row = (to: string, label: string, Icon: LucideIcon, o: { extra?: ReactNode; also?: string; under?: RegExp } = {}) => (
    <NavItem key={to} to={to} also={o.also} under={o.under} className={item} aria-label={wide ? undefined : label} title={wide ? undefined : label}>
      <Icon size={14} strokeWidth={1.75} aria-hidden className="shrink-0 text-muted" />
      {wide && <span>{label}</span>}
      {wide && o.extra}
    </NavItem>
  );
  const count = (n: number, tone: "need" | "n") => (
    <span className={`ml-auto inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-full px-1.5 text-[11px] font-semibold tabular-nums ${tone === "need" ? "bg-warning-soft text-warning" : "bg-surface-3 text-muted"}`}>
      {n}
      <span className="sr-only"> waiting</span>
    </span>
  );
  return (
    <nav aria-label="Main" className={`z-30 flex h-full shrink-0 flex-col gap-0.5 px-2 py-2.5 ${wide ? "w-rail" : "w-[64px]"}`}>
      {/* Only the rows scroll: the brand and account menus are wider than the rail and must not be clipped by it. */}
      {switcher}
      {current && (
        <div className={`flex gap-2 pt-0.5 ${wide ? "" : "flex-col"}`}>
          {/* Home, with its key: N opens it on the words box from anywhere. */}
          <NavItem to={`/b/${current}`} exact under={HOME} aria-label="Home" title="Home (N)" className={(on) => `${item(on)} ${wide ? "min-w-0 flex-1" : ""}`}>
            <House size={14} strokeWidth={1.75} aria-hidden className="shrink-0 text-muted" />
            {wide && <span aria-hidden className="flex-1">Home</span>}
            {wide && <kbd aria-hidden className="rounded-sm border border-border-button px-1 font-sans text-[11px] leading-4 text-muted">N</kbd>}
          </NavItem>
          {wide && <QuickSearch brandId={current} />}
        </div>
      )}
      <div className="-mx-2 flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto px-2">
        {current && row(`/b/${current}/videos`, "All videos", Film, { also: "projects" })}
        {/* Needs you shows only while something waits (its count is everything it lists, every brand); it is always in the account menu. */}
        {owner ? !!waiting && row("/approvals", "Needs you", Inbox, { extra: count(waiting, "need") }) : row("/requests", "My requests", Clock, { extra: count(mine, "n") })}
        {current && (
          <RailGroup id="assets" label="Assets" wide={wide}>
            {ASSETS.map((a) => row(`/b/${current}/${a.to}`, a.label, a.icon, { under: a.under }))}
          </RailGroup>
        )}
        {current &&
          (wide ? (
            <FolderTree brandId={current} />
          ) : (
            <RailGroup id="projects" label="Projects" wide={false}>
              <NewVideoRow brandId={current} wide={false} />
            </RailGroup>
          ))}
      </div>
      <div className="pt-2">
        <AccountMenu inRail iconOnly={!wide} />
      </div>
    </nav>
  );
}
