import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useMe } from "../auth/useMe";
import { weekStop } from "../scripts/useScript";

/** On an editor's own script a paid step runs on their weekly allowance and is declined past it, never sent to Reed. Returns why a price is declined, or null. */
export function useOwnScriptStop(ownScript: boolean | undefined) {
  const { data: me } = useMe();
  const on = !!ownScript && me?.role !== undefined && me.role !== "owner";
  const allowance = useQuery({ enabled: on, queryKey: ["allowance"], queryFn: async () => (await api.GET("/credits/me")).data ?? null });
  return (cost: number | undefined): string | null => (on && cost !== undefined && allowance.data ? weekStop(allowance.data, cost) : null);
}
