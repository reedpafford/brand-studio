import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { api, errorText, polled } from "../api/client";
import { fileUrl } from "../api/upload";
import { Button } from "../components";
import { refreshJobs } from "../jobs/refresh";
import { lookFitNote } from "../library/sheets";

const FROM = { library: "From the brand's library", uploaded: "Uploaded for this video", video: "Made for this video", script: "Made for this script" } as const;

/** The video's cast and places as the checkpoint reads them (its items, previews and state), read again every 4 s. */
export function useCast(projectId: number) {
  return useQuery({
    queryKey: ["cast", projectId],
    queryFn: () => polled(api.GET("/projects/{project_id}/cast", { params: { path: { project_id: projectId } } }), null),
    // Read again while looks are being drawn; any other change comes with the director's moves or this person's presses.
    refetchInterval: (q) => (q.state.data?.state === "not_ready" ? 4000 : false),
  });
}

/** The director's "Cast & places waiting for your OK" in the chat (S-gaps-07 B): the whole set with its previews, and the
 *  one press. The Cast tab (screen 9) shows the same set with its own press; both call the same route. */
export function CastOk({ projectId }: { projectId: number }) {
  const queryClient = useQueryClient();
  const cast = useCast(projectId);
  const approve = useMutation({
    mutationFn: async ({ seen, anyway }: { seen: Record<string, string>; anyway: boolean }) => {
      const { data, error } = await api.POST("/projects/{project_id}/cast/approve", { params: { path: { project_id: projectId } }, body: { seen, anyway } });
      if (!data) throw new Error(errorText(error));
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["cast", projectId], data);
      void queryClient.invalidateQueries({ queryKey: ["director", projectId] });
      return refreshJobs(queryClient);
    },
    onError: () => queryClient.invalidateQueries({ queryKey: ["cast", projectId] }), // refused as changed: show what it is now
  });
  const shown = cast.data;
  // Whenever the set is ready and this person may approve it, not only once the director asked: a video with no run, or a
  // look changed after it asked, is never left without the press.
  if (!shown || shown.state !== "ready" || !shown.can_approve) return null;
  const changed = shown.items.filter((i) => i.approval === "changed").map((i) => i.name);
  const wrong = shown.items.some((i) => i.approval !== "approved" && i.look_fit); // the look check says it's wrong: "anyway"
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
            {i.look_fit && i.approval !== "approved" && <p className="text-xs text-warning">{lookFitNote(i.look_fit)}</p>}
          </li>
        ))}
      </ul>
      <Button icon={Check} busy={approve.isPending} onClick={() => approve.mutate({ seen: Object.fromEntries(shown.items.map((i) => [i.ref, i.sig])), anyway: wrong })}>
        {wrong ? "Approve anyway" : <>Approve cast &amp; places</>}
      </Button>
      {approve.isError && <p role="alert" className="text-sm text-danger">{approve.error.message}</p>}
    </section>
  );
}
