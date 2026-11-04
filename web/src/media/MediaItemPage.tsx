import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Download, Trash2 } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import { fileUrl } from "../api/upload";
import { useMe } from "../auth/useMe";
import { Button, buttonClass, Dialog, Skeleton, useToast } from "../components";
import { errorText as errorClass } from "../ui";
import { useBrands } from "../shell/useBrands";
import { serverTime } from "../time";
import { kindName, opens } from "./MediaPage";

const when = (iso: string) => serverTime(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
/** "MP4", "PNG", "MP3": what Download gives (G_MediaItem's "Download MP4"). */
const fileType = (t: string) => ({ "video/mp4": "MP4", "image/png": "PNG", "image/jpeg": "JPG", "image/webp": "WebP", "audio/mpeg": "MP3", "audio/mp4": "M4A", "audio/wav": "WAV" })[t] ?? "";

/** One thing in Media (v5 G_MediaItem): the picture, take, song or video itself, what it is and who made it, where it came from
 *  (one press back to its step), and Download. */
export function MediaItemPage() {
  const { brandId: b, key: raw } = useParams();
  const brandId = Number(b);
  const key = decodeURIComponent(raw ?? "");
  const brand = useBrands().data?.find((x) => x.id === brandId);
  const owner = useMe().data?.role === "owner";
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [asking, setAsking] = useState(false);
  // One item's own read (#1212); a 404 says, in the server's words, that it's gone.
  const item = useQuery({
    queryKey: ["media-item", brandId, key],
    retry: false,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/brands/{brand_id}/media/{key}", { params: { path: { brand_id: brandId, key } } });
      if (response.status === 404) return { gone: errorText(error) || "That's no longer in Media." };
      if (!data) throw new Error(errorText(error));
      return { item: data };
    },
  });
  const m = item.data?.item;
  // The owner deletes a quick clip, a script's song or a final cut; the server refuses the rest in plain words.
  const remove = useMutation({
    mutationFn: async () => {
      const { error, response } = await api.DELETE("/brands/{brand_id}/media/{key}", { params: { path: { brand_id: brandId, key } } });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["media"] });
      // An added picture or clip, or a final cut, comes back with Undo (#1267's restore).
      const back = key.startsWith("upload:") || key.startsWith("final:")
        ? () => void api.POST("/brands/{brand_id}/media/{key}/restore", { params: { path: { brand_id: brandId, key } } }).then(({ response, error }) => {
            if (!response.ok) toast(errorText(error), undefined, "error");
            void queryClient.invalidateQueries({ queryKey: ["media"] });
          })
        : undefined;
      toast("Deleted from Media.", back);
      navigate(`/b/${brandId}/media`, { replace: true });
    },
    onError: () => setAsking(false),
  });
  const crumb = (
    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
      <nav aria-label="Breadcrumb" className="flex min-w-0 flex-wrap items-center gap-x-2 text-sm text-muted">
        <Link to={`/b/${brandId}/media`} className="inline-flex min-h-control min-w-11 items-center justify-center hover:text-text sm:min-h-control-dense">Media</Link>
        <span aria-hidden>›</span>
        <span className="font-medium text-text" aria-current="page">{m ? `${m.video_name ? `${m.video_name} · ` : ""}${kindName(m.kind)}` : "…"}</span>
      </nav>
      <Link to={`/b/${brandId}/media`} className={buttonClass("ghost")}>Close</Link>
    </div>
  );
  if (item.isPending) return <main className="mx-auto max-w-content space-y-6 p-4 sm:p-6">{crumb}<Skeleton className="h-96" /></main>;
  if (!m)
    return (
      <main className="mx-auto max-w-content space-y-4 p-4 sm:p-6">
        {crumb}
        <p role={item.isError ? "alert" : undefined}>{item.data?.gone ?? "Couldn't load this item. Check your connection."}</p>
        <div className="flex flex-wrap gap-2">
          {item.isError && <Button variant="secondary" onClick={() => void item.refetch()}>Try again</Button>}
          <Link to={`/b/${brandId}/media`} className={buttonClass("secondary")}>Back to Media</Link>
        </div>
      </main>
    );
  const deletable = owner && (m.kind === "song" || m.kind === "final" || m.kind === "upload" || m.open_step === "quick");
  const { to, step } = opens(m, brandId);
  const src = fileUrl(m.file_id);
  const isVideo = m.content_type.startsWith("video/");
  const isAudio = m.content_type.startsWith("audio/");
  const meta = [m.made_by?.name && `made by ${m.made_by.name}`, when(m.made_at)].filter(Boolean).join(" · ");
  return (
    <main className="mx-auto max-w-content space-y-6 p-4 sm:p-6">
      {crumb}
      <div className="grid gap-8 lg:grid-cols-[405px_minmax(0,1fr)]">
        <div className="flex justify-center">
          {isVideo ? (
            <video controls src={src} poster={m.poster_file_id ? fileUrl(m.poster_file_id) : undefined} className="max-h-[720px] w-full max-w-[405px] rounded-md bg-surface-2" aria-label={kindName(m.kind)} />
          ) : isAudio ? (
            <audio controls src={src} className="w-full max-w-[405px]" aria-label={`Play ${kindName(m.kind).toLowerCase()}`} />
          ) : (
            <img src={src} alt={kindName(m.kind)} className="max-h-[720px] w-full max-w-[405px] rounded-md bg-surface-2 object-contain" />
          )}
        </div>
        <section className="min-w-0 max-w-[560px]">
          <div className="space-y-1 pb-4">
            <h1 className="type-page">{kindName(m.kind)}</h1>
            <p className="text-sm text-muted tabular-nums">{meta}</p>
          </div>
          <div className="space-y-2 border-t border-border py-4">
            <h2 className="text-sm font-medium">Where it came from</h2>
            {m.kind === "upload" ? (
              <p className="text-sm text-muted">Added to this brand's Media{m.made_by ? ` by ${m.made_by.name}` : ""}.</p>
            ) : (
              <>
                <Link to={to} className="inline-flex min-h-control items-center text-accent-text hover:underline">
                  {m.video_name ? `Open its video: ${m.video_name}` : `Open in ${step}`}
                </Link>
                <p className="text-sm text-muted">{m.open_step === "quick" ? "Made in Freestyle; it opens its own thread." : m.video_name ? `Opens the video at ${step}, where it was made.` : `Opens ${step}, where it was made.`}</p>
              </>
            )}
          </div>
          <div className="space-y-2 border-t border-border py-4">
            <h2 className="text-sm font-medium">Kind</h2>
            <div className="flex flex-wrap gap-2">
              {[kindName(m.kind), brand?.name].filter(Boolean).map((t) => (
                <span key={t} className="inline-flex h-7 items-center rounded-sm border border-border-strong px-2 text-sm">{t}</span>
              ))}
            </div>
          </div>
          <div className="space-y-2 border-t border-border py-4">
            <div className="flex flex-wrap gap-2">
              <a href={src} download className={`${buttonClass("primary")} gap-2`}>
                <Download size={20} strokeWidth={1.75} aria-hidden />
                Download {fileType(m.content_type)}
              </a>
              {deletable && (
                <Button variant="secondary" icon={Trash2} busy={remove.isPending} onClick={() => setAsking(true)}>
                  Delete
                </Button>
              )}
            </div>
            {deletable && <p className="text-sm text-muted">Deleting removes it from Media.{m.video_name ? " Its video keeps its own copy." : ""}</p>}
            {remove.isError && <p role="alert" className={errorClass}>{remove.error.message}</p>}
          </div>
        </section>
      </div>
      {asking && (
        <Dialog title={`Delete this ${m.open_step === "quick" ? "clip" : m.kind === "final" ? "final cut" : kindName(m.kind).toLowerCase()}?`} cancelLabel="Keep it" actionLabel="Delete" danger busy={remove.isPending} onCancel={() => setAsking(false)} onConfirm={() => remove.mutate()}>
          It leaves Media for everyone.{m.video_name ? " Its video keeps its own copy." : ""}
        </Dialog>
      )}
    </main>
  );
}
