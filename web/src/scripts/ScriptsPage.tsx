import { ProjectsChip, folderQuery, useFolderFilter, useFolders } from "../folders/Projects";
import { useEffect, useState } from "react";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, FileText, Layers } from "lucide-react";
import { BulkCreate } from "./BulkCreate";
import { VersionPanel } from "./VersionPanel";
import { useParams, useSearchParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import { useToast } from "../toast";
import type { components } from "../api/schema";
import { ImportReelLink, NewScriptButton } from "./NewScriptButton";
import { Banner, Button, EmptyState, Skeleton } from "../components";
import { useMe } from "../auth/useMe";
import { useReferences } from "../projects/BriefPickers";
import { useBrands } from "../shell/useBrands";
import { ActionBar } from "../shell/ActionBar";
import { useRail } from "../useMedia";
import { toTarget, useDeleteScript, useMayDelete } from "./DeleteScript";
import { LegacyVideos, useProjectList } from "../projects/LegacyVideos";
import { beingMade, useDebounced } from "./status";
import { ScriptRow, waitingOn, type Row } from "./list/ScriptRow";
import { ProjectGroups, ScriptTable } from "./list/ScriptTable";
import { ScriptFilters, StageTabs } from "./list/ScriptFilters";
import { BulkBar } from "./list/BulkBar";

type Version = Row["versions"][number];
type Project = components["schemas"]["ProjectOut"];

const PAGE = 30;

/** The brand's home: every script as a table row, in stage tabs, grouped by project. Filters live in the address so a view can be shared. */
export function ScriptsPage() {
  const brandId = Number(useParams().brandId);
  const { data: brands } = useBrands();
  const { data: me } = useMe();
  const rail = useRail();
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
  // An editor starts on what is ready to make; Reed on everything.
  const status = params.get("status") ?? (owner ? "" : "published");
  const removed = params.get("removed") === "1"; // only scripts that were deleted or archived
  const apiStatus = removed || status === "any" ? "" : status;
  const len = params.get("len") ?? "";
  const ref = params.get("ref") ?? "";
  const left = params.get("left") ?? "";
  const mine = params.get("mine") === "1";
  const all = owner && params.get("brand") === "all";
  const sort = params.get("sort") ?? "";
  const [text, setText] = useState(params.get("q") ?? "");
  const q = useDebounced(text.trim());
  const [bulk, setBulk] = useState(false);
  useEffect(() => set("q", q), [q]); // eslint-disable-line react-hooks/exhaustive-deps
  const [lo, hi] = len ? len.split("-") : ["", ""];
  const refs = useReferences();

  // "Mine" and "Versions left: None" aren't asked of the server, so they are applied to what came back: then one page holds everything.
  const folder = useFolderFilter(); // a project picked in the Projects list (flows OR1)
  const clientSide = mine || left === "0";
  const pageSize = clientSide ? 200 : PAGE;
  // What every list and stage count asks, besides status and the page.
  const ask = {
    ...(all ? {} : { brand_id: brandId }),
    ...folderQuery(folder),
    ...(q ? { q } : {}),
    ...(ref === "none" ? { reference: false } : ref ? { reference_id: ref } : {}),
    ...(left === "1" ? { versions_left: 1 } : {}),
    ...(lo ? { min_seconds: Number(lo) } : {}),
    ...(hi ? { max_seconds: Number(hi) } : {}),
  };
  const scripts = useInfiniteQuery({
    queryKey: ["scripts", { brandId: all ? null : brandId, removed, status: apiStatus, q, ref, left, lo, hi, sort, pageSize, folder }],
    initialPageParam: 0,
    queryFn: async ({ pageParam }) => {
      const { data, response } = await api.GET("/scripts", {
        params: { query: { ...ask, ...(removed ? { removed: true } : {}), ...(apiStatus ? { status: apiStatus } : {}), ...(sort === "newest" || sort === "title" ? { sort } : {}), limit: pageSize, offset: pageParam } },
      });
      if (!data) throw new Error("load");
      const total = Number(response.headers.get("X-Total-Count"));
      return { items: data, total: Number.isFinite(total) && total > 0 ? total : data.length, offset: pageParam };
    },
    getNextPageParam: (last) => (last.offset + last.items.length < last.total && last.items.length > 0 ? last.offset + last.items.length : undefined),
  });
  const loaded = scripts.data?.pages.flatMap((p) => p.items);

  // An editor's own unpublished scripts, whatever the filters say: the main list asks for Ready to make, which leaves them out.
  const myDraftRows = useQuery({
    enabled: !owner && me !== undefined,
    queryKey: ["scripts", "my-drafts", all ? null : brandId],
    queryFn: async () => (await api.GET("/scripts", { params: { query: { ...(all ? {} : { brand_id: brandId }), status: "draft" } } })).data ?? [],
  });

  // The versions an editor has reserved and not finished: the main list asks for Ready to make, which would drop a script once they start its last version.
  const makingRows = useQuery({
    enabled: !owner && me !== undefined,
    queryKey: ["scripts", "making-now", all ? null : brandId],
    queryFn: async () => (await api.GET("/scripts", { params: { query: { ...(all ? {} : { brand_id: brandId }), status: "in_production" } } })).data ?? [],
  });

  // Filters the server doesn't take are applied here.
  let rows = loaded ?? [];
  // A script with one version started and another still ready is "in production" to the server, so Ready to make drops it; an editor still needs it here.
  if (!owner && !removed && status === "published" && !(q || len || ref || left || mine || all)) {
    const ready = (makingRows.data ?? []).filter((r) => r.versions.some((v) => v.status === "approved") && !rows.some((x) => x.id === r.id));
    // Keep the order the person asked for: by title for Title A–Z, otherwise newest first.
    if (ready.length > 0) rows = [...rows, ...ready].sort((a, b) => (sort === "title" ? a.title.localeCompare(b.title) : b.created_at.localeCompare(a.created_at)));
  }
  if (mine) rows = rows.filter((r) => r.created_by_id === me?.id);
  if (left === "0") rows = rows.filter((r) => r.versions_left === 0);
  const count = clientSide ? rows.length : Math.max(scripts.data?.pages[0]?.total ?? 0, rows.length);
  const filtered = removed || status !== (owner ? "" : "published") || !!(q || len || ref || left || mine || all);
  const clear = () => {
    setText("");
    setPicked(new Set());
    setParams({}, { replace: true });
  };
  const refName = (id: string | null) => refs.data?.find((r) => r.id === id)?.name;
  const active = [removed, !!len, !!ref, !!left, mine, all, !!sort].filter(Boolean).length;

  // Picking: Reed's scripts and an editor's own, for Move to project and Archive.
  const mayPick = (r: Row) => !removed && (owner || r.created_by_id === me?.id);
  const pick = (id: number, on: boolean) => setPicked((was) => { const next = new Set(was); if (on) next.add(id); else next.delete(id); return next; });
  const pickedRows = rows.filter((r) => picked.has(r.id) && mayPick(r));

  const row = (r: Row) => (
    <ScriptRow
      key={r.id}
      row={r}
      mayOpen={!removed && (r.published || owner || r.created_by_id === me?.id)}
      ownScript={owner || r.created_by_id === me?.id}
      brandName={all ? brands?.find((b) => b.id === r.brand_id)?.name : undefined}
      refName={r.reference_name ?? refName(r.reference_id)}
      refThumb={!!r.reference_id && !!refs.data?.find((x) => x.id === r.reference_id)?.has_thumbnail}
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
  );
  const newScript = (
    <>
      <ImportReelLink brandId={brandId} />
      <NewScriptButton brandId={brandId} />
    </>
  );
  const myMaking = removed ? [] : (makingRows.data ?? []).filter((r) => r.versions.some((v) => beingMade(v.status) && v.editor?.id === me?.id));
  const myDrafts = removed ? [] : (myDraftRows.data ?? []).filter((r) => r.created_by_id === me?.id);

  return (
    <main className="mx-auto max-w-content space-y-4 p-4 sm:p-6">
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="type-eyebrow text-muted">{brand?.name}</p>
          <h1 className="type-page">Scripts</h1>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" icon={Layers} onClick={() => setBulk(true)} aria-label={rail ? undefined : "Bulk create"}>
            {rail ? "Bulk create" : ""}
          </Button>
          {rail && newScript}
        </div>
      </div>
      {bulk && <BulkCreate brandId={brandId} onClose={() => setBulk(false)} />}
      {!rail && <ActionBar phone><div className="flex gap-2">{newScript}</div></ActionBar>}
      <StageTabs status={removed ? "removed" : status} owner={owner} ask={ask} onPick={(s) => setParams((prev) => { const next = new URLSearchParams(prev); next.delete("removed"); if (s === (owner ? "" : "published")) next.delete("status"); else next.set("status", s); return next; }, { replace: true })} />
      <div className="flex flex-wrap items-end gap-3">
        <ProjectsChip brandId={brandId} />
      </div>
      <ScriptFilters rail={rail} owner={owner} text={text} onText={setText} f={{ len, ref, left, mine, removed, all, sort }} set={set} filtered={filtered} active={active} clear={clear} />
      {scripts.isError && (
        <Banner title="Couldn't load your scripts." action={<Button variant="secondary" onClick={() => void scripts.refetch()}>Try again</Button>}>
          Check your connection.
        </Banner>
      )}
      {scripts.isPending && (
        <div className="space-y-2" aria-label="Loading">
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-14" />
          ))}
        </div>
      )}
      {loaded && (
        <>
          {myMaking.length > 0 && (
            <section aria-label="Making now" className="space-y-2">
              <h2 className="type-section">Making now</h2>
              <ScriptTable rows={myMaking} row={row} />
            </section>
          )}
          {myDrafts.length > 0 && (
            <section aria-label="Your drafts" className="space-y-2">
              <h2 className="type-section">Your drafts</h2>
              <ScriptTable rows={myDrafts} row={row} />
            </section>
          )}
          {rows.length === 0 && removed && (
            <EmptyState icon={Archive} title="Nothing deleted or archived." action={<Button variant="ghost" onClick={() => set("removed", "")}>Show all scripts</Button>} />
          )}
          {rows.length === 0 && !filtered && (
            <EmptyState icon={FileText} title={owner ? `No scripts for ${brand?.name ?? "this brand"} yet.` : "No scripts ready to make yet."}>
              {owner ? "Write a script once and make up to three videos from it." : "The owner publishes scripts here. You can also write your own."}
            </EmptyState>
          )}
          {rows.length === 0 && filtered && !removed && (
            <div className="flex items-center gap-3">
              <p className="text-muted">Nothing matches these filters.</p>
              <Button variant="ghost" onClick={clear}>
                Clear filters
              </Button>
            </div>
          )}
          {rows.length > 0 && (
            <>
              <p className="text-sm text-muted">{`${count} script${count === 1 ? "" : "s"}`}</p>
              {folder || all || removed ? <ScriptTable rows={rows} row={row} /> : <ProjectGroups rows={rows} folders={folders.data} row={row} />}
              {scripts.hasNextPage && (
                <Button variant="secondary" busy={scripts.isFetchingNextPage} onClick={() => void scripts.fetchNextPage()}>
                  Show more
                </Button>
              )}
            </>
          )}
          {pickedRows.length > 0 && <BulkBar brandId={brandId} picked={pickedRows} mayArchive={pickedRows.every(mayDelete)} onDone={() => setPicked(new Set())} />}
        </>
      )}
      <LegacyVideos brandId={brandId} />
      {del.dialog}
      {making && <VersionPanel scriptId={Number(making[1])} slot={Number(making[2])} brandId={brandId} onClose={() => set("make", "")} />}
    </main>
  );
}
