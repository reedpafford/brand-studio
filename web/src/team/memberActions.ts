import { useQuery } from "@tanstack/react-query";
import { api, errorText } from "../api/client";

export async function setRole(id: number, role: "owner" | "editor") {
  const { error, response } = await api.PATCH("/team/members/{member_id}", { params: { path: { member_id: id } }, body: { role } });
  if (!response.ok) throw new Error(errorText(error));
}

export async function restoreMember(id: number) {
  const { error, response } = await api.POST("/team/members/{member_id}/restore", { params: { path: { member_id: id } } });
  if (!response.ok) throw new Error(errorText(error));
}

/** People Reed removed, so they can be found after the toast is gone. Owner only. */
export function useRemovedMembers(enabled: boolean) {
  return useQuery({
    enabled,
    queryKey: ["team", "removed"],
    queryFn: async () => (await api.GET("/team/members", { params: { query: { removed: true } } })).data ?? [],
  });
}
