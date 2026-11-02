import { useInfiniteQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Download } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { api, must } from "../api/client";
import { fileUrl } from "../api/upload";
import { buttonClass, Skeleton } from "../components";
import { useBrands } from "../shell/useBrands";
import { serverTime } from "../time";
import { kindName, opens } from "./MediaPage";

const when = (iso: string) => serverTime(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const PAGES = 5;
/** "MP4", "PNG", "MP3": what Download gives (G_MediaItem's "Download MP4"). */
const fileType = (t: string) => ({ "video/mp4": "MP4", "image/png": "PNG", "image/jpeg": "JPG", "image/webp": "WebP", "audio/mpeg": "MP3", "audio/mp4": "M4A", "audio/wav": "WAV" })[t] ?? ""; // there is no read of one item: it is found in the brand's media list, newest first

/** One thing in Media (v5 G_MediaItem): the picture, take, song or video itself, what it is and who made it, where it came from
 *  (one press back to its step), and Download. */
export function MediaItemPage() {
  const { brandId: b, key: raw } = useParams();
  const brandId = Number(b);
  const key = decodeURIComponent(raw ?? "");
  const brand = useBrands().data?.find((x) => x.id === brandId);
  const media = useInfiniteQuery({
    queryKey: ["media", brandId, null, null, null],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => must(api.GET("/brands/{brand_id}/media", { params: { path: { brand_id: brandId }, query: pageParam ? { before: pageParam } : {} } })).then((r) => r.data!),
    getNextPageParam: (last) => last.next,
  });
  const pages = media.data?.pages ?? [];
  const m = pages.flatMap((p) => p.items).find((x) => x.key === key);
  const more = !m && media.hasNextPage && pages.length < PAGES;
  useEffect(() => {
    if (more && !media.isFetchingNextPage) void media.fetchNextPage();
  }, [more, media]);
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
  if (media.isPending || more) return <main className="mx-auto max-w-content space-y-6 p-4 sm:p-6">{crumb}<Skeleton className="h-96" /></main>;
  if (!m)
    return (
      <main className="mx-auto max-w-content space-y-4 p-4 sm:p-6">
        {crumb}
        <p>That item isn't in Media any more.</p>
        <Link to={`/b/${brandId}/media`} className={buttonClass("secondary")}>Back to Media</Link>
      </main>
    );
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
            <Link to={to} className="inline-flex min-h-control items-center text-accent-text hover:underline">
              {m.video_name ? `Open its video: ${m.video_name}` : `Open in ${step}`}
            </Link>
            <p className="text-sm text-muted">{m.open_step === "quick" ? "Made in Freestyle; it opens its own thread." : m.video_name ? `Opens the video at ${step}, where it was made.` : `Opens ${step}, where it was made.`}</p>
          </div>
          <div className="space-y-2 border-t border-border py-4">
            <h2 className="text-sm font-medium">Kind</h2>
            <div className="flex flex-wrap gap-2">
              {[kindName(m.kind), brand?.name].filter(Boolean).map((t) => (
                <span key={t} className="inline-flex h-7 items-center rounded-sm border border-border-strong px-2 text-sm">{t}</span>
              ))}
            </div>
          </div>
          <div className="border-t border-border py-4">
            <a href={src} download className={`${buttonClass("primary")} gap-2`}>
              <Download size={20} strokeWidth={1.75} aria-hidden />
              Download {fileType(m.content_type)}
            </a>
          </div>
        </section>
      </div>
    </main>
  );
}
