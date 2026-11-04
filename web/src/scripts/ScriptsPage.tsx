import { ProjectsChip, folderQuery, useFolderFilter, useFolders } from "../folders/Projects";
import { useEffect, useState } from "react";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, Ellipsis, FileText, Search } from "lucide-react";
import { BulkCreate } from "./BulkCreate";
import { VersionPanel } from "./VersionPanel";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import { useToast } from "../toast";
import type { components } from "../api/schema";
import { ImportReelLink, NewScriptButton } from "./NewScriptButton";
import { Banner, Button, EmptyState, Menu, MenuItem, PageTop, Skeleton, buttonClass } from "../components";
import { useMe } from "../auth/useMe";
import { useBrands } from "../shell/useBrands";
import { ActionBar } from "../shell/ActionBar";
import { useRail } from "../useMedia";
import { toTarget, useDeleteScript, useMayDelete } from "./DeleteScript";
import { LegacyVideos, useProjectList } from "../projects/LegacyVideos";
import { beingMade, useDebounced } from "./status";
import { EditorRow, ScriptRow, waitingOn, type Row } from "./list/ScriptRow";
import { ProjectGroups, ScriptTable } from "./list/ScriptTable";
import { StageTabs } from "./list/ScriptFilters";
import { BulkBar } from "./list/BulkBar";
import { MakeVideoPanel } from "./MakeVideoPanel";
import { finished } from "../freestyle/FromScript";
import { directed } from "../freestyle/useFreestyle";
import { lookName, useLooks } from "./Looks";

type Version = Row["versions"][number];
type Project = components["schemas"]["ProjectOut"];

const PAGE = 30;
const SORTS = [
  ["", "Updated"],
  ["newest", "Newest"],
  ["title", "Title A–Z"],
] as const;

/** A quiet menu press in the stage band: "Sort: Updated ▾" (v5 C_Scripts). */
function BandMenu({ label, value, options, onPick }: { label: string; value: string; options: readonly (readonly [string, string])[]; onPick: (v: string) => void }) {
  const name = options.find(([v]) => v === value)?.[1] ?? options[0][1];
  return (
    <Menu
      title={label}
      align="right"
      trigger={(p) => (
        <Button {...p} variant="ghost" dense className="text-muted!">
          {label}: {name} ▾
        </Button>
      )}
    >
      {(close) =>
        options.map(([v, l]) => (
          <MenuItem key={v} onClick={() => { close(); onPick(v); }}>
            {l}
          </MenuItem>
        ))
      }
    </Menu>
  );
}

/** The brand's scripts (v5 C_Scripts for the owner, E_EditorScripts for an editor): stage tabs, then the table. The owner's
 *  is grouped by project with a selection bar; an editor's lists what can be made, each with Make a video. Filters live in
 *  the address so a view can be shared. */
export function ScriptsPage() {
  const brandId = Number(useParams().brandId);
  const { data: brands } = useBrands();
  const { data: me } = useMe();
  const rail = useRail();
  const looks = useLooks().data;
  const [params, setParams] = useSearchParams();
  const brand = brands?.find((b) => b.id === brandId);
  const owner = me?.role === "owner";
  const set = (key: string, value: string) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (value) next.set(key, value);
        else next.delete(key);
        return next;
      },
      { replace: true },
    );
  const panelTo = (id: number, slot: number) => `?${new URLSearchParams({ ...Object.fromEntries(params), make: `${id}.${slot}` })}`;
  const videos = useProjectList(brandId);
  const videoById = new Map<number, Project>((videos.data ?? []).map((p) => [p.id, p]));
  const folders = useFolders(brandId);
  const mayDelete = useMayDelete();
  const del = useDeleteScript();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [restoring, setRestoring] = useState<number | null>(null);
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const restore = async (r: Row) => {
    setRestoring(r.id);
    const { error, response } = await api.POST("/scripts/{script_id}/restore", { params: { path: { script_id: r.id } } });
    setRestoring(null);
    if (!response.ok) return toast(errorText(error), undefined, "error");
    await queryClient.invalidateQueries({ queryKey: ["scripts"] });
    toast(`Restored "${r.title}".`);
  };
  const ownVideo = (v: Version) => !!v.project_id && (owner || v.editor?.id === me?.id || videoById.get(v.project_id)?.created_by_id === me?.id);
  const making = /^(\d+)\.(\d+)$/.exec(params.get("make") ?? "");
  // An editor starts on what is ready to make; the owner on everything.
  const status = params.get("status") ?? (owner ? "" : "published");
  const removed = params.get("removed") === "1"; // only scripts that were deleted or archived
  const apiStatus = removed || status === "any" ? "" : status;
  const all = owner && params.get("brand") === "all";
  const flat = params.get("group") === "none";
  const sort = params.get("sort") ?? "";
  const [text, setText] = useState(params.get("q") ?? "");
  const q = useDebounced(text.trim());
  const [bulk, setBulk] = useState(false);
  useEffect(() => set("q", q), [q]); // eslint-disable-line react-hooks/exhaustive-deps

  const folder = useFolderFilter(); // a project picked in the Projects list (flows OR1)
  // What every list and stage count asks, besides status and the page.
  const ask = { ...(all ? {} : { brand_id: brandId }), ...folderQuery(folder), ...(q ? { q } : {}) };
  const scripts = useInfiniteQuery({
    queryKey: ["scripts", { brandId: all ? null : brandId, removed, status: apiStatus, q, sort, folder }],
    initialPageParam: 0,
    queryFn: async ({ pageParam }) => {
      const { data, response } = await api.GET("/scripts", {
        params: { query: { ...ask, ...(removed ? { removed: true } : {}), ...(apiStatus ? { status: apiStatus } : {}), ...(sort === "newest" || sort === "title" ? { sort } : {}), limit: PAGE, offset: pageParam } },
      });
      if (!data) throw new Error("load");
      const total = Number(response.headers.get("X-Total-Count"));
      return { items: data, total: Number.isFinite(total) && total > 0 ? total : data.length, offset: pageParam };
    },
    getNextPageParam: (last) => (last.offset + last.items.length < last.total && last.items.length > 0 ? last.offset + last.items.length : undefined),
  });
  // A script with one version started and another still ready is "in production" to the server, so Ready to make drops
  // it; an editor still needs it there.
  const makingRows = useQuery({
    enabled: !owner && me !== undefined && status === "published" && !removed,
    queryKey: ["scripts", "making-now", all ? null : brandId, q, folder],
    queryFn: async () => (await api.GET("/scripts", { params: { query: { ...ask, status: "in_production" } } })).data ?? [],
  });
  let rows = scripts.data?.pages.flatMap((p) => p.items) ?? [];
  const stillReady = (makingRows.data ?? []).filter((r) => r.versions.some((v) => v.status === "approved") && !rows.some((x) => x.id === r.id));
  if (!owner && status === "published" && stillReady.length > 0) rows = [...rows, ...stillReady].sort((a, b) => (sort === "title" ? a.title.localeCompare(b.title) : b.created_at.localeCompare(a.created_at)));
  const loaded = !!scripts.data;
  const filtered = removed || !!q || !!folder || status !== (owner ? "" : "published");
  const clear = () => {
    setText("");
    setPicked(new Set());
    setParams({}, { replace: true });
  };

  // Picking: the owner's scripts and an editor's own, for Move to project and Archive.
  const mayPick = (r: Row) => !removed && (owner || r.created_by_id === me?.id);
  const pick = (id: number, on: boolean) => setPicked((was) => { const next = new Set(was); if (on) next.add(id); else next.delete(id); return next; });
  const pickedRows = rows.filter((r) => picked.has(r.id) && mayPick(r));

  const row = (r: Row) =>
    owner ? (
      <ScriptRow
        key={r.id}
        row={r}
        mayOpen={!removed}
        ownScript
        brandName={all ? brands?.find((b) => b.id === r.brand_id)?.name : undefined}
        narrow={!rail}
        panelTo={panelTo}
        ownVideo={ownVideo}
        meId={me?.id}
        waiting={removed ? "" : waitingOn(r, videoById, me?.id)}
        onDelete={!removed && mayDelete(r) ? () => del.ask(toTarget(r)) : undefined}
        removed={removed}
        onRestore={() => void restore(r)}
        restoring={restoring === r.id}
        selected={picked.has(r.id)}
        onSelect={mayPick(r) ? (on) => pick(r.id, on) : undefined}
      />
    ) : (
      <EditorRow
        key={r.id}
        row={r}
        project={folders.data?.find((f) => f.id === r.folder_id)?.name ?? "No project"}
        look={lookName(looks, r.look)}
        video={r.versions.some((v) => beingMade(v.status) && !!v.project_id)}
        onMakeVideo={directed(r.kind) && r.versions.some((v) => finished(v) && !v.project_id) ? () => set("video", String(r.id)) : undefined}
        onDelete={mayDelete(r) ? () => del.ask(toTarget(r)) : undefined}
      />
    );
  const presses = owner ? (
    <>
      <ImportReelLink brandId={brandId} />
      <NewScriptButton brandId={brandId} />
    </>
  ) : (
    <>
      <Link to={`/b/${brandId}/videos/new?from=script`} className={buttonClass("secondary")}>
        New video from a script
      </Link>
      {/* Editors write their own scripts too (rule 5); the board's page top leaves it out, so it stays here. */}
      <NewScriptButton brandId={brandId} />
    </>
  );
  const pickStage = (s: string) =>
    setParams((prev) => { const next = new URLSearchParams(prev); next.delete("removed"); if (s === (owner ? "" : "published")) next.delete("status"); else next.set("status", s); return next; }, { replace: true });
  const search = (
    <label className="relative block w-full sm:w-60">
      <span className="sr-only">Search scripts</span>
      <Search size={16} strokeWidth={1.75} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
      <input type="search" value={text} onChange={(e) => setText(e.target.value)} placeholder="Search scripts" className="min-h-control w-full rounded-md border border-border bg-bg pl-9 pr-3 text-sm text-text placeholder:text-muted lg:min-h-control-dense" />
    </label>
  );
  // What the board leaves out stays reachable from here: removed scripts, Bulk create, every brand at once.
  const more = (
    <Menu
      title="More for scripts"
      align="right"
      trigger={(p) => (
        <button type="button" {...p} aria-label="More for scripts" className="grid size-control place-items-center rounded-md text-muted hover:bg-surface-2 lg:size-control-dense">
          <Ellipsis size={18} strokeWidth={1.75} aria-hidden />
        </button>
      )}
    >
      {(close) => (
        <>
          <MenuItem onClick={() => { close(); set("removed", removed ? "" : "1"); }}>
            <Archive size={20} strokeWidth={1.75} aria-hidden />
            {removed ? "Show all scripts" : "Deleted and archived"}
          </MenuItem>
          <MenuItem onClick={() => { close(); setBulk(true); }}>Bulk create</MenuItem>
          <MenuItem onClick={() => { close(); set("brand", all ? "" : "all"); }}>{all ? "This brand only" : "All brands"}</MenuItem>
        </>
      )}
    </Menu>
  );

  return (
    <main className={`mx-auto max-w-content space-y-0 p-4 sm:p-6 ${rail ? "" : "pb-28"}`}>
      <PageTop title="Scripts">{rail && presses}</PageTop>
      {!rail && (
        <ActionBar phone>
          <div className="flex gap-2 [&>*]:min-w-0 [&>*]:flex-1 [&_a]:w-full [&_button]:w-full">{presses}</div>
        </ActionBar>
      )}
      {bulk && <BulkCreate brandId={brandId} onClose={() => setBulk(false)} />}
      <div className="-mx-4 flex min-h-11 flex-wrap items-center gap-x-2 gap-y-2 border-b border-border px-4 py-1.5 sm:-mx-6 sm:px-6">
        <StageTabs status={removed ? "removed" : status} owner={owner} ask={ask} onPick={pickStage} />
        <span className="hidden flex-1 lg:block" />
        {owner ? (
          <div className="flex flex-wrap items-center gap-1">
            <ProjectsChip brandId={brandId} />
            <BandMenu label="Group" value={flat ? "none" : ""} options={[["", "Project"], ["none", "None"]]} onPick={(v) => set("group", v)} />
            <BandMenu label="Sort" value={sort} options={SORTS} onPick={(v) => set("sort", v)} />
            {more}
          </div>
        ) : (
          search
        )}
      </div>
      {removed && (
        <div className="flex flex-wrap items-center gap-3 py-3">
          <Button variant="secondary" dense icon={Archive} aria-pressed onClick={() => set("removed", "")}>
            Deleted and archived
          </Button>
          <p className="text-sm text-muted">Restore brings a script back.</p>
        </div>
      )}
      {pickedRows.length > 0 && <BulkBar brandId={brandId} picked={pickedRows} mayArchive={pickedRows.every(mayDelete)} onDone={() => setPicked(new Set())} />}
      {scripts.isError && (
        <div className="pt-4">
          <Banner title="Couldn't load your scripts." action={<Button variant="secondary" onClick={() => void scripts.refetch()}>Try again</Button>}>
            Check your connection.
          </Banner>
        </div>
      )}
      {scripts.isPending && (
        <div className="space-y-2 pt-4" aria-label="Loading">
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-11" />
          ))}
        </div>
      )}
      {loaded && (
        <>
          {rows.length === 0 && removed && (
            <EmptyState icon={Archive} title="Nothing deleted or archived." action={<Button variant="ghost" onClick={() => set("removed", "")}>Show all scripts</Button>} />
          )}
          {rows.length === 0 && !filtered && (
            <EmptyState icon={FileText} title={owner ? `No scripts for ${brand?.name ?? "this brand"} yet.` : "Nothing ready to make yet."} action={owner ? <NewScriptButton brandId={brandId} /> : undefined}>
              {owner ? "Write a script once and make up to three videos from it." : "Scripts the owner finishes show up here, ready to make."}
            </EmptyState>
          )}
          {rows.length === 0 && filtered && !removed && (
            <div className="flex items-center gap-3 py-4">
              <p className="text-muted">Nothing matches these filters.</p>
              <Button variant="ghost" onClick={clear}>
                Clear filters
              </Button>
            </div>
          )}
          {rows.length > 0 && (owner && !(folder || all || removed || flat) ? <ProjectGroups rows={rows} folders={folders.data} row={row} /> : <ScriptTable rows={rows} row={row} editor={!owner} />)}
          {scripts.hasNextPage && (
            <div className="pt-3">
              <Button variant="secondary" busy={scripts.isFetchingNextPage} onClick={() => void scripts.fetchNextPage()}>
                Show more
              </Button>
            </div>
          )}
          {!owner && <p className="py-4 text-xs text-muted">Any version can become a video; publishing isn't needed. The owner approves each video before anything is spent.</p>}
        </>
      )}
      {owner && <div className="pt-6"><LegacyVideos brandId={brandId} /></div>}
      {del.dialog}
      {making && <VersionPanel scriptId={Number(making[1])} slot={Number(making[2])} brandId={brandId} onClose={() => set("make", "")} />}
      {Number(params.get("video")) > 0 && <MakeVideoPanel scriptId={Number(params.get("video"))} onClose={() => set("video", "")} />}
    </main>
  );
}
