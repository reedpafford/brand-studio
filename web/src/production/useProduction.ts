import { useState } from "react";
import { keepPreviousData, useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components, operations } from "../api/schema";
import { useMe } from "../auth/useMe";

export type Row = components["schemas"]["ProductionRow"];
export type Step = Row["step"];
export type Sort = NonNullable<NonNullable<operations["in_production_production_get"]["parameters"]["query"]>["sort"]>;
export type Filters = { brand: string; editor: string; attention: boolean; q: string; sort: Sort };

const PAGE = 25;
const REFRESH = 30_000;

/** The header count and the rail badge. A 404 means the person isn't the owner. */
export function useProductionSummary(enabled = true) {
  return useQuery({
    enabled,
    queryKey: ["production", "summary"],
    refetchInterval: REFRESH,
    queryFn: async () => {
      const { data, response } = await api.GET("/production/summary");
      if (!data) throw new Error(response.status === 404 ? "404" : "load");
      return data;
    },
    retry: false,
  });
}

/** Rows in the order they first came in: a refresh updates them in place and never reorders. */
function useSteadyOrder(rows: Row[], key: string, settled: boolean) {
  const [order, setOrder] = useState<{ key: string; ids: number[] }>({ key, ids: [] });
  const ids = order.key === key ? order.ids : [];
  if (settled) {
    const known = new Set(ids);
    const next = [...ids.filter((id) => rows.some((r) => r.project_id === id)), ...rows.filter((r) => !known.has(r.project_id)).map((r) => r.project_id)];
    if (order.key !== key || next.join() !== ids.join()) setOrder({ key, ids: next });
  }
  if (ids.length === 0) return rows;
  const place = new Map(ids.map((id, i) => [id, i]));
  return [...rows].sort((a, b) => (place.get(a.project_id) ?? 1e9) - (place.get(b.project_id) ?? 1e9));
}

/** Every version being made, 25 at a time, refreshed every 30 s and when the tab returns. */
export function useProduction(f: Filters) {
  const owner = useMe().data?.role === "owner";
  const query = useInfiniteQuery({
    enabled: owner,
    queryKey: ["production", "rows", f],
    initialPageParam: 0,
    refetchInterval: REFRESH,
    queryFn: async ({ pageParam }) => {
      const { data, response } = await api.GET("/production", {
        params: { query: { ...(f.brand ? { brand_id: Number(f.brand) } : {}), ...(f.editor ? { editor_id: Number(f.editor) } : {}), ...(f.attention ? { attention: true } : {}), ...(f.q ? { q: f.q } : {}), sort: f.sort, limit: PAGE, offset: pageParam } },
      });
      if (!data) throw new Error(response.status === 404 ? "404" : "load");
      const total = Number(response.headers.get("X-Total-Count"));
      return { items: data, total: Number.isFinite(total) && total > 0 ? total : data.length, offset: pageParam };
    },
    getNextPageParam: (last) => (last.items.length > 0 && last.offset + last.items.length < last.total ? last.offset + last.items.length : undefined),
    placeholderData: keepPreviousData,
    retry: false,
  });
  const loaded = query.data?.pages.flatMap((p) => p.items) ?? [];
  const rows = useSteadyOrder(loaded, JSON.stringify(f), query.isSuccess && !query.isPlaceholderData && !query.isFetching);
  return { query, rows, total: query.data?.pages[0]?.total };
}
