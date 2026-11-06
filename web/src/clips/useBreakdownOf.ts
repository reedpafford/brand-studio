import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

/** The video's newest shots and clips (its scenes and what each clip shows), or null before there are any. */
export function useBreakdownOf(projectId: number) {
  return useQuery({
    queryKey: ["breakdown", projectId, "clips"],
    queryFn: async () => {
      const { data, response } = await api.GET("/projects/{project_id}/breakdown", { params: { path: { project_id: projectId } } });
      if (response.status === 404 || response.status === 409) return null;
      if (!data) throw new Error("load");
      return data;
    },
  });
}
