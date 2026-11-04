import { ProjectsChip, folderQuery, useFolderFilter } from "../folders/Projects";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Film, Plus, Search } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { useMe } from "../auth/useMe";
import { Banner, Button, EmptyState, PageTop, Skeleton, Tabs, buttonClass } from "../components";
import { useDebounced } from "../scripts/status";
import { useRail } from "../useMedia";
import { VideoTable, type MadeFrom } from "./VideoRows";

type Project = components["schemas"]["ProjectOut"];
type Ask = { brandId: number; q: string; mine: boolean; status: "" | "making" | "done" | "needs_you"; archived: boolean; folder: string | null };

const load = async ({ brandId, q, mine, status, archived, folder }: Ask) => {
  const { data } = await api.GET("/projects", { params: { query: { brand_id: brandId, ...folderQuery(folder), ...(q ? { q } : {}), ...(mine ? { mine: true } : {}), ...(status ? { status } : {}), ...(archived ? { archived: true } : {}) } } });
  if (!data) throw new Error("load");
  return data;
};

// The groups with no tab picked (audit M6): what waits on you, what's being made, what's done.
const needsYou = (p: Project) => p.needs_you;
const making = (p: Project) => !p.needs_you && !p.finished_at;
const done = (p: Project) => !p.needs_you && !!p.finished_at;

/** The brand's videos as a table: yours (or everyone's, for Reed), in tabs All · Needs you · Making · Done · Archived,
 *  with search and Mine. Everything lives in the address. */
export function VideosPage() {
  const brandId = Number(useParams().brandId);
  const { data: me } = useMe();
  const rail = useRail();
  const [params, setParams] = useSearchParams();
  const owner = me?.role === "owner";
  const set = (changes: Record<string, string>) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        for (const [key, value] of Object.entries(changes)) {
          if (value) next.set(key, value);
          else next.delete(key);
        }
        return next;
      },
      { replace: true },
    );
  const asked = params.get("status");
  const status = asked === "making" || asked === "done" || asked === "needs_you" ? asked : "";
  const archived = params.get("archived") === "1";
  const mine = !owner || params.get("mine") === "1"; // an editor only ever sees their own
  const folder = useFolderFilter(); // a project picked in the Projects list (flows OR1)
  const [text, setText] = useState(params.get("q") ?? "");
  const q = useDebounced(text.trim());
  useEffect(() => set({ q }), [q]); // eslint-disable-line react-hooks/exhaustive-deps

  const ask = { brandId, q, mine, folder };
  const videos = useQuery({ enabled: me !== undefined, queryKey: ["videos", { ...ask, status, archived }], queryFn: () => load({ ...ask, status, archived }) });
  // The tabs' counts: every live video (the same ask as All, so it is one request there), and the archived ones.
  const live = useQuery({ enabled: me !== undefined, queryKey: ["videos", { ...ask, status: "", archived: false }], queryFn: () => load({ ...ask, status: "", archived: false }) });
  const gone = useQuery({ enabled: me !== undefined, queryKey: ["videos", { ...ask, status: "", archived: true }], queryFn: () => load({ ...ask, status: "", archived: true }) });
  // Which script and version each video was made from: the scripts list names them (a video only knows its script's id).
  const scripts = useQuery({ queryKey: ["scripts", "made-from", brandId], queryFn: async () => (await api.GET("/scripts", { params: { query: { brand_id: brandId, limit: 200 } } })).data ?? [] });
  const madeFrom = new Map<number, MadeFrom>();
  for (const s of scripts.data ?? []) for (const v of s.versions) if (v.project_id) madeFrom.set(v.project_id, { scriptId: s.id, title: s.title, slot: v.slot });

  const filtered = !!(q || status || archived || (owner && mine));
  const clear = () => {
    setText("");
    setParams({}, { replace: true });
  };
  const rows = videos.data ?? [];
  const all = live.data ?? [];
  const tab = archived ? "archived" : status || "all";
  const tabs = [
    { id: "all", label: "All", count: live.data ? all.length : undefined },
    { id: "needs_you", label: "Needs you", count: live.data ? all.filter(needsYou).length : undefined },
    { id: "making", label: "Making", count: live.data ? all.filter(making).length : undefined },
    { id: "done", label: "Done", count: live.data ? all.filter(done).length : undefined },
    { id: "archived", label: "Archived", count: gone.data?.length },
  ];
  const groups: [string, Project[]][] =
    status || archived
      ? [["", rows]]
      : ([
          ["Needs you", rows.filter(needsYou)],
          ["Making", rows.filter(making)],
          ["Done", rows.filter(done)],
        ] as [string, Project[]][]).filter(([, ps]) => ps.length > 0);

  return (
    <main className="mx-auto max-w-content space-y-4 p-4 sm:p-6">
      {/* v5 C_Videos: "Videos" and the one primary, + New video, in the flush 52 px bar. */}
      <PageTop title="Videos">
        {!rail && ( // the phone's five tabs have no Media: it opens from here
          <Link to={`/b/${brandId}/media`} className="inline-flex min-h-control items-center gap-1 text-accent-text hover:underline">
            Media
            <ChevronRight size={20} strokeWidth={1.75} aria-hidden />
          </Link>
        )}
        {rail && (
          <Link to={`/b/${brandId}/videos/new`} className={`${buttonClass("primary")} lg:min-h-control-dense lg:px-3`}>
            <Plus size={16} strokeWidth={1.75} aria-hidden />
            New video
          </Link>
        )}
      </PageTop>
      <Tabs label="Status" tabs={tabs} value={tab} onChange={(id) => set({ status: id === "all" || id === "archived" ? "" : id, archived: id === "archived" ? "1" : "" })} />
      <div className="flex flex-wrap items-center gap-3">
        <label className="relative block w-full sm:w-[320px]">
          <span className="sr-only">Search videos</span>
          <Search size={16} strokeWidth={1.75} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input type="search" value={text} onChange={(e) => setText(e.target.value)} placeholder="Search videos" className="min-h-control w-full rounded-md border border-border-strong bg-surface pl-9 pr-3 text-base text-text placeholder:text-muted" />
        </label>
        <ProjectsChip brandId={brandId} />
        {owner && (
          <Button variant={mine ? "primary" : "secondary"} dense aria-pressed={mine} onClick={() => set({ mine: mine ? "" : "1" })}>
            Mine
          </Button>
        )}
        {filtered && rows.length > 0 && (
          <Button variant="ghost" dense onClick={clear}>
            Clear filters
          </Button>
        )}
      </div>
      {videos.isError && (
        <Banner tone="danger" title="Couldn't load your videos. Check your connection." action={<Button variant="secondary" onClick={() => videos.refetch()}>Try again</Button>} />
      )}
      {videos.isPending && (
        <div role="status" aria-label="Loading" className="space-y-2">
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-14" />
          ))}
        </div>
      )}
      {videos.data && (
        <>
          <p className="text-sm text-muted tabular-nums" role="status">
            {`${rows.length} video${rows.length === 1 ? "" : "s"}`}
          </p>
          {rows.length === 0 ? (
            filtered ? (
              <EmptyState icon={Film} title="Nothing matches these filters." action={<Button variant="ghost" onClick={clear}>Clear filters</Button>} />
            ) : (
              <EmptyState icon={Film} title={owner ? "No videos yet." : "You haven't started a video yet."} action={<Link to={`/b/${brandId}/scripts`} className="inline-flex min-h-control items-center text-accent-text hover:underline">Show scripts</Link>}>
                {owner ? "Videos made from your scripts show up here." : "Pick a version that's Ready to make."}
              </EmptyState>
            )
          ) : (
            groups.map(([title, ps]) => (
              <section key={title} aria-label={title || undefined} className="space-y-2">
                {title && (
                  <h2 className="type-section">
                    {title} <span className="font-normal text-muted tabular-nums">· {ps.length}</span>
                  </h2>
                )}
                <VideoTable rows={ps} madeFrom={madeFrom} />
              </section>
            ))
          )}
        </>
      )}
    </main>
  );
}
