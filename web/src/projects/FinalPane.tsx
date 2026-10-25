import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, Film } from "lucide-react";
import { api, errorText } from "../api/client";
import { fileUrl } from "../api/upload";
import { Badge, Banner, Button, Card, Skeleton, buttonClass, useToast } from "../components";
import { useProjectClips, useProjectVideo } from "./useProgress";

/** The finished video: put the approved clips together (free), watch it, download it. */
export function FinalPane({ projectId, aspect, projectName }: { projectId: number; aspect: string; projectName: string }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const clips = useProjectClips(projectId);
  const video = useProjectVideo(projectId);
  const stitch = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/projects/{project_id}/video", { params: { path: { project_id: projectId } } });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["project-video", projectId] });
      toast("Your video is ready.");
    },
  });
  if (clips.isPending || video.isPending) return <Skeleton className="h-64" />;
  const list = clips.data ?? [];
  const approved = list.filter((c) => c.approved);
  const v = video.data;
  const seconds = Math.round(list.reduce((n, c) => n + c.seconds, 0));
  const ratio = aspect.replace(":", " / ");
  const madeFrom = approved
    .map((c) => {
      const take = c.takes.find((t) => t.id === c.picked_take_id);
      return take ? `Clip ${c.clip_id} Take ${take.number}` : null;
    })
    .filter(Boolean)
    .join(", ");
  const left = list.length - approved.length;

  if (stitch.isPending)
    return (
      <Card className="space-y-3">
        <Skeleton className="h-64" />
        <p className="text-sm text-muted" role="status">
          Putting your clips together…
        </p>
      </Card>
    );

  return (
    <div className="space-y-4" aria-label="Final video">
      {stitch.isError && (
        <Banner title="The video couldn't be put together." action={<Button variant="secondary" onClick={() => stitch.mutate()}>Try again</Button>}>
          Nothing was charged. {stitch.error.message}
        </Banner>
      )}
      {v && v.out_of_date && (
        <Banner tone="warning" title="Out of date." action={<Button onClick={() => stitch.mutate()}>Make the video again</Button>}>
          A clip changed since this video was made.
        </Banner>
      )}
      {v ? (
        <Card className="grid gap-4 sm:grid-cols-[minmax(0,420px)_1fr]">
          <video controls src={fileUrl(v.file_id)} className="w-full rounded-lg bg-surface-2" style={{ aspectRatio: ratio }} aria-label="The finished video" />
          <div className="space-y-3">
            <Badge tone={v.out_of_date ? "warning" : "success"}>{v.out_of_date ? "Out of date" : "Ready"}</Badge>
            <p className="text-sm text-muted tabular-nums">
              {seconds} s · {aspect}
            </p>
            {madeFrom && <p className="text-sm text-muted">Made from: {madeFrom}</p>}
            <div className="flex flex-wrap gap-2">
              <a className={buttonClass(v.out_of_date ? "ghost" : "primary")} href={fileUrl(v.file_id)} download={`${projectName}.mp4`}>
                <Download size={20} strokeWidth={1.75} aria-hidden />
                {v.out_of_date ? "Download the older video" : "Download MP4"}
              </a>
            </div>
          </div>
        </Card>
      ) : (
        <Card className="space-y-4">
          <p className="flex items-center gap-2 font-medium">
            <Film size={20} strokeWidth={1.75} aria-hidden />
            {approved.length} clip{approved.length === 1 ? "" : "s"} ready · {seconds} s · {aspect}
          </p>
          <ul className="flex gap-3 overflow-x-auto" aria-label="Approved clips in order">
            {approved.map((c) => (
              <li key={c.id} className="w-28 shrink-0 space-y-1">
                {c.file_id ? <video muted preload="metadata" src={fileUrl(c.file_id)} className="w-full rounded-md bg-surface-2" style={{ aspectRatio: ratio }} aria-label={`Clip ${c.clip_id}`} /> : <div className="rounded-md bg-surface-2" style={{ aspectRatio: ratio }} />}
                <p className="text-sm">
                  Clip {c.clip_id} · {c.seconds} s
                </p>
              </li>
            ))}
          </ul>
          <div className="space-y-1">
            <Button disabled={left > 0} reason={left > 0 ? `Approve every clip first (${left} left)` : undefined} onClick={() => stitch.mutate()}>
              Make the video
            </Button>
            {left === 0 && <p className="text-sm text-muted">Free. Puts your approved clips together in order.</p>}
          </div>
        </Card>
      )}
    </div>
  );
}
