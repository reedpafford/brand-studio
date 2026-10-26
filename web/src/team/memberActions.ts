import { useQuery } from "@tanstack/react-query";
import createClient from "openapi-fetch";
import { errorText } from "../api/client";

export type Member = { id: number; email: string; name: string; role: "owner" | "editor" };

// The role change, restore and removed list, until the server's schema has them (then these go and `api` is used).
type Paths = {
  "/team/members": { get: { parameters: { query?: { removed?: boolean } }; responses: { 200: { content: { "application/json": Member[] } } } } };
  "/team/members/{member_id}": { patch: { parameters: { path: { member_id: number } }; requestBody: { content: { "application/json": { role: "owner" | "editor" } } }; responses: { 200: { content: never } } } };
  "/team/members/{member_id}/restore": { post: { parameters: { path: { member_id: number } }; responses: { 200: { content: never } } } };
};
const team = createClient<Paths>({ baseUrl: `${location.origin}/api`, credentials: "include", fetch: (req) => fetch(req) });

export async function setRole(id: number, role: "owner" | "editor") {
  const { error, response } = await team.PATCH("/team/members/{member_id}", { params: { path: { member_id: id } }, body: { role } });
  if (!response.ok) throw new Error(errorText(error));
}

export async function restoreMember(id: number) {
  const { error, response } = await team.POST("/team/members/{member_id}/restore", { params: { path: { member_id: id } } });
  if (!response.ok) throw new Error(errorText(error));
}

/** People Reed removed, so they can be found after the toast is gone. Owner only. */
export function useRemovedMembers(enabled: boolean) {
  return useQuery({
    enabled,
    queryKey: ["team", "removed"],
    queryFn: async () => (await team.GET("/team/members", { params: { query: { removed: true } } })).data ?? [],
  });
}
