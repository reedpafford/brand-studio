import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { useMe } from "../auth/useMe";

export type Job = components["schemas"]["JobOut"];

/** Every press held for the owner's OK (Usage's "Waiting for your OK"). Only the owner asks. */
export function useHeld() {
  const { data: me } = useMe();
  const owner = me?.role === "owner";
  const jobs = useQuery({
    enabled: owner,
    queryKey: ["held-jobs"],
    refetchInterval: 30_000,
    queryFn: async () => (await api.GET("/jobs", { params: { query: { status: "needs_owner_approval" } } })).data ?? [],
  });
  const heldJobs = jobs.data ?? [];
  return { owner, heldJobs, count: heldJobs.length };
}
