import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Navigate, useParams, useSearchParams } from "react-router-dom";
import { useMe } from "../auth/useMe";
import { Dialog, Tabs } from "../components";
import { ArchiveBrand } from "./ArchiveBrand";
import { ActionBar } from "../shell/ActionBar";
import { useBrands } from "../shell/useBrands";
import { useRail } from "../useMedia";
import { KitPage } from "./KitPage";
import { setupOf } from "./BrandSetup";
import { ProductsTab } from "./ProductsTab";
import { ScreensTab } from "./ScreensTab";
import { groupProducts, useScreens } from "./screens";

const IDS = ["look", "products", "screens"] as const;

type Frame = { slot: HTMLElement | null; setDirty: (dirty: boolean) => void };
const FrameContext = createContext<Frame>({ slot: null, setDirty: () => {} });

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
    { id: "products", label: "Products", count: screens.data ? products : undefined },
    { id: "screens", label: "App screens", count: screens.data?.length },
  ];
  const [slot, setSlot] = useState<HTMLElement | null>(null);
  const [dirty, setDirty] = useState(false);
  const [leaving, setLeaving] = useState<string | null>(null);
  const go = (id: string) => setParams(id === "look" ? {} : { tab: id }, { replace: true });

  return (
    <FrameContext.Provider value={{ slot, setDirty }}>
      <div className="mx-auto max-w-content space-y-4 p-4 sm:p-6">
        <div className="flex items-end justify-between gap-3">
          <div className="flex items-end gap-2">
            <div>
              <p className="type-eyebrow text-muted">{brand?.name}</p>
              <h1 className="type-page">Brand</h1>
              {brand && setupOf(brand) && <p className="text-sm text-muted">Changes apply to work from now on. Nothing already made changes.</p>}
            </div>
            {owner && brand && <ArchiveBrand brand={brand} others={(brands ?? []).filter((b) => b.id !== brand.id)} />}
          </div>
          {rail && <div ref={setSlot} className="flex flex-col items-end" />}
        </div>
        <Tabs
          label="Brand"
          tabs={tabs}
          value={tab}
          onChange={(id) => {
            if (tab === "look" && dirty && id !== "look") setLeaving(id);
            else go(id);
          }}
        />
        {tab === "look" ? <KitPage /> : tab === "products" ? <ProductsTab /> : <ScreensTab />}
      </div>
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
          Your changes to the look and voice haven't been saved.
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
