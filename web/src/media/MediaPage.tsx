import { useState } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, Download, Film, Images, Music, Users } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, must } from "../api/client";
import type { components } from "../api/schema";
import { fileUrl } from "../api/upload";
import { useMe } from "../auth/useMe";
import { Badge, Banner, Button, EmptyState, MediaCard, Select, Sheet, Skeleton, buttonClass, useToast } from "../components";
import { ProjectsChip } from "../folders/Projects";
import { useBrands } from "../shell/useBrands";
import { serverTime } from "../time";
import { useRail } from "../useMedia";

type Item = components["schemas"]["MediaItem"];
type Kind = Item["kind"];

const KINDS: { id: Kind; label: string; one: string }[] = [
  { id: "still", label: "Stills", one: "Still" },
  { id: "sheet", label: "Character sheets", one: "Sheet" },
  { id: "take", label: "Takes", one: "Take" },
  { id: "song", label: "Songs", one: "Song" },
  { id: "final", label: "Final videos", one: "Final video" },
];
const kindName = (k: Kind) => KINDS.find((x) => x.id === k)!.one;
const date = (iso: string) => serverTime(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });

/** Where an item is opened, and the step's name for "Open in {step}". */
function opens(m: Item, brandId: number): { to: string; step: string } {
  const video = (step: string) => `/b/${brandId}/videos/${m.project_id}?step=${step}`;
  if (m.open_step === "quick") return { to: `/b/${brandId}/clip`, step: "Quick clip" };
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
      toast(`${m.video_name ?? "The video"} is back.`);
      return queryClient.invalidateQueries({ queryKey: ["media"] });
    },
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  const { to, step } = opens(m, brandId);
  const isVideo = m.content_type.startsWith("video/");
  const title = m.video_name ?? (m.open_step === "quick" ? "Quick clip" : m.kind === "sheet" ? "Cast & places" : kindName(m.kind));
  const gone = m.deleted_video_by; // the deleted video's maker: they or the owner may restore it (as the Archived list offers)
  const mayRestore = owner || (!!gone && gone.id === meId);
  const meta = [kindName(m.kind), date(m.made_at), m.made_by?.name].filter(Boolean).join(" · ");
  return (
    <li>
      <MediaCard
        title={title}
        meta={meta}
        aspect="4 / 5"
        image={m.poster_file_id ? fileUrl(m.poster_file_id) : m.content_type.startsWith("image/") ? fileUrl(m.file_id) : null}
        video={!m.poster_file_id && isVideo ? fileUrl(m.file_id) : null}
        playable={isVideo}
        icon={m.kind === "song" ? Music : m.kind === "sheet" ? Users : Images}
        badge={m.from_deleted_video ? <Badge tone="warning">{!gone ? "From a deleted video" : gone.id === meId ? "From your deleted video" : `From ${gone.name}'s deleted video`}</Badge> : undefined}
      >
        {m.kind === "song" && <audio controls preload="none" src={fileUrl(m.file_id)} aria-label={`Play ${title}`} className="w-full" />}
        <div className="flex flex-wrap gap-2">
          {m.from_deleted_video ? (
            mayRestore && (
              <Button variant="secondary" dense busy={restore.isPending} onClick={() => restore.mutate()}>
                Restore the video
              </Button>
            )
          ) : (
            <Link to={to} className={buttonClass("secondary")}>
              Open in {step}
            </Link>
          )}
          <a href={fileUrl(m.file_id)} download aria-label={`Download ${kindName(m.kind).toLowerCase()} from ${title}`} className={`${buttonClass("ghost")} gap-2`}>
            <Download size={20} strokeWidth={1.75} aria-hidden />
            Download
          </a>
        </div>
      </MediaCard>
    </li>
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
  const [sheet, setSheet] = useState(false);
  const kind = (KINDS.find((k) => k.id === params.get("kind"))?.id ?? null) as Kind | null;
  const folder = params.get("folder");
  const by = owner ? Number(params.get("by")) || null : null;
  const set = (key: string, value: string) =>
    setParams((p) => {
      if (value) p.set(key, value);
      else p.delete(key);
      return p;
    }, { replace: true });
  const clear = () => setParams((p) => { ["kind", "by", "folder"].forEach((k) => p.delete(k)); return p; }, { replace: true });

  const people = useQuery({ enabled: owner, queryKey: ["team-members"], queryFn: async () => (await api.GET("/team/members")).data ?? [] });
  const media = useInfiniteQuery({
    queryKey: ["media", brandId, kind, folder, by],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) =>
      must(api.GET("/brands/{brand_id}/media", { params: { path: { brand_id: brandId }, query: { ...(kind ? { kind } : {}), ...(folder ? { folder } : {}), ...(by ? { by } : {}), ...(pageParam ? { before: pageParam } : {}) } } })).then((r) => r.data!),
    getNextPageParam: (last) => last.next,
  });
  const items = media.data?.pages.flatMap((p) => p.items) ?? [];
  const filtered = !!kind || !!folder || !!by;

  const controls = (
    <>
      <div className="w-full lg:w-52">
        <Select label="Kind" value={kind ?? ""} onChange={(e) => set("kind", e.target.value)}>
          <option value="">Everything</option>
          {KINDS.map((k) => (
            <option key={k.id} value={k.id}>
              {k.label}
            </option>
          ))}
        </Select>
      </div>
      {owner && (
        <div className="w-full lg:w-52">
          <Select label="Made by" value={by ? String(by) : ""} onChange={(e) => set("by", e.target.value)}>
            <option value="">Anyone</option>
            {(people.data ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}
              </option>
            ))}
          </Select>
        </div>
      )}
      {filtered && (
        <Button variant="ghost" onClick={clear}>
          Clear filters
        </Button>
      )}
    </>
  );
  const active = [!!kind, !!by].filter(Boolean).length; // the project shows on its own chip

  return (
    <main className="mx-auto max-w-content space-y-5 p-4 sm:p-6">
      {!rail && ( // on a phone Media opens from Videos
        <Link to={`/b/${brandId}/videos`} className="inline-flex min-h-control items-center gap-1 text-accent-text hover:underline">
          <ChevronLeft size={20} strokeWidth={1.75} aria-hidden />
          Videos
        </Link>
      )}
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="type-eyebrow text-muted">{brand?.name}</p>
          <h1 className="type-page">Media</h1>
        </div>
        <div className="flex items-center gap-2">
          <ProjectsChip brandId={brandId} />
          {!rail && (
            <Button variant={active > 0 ? "primary" : "secondary"} className="shrink-0 whitespace-nowrap" onClick={() => setSheet(true)}>
              Filters{active > 0 ? ` (${active})` : ""}
            </Button>
          )}
        </div>
      </div>
      {rail && <div className="flex flex-wrap items-end gap-3">{controls}</div>}
      {media.isError && <Banner tone="danger" title="Couldn't load the media. Check your connection." action={<Button variant="secondary" onClick={() => media.refetch()}>Try again</Button>} />}
      {media.isPending && (
        <ul role="status" aria-label="Loading" className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
            <li key={i}>
              <Skeleton className="aspect-[4/5]" />
            </li>
          ))}
        </ul>
      )}
      {media.data &&
        (items.length === 0 ? (
          filtered ? (
            <EmptyState icon={Images} title="Nothing matches these filters." action={<Button variant="ghost" onClick={clear}>Clear filters</Button>} />
          ) : (
            <EmptyState icon={Film} title={`Nothing made yet in ${brand?.name ?? "this brand"}.`} action={<Link to={`/b/${brandId}/clip`} className={buttonClass("primary")}>Make a quick clip</Link>}>
              Stills, takes, songs and final videos show up here as they're made.
            </EmptyState>
          )
        ) : (
          <>
            <ul aria-label="Media" className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
              {items.map((m) => (
                <Tile key={m.key} m={m} brandId={brandId} meId={me?.id} owner={owner} />
              ))}
            </ul>
            {media.hasNextPage && (
              <div className="flex justify-center">
                <Button variant="secondary" busy={media.isFetchingNextPage} onClick={() => void media.fetchNextPage()}>
                  Show more
                </Button>
              </div>
            )}
          </>
        ))}
      {sheet && (
        <Sheet title="Filters" onClose={() => setSheet(false)}>
          <div className="space-y-3">{controls}</div>
        </Sheet>
      )}
    </main>
  );
}
