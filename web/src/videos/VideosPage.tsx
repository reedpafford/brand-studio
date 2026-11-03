import { ProjectsChip, folderQuery, useFolderFilter, useFolders } from "../folders/Projects";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Film, Plus } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { useHeld } from "../approvals/useHeld";
import { useMe } from "../auth/useMe";
import { Banner, Button, buttonClass, EmptyState, Menu, MenuItem, PageTop, Skeleton } from "../components";
import { useRail } from "../useMedia";
import { RequestRow, VideoHead, VideoRow } from "./VideoRows";

type Project = components["schemas"]["ProjectOut"];

const load = async (brandId: number, folder: string | null, mine: boolean, archived: boolean) => {
  const { data } = await api.GET("/projects", { params: { query: { brand_id: brandId, ...folderQuery(folder), ...(mine ? { mine: true } : {}), ...(archived ? { archived: true } : {}) } } });
  if (!data) throw new Error("load");
  return data;
};

/** A group bar (v5 C_Videos): a coloured dot, the name and its count. */
function Bar({ tone, title, n }: { tone: string; title: string; n: number }) {
  return (
    <h2 className="flex items-center gap-2 border-b border-border bg-surface-2/40 px-4 py-1.5 text-xs font-semibold">
      <span aria-hidden className={`size-2 rounded-full ${tone}`} />
      {title} <span className="font-normal tabular-nums text-muted">{n}</span>
    </h2>
  );
}

/** The brand's videos (v5 C_Videos): yours (or everyone's, for Reed) in groups Needs you / Making / Done, with an editor's
 *  held sends as request rows. Project and Maker narrow it; Archived shows the archive. Everything lives in the address. */
export function VideosPage() {
  const brandId = Number(useParams().brandId);
  const { data: me } = useMe();
  const rail = useRail();
  const [params, setParams] = useSearchParams();
  const owner = me?.role === "owner";
  const archived = params.get("archived") === "1";
  const maker = Number(params.get("maker")) || null; // Reed only: an editor only ever sees their own
  const folder = useFolderFilter();
  const folders = useFolders(brandId);
  const videos = useQuery({ enabled: me !== undefined, queryKey: ["videos", { brandId, folder, mine: !owner, archived }], queryFn: () => load(brandId, folder, !owner, archived) });
  const gone = useQuery({ enabled: me !== undefined && !archived, queryKey: ["videos", { brandId, folder, mine: !owner, archived: true }], queryFn: () => load(brandId, folder, !owner, true) });
  // Held sends with no video yet: Reed sees every editor's (the rail counts them), an editor their own.
  const held = useHeld();
  // An editor's own held sends: /jobs?mine=true leaves Freestyle jobs out, so ask for them too.
  const mineHeld = useQuery({
    enabled: me !== undefined && !owner,
    queryKey: ["jobs", "mine", "freestyle"],
    refetchInterval: 15_000,
    queryFn: async () => (await api.GET("/jobs", { params: { query: { mine: true, freestyle: true } } })).data ?? [],
  });
  // A held send with no visible video yet: its project is hidden (not in /projects) or it has none. A Freestyle's brand is on
  // the freestyle (the job's own is empty). Reed sees every editor's (the rail counts them), an editor their own.
  const heldAll = owner ? held.allHeldJobs : (mineHeld.data ?? []).filter((j) => j.status === "needs_owner_approval");
  const known = new Set([...(videos.data ?? []), ...(gone.data ?? [])].map((v) => v.id));
  const asks = heldAll.filter((j) => (j.freestyle?.brand_id ?? j.brand_id) === brandId && (j.project_id == null || !known.has(j.project_id)) && (!maker || j.created_by_id === maker) && !archived && !folder);
  const heldOn = new Set(heldAll.map((j) => j.project_id));

  const set = (changes: Record<string, string>) => setParams((prev) => { const next = new URLSearchParams(prev); for (const [k, v] of Object.entries(changes)) { if (v) next.set(k, v); else next.delete(k); } return next; }, { replace: true });
  const project = (id?: number | null) => folders.data?.find((f) => f.id === id)?.name ?? "No project";
  const all = videos.data ?? [];
  const makers = [...new Map(all.map((v) => [v.created_by_id, v.created_by_name])).entries()].filter(([id]) => id != null) as [number, string][];
  const rows = all.filter((v) => !maker || v.created_by_id === maker);
  const filtered = !!(folder || maker || archived);
  const clear = () => setParams({}, { replace: true });
  const row = (v: Project) => <VideoRow key={v.id} p={v} project={project(v.folder_id)} held={heldOn.has(v.id)} owner={owner} />;
  const request = (j: (typeof asks)[number]) => <RequestRow key={`job-${j.id}`} job={j} project={project(null)} owner={owner} maker={j.created_by_name} />;
  // A video with a change waiting for the owner's OK sits with the held sends, in Needs you (for the editor too).
  const waits = (p: Project) => p.needs_you || heldOn.has(p.id);
  const needs = rows.filter(waits);
  const making = rows.filter((p) => !waits(p) && !p.finished_at);
  const done = rows.filter((p) => !waits(p) && !!p.finished_at);
  const empty = rows.length + asks.length === 0;
  const group = (title: string, tone: string, items: React.ReactNode[]) => items.length > 0 && (
    <section key={title} aria-label={title}>
      <Bar tone={tone} title={title} n={items.length} />
      <ul className="divide-y divide-border">{items}</ul>
    </section>
  );

  return (
    <main className="mx-auto max-w-content p-4 sm:p-6">
      <PageTop title="Videos">
        {!rail && ( // the phone's five tabs have no Media: it opens from here
          <Link to={`/b/${brandId}/media`} className="inline-flex min-h-control items-center gap-1 text-accent-text hover:underline">
            Media
            <ChevronRight size={20} strokeWidth={1.75} aria-hidden />
          </Link>
        )}
        {rail && ( // on a phone the bottom tabs have New
          <Link to={`/b/${brandId}/videos/new`} className={`${buttonClass("primary")} lg:min-h-9 lg:px-3`}>
            <Plus size={16} strokeWidth={1.75} aria-hidden />
            New video
          </Link>
        )}
      </PageTop>
      <div className="-mx-4 flex min-h-11 flex-wrap items-center gap-2 border-b border-border px-4 sm:-mx-6 sm:px-6 lg:h-11 [&_button]:text-[13px] [&_button]:font-medium">
        <ProjectsChip brandId={brandId} />
        {owner && (
          <Menu title="Maker" trigger={(p) => (
            <Button variant="ghost" dense trailing={ChevronDown} {...p}>
              {maker ? `Maker: ${makers.find(([id]) => id === maker)?.[1] ?? "…"}` : "Maker"}
            </Button>
          )}>
            {(close) => (
              <>
                <MenuItem checked={!maker} onClick={() => { close(); set({ maker: "" }); }}>Everyone</MenuItem>
                {makers.map(([id, name]) => <MenuItem key={id} checked={maker === id} onClick={() => { close(); set({ maker: String(id) }); }}>{name}</MenuItem>)}
              </>
            )}
          </Menu>
        )}
        {(archived || (gone.data?.length ?? 0) > 0) && (
          <Button variant="ghost" dense aria-pressed={archived} onClick={() => set({ archived: archived ? "" : "1" })}>
            {archived ? "Back to videos" : `Archived · ${gone.data?.length}`}
          </Button>
        )}
        {filtered && !empty && <Button variant="ghost" dense onClick={clear}>Clear filters</Button>}
        <span className="ml-auto hidden text-xs text-muted lg:block">Steps: Plan · Cast · Clips · Final cut</span>
      </div>
      {videos.isError && (
        <Banner tone="danger" title="Couldn't load your videos. Check your connection." action={<Button variant="secondary" onClick={() => videos.refetch()}>Try again</Button>} />
      )}
      {videos.isPending && (
        <div role="status" aria-label="Loading" className="space-y-2 pt-4">
          {[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-14" />)}
        </div>
      )}
      {videos.data &&
        (empty ? (
          <div className="pt-4">
            {filtered ? (
              <EmptyState icon={Film} title="Nothing matches these filters." action={<Button variant="ghost" onClick={clear}>Clear filters</Button>} />
            ) : (
              <EmptyState icon={Film} title={owner ? "No videos yet." : "You haven't started a video yet."} action={<Link to={`/b/${brandId}/scripts`} className="inline-flex min-h-control items-center text-accent-text hover:underline">Show scripts</Link>}>
                {owner ? "Videos made from your scripts show up here." : "Pick a version that's Ready to make."}
              </EmptyState>
            )}
          </div>
        ) : (
          <div role="status" className="-mx-4 sm:-mx-6">
            <span className="sr-only">{rows.length + asks.length} videos</span>
            <VideoHead />
            {archived ? group("Archived", "bg-muted", rows.map(row)) : (
              <>
                {group("Needs you", "bg-warning", [...asks.map(request), ...needs.map(row)])}
                {group("Making", "bg-accent", making.map(row))}
                {group("Done", "bg-success", done.map(row))}
              </>
            )}
          </div>
        ))}
    </main>
  );
}
