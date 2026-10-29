import { ProjectsChip, folderQuery, useFolderFilter } from "../folders/Projects";
import { useEffect, useState } from "react";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, Check, CircleAlert, Clock, FileText, Layers, Pencil, Search } from "lucide-react";
import { BulkCreate } from "./BulkCreate";
import { isNarrated } from "./flow";
import { VersionPanel } from "./VersionPanel";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, errorText } from "../api/client";
import { useToast } from "../toast";
import { fileUrl } from "../api/upload";
import type { components } from "../api/schema";
import { ImportReelLink, NewScriptButton } from "./NewScriptButton";
import { Badge, Banner, Button, Card, EmptyState, Select, Sheet, Skeleton, type Tone } from "../components";
import { useMe } from "../auth/useMe";
import { useReferences } from "../projects/BriefPickers";
import { useBrands } from "../shell/useBrands";
import { ActionBar } from "../shell/ActionBar";
import { useRail } from "../useMedia";
import { ScriptMenu, toTarget, useDeleteScript, useMayDelete } from "./DeleteScript";
import { ReelChip } from "./ReelImport";
import { LegacyVideos, useProjectList } from "../projects/LegacyVideos";
import { serverTime } from "../time";

type Row = components["schemas"]["ScriptRow"];
type Version = Row["versions"][number];

const PAGE = 30;
const LETTER = ["A", "B", "C"];

/** A version's status in words, with a tone as the second signal. Never an internal word. */
/** A version someone has started and not finished: its words are being made into a video. */
export const beingMade = (status: string) => status === "in_production" || status === "clips_ready";

export const STATUS: Record<string, { label: string; tone: Tone; icon?: typeof Check }> = {
  draft: { label: "Writing", tone: "neutral", icon: Pencil },
  approved: { label: "Ready to make", tone: "accent" },
  in_production: { label: "In production", tone: "warning", icon: Clock },
  clips_ready: { label: "In production", tone: "warning", icon: Clock },
  done: { label: "Finished", tone: "success", icon: Check },
  failed: { label: "Didn't finish", tone: "danger", icon: CircleAlert },
};

const STATUS_FILTER = [
  ["", "Any"],
  ["draft", "Writing"],
  ["published", "Ready to make"],
  ["in_production", "In production"],
  ["done", "Finished"],
] as const;
const LENGTH_FILTER = [
  ["", "Any"],
  ["0-15", "Under 15 s"],
  ["15-30", "15–30 s"],
  ["30-60", "30–60 s"],
  ["60-", "Over 60 s"],
] as const;
const SORTS = [
  ["", "Recently changed"],
  ["newest", "Newest"],
  ["title", "Title A–Z"],
] as const;

/** "just now", "5 min ago", "3 h ago", "yesterday", "2 days ago", then the date. */
export function age(iso: string, now = Date.now()) {
  const mins = Math.max(0, Math.floor((now - serverTime(iso).getTime()) / 60_000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "yesterday";
  if (days < 7) return `${days} days ago`;
  return serverTime(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

const lengthText = (versions: Version[]) => {
  const s = versions.map((v) => v.seconds).filter((n) => n > 0);
  if (s.length === 0) return "Length set at Breakdown";
  const lo = Math.round(Math.min(...s));
  const hi = Math.round(Math.max(...s));
  return lo === hi ? `about ${lo} s` : `about ${lo}–${hi} s`;
};

export function useDebounced<T>(value: T, ms = 300) {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return settled;
}

/** The brand's home: every script, with its versions as chips. Filters live in the address so a view can be shared. */
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
  const mayDelete = useMayDelete();
  const del = useDeleteScript();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [restoring, setRestoring] = useState<number | null>(null);
  const restore = async (r: Row) => {
    setRestoring(r.id);
    const { error, response } = await api.POST("/scripts/{script_id}/restore", { params: { path: { script_id: r.id } } });
    setRestoring(null);
    if (!response.ok) return toast(errorText(error), undefined, "error");
    await queryClient.invalidateQueries({ queryKey: ["scripts"] });
    toast(`Restored "${r.title}".`);
  };
  const ownVideo = (v: Version) => !!v.project_id && (owner || v.editor?.id === me?.id || videos.data?.find((p) => p.id === v.project_id)?.created_by_id === me?.id);
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
  const [sheet, setSheet] = useState(false);
  const [bulk, setBulk] = useState(false);
  useEffect(() => set("q", q), [q]); // eslint-disable-line react-hooks/exhaustive-deps
  const [lo, hi] = len ? len.split("-") : ["", ""];
  const refs = useReferences();

  // "Mine" and "Versions left: None" aren't asked of the server, so they are applied to what came back: then one page holds everything.
  const folder = useFolderFilter(); // a project picked in the Projects list (flows OR1)
  const clientSide = mine || left === "0";
  const pageSize = clientSide ? 200 : PAGE;
  const scripts = useInfiniteQuery({
    queryKey: ["scripts", { brandId: all ? null : brandId, removed, status: apiStatus, q, ref, left, lo, hi, sort, pageSize, folder }],
    initialPageParam: 0,
    queryFn: async ({ pageParam }) => {
      const { data, response } = await api.GET("/scripts", {
        params: {
          query: {
            ...(all ? {} : { brand_id: brandId }),
            ...folderQuery(folder),
            ...(removed ? { removed: true } : {}),
            ...(apiStatus ? { status: apiStatus } : {}),
            ...(q ? { q } : {}),
            ...(ref === "none" ? { reference: false } : ref ? { reference_id: ref } : {}),
            ...(left === "1" ? { versions_left: 1 } : {}),
            ...(lo ? { min_seconds: Number(lo) } : {}),
            ...(hi ? { max_seconds: Number(hi) } : {}),
            ...(sort === "newest" || sort === "title" ? { sort } : {}),
            limit: pageSize,
            offset: pageParam,
          },
        },
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
    setParams({}, { replace: true });
  };
  const refName = (id: string | null) => refs.data?.find((r) => r.id === id)?.name;
  const search = (
      <div className="w-full sm:w-[360px]">
        <label className="relative block">
          <span className="sr-only">Search scripts</span>
          <Search size={20} strokeWidth={1.75} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input
            type="search"
            value={text}
            onChange={(e) => {
              setText(e.target.value);
            }}
            placeholder="Search titles, descriptions and scripts"
            className="min-h-control w-full rounded-md border border-border-strong bg-surface pl-10 pr-3 text-base text-text placeholder:text-muted"
          />
        </label>
      </div>
  );
  const selects = (
    <>
      <div className="w-full lg:w-40">
        <Select label="Status" value={status} onChange={(e) => (e.target.value === (owner ? "" : "published") ? set("status", "") : set("status", e.target.value))}>
          {STATUS_FILTER.map(([v, l]) => (
            <option key={v} value={v || (owner ? "" : "any")}>
              {l}
            </option>
          ))}
        </Select>
      </div>
      <div className="w-full lg:w-36">
        <Select label="Length" value={len} onChange={(e) => set("len", e.target.value)}>
          {LENGTH_FILTER.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </Select>
      </div>
      <div className="w-full lg:w-44">
        <Select label="Reference" value={ref} onChange={(e) => set("ref", e.target.value)}>
          <option value="">Any</option>
          <option value="none">No reference</option>
          {refs.data?.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </Select>
      </div>
      <div className="w-full lg:w-44">
        <Select label="Versions left" value={left} onChange={(e) => set("left", e.target.value)}>
          <option value="">Any</option>
          <option value="1">At least one</option>
          <option value="0">None</option>
        </Select>
      </div>
      <Button variant={mine ? "primary" : "secondary"} aria-pressed={mine} onClick={() => set("mine", mine ? "" : "1")}>
        Mine
      </Button>
      <Button variant={removed ? "primary" : "secondary"} icon={Archive} aria-pressed={removed} onClick={() => set("removed", removed ? "" : "1")}>
        Deleted and archived
      </Button>
      {owner && (
        <div className="w-full lg:w-40">
          <Select label="Brand" value={all ? "all" : ""} onChange={(e) => set("brand", e.target.value)}>
            <option value="">This brand</option>
            <option value="all">All brands</option>
          </Select>
        </div>
      )}
      <div className="w-full lg:w-44">
        <Select label="Sort" value={sort} onChange={(e) => set("sort", e.target.value)}>
          {SORTS.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </Select>
      </div>
      {filtered && (
        <Button variant="ghost" onClick={clear}>
          Clear filters
        </Button>
      )}
    </>
  );
  const active = [removed, status !== (owner ? "" : "published"), !!len, !!ref, !!left, mine, all, !!sort].filter(Boolean).length;
  const filters = rail ? (
    <div className="flex flex-wrap items-end gap-3">
      {search}
      {selects}
    </div>
  ) : (
    <div className="flex items-center gap-3">
      {search}
      <Button variant={active > 0 ? "primary" : "secondary"} className="shrink-0 whitespace-nowrap" onClick={() => setSheet(true)}>
        Filters{active > 0 ? ` (${active})` : ""}
      </Button>
    </div>
  );

  const list = (items: Row[]) => (
    <Card className="p-0 sm:p-0">
      <ul className="divide-y divide-border">
        {items.map((r) => (
          <ScriptItem key={r.id} mayOpen={!removed && (r.published || owner || r.created_by_id === me?.id)} row={r} brandName={all ? brands?.find((b) => b.id === r.brand_id)?.name : undefined} refName={r.reference_name ?? refName(r.reference_id)} refThumb={!!r.reference_id && !!refs.data?.find((x) => x.id === r.reference_id)?.has_thumbnail} narrow={!rail} panelTo={panelTo} ownVideo={ownVideo} meId={me?.id} onDelete={!removed && mayDelete(r) ? () => del.ask(toTarget(r)) : undefined} removed={removed} onRestore={() => void restore(r)} restoring={restoring === r.id} />
        ))}
      </ul>
    </Card>
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
    <main className="mx-auto max-w-content space-y-5 p-4 sm:p-6">
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="type-eyebrow text-muted">{brand?.name}</p>
          <h1 className="type-page">Scripts</h1>
        </div>
        <div className="flex items-center gap-2">
          <ProjectsChip brandId={brandId} />
          <Button variant="secondary" icon={Layers} onClick={() => setBulk(true)} aria-label={rail ? undefined : "Bulk create"}>
            {rail ? "Bulk create" : ""}
          </Button>
          {rail && newScript}
        </div>
      </div>
      {bulk && <BulkCreate brandId={brandId} onClose={() => setBulk(false)} />}
      {!rail && <ActionBar phone><div className="flex gap-2">{newScript}</div></ActionBar>}
      {filters}
      {sheet && (
        <Sheet title="Filters" onClose={() => setSheet(false)}>
          <div className="space-y-3 pb-2">
            {selects}
            {filtered && (
              <Button variant="ghost" onClick={clear}>
                Clear filters
              </Button>
            )}
          </div>
        </Sheet>
      )}
      {scripts.isError && (
        <Banner title="Couldn't load your scripts." action={<Button variant="secondary" onClick={() => void scripts.refetch()}>Try again</Button>}>
          Check your connection.
        </Banner>
      )}
      {scripts.isPending && (
        <div className="space-y-3" aria-label="Loading">
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      )}
      {loaded && (
        <>
          {myMaking.length > 0 && (
            <section aria-label="Making now" className="space-y-3">
              <h2 className="type-section">Making now</h2>
              {list(myMaking)}
            </section>
          )}
          {myDrafts.length > 0 && (
            <section aria-label="Your drafts" className="space-y-3">
              <h2 className="type-section">Your drafts</h2>
              {list(myDrafts)}
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
              {list(rows)}
              {scripts.hasNextPage && (
                <Button variant="secondary" busy={scripts.isFetchingNextPage} onClick={() => void scripts.fetchNextPage()}>
                  Show more
                </Button>
              )}
            </>
          )}
        </>
      )}
      <LegacyVideos brandId={brandId} />
      {del.dialog}
      {making && <VersionPanel scriptId={Number(making[1])} slot={Number(making[2])} brandId={brandId} onClose={() => set("make", "")} />}
    </main>
  );
}

function ScriptItem({ row: r, brandName, refName, refThumb, narrow, mayOpen, panelTo, ownVideo, meId, onDelete, removed, onRestore, restoring }: { row: Row; brandName?: string; refName?: string; refThumb?: boolean; narrow: boolean; mayOpen: boolean; panelTo: (id: number, slot: number) => string; ownVideo: (v: Version) => boolean; meId?: number; onDelete?: () => void; removed?: boolean; onRestore?: () => void; restoring?: boolean }) {
  const brandId = r.brand_id;
  // A script archived because a video was made from it keeps its videos and is never removed for good.
  const kept = r.removed ? r.removed === "archived" : r.versions.some((v) => !!v.project_id);
  const meta = [brandName, r.created_by_name && `${r.created_by_name} · ${age(r.created_at)}`, refName && `Ref: ${refName}`, lengthText(r.versions), r.published && r.versions_left > 0 && `${r.versions_left} version${r.versions_left === 1 ? "" : "s"} left to make`].filter(Boolean).join(" · ");
  return (
    <li className="flex gap-3 p-4 sm:p-5">
      <span aria-hidden className="grid h-[88px] w-14 shrink-0 place-items-center overflow-hidden rounded-lg bg-surface-2 text-muted sm:h-[100px] sm:w-16">
        {r.poster_file_id ? <img src={fileUrl(r.poster_file_id)} alt="" className="size-full object-cover" /> : refThumb ? <img src={`/api/references/${r.reference_id}/thumbnail`} alt="" className="size-full object-cover" /> : <FileText size={20} strokeWidth={1.75} />}
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        <h3 className="font-display text-md font-bold">
          {mayOpen ? (
            <Link to={`/b/${brandId}/scripts/${r.id}${r.published ? "?step=publish" : ""}`} className="hover:underline">
              {r.title}
            </Link>
          ) : (
            r.title
          )}
          {r.kind === "song" && (
            <>
              {" "}
              <Badge tone="accent">Song</Badge>
            </>
          )}
          {isNarrated(r) && (
            <>
              {" "}
              <Badge tone="accent">Narrated</Badge>
            </>
          )}
        </h3>
        {removed && (
          <p className="flex flex-wrap items-center gap-2">
            <Badge>{kept || !r.removed_at ? "Archived" : `Deleted · ${age(r.removed_at)}`}</Badge>
            <span className="text-sm text-muted">{kept || !r.purge_on ? "Its videos are kept" : `Removed for good on ${serverTime(r.purge_on).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}`}</span>
          </p>
        )}
        {r.description && <p className="truncate text-sm text-muted">{r.description}</p>}
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted">
          {r.reel_imported && <ReelChip reel={r.reel} />}
          <span>{meta}</span>
        </p>
        <ul className="flex flex-wrap gap-2 pt-1" aria-label="Versions">
          {r.versions.map((v) => {
            const s = STATUS[v.status] ?? { label: v.status, tone: "neutral" as Tone };
            const letter = LETTER[v.slot] ?? String(v.slot + 1);
            const by = beingMade(v.status) && v.editor ? (v.editor.id === meId ? "you" : v.editor.name) : null;
            const label = `${letter} · ${s.label}${by ? ` · ${by}` : ""}`;
            // Ready opens the version panel; so does a version someone else is making. Your own video, and any video for Reed, opens the video; a draft opens its writing flow.
            const to = removed ? null : beingMade(v.status) && !ownVideo(v) ? panelTo(r.id, v.slot) : v.status === "approved" ? panelTo(r.id, v.slot) : v.project_id ? `/b/${brandId}/projects/${v.project_id}` : v.status === "draft" && mayOpen ? `/b/${brandId}/scripts/${r.id}` : null;
            const chip = (
              <Badge tone={s.tone} icon={s.icon}>
                {label}
              </Badge>
            );
            return (
              <li key={v.slot}>
                {to ? (
                  <Link to={to} aria-label={`Version ${letter}, ${s.label.toLowerCase()}${by ? ` by ${by}` : ""}`} className={`inline-flex items-center ${narrow ? "min-h-control" : "min-h-9"} rounded-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent`}>
                    {chip}
                  </Link>
                ) : (
                  <span aria-label={`Version ${letter}, ${s.label.toLowerCase()}${by ? ` by ${by}` : ""}`} className="inline-flex">
                    {chip}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      </div>
      {removed && (
        <div className="shrink-0">
          <Button variant="secondary" dense busy={restoring} onClick={onRestore} aria-label={`Restore ${r.title}`}>
            Restore
          </Button>
        </div>
      )}
      {onDelete && (
        <div className="shrink-0">
          <ScriptMenu title={r.title} onDelete={onDelete} />
        </div>
      )}
    </li>
  );
}
