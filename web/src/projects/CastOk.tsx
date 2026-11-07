import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { api, errorText, polled } from "../api/client";
import { fileUrl } from "../api/upload";
import { Button } from "../components";
import { refreshJobs } from "../jobs/refresh";

const FROM = { library: "From the brand's library", uploaded: "Uploaded for this video", video: "Made for this video", script: "Made for this script" } as const;

/** The director's "Cast & places waiting for your OK" in the chat (S-gaps-07 B): the whole set with its previews, and the
 *  one press. The Cast tab (screen 9) shows the same set with its own press; both call the same route. */
export function CastOk({ projectId }: { projectId: number }) {
  const queryClient = useQueryClient();
  const cast = useQuery({
    queryKey: ["cast", projectId],
    queryFn: () => polled(api.GET("/projects/{project_id}/cast", { params: { path: { project_id: projectId } } }), null),
    refetchInterval: 4000,
  });
  const approve = useMutation({
    mutationFn: async (seen: Record<string, string>) => {
      const { data, error } = await api.POST("/projects/{project_id}/cast/approve", { params: { path: { project_id: projectId } }, body: { seen } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["cast", projectId], data);
      void queryClient.invalidateQueries({ queryKey: ["director", projectId] });
      return refreshJobs(queryClient);
    },
  });
  const shown = cast.data;
  // Whenever the set is ready and this person may approve it, not only once the director asked: a video with no run, or a
  // look changed after it asked, is never left without the press.
  if (!shown || shown.state !== "ready" || !shown.can_approve) return null;
  const changed = shown.items.filter((i) => i.approval === "changed").map((i) => i.name);
  return (
    <section aria-label="Cast & places waiting for your OK" className="space-y-3 rounded-lg border border-border bg-surface p-4">
      <p className="text-sm">
        {changed.length ? `${changed.join(", ")} changed. ` : ""}
        {shown.asked ? "The director is waiting for this. " : ""}Check the cast and places together. Stills and clips that use them wait until you approve.
      </p>
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {shown.items.map((i) => (
          <li key={i.ref} className="space-y-1">
            {i.preview_file_id ? <img src={fileUrl(i.preview_file_id)} alt={i.name} className="aspect-square w-full rounded-md object-cover" /> : <div aria-hidden className="aspect-square w-full rounded-md bg-surface-3" />}
            <p className="text-sm">{i.name}</p>
            <p className="text-xs text-muted">{i.source ? FROM[i.source] : "No look yet"}</p>
          </li>
        ))}
      </ul>
      <Button icon={Check} busy={approve.isPending} onClick={() => approve.mutate(Object.fromEntries(shown.items.map((i) => [i.ref, i.sig])))}>
        Approve cast &amp; places
      </Button>
      {approve.isError && <p role="alert" className="text-sm text-danger">{approve.error.message}</p>}
    </section>
  );
}
