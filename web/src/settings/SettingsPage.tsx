import { useSearchParams } from "react-router-dom";
import { useMe } from "../auth/useMe";
import { PageTop, Tabs } from "../components";
import { LanguagesTab } from "../languages/LanguagesTab";
import { LooksTab } from "../looks/LooksTab";
import { CreditLimits } from "./CreditLimits";
import { StudioName } from "./StudioName";

// v5 D_Settings: Studio, Limits, Styles, Languages (the ids stay, so old links still land).
const TABS = [
  { id: "name", label: "Studio" },
  { id: "limits", label: "Limits" },
  { id: "looks", label: "Styles" },
  { id: "languages", label: "Languages" },
];

/** The owner's settings for the whole studio, one tab each; the tab lives in the address (/looks and /languages land here). */
export function SettingsPage() {
  const { data: me } = useMe();
  const [params, setParams] = useSearchParams();
  const tab = TABS.find((t) => t.id === params.get("tab"))?.id ?? "name";
  if (!me) return null;
  if (me.role !== "owner") return <p className="p-6">Only the owner manages settings.</p>;
  return (
    <main className="mx-auto max-w-content space-y-4 p-4 sm:p-6">
      <PageTop title="Settings" line="For the whole studio. Editors pick from what's switched on here." />
      <div className="-mx-4 -mt-4 border-b border-border px-4 py-2 sm:-mx-6 sm:px-6">
        <Tabs label="Settings" value={tab} onChange={(id) => setParams({ tab: id }, { replace: true })} tabs={TABS} />
      </div>
      {tab === "looks" ? <LooksTab /> : tab === "languages" ? <LanguagesTab /> : <div className="max-w-[900px]">{tab === "name" ? <StudioName owner={me.name} /> : <CreditLimits />}</div>}
    </main>
  );
}
