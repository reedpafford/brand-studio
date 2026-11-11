import { useSearchParams } from "react-router-dom";
import { useMe } from "../auth/useMe";
import { PageTop, Tabs } from "../components";
import { LanguagesTab } from "../languages/LanguagesTab";
import { LooksTab } from "../looks/LooksTab";
import { CreditLimits } from "./CreditLimits";
import type { SettingsTop } from "./SettingRow";
import { StudioName } from "./StudioName";

// v5 D_Settings: Studio · Limits · Looks · Languages ("Styles", Reed's word everywhere, #1196).
const TABS = [
  { id: "studio", label: "Studio" },
  { id: "limits", label: "Limits" },
  { id: "looks", label: "Styles" },
  { id: "languages", label: "Languages" },
];
const OLD: Record<string, string> = { name: "studio" }; // links made before v5

/** The owner's settings for the whole studio, one tab each; the tab lives in the address (/looks and /languages land here). */
export function SettingsPage() {
  const { data: me } = useMe();
  const [params, setParams] = useSearchParams();
  const asked = params.get("tab") ?? "";
  const tab = TABS.find((t) => t.id === (OLD[asked] ?? asked))?.id ?? "studio";
  if (!me) return null;
  if (me.role !== "owner") return <p className="p-6">Only the owner manages settings.</p>;
  const top: SettingsTop = (save) => (
    <>
      <PageTop title="Settings">{save}</PageTop>
      {/* v5 D_Settings: the tabs in a 44 px band with a line under it across the page. */}
      <div className="-mx-4 -mt-4 flex min-h-11 items-center border-b border-border px-4 py-1.5 sm:-mx-6 sm:px-6">
        <Tabs label="Settings" value={tab} onChange={(id) => setParams({ tab: id }, { replace: true })} tabs={TABS} />
      </div>
    </>
  );
  return (
    <main className="mx-auto max-w-content space-y-4 p-4 sm:p-6">
      {tab === "studio" ? (
        <StudioName owner={me.name} top={top} />
      ) : tab === "limits" ? (
        <CreditLimits top={top} />
      ) : (
        <>
          {top()}
          {tab === "looks" ? <LooksTab /> : <LanguagesTab />}
        </>
      )}
    </main>
  );
}
