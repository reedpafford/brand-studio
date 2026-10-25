import { useState } from "react";
import { keepPreviousData, useInfiniteQuery, useQuery } from "@tanstack/react-query";
import createClient from "openapi-fetch";
import { useMe } from "../auth/useMe";

export type Step = "breakdown" | "assets" | "storyboard" | "clips" | "downloads";
export type Flag = "failed" | "stuck" | "idle";
export type Row = {
  project_id: number;
  brand: { id: number; name: string };
  script: { id: number; title: string };
  letter: string;
  editor: { id: number; name: string };
  step: Step;
  last_activity_at: string;
  credits_used: number;
  budget_credits: number;
  spent_usd: number;
  poster_file_id: number | null;
  flag: Flag | null;
  flag_since: string | null;
  flag_job: string | null;
  flag_problem: string | null;
};
export type Sort = "attention" | "activity" | "credits" | "budget";
export type Filters = { brand: string; editor: string; attention: boolean; q: string; sort: Sort };

// The spec's shapes, until the server's schema has them (then these go and `api` is used).
type Paths = {
  "/production": { get: { parameters: { query?: { brand_id?: number; editor_id?: number; attention?: boolean; q?: string; sort?: Sort; limit?: number; offset?: number } }; responses: { 200: { content: { "application/json": Row[] } } } } };
  "/production/summary": { get: { responses: { 200: { content: { "application/json": { in_production: number; needs_attention: number } } } } } };
};
const production = createClient<Paths>({ baseUrl: `${location.origin}/api`, credentials: "include", fetch: (req) => fetch(req) });

const PAGE = 25;
const REFRESH = 30_000;

/** The header count and the rail badge. A 404 means the person isn't the owner. */
export function useProductionSummary(enabled = true) {
  return useQuery({
    enabled,
    queryKey: ["production", "summary"],
    refetchInterval: REFRESH,
    queryFn: async () => {
      const { data, response } = await production.GET("/production/summary");
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
      const { data, response } = await production.GET("/production", {
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
