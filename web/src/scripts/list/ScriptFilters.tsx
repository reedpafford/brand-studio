import { useQueries } from "@tanstack/react-query";
import { api } from "../../api/client";
import { Tabs } from "../../components";

/** The stage tabs are the Status filter: the server's status for each, and the words. */
const STAGES = [
  ["", "All"],
  ["draft", "Writing"],
  ["published", "Ready to make"],
  ["in_production", "In production"],
  ["done", "Finished"],
] as const;

/** The list's query without status or paging: what the stage counts are asked with. */
export type Ask = Record<string, string | number | boolean | undefined>;

/** All · Writing · Ready to make · In production · Finished, each with how many scripts the server has for it (v5
 *  C_Scripts). An editor's tabs leave out All, as E_EditorScripts does: they start on Ready to make. */
export function StageTabs({ status, owner, ask, onPick }: { status: string; owner: boolean; ask: Ask; onPick: (status: string) => void }) {
  const counts = useQueries({
    queries: STAGES.map(([s]) => ({
      queryKey: ["scripts", "count", ask, s],
      queryFn: async () => {
        const { response } = await api.GET("/scripts", { params: { query: { ...ask, ...(s ? { status: s } : {}), limit: 1 } } });
        const n = Number(response.headers.get("X-Total-Count"));
        return response.headers.has("X-Total-Count") && Number.isFinite(n) ? n : null; // no count, no number
      },
    })),
  });
  const all = owner ? "" : "any";
  return (
    <Tabs
      label="Stage"
      value={status === all || status === "any" ? "all" : status}
      onChange={(id) => onPick(id === "all" ? all : id)}
      tabs={STAGES.map(([s, label], i) => ({ id: s || "all", label, count: counts[i].data ?? undefined })).filter((t) => owner || t.id !== "all")}
    />
  );
}
