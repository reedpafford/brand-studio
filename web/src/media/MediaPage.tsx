import { useRef } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronLeft, Film, Images, Music, Users } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, errorText, must } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { useMe } from "../auth/useMe";
import { Banner, Button, EmptyState, Menu, MenuItem, Skeleton, buttonClass, useToast, PageTop, pillClass, pillStrip } from "../components";
import { useBrands } from "../shell/useBrands";
import { serverTime } from "../time";
import { useRail } from "../useMedia";

type Item = components["schemas"]["MediaItem"];
type Kind = Item["kind"];

const KINDS: { id: Kind; label: string; one: string }[] = [
  { id: "still", label: "Stills", one: "Still" },
  { id: "sheet", label: "Character sheets", one: "Sheet" },
  { id: "take", label: "Clips", one: "Take" },
  { id: "song", label: "Songs", one: "Song" },
  { id: "final", label: "Final videos", one: "Final video" },
  { id: "upload", label: "Added", one: "Upload" }, // a picture or clip added to the brand's Media (#1267)
];
/** The board's tabs: All · Clips · Stills · Songs, each a server group with its count. */
const GROUPS = [
  { id: "clip", label: "Clips", count: "clips" },
  { id: "still", label: "Stills", count: "stills" },
  { id: "song", label: "Songs", count: "songs" },
] as const;
type Group = (typeof GROUPS)[number]["id"];
/** 130 px tiles, as many to a row as fit (the board shows eight at 1440); three across on a phone. */
const GRID = "grid grid-cols-3 gap-3 sm:grid-cols-[repeat(auto-fill,minmax(130px,1fr))] sm:gap-4";
/** The chip on a tile is its group: a final cut is a Clip, a sheet or an added picture a Still. */
const CHIP: Record<Group, string> = { clip: "Clip", still: "Still", song: "Song" };
/** "00:08": a clip's or song's length. */
const length = (s: number) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.round(s % 60)).padStart(2, "0")}`;
export const kindName = (k: Kind) => KINDS.find((x) => x.id === k)!.one;
const date = (iso: string) => serverTime(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });

/** Where an item is opened, and the step's name for "Open in {step}". */
export function opens(m: Item, brandId: number): { to: string; step: string } {
  const video = (step: string) => `/b/${brandId}/videos/${m.project_id}?step=${step}`;
  if (m.open_step === "quick") return { to: m.freestyle_id ? `/freestyle/${m.freestyle_id}` : "/freestyle", step: "Freestyle" }; // Freestyle replaced Quick clip
  if (m.open_step === "song" && m.script_id) return { to: `/b/${brandId}/scripts/${m.script_id}?step=takes`, step: "Takes" };
  if (!m.project_id) return { to: `/b/${brandId}/library`, step: "Cast & places" }; // the brand's own sheets
  if (m.open_step === "storyboard") return { to: video("storyboard"), step: "Storyboard" };
  if (m.open_step === "cast") return { to: video("cast"), step: "Cast" };
  if (m.open_step === "clips") return { to: video("clips"), step: "Clips" };
  return { to: video("downloads"), step: "Final cut" }; // a final video, or a video's song
}

function Tile({ m, brandId, meId, owner }: { m: Item; brandId: number; meId: number | undefined; owner: boolean }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const restore = useMutation({
    mutationFn: () => must(api.POST("/projects/{project_id}/restore", { params: { path: { project_id: m.project_id! } } })),
    onSuccess: () => {
      const refresh = () => queryClient.invalidateQueries({ queryKey: ["media"] });
      // Undo puts it back as it was, free: released again (its version back to Ready to make), or deleted again.
      const again = m.deleted_video_released ? "/projects/{project_id}/release" : "/projects/{project_id}/archive";
      toast(`${m.video_name ?? "The video"} is back.`, () => void must(api.POST(again, { params: { path: { project_id: m.project_id! } } })).then(refresh, (e: Error) => toast(e.message, undefined, "error")));
      return refresh();
    },
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  const isVideo = m.content_type.startsWith("video/");
  // A song made on a script (not yet in a video) says which script: its title, read once and shared with the script's own page.
  const fromScript = m.kind === "song" && !m.video_name && m.script_id ? m.script_id : null;
  const script = useQuery({ enabled: fromScript !== null, queryKey: ["script-lib", fromScript], queryFn: async () => (await api.GET("/scripts/{script_id}", { params: { path: { script_id: fromScript! } } })).data ?? null });
  const title = m.video_name ?? script.data?.title ?? (m.open_step === "quick" ? "Quick clip" : m.kind === "sheet" ? "Cast & places" : kindName(m.kind));
  const gone = m.deleted_video_by; // the deleted video's maker: they or the owner may restore it (as the Archived list offers)
  const mayRestore = owner || (!!gone && gone.id === meId);
  const meta = [fromScript ? "Song from the script" : m.kind === "song" && m.video_name ? "Song from the video" : m.kind === "final" ? "Director video" : kindName(m.kind), date(m.made_at), m.made_by?.name].filter(Boolean).join(" · ");
  const picture = m.poster_file_id ? fileUrl(m.poster_file_id) : m.content_type.startsWith("image/") ? fileUrl(m.file_id) : null;
  const Icon = m.kind === "song" ? Music : m.kind === "sheet" ? Users : Images;
  return (
    <li className="min-w-0">
      <Link to={`/b/${brandId}/media/${encodeURIComponent(m.key)}`} aria-label={`Open ${title}, ${meta}`} className="relative block aspect-[9/16] overflow-hidden rounded-md border border-border bg-surface-2">
        {picture ? <img src={picture} alt="" className="absolute inset-0 size-full object-cover" /> : !m.poster_file_id && isVideo ? <video src={`${fileUrl(m.file_id)}#t=0.1`} muted playsInline preload="metadata" aria-hidden className="absolute inset-0 size-full object-cover" /> : (
          <span className="absolute inset-0 grid place-items-center text-muted" aria-hidden>
            <Icon size={24} strokeWidth={1.75} />
          </span>
        )}
        <span className="absolute left-1.5 top-1.5 rounded-sm bg-scrim px-1.5 text-xs font-medium text-on-media">{CHIP[m.group]}</span>
        {m.duration_seconds != null && <span className="absolute bottom-1.5 left-1.5 rounded-sm bg-scrim px-1.5 text-xs tabular-nums text-on-media">{length(m.duration_seconds)}</span>}
      </Link>
      <p className="mt-1.5 truncate text-xs font-medium">{title}</p>
      <p className="truncate text-xs text-muted">{meta}</p>
      {m.from_deleted_video && (
        <div className="mt-1 space-y-1">
          <span className="block rounded-sm bg-warning-soft px-1.5 py-0.5 text-xs text-warning [overflow-wrap:anywhere]">{!gone ? "From a deleted video" : gone.id === meId ? "From your deleted video" : `From ${gone.name}'s deleted video`}</span>
          {mayRestore && (
            <Button variant="ghost" dense busy={restore.isPending} onClick={() => restore.mutate()}>
              Restore the video
            </Button>
          )}
        </div>
      )}
    </li>
  );
}

/** "Upload": a picture or clip added to the brand's Media (a PNG, JPEG or WebP, or an MP4 or WebM); the server says why it refuses one. */
function UploadButton({ brandId }: { brandId: number }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const add = useMutation({
    mutationFn: async (file: File) => {
      const { data, error } = await api.POST("/brands/{brand_id}/media", {
        params: { path: { brand_id: brandId } },
        body: { upload: file as unknown as string },
        bodySerializer: () => {
          const form = new FormData();
          form.append("upload", file);
          return form;
        },
      });
      if (!data) throw new Error(errorText(error));
    },
    onSuccess: () => {
      toast("Added to Media.");
      void queryClient.invalidateQueries({ queryKey: ["media"] });
      void queryClient.invalidateQueries({ queryKey: ["media-counts"] });
    },
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  return (
    <>
      <input ref={input} type="file" accept="image/png,image/jpeg,image/webp,video/mp4,video/webm" hidden aria-label="Choose a picture or clip" onChange={(e) => { const f = e.target.files?.[0]; if (f) add.mutate(f); e.target.value = ""; }} />
      <Button variant="secondary" dense busy={add.isPending} className="lg:min-h-9" onClick={() => input.current?.click()}>
        Upload
      </Button>
    </>
  );
}

/** Everything made in a brand (flows OR2): stills, sheets, takes, songs and final videos, newest first.
 *  An editor sees only what they can already open; the server decides. Filters: kind, project (?folder=), who made it. */
export function MediaPage() {
  const brandId = Number(useParams().brandId);
  const { data: me } = useMe();
  const owner = me?.role === "owner";
  const brand = useBrands().data?.find((b) => b.id === brandId);
  const rail = useRail();
  const [params, setParams] = useSearchParams();
  const group = (GROUPS.find((g) => g.id === params.get("group"))?.id ?? null) as Group | null;
  const video = params.get("video"); // one video's own media (a Freestyle counts as a video)
  const oldest = params.get("sort") === "oldest";
  const set = (key: string, value: string) =>
    setParams((p) => {
      if (value) p.set(key, value);
      else p.delete(key);
      return p;
    }, { replace: true });
  const clear = () => setParams((p) => { ["group", "video", "sort"].forEach((k) => p.delete(k)); return p; }, { replace: true });

  const media = useInfiniteQuery({
    queryKey: ["media", brandId, group, oldest],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) =>
      must(api.GET("/brands/{brand_id}/media", { params: { path: { brand_id: brandId }, query: { ...(group ? { group } : {}), ...(oldest ? { sort: "oldest" as const } : {}), ...(pageParam ? { before: pageParam } : {}) } } })).then((r) => r.data!),
    getNextPageParam: (last) => last.next,
  });
  const loaded = media.data?.pages.flatMap((p) => p.items) ?? [];
  const videoKey = (m: Item) => (m.project_id ? `p${m.project_id}` : m.freestyle_id ? `f${m.freestyle_id}` : null);
  const videos = [...new Map(loaded.flatMap((m) => (videoKey(m) && m.video_name ? [[videoKey(m)!, m.video_name] as const] : []))).entries()];
  const picked = videos.find(([k]) => k === video)?.[1];
  const items = loaded.filter((m) => !video || videoKey(m) === video); // the server sorts (newest or oldest first)
  const filtered = !!group || !!video;
  const counts = useQuery({ queryKey: ["media-counts", brandId], queryFn: async () => (await api.GET("/brands/{brand_id}/media-counts", { params: { path: { brand_id: brandId } } })).data });

  const menu = (title: string, label: string, options: [string, string][], current: string, onPick: (v: string) => void) => (
    <Menu title={title} align="right" trigger={(p) => (
      <Button variant="ghost" dense trailing={ChevronDown} className="text-[13px] lg:min-h-11" {...p}>
        {label}
      </Button>
    )}>
      {(close) => options.map(([id, name]) => <MenuItem key={id} checked={current === id} onClick={() => { close(); onPick(id); }}>{name}</MenuItem>)}
    </Menu>
  );
  // The board's band: the kinds as pills on the left, the filters as plain text on the right.
  const tabs = (
    <nav aria-label="Kinds" className={pillStrip}>
      {[{ id: "", label: "All", n: counts.data?.all }, ...GROUPS.map((g) => ({ id: g.id as string, label: g.label, n: counts.data?.[g.count] }))].map((k) => (
        <button key={k.id} type="button" aria-pressed={(group ?? "") === k.id} className={pillClass((group ?? "") === k.id)} onClick={() => set("group", k.id)}>
          {k.label}
          {k.n !== undefined && <span className="tabular-nums text-muted"> {k.n}</span>}
        </button>
      ))}
    </nav>
  );

  return (
    <main className="mx-auto max-w-content p-4 sm:p-6">
      <PageTop title="Media">
        <UploadButton brandId={brandId} />
        {!rail && ( // on a phone Media opens from Videos
          <Link to={`/b/${brandId}/videos`} className="inline-flex min-h-control items-center gap-1 text-accent-text hover:underline">
            <ChevronLeft size={20} strokeWidth={1.75} aria-hidden />
            Videos
          </Link>
        )}
      </PageTop>
      <div className="-mx-4 mb-4 flex min-h-11 flex-wrap items-center gap-x-3 gap-y-1 border-b border-border px-4 py-1.5 sm:-mx-6 sm:px-6">
        {tabs}
        <span className="hidden flex-1 sm:block" />
        {menu("Video", picked ? `Video: ${picked}` : "Video", [["", "All videos"], ...videos], video ?? "", (v) => set("video", v))}
        {menu("Sort", oldest ? "Oldest first" : "Newest first", [["", "Newest first"], ["oldest", "Oldest first"]], oldest ? "oldest" : "", (v) => set("sort", v))}
        {(filtered || oldest) && <Button variant="ghost" dense onClick={clear}>Clear filters</Button>}
      </div>
      {media.isError && <Banner tone="danger" title="Couldn't load the media. Check your connection." action={<Button variant="secondary" onClick={() => media.refetch()}>Try again</Button>} />}
      {media.isPending && (
        <ul role="status" aria-label="Loading" className={GRID}>
          {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
            <li key={i}>
              <Skeleton className="aspect-[9/16]" />
            </li>
          ))}
        </ul>
      )}
      {media.data &&
        (items.length === 0 ? (
          filtered ? (
            <EmptyState icon={Images} title="Nothing matches these filters." action={<Button variant="ghost" onClick={clear}>Clear filters</Button>} />
          ) : (
            <EmptyState icon={Film} title={`Nothing made yet in ${brand?.name ?? "this brand"}.`} action={<Link to={`/b/${brandId}/videos/new`} className={buttonClass("secondary")}>New video</Link>}>
              Stills, takes, songs and final videos show up here as they're made.
            </EmptyState>
          )
        ) : (
          <>
            <ul aria-label="Media" className={GRID}>
              {items.map((m) => (
                <Tile key={m.key} m={m} brandId={brandId} meId={me?.id} owner={owner} />
              ))}
            </ul>
          </>
        ))}
      {/* Also under "Nothing matches": the Video filter reads the pages loaded so far, so older ones may hold it. */}
      {media.data && media.hasNextPage && (
        <div className="flex justify-center">
          <Button variant="secondary" busy={media.isFetchingNextPage} onClick={() => void media.fetchNextPage()}>
            Show more
          </Button>
        </div>
      )}
    </main>
  );
}
