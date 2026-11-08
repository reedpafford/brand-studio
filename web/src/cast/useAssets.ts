import { useQuery } from "@tanstack/react-query";
import { api, polled } from "../api/client";
import type { components } from "../api/schema";

type Asset = components["schemas"]["AssetOut"];

/** The video's cast, places, products and screens, read again every 3 s while a look is drawn. */
export function useAssets(projectId: number) {
  return useQuery({
    queryKey: ["assets", projectId],
    enabled: projectId > 0,
    refetchInterval: (q) => (q.state.data?.some((a) => a.sheet_status === "drawing") ? 3000 : false),
    queryFn: () => polled(api.GET("/projects/{project_id}/assets", { params: { path: { project_id: projectId } } }), []),
  });
}

/** A cast role none of this video's shots uses: nothing to make for it here, and it stays out of every count. */
export const notInShots = (a: Asset) => a.slot_id != null && a.shots === 0;
