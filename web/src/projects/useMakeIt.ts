import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import { refreshJobs } from "../jobs/refresh";
import { useToast } from "../toast";

/** Make it on a run's start card (S3-02): after its treatment, nothing is spent until this press. The cards themselves
 *  (S4) come with screen 5; until then the video page and its chat carry this one press. */
export function useMakeIt(projectId: number, freestyleId?: number) {
  const queryClient = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: async (askId: number) => {
      const { data, error } = await api.POST("/asks/{ask_id}/answer", { params: { path: { ask_id: askId } }, body: { how: "make_it" } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["director", projectId] });
      if (freestyleId) void queryClient.invalidateQueries({ queryKey: ["freestyle", freestyleId] });
      return refreshJobs(queryClient);
    },
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
}
