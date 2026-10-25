import { Navigate, useParams, useSearchParams } from "react-router-dom";
import { Tabs } from "../components";
import { KitPage } from "./KitPage";
import { ScreensPage } from "./ScreensPage";

const TABS = [
  { id: "look", label: "Look" },
  { id: "screens", label: "App screens" },
];

/** Brand: the kit and the app screens on one page (Products joins them in the Brand redesign step). */
export function BrandPage() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "screens" ? "screens" : "look";
  return (
    <div>
      <div className="mx-auto max-w-4xl px-4 pt-4 sm:px-6 sm:pt-6">
        <Tabs label="Brand" tabs={TABS} value={tab} onChange={(id) => setParams(id === "look" ? {} : { tab: id }, { replace: true })} />
      </div>
      {tab === "look" ? <KitPage /> : <ScreensPage />}
    </div>
  );
}

/** The old /kit and /screens addresses land on the Brand page. */
export function ToBrand({ tab }: { tab?: "screens" }) {
  const { brandId } = useParams();
  return <Navigate to={`/b/${brandId}/brand${tab ? `?tab=${tab}` : ""}`} replace />;
}
