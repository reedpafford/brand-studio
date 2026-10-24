import { useQueries, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { useMe } from "../auth/useMe";
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
