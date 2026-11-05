import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import type { components } from "../api/schema";
import { useToast } from "../toast";

type LocksIO = components["schemas"]["LocksIO"];

/** The choices the director builds around (director-chat.md §1): read, and a press locks or unlocks one; unlocking hands
 *  the choice back to it. The screens it must use are picked in the plan. */
export function useLocks(projectId: number) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const key = ["locks", projectId];
  const read = useQuery({
    queryKey: key,
    queryFn: async () => (await api.GET("/projects/{project_id}/locks", { params: { path: { project_id: projectId } } })).data ?? null,
  });
  const save = useMutation({
    mutationFn: async (body: LocksIO) => {
      const { data, error } = await api.PUT("/projects/{project_id}/locks", { params: { path: { project_id: projectId } }, body });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data) => queryClient.setQueryData(key, data),
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  return { locks: read.data ?? null, save };
}
