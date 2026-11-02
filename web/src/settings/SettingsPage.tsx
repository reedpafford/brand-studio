import { useSearchParams } from "react-router-dom";
import { useMe } from "../auth/useMe";
import { Tabs } from "../components";
import { LanguagesTab } from "../languages/LanguagesTab";
import { LooksTab } from "../looks/LooksTab";
import { CreditLimits } from "./CreditLimits";
import { StudioName } from "./StudioName";

const TABS = [
  { id: "looks", label: "Styles" },
  { id: "languages", label: "Languages" },
  { id: "name", label: "Studio name" },
  { id: "limits", label: "Credit limits" },
];

/** The owner's settings for the whole studio, one tab each; the tab lives in the address (/looks and /languages land here). */
export function SettingsPage() {
  const { data: me } = useMe();
  const [params, setParams] = useSearchParams();
  const tab = TABS.find((t) => t.id === params.get("tab"))?.id ?? "looks";
  if (!me) return null;
  if (me.role !== "owner") return <p className="p-6">Only the owner manages settings.</p>;
  return (
    <main className="mx-auto max-w-content space-y-4 p-4 sm:p-6">
      <div>
        <h1 className="type-page">Settings</h1>
        <p className="text-sm text-muted">For the whole studio. Editors pick from what's switched on here.</p>
      </div>
      <Tabs label="Settings" value={tab} onChange={(id) => setParams({ tab: id }, { replace: true })} tabs={TABS} />
      {tab === "looks" ? <LooksTab /> : tab === "languages" ? <LanguagesTab /> : <div className="max-w-[720px]">{tab === "name" ? <StudioName owner={me.name} /> : <CreditLimits />}</div>}
    </main>
  );
}
