import { useEffect, useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { api, errorText } from "../api/client";
import { fileUrl } from "../api/upload";
import { Badge, Banner, Button, Card, Skeleton, buttonClass, useToast } from "../components";
import { useProjectClips, useProjectVideo } from "./useProgress";

const slug = (name: string) => name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "video";

/** Downloads (there is no upload): the whole video, every clip's picked take, and the older takes. */
export function DownloadsPane({ projectId, aspect, projectName }: { projectId: number; aspect: string; projectName: string }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const clips = useProjectClips(projectId);
  const video = useProjectVideo(projectId);
  const stitch = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/projects/{project_id}/video", { params: { path: { project_id: projectId } } });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project-video", projectId] }),
  });
  // The whole video is put together the first time the step opens. It is free.
  const asked = useRef(false);
  const ready = !clips.isPending && !video.isPending && (clips.data ?? []).length > 0 && (clips.data ?? []).every((c) => c.approved);
  useEffect(() => {
    if (ready && !video.data && !asked.current) {
      asked.current = true;
      stitch.mutate();
    }
  });
  if (clips.isPending || video.isPending) return <Skeleton className="h-64" />;
  const list = clips.data ?? [];
  const v = video.data;
  const seconds = Math.round(list.reduce((n, c) => n + c.seconds, 0));
  const ratio = aspect.replace(":", " / ");
  const base = slug(projectName);
  const madeFrom = list
    .map((c) => {
      const take = c.takes.find((t) => t.id === c.picked_take_id);
      return take ? `Clip ${c.clip_id} Take ${take.number}` : null;
    })
    .filter(Boolean)
    .join(", ");
  const save = (fileId: number, name: string, label: string, variant: "secondary" | "ghost" = "secondary") => (
    <a className={buttonClass(variant)} href={fileUrl(fileId)} download={name} aria-label={`${label} (${name})`}>
      <Download size={20} strokeWidth={1.75} aria-hidden />
      Download
    </a>
  );

  return (
    <div className="space-y-6" aria-label="Downloads">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted tabular-nums">
          {list.length} clip{list.length === 1 ? "" : "s"} · {seconds} s · {aspect} · every clip approved
        </p>
        <a className={buttonClass("primary")} href={`/api/projects/${projectId}/clips.zip`} download={`${base}-clips.zip`} onClick={() => toast("Video done. Downloads stay here.")}>
          <Download size={20} strokeWidth={1.75} aria-hidden />
          Download all clips (.zip)
        </a>
      </div>
      <section aria-label="The whole video" className="space-y-3">
        <h3 className="type-section">The whole video</h3>
        {stitch.isError && (
          <Banner title="The video couldn't be put together." action={<Button variant="secondary" onClick={() => stitch.mutate()}>Try again</Button>}>
            Nothing was charged. {stitch.error.message}
          </Banner>
        )}
        {v && v.out_of_date && (
          <Banner tone="warning" title="Out of date." action={<Button onClick={() => stitch.mutate()}>Make it again</Button>}>
            A clip changed since this video was made. It's free.
          </Banner>
        )}
        {v ? (
          <Card className="grid gap-4 sm:grid-cols-[minmax(0,360px)_1fr]">
            <video controls src={fileUrl(v.file_id)} className="w-full rounded-lg bg-surface-2" style={{ aspectRatio: ratio }} aria-label="The finished video" />
            <div className="space-y-3">
              <Badge tone={v.out_of_date ? "warning" : "success"}>{v.out_of_date ? "Out of date" : "Ready"}</Badge>
              <p className="text-sm text-muted tabular-nums">
                {base}.mp4 · {seconds} s
              </p>
              {madeFrom && <p className="text-sm text-muted">Made from: {madeFrom}</p>}
              <a className={buttonClass("secondary")} href={fileUrl(v.file_id)} download={`${base}.mp4`}>
                <Download size={20} strokeWidth={1.75} aria-hidden />
                Download MP4
              </a>
            </div>
          </Card>
        ) : (
          <Card>
            <p className="text-sm text-muted" role="status">
              Putting your clips together…
            </p>
            <Skeleton className="mt-3 h-40" />
          </Card>
        )}
      </section>
      <section aria-label="Each clip" className="space-y-3">
        <h3 className="type-section">Each clip</h3>
        <ul className="space-y-3">
          {list.map((c, i) => {
            const picked = c.takes.find((t) => t.id === c.picked_take_id);
            const older = c.takes.filter((t) => t.id !== c.picked_take_id).sort((a, b) => b.number - a.number);
            return (
              <li key={c.id} aria-label={`Clip ${c.clip_id}`}>
                <Card className="space-y-2">
                  <div className="flex items-center gap-3">
                    {picked ? <video muted preload="metadata" src={fileUrl(picked.file_id)} className="w-16 shrink-0 rounded-md bg-surface-2 sm:w-20" style={{ aspectRatio: ratio }} aria-hidden /> : <div className="w-16 shrink-0 rounded-md bg-surface-2 sm:w-20" style={{ aspectRatio: ratio }} />}
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">
                        Clip {c.clip_id} · {c.seconds} s
                      </p>
                      <p className="text-sm text-muted">{picked ? `Take ${picked.number} · picked` : "No take picked"}</p>
                    </div>
                    {picked && save(picked.file_id, `${base}-clip-${i + 1}.mp4`, `Download clip ${c.clip_id}`)}
                  </div>
                  {older.length > 0 && (
                    <details className="text-sm">
                      <summary className="flex min-h-control cursor-pointer items-center text-accent-text sm:min-h-control-dense">Older takes ({older.length})</summary>
                      <ul className="space-y-1">
                        {older.map((t) => (
                          <li key={t.id} className="flex items-center justify-between gap-3">
                            Take {t.number}
                            {save(t.file_id, `${base}-clip-${i + 1}-take-${t.number}.mp4`, `Download clip ${c.clip_id} take ${t.number}`, "ghost")}
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                </Card>
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}
