import { keepPreviousData, useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";

export type Period = "week" | "month" | "all";
export type BrandRow = components["schemas"]["UsageBrandRow"];
export type Sort = "spend" | "finished" | "cost" | "activity" | "name";

export const periodFrom = (p: string | null): Period => (p === "month" || p === "all" ? p : "week");

/** Reed's totals for the period. A 404 means the person isn't the owner. */
export function useSummary(period: Period) {
  return useQuery({
    queryKey: ["usage", "summary", period],
    queryFn: async () => {
      const { data, response } = await api.GET("/usage/summary", { params: { query: { period } } });
      if (!data) throw new Error(response.status === 404 ? "404" : "load");
      return data;
    },
    retry: false,
  });
}

/** The brands table, 25 at a time. */
export function useBrandRows(a: { period: Period; q: string; archived: boolean; sort: Sort }) {
  return useInfiniteQuery({
    queryKey: ["usage", "brands", a],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const { data } = await api.GET("/usage/brands", { params: { query: { period: a.period, q: a.q || undefined, archived: a.archived, sort: a.sort, cursor: pageParam, limit: 25 } } });
      if (!data) throw new Error("load");
      return data;
    },
    getNextPageParam: (last) => last.next_cursor,
    placeholderData: keepPreviousData, // the list stays while a search or sort loads
    retry: false,
  });
}

export function useBrandUsage(brandId: number, period: Period) {
  return useQuery({
    queryKey: ["usage", "brand", brandId, period],
    queryFn: async () => {
      const { data, response } = await api.GET("/usage/brands/{brand_id}", { params: { path: { brand_id: brandId }, query: { period } } });
      if (!data) throw new Error(response.status === 404 ? "404" : "load");
      return data;
    },
    retry: false,
  });
}

export type VideoFilters = { period: Period; status: "any" | "in_production" | "done" | "failed"; person: number | null; q: string; sort: "activity" | "spend" | "finished" | "title" };
export type ScriptFilters = { status: "any" | "writing" | "ready" | "in_production" | "done"; author: number | null; q: string; sort: "changed" | "spend" | "title" };

/** One brand's videos, 25 at a time. */
export function useBrandVideos(brandId: number, f: VideoFilters) {
  return useInfiniteQuery({
    queryKey: ["usage", "videos", brandId, f],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const { data } = await api.GET("/usage/brands/{brand_id}/videos", { params: { path: { brand_id: brandId }, query: { period: f.period, status: f.status, person_id: f.person, q: f.q || undefined, sort: f.sort, cursor: pageParam, limit: 25 } } });
      if (!data) throw new Error("load");
      return data;
    },
    getNextPageParam: (last) => last.next_cursor,
    placeholderData: keepPreviousData,
    retry: false,
  });
}

export function useBrandScripts(brandId: number, f: ScriptFilters) {
  return useInfiniteQuery({
    queryKey: ["usage", "scripts", brandId, f],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const { data } = await api.GET("/usage/brands/{brand_id}/scripts", { params: { path: { brand_id: brandId }, query: { status: f.status, author_id: f.author, q: f.q || undefined, sort: f.sort, cursor: pageParam, limit: 25 } } });
      if (!data) throw new Error("load");
      return data;
    },
    getNextPageParam: (last) => last.next_cursor,
    placeholderData: keepPreviousData,
    retry: false,
  });
}

/** Every charge, newest first, 50 at a time. Only asked for once the list is opened. */
export function useCharges(enabled: boolean, brandId: number | null) {
  return useInfiniteQuery({
    enabled,
    queryKey: ["usage", "charges", brandId],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const { data } = await api.GET("/usage/charges", { params: { query: { brand_id: brandId, cursor: pageParam, limit: 50 } } });
      if (!data) throw new Error("load");
      return data;
    },
    getNextPageParam: (last) => last.next_cursor,
    retry: false,
  });
}
