import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Navigate, useParams, useSearchParams } from "react-router-dom";
import { useMe } from "../auth/useMe";
import { Button, Dialog, Tabs } from "../components";
import { ArchiveBrand } from "./ArchiveBrand";
import { ActionBar } from "../shell/ActionBar";
import { useBrands } from "../shell/useBrands";
import { useRail } from "../useMedia";
import { KitPage } from "./KitPage";
import { setupOf } from "./BrandSetup";
import { ProductsTab } from "./ProductsTab";
import { ScreensTab } from "./ScreensTab";
import { groupProducts, useScreens } from "./screens";

const IDS = ["look", "voice", "products", "screens"] as const;

type Frame = { slot: HTMLElement | null; setDirty: (dirty: boolean) => void; importing: boolean; setImporting: (on: boolean) => void; goTab: (id: string) => void };
const FrameContext = createContext<Frame>({ slot: null, setDirty: () => {}, importing: false, setImporting: () => {}, goTab: () => {} });
/** Import from website, opened from the page's top bar (v5 F_BrandImport), and a tab change from inside the Look tab. */
export const useBrandFrame = () => useContext(FrameContext);

/** Brand: look and voice, products, and app screens on one page. */
export function BrandPage() {
  const [params, setParams] = useSearchParams();
  const { brandId } = useParams();
  const { data: brands } = useBrands();
  const brand = brands?.find((b) => b.id === Number(brandId));
  const rail = useRail();
  const owner = useMe().data?.role === "owner";
  const asked = params.get("tab");
  const tab = IDS.find((t) => t === asked) ?? "look";
  const screens = useScreens(Number(brandId));
  const products = groupProducts(screens.data ?? []).length;
  const tabs = [
    { id: "look", label: "Look" },
    { id: "voice", label: "Voice & lines" },
    { id: "products", label: "Products", count: screens.data ? products : undefined },
    { id: "screens", label: "App screens", count: screens.data?.length },
  ];
  const [slot, setSlot] = useState<HTMLElement | null>(null);
  const [dirty, setDirty] = useState(false);
  const [leaving, setLeaving] = useState<string | null>(null);
  // Import from website lives in the address (?import=1), so New brand can open on it and a reload keeps it open.
  const importing = params.get("import") === "1";
  const setImporting = (on: boolean) => setParams(on ? { import: "1" } : {}, { replace: true });
  const go = (id: string) => setParams(id === "look" ? {} : { tab: id }, { replace: true });

  return (
    <FrameContext.Provider value={{ slot, setDirty, importing, setImporting, goTab: go }}>
      <main className="mx-auto max-w-content space-y-4 p-4 sm:p-6">
        {/* v5 F boards: the brand's dot and name, Import from website (the owner) and More; then the tabs with the note on the right. */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
          <h1 className="flex min-w-0 items-center gap-3 type-page">
            <span aria-hidden className="size-5 shrink-0 rounded-sm" style={{ background: brand?.colours?.[0] || "var(--accent)" }} />
            <span className="min-w-0 break-words">{brand?.name ?? "Brand"}</span>
          </h1>
          <div className="flex flex-wrap items-center gap-2">
            {owner && brand && (tab === "look" || tab === "voice") && (
              <Button variant="secondary" onClick={() => setImporting(true)}>
                Import from website
              </Button>
            )}
            {/* Products and App screens put their Add here, as F_BrandProducts does (QA-3 on #1210); Look and Voice save in the bottom bar. */}
            {rail && tab !== "look" && tab !== "voice" && <div ref={setSlot} className="flex items-center gap-2" />}
            {owner && brand && <ArchiveBrand brand={brand} others={(brands ?? []).filter((b) => b.id !== brand.id)} />}
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          <Tabs
            label="Brand"
            tabs={tabs}
            value={tab}
            onChange={(id) => {
              const kit = (t: string) => t === "look" || t === "voice";
              if (kit(tab) && dirty && !kit(id)) setLeaving(id);
              else go(id);
            }}
          />
          {brand && setupOf(brand) && <p className="text-sm text-muted">Changes apply to work from now on. Nothing already made changes.</p>}
        </div>
        {/* Look and Voice & lines are one form: switching between them keeps what's typed. */}
        {tab === "look" || tab === "voice" ? <KitPage part={tab} /> : tab === "products" ? <ProductsTab /> : <ScreensTab />}
        {rail && (tab === "look" || tab === "voice") && <div ref={setSlot} className="sticky bottom-0 z-10 -mx-4 flex items-center justify-end gap-3 border-t border-border bg-bg px-4 py-3 sm:-mx-6 sm:px-6" />}
      </main>
      {leaving && (
        <Dialog
          title="Leave without saving?"
          cancelLabel="Keep editing"
          actionLabel="Leave"
          danger
          onCancel={() => setLeaving(null)}
          onConfirm={() => {
            go(leaving);
            setDirty(false);
            setLeaving(null);
          }}
        >
          Your changes to the Look and Voice & lines aren't saved. Leaving drops them.
        </Dialog>
      )}
    </FrameContext.Provider>
  );
}

/** The page's one amber button: top right on desktop, in the action bar on a phone. */
export function BrandAction({ children }: { children: ReactNode }) {
  const { slot } = useContext(FrameContext);
  const rail = useRail();
  if (!rail) return <ActionBar phone>{children}</ActionBar>;
  return slot ? createPortal(children, slot) : null;
}

/** Tells the frame whether the tab has unsaved changes, so leaving it can ask first. */
export function useReportDirty(dirty: boolean) {
  const { setDirty } = useContext(FrameContext);
  useEffect(() => {
    setDirty(dirty);
    return () => setDirty(false);
  }, [dirty, setDirty]);
  // Reloading or closing the tab asks too.
  useEffect(() => {
    if (!dirty) return;
    const ask = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", ask);
    return () => window.removeEventListener("beforeunload", ask);
  }, [dirty]);
}

/** The old /kit and /screens addresses land on the Brand page. */
export function ToBrand({ tab }: { tab?: "screens" }) {
  const { brandId } = useParams();
  return <Navigate to={`/b/${brandId}/brand${tab ? `?tab=${tab}` : ""}`} replace />;
}
