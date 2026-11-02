import { useQueries, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { useMe } from "../auth/useMe";
import { useProductionSummary } from "../production/useProduction";
import { useBrands } from "../shell/useBrands";

export type Job = components["schemas"]["JobOut"];
export type Project = components["schemas"]["ProjectOut"];

/** Everything waiting for the owner: projects and jobs held over a limit. Only the owner asks. */
export function useHeld() {
  const { data: me } = useMe();
  const owner = me?.role === "owner";
  const { data: brands } = useBrands();
  const jobs = useQuery({
    enabled: owner,
    queryKey: ["held-jobs"],
    refetchInterval: 30_000,
    queryFn: async () => (await api.GET("/jobs", { params: { query: { status: "needs_owner_approval" } } })).data ?? [],
  });
  const projectLists = useQueries({
    queries: (owner ? (brands ?? []) : []).map((b) => ({
      queryKey: ["projects", b.id],
      refetchInterval: 30_000,
      queryFn: async () => {
        const { data } = await api.GET("/projects", { params: { query: { brand_id: b.id } } });
        if (!data) throw new Error("load");
        return data;
      },
    })),
  });
  const projects = projectLists.flatMap((q) => q.data ?? []);
  const heldProjects = projects.filter((p) => p.status === "needs_owner_approval");
  // Work inside a held project is decided with the project; approving it releases what fits.
  const heldIds = new Set(heldProjects.map((p) => p.id));
  const heldJobs = (jobs.data ?? []).filter((j) => j.project_id === null || !heldIds.has(j.project_id));
  return {
    owner,
    projects,
    heldProjects,
    heldJobs,
    allHeldJobs: jobs.data ?? [],
    count: heldProjects.length + heldJobs.length,
    isPending: owner && (jobs.isPending || projectLists.some((q) => q.isPending)),
    isError: jobs.isError || projectLists.some((q) => q.isError),
  };
}

/** Videos that need attention (stuck, didn't finish, or quiet), from In production; one read across brands. */
export function useStuck(owner: boolean) {
  return useQuery({
    enabled: owner,
    queryKey: ["production", "attention"],
    refetchInterval: 30_000,
    retry: false,
    queryFn: async () => {
      const { data } = await api.GET("/production", { params: { query: { attention: true, sort: "attention", limit: 100 } } });
      if (!data) throw new Error("load");
      return data;
    },
  });
}

/** Finished videos whose clips changed since. The summary counts them; the brands' video lists are read only when some wait. */
export function useChangesWaiting(owner: boolean) {
  const summary = useProductionSummary(owner);
  const some = (summary.data?.changes_waiting ?? 0) > 0;
  const { data: brands } = useBrands();
  const lists = useQueries({
    queries: (owner && some ? (brands ?? []) : []).map((b) => ({
      queryKey: ["usage", "changes-waiting", b.id],
      retry: false,
      queryFn: async () => {
        const { data } = await api.GET("/usage/brands/{brand_id}/videos", { params: { path: { brand_id: b.id }, query: { period: "all", status: "done", limit: 100 } } });
        if (!data) throw new Error("load");
        return data.items.filter((v) => v.final_out_of_date).map((v) => ({ ...v, brand_id: b.id }));
      },
    })),
  });
  return {
    rows: lists.flatMap((q) => q.data ?? []),
    isPending: owner && (summary.isPending || lists.some((q) => q.isPending)),
    isError: lists.some((q) => q.isError),
    refetch: () => Promise.all(lists.map((q) => q.refetch())),
  };
}
