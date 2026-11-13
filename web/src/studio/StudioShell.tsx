import { useEffect, useState } from "react";
import { ChevronDown, Clapperboard, Film, Plus, Search, Settings, Undo2 } from "lucide-react";
import { Link, Outlet, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { fileUrl } from "../api/upload";
import { studioName } from "../auth/pages";
import { useMe } from "../auth/useMe";
import { said, useIdeas, type Idea, type Status } from "../folders/ideas";
import { useWorkspace } from "../settings/StudioName";
import { lastBrand, rememberBrand, useBrands } from "../shell/useBrands";
import { ToastProvider } from "../toast";
import { Jump, type Hit } from "./Jump";
import { setNewLook } from "./look";
import { PAGES } from "./pages";
import { Choice, Popover } from "./Popover";
import { RailFolders } from "./RailFolders";
import "./studio.css";

const ICON = { size: 16, strokeWidth: 1.75, "aria-hidden": true } as const;
/** The brand's videos, newest first: the rail's "Being made" and Search or jump read the same list. */
const EVERY = { folder: "all", tab: "all", q: "", sort: "newest", madeBy: null, archived: false } as const;
/** A video still on its way: being made, or stopped on something only a person can answer. */
export const MAKING: Status["kind"][] = ["working", "waiting", "needs_you", "needs_fix"];
/** The dot beside a status: amber while it waits on a person, red on a fault, green once delivered, grey when it is over. */
export const DOT: Partial<Record<Status["kind"], string>> = { waiting: "wait", needs_you: "wait", needs_fix: "bad", delivered: "ok", stopped: "idle", archived: "idle" };

/** The new look's frame (the redesign, stage 0): a rail on the canvas (the studio, the brand, the four pages, what is
 *  being made, the folders, search, you) and the page as one panel beside it. On a phone the rail is a row of tabs at
 *  the bottom. It reads the same server as the current site, through the same hooks. */
export function StudioShell() {
  const { data: brands, isPending, isError } = useBrands();
  const me = useMe().data;
  const fromUrl = Number(useParams().brandId) || null;
  const id = fromUrl ?? (brands?.some((b) => b.id === lastBrand()) ? lastBrand() : (brands?.[0]?.id ?? null));
  const brand = brands?.find((b) => b.id === id);
  const base = `/s/b/${id}`;
  const { pathname } = useLocation();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const page = /^\/s\/b\/\d+\/([a-z]+)/.exec(pathname)?.[1] ?? (fromUrl ? "" : null); // null: a page of no brand (Settings)
  const folder = page === "videos" ? params.get("folder") : null;
  const at = (to: string) => (to ? `${base}/${to}` : base);
  const video = (i: Idea) => `${base}/videos/${i.id}`;

  const workspace = useWorkspace().data;
  const list = useIdeas(id ?? 0, EVERY, !!id);
  const ideas = list.data?.pages[0]?.ideas ?? [];
  const making = ideas.filter((i) => MAKING.includes(i.status.kind));

  useEffect(() => {
    if (fromUrl) rememberBrand(fromUrl);
  }, [fromUrl]);

  const [jumping, setJumping] = useState(false);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() !== "k" || !(e.metaKey || e.ctrlKey)) return;
      e.preventDefault();
      setJumping((was) => !was);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const colour = (b?: { colours?: string[] }) => <span aria-hidden className="sq" style={{ background: b?.colours?.[0] || "var(--accent)" }} />;
  const leave = { to: id ? `/b/${id}` : "/", onClick: () => setNewLook(false) };
  const hits = (): Hit[] => [
    ...making.map((i) => ({ group: "Being made", label: i.title, to: video(i), lead: <Clapperboard {...ICON} />, note: said(i.status) })),
    ...PAGES.map((p) => ({ group: "Go to", label: p.title, to: at(p.page), lead: <p.icon {...ICON} /> })),
    { group: "Go to", label: "Settings", to: "/s/settings", lead: <Settings {...ICON} /> },
    { group: "Go to", label: "Back to the current site", to: leave.to, lead: <Undo2 {...ICON} />, onPick: leave.onClick },
    ...(brands ?? []).filter((b) => b.id !== id).map((b) => ({ group: "Switch brand", label: b.name, to: `/s/b/${b.id}`, lead: colour(b) })),
    ...ideas.filter((i) => !making.includes(i)).map((i) => ({ group: "Videos", label: i.title, to: video(i), lead: <Film {...ICON} />, note: said(i.status) })),
  ];

  return (
    <div className="studio app">
      <ToastProvider>
        <a className="skip" href="#panel">
          Skip to the page
        </a>
        <nav className="rail" aria-label="Main">
          <div className="mark">
            <i aria-hidden />
            <span className="clip">{workspace ? studioName(workspace.name, me?.role === "owner" ? me.name : undefined) : "Brand Studio"}</span>
          </div>
          <Popover
            label="Brands"
            button={(p) => (
              <button type="button" className="brand" aria-label={brand ? `Brand: ${brand.name}` : "Choose a brand"} {...p}>
                {colour(brand)}
                <b className="clip">{brand ? brand.name : "Choose a brand"}</b>
                <ChevronDown size={14} strokeWidth={1.75} aria-hidden />
              </button>
            )}
          >
            {(close) => (
              <>
                {(brands ?? []).map((b) => (
                  <Choice
                    key={b.id}
                    checked={b.id === id}
                    lead={colour(b)}
                    onPick={() => {
                      close();
                      navigate(page ? `/s/b/${b.id}/${page}` : `/s/b/${b.id}`);
                    }}
                  >
                    {b.name}
                  </Choice>
                ))}
                {me?.role === "owner" && (
                  <Link className="pa" to="/s/brands/new" onClick={close}>
                    <Plus {...ICON} />
                    New brand
                  </Link>
                )}
              </>
            )}
          </Popover>
          {id && (
            <>
              <div className="nav">
                {PAGES.map((p) => (
                  <Link key={p.page} to={at(p.page)} aria-current={p.page === page && !folder ? "page" : undefined}>
                    <p.icon {...ICON} />
                    {p.label}
                  </Link>
                ))}
              </div>
              <h6 id="studio-making">Being made</h6>
              <div className="live" role="group" aria-labelledby="studio-making">
                {making.map((i) => (
                  <Link key={i.id} to={video(i)}>
                    {i.still_file_id ? <img src={fileUrl(i.still_file_id)} alt="" /> : <span aria-hidden className="still" />}
                    <span>
                      <b className="clip">{i.title}</b>
                      <span className="st">
                        <i aria-hidden className={`dot ${DOT[i.status.kind] ?? ""}`} />
                        <span className="clip">{said(i.status)}</span>
                      </span>
                    </span>
                  </Link>
                ))}
                {list.isSuccess && making.length === 0 && <p className="none">Nothing right now.</p>}
              </div>
              <RailFolders brandId={id} base={base} folder={folder} />
            </>
          )}
          <span className="grow" />
          <div className="nav">
            <Link className="back" {...leave}>
              <Undo2 {...ICON} />
              Back to the current site
            </Link>
          </div>
          <button type="button" className="find" onClick={() => setJumping(true)}>
            <Search {...ICON} />
            Search or jump
            <kbd aria-hidden>⌘K</kbd>
          </button>
          <div className="me">
            <i aria-hidden>{me?.name.slice(0, 1).toUpperCase()}</i>
            <span className="clip">{me?.name}</span>
            <span className="grow" />
            <Link className="btn ghost square" to="/s/settings" aria-label="Settings" title="Settings">
              <Settings {...ICON} />
            </Link>
          </div>
        </nav>
        <main className="panel" id="panel" tabIndex={-1}>
          {isPending ? (
            <p className="none" role="status">
              Loading…
            </p>
          ) : isError || !brands ? (
            <p className="none" role="alert">
              Could not load brands.
            </p>
          ) : (
            <Outlet />
          )}
        </main>
        {id && (
          <nav className="tabs" aria-label="Tabs">
            {PAGES.map((p) => (
              <Link key={p.page} to={at(p.page)} aria-current={p.page === page ? "page" : undefined}>
                <p.icon size={18} strokeWidth={1.75} aria-hidden />
                {p.label}
              </Link>
            ))}
            <button type="button" onClick={() => setJumping(true)}>
              <Search size={18} strokeWidth={1.75} aria-hidden />
              Search
            </button>
          </nav>
        )}
        {jumping && <Jump hits={hits()} onClose={() => setJumping(false)} />}
      </ToastProvider>
    </div>
  );
}
