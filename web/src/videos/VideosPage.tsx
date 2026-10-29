import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, Clock, Film, Search } from "lucide-react";
import { fileUrl } from "../api/upload";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { useMe } from "../auth/useMe";
import { Badge, Banner, Button, Card, EmptyState, Select, Sheet, Skeleton } from "../components";
import { useDebounced } from "../scripts/ScriptsPage";
import { useBrands } from "../shell/useBrands";
import { useRail } from "../useMedia";
import { ViewSwitch } from "./ViewSwitch";
import { serverTime } from "../time";

type Project = components["schemas"]["ProjectOut"];

const STEP: Record<string, string> = { breakdown: "Breakdown", assets: "Assets", storyboard: "Storyboard", clips: "Clips", downloads: "Final cut" };
const date = (iso: string) => serverTime(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });

/** Where a video opens: the new page for one made from a script version (Final cut when it is done), the earlier six-step page for the rest. */
// A finished video whose clips changed since opens at Clips, where the changes wait (#749 LW2).
const to = (p: Project) => (p.script_draft_id ? `/b/${p.brand_id}/videos/${p.id}${p.final_out_of_date ? "?step=clips" : p.finished_at ? "?step=downloads" : ""}` : `/b/${p.brand_id}/projects/${p.id}`);

function Row({ p, mineView }: { p: Project; mineView: boolean }) {
  const done = !!p.finished_at;
  const meta = [
    p.created_by_name || "Someone",
    done ? `Finished · ${date(p.finished_at!)}` : p.script_draft_id && p.step && STEP[p.step] ? `At ${STEP[p.step]}` : `${Math.round(p.credits_used)} of ${Math.round(p.budget_credits)} credits`,
    p.own_script && mineView ? "On your week" : null,
    p.script_draft_id ? null : "(earlier way)",
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <li>
      <Link to={to(p)} className={`flex min-h-control items-center gap-3 p-4 hover:bg-surface-2 ${p.archived_at ? "opacity-70" : ""}`}>
        <span aria-hidden className="grid h-[88px] w-14 shrink-0 place-items-center overflow-hidden rounded-md bg-surface-2 text-muted">
          {p.poster_file_id ? <img src={fileUrl(p.poster_file_id)} alt="" className="size-full object-cover" /> : <Film size={20} strokeWidth={1.75} />}
        </span>
        <span className="min-w-0 flex-1 space-y-1">
          <span className="block break-words type-card">{p.name}</span>
          <span className="block text-sm text-muted">{meta}</span>
          <span className="flex flex-wrap gap-2">
            {done && p.final_out_of_date ? (
              <Badge tone="warning" icon={Clock}>
                Finished · changes waiting
              </Badge>
            ) : done ? (
              <Badge tone="success" icon={Check}>
                Finished
              </Badge>
            ) : (
              <Badge tone="warning" icon={Clock}>
                In production
              </Badge>
            )}
            {p.archived_at && <Badge>Archived</Badge>}
          </span>
        </span>
      </Link>
    </li>
  );
}

/** The brand's videos: yours (or everyone's, for Reed), with search, status, Archived and Mine. Filters live in the address. */
export function VideosPage() {
  const brandId = Number(useParams().brandId);
  const { data: brands } = useBrands();
  const { data: me } = useMe();
  const rail = useRail();
  const [params, setParams] = useSearchParams();
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
  const status = params.get("status") === "making" || params.get("status") === "done" ? (params.get("status") as "making" | "done") : "";
  const archived = params.get("archived") === "1";
  const mine = !owner || params.get("mine") === "1"; // an editor only ever sees their own
  const [text, setText] = useState(params.get("q") ?? "");
  const q = useDebounced(text.trim());
  const [sheet, setSheet] = useState(false);
  useEffect(() => set("q", q), [q]); // eslint-disable-line react-hooks/exhaustive-deps

  const videos = useQuery({
    enabled: me !== undefined,
    queryKey: ["videos", { brandId, q, mine, status, archived }],
    queryFn: async () => {
      const { data } = await api.GET("/projects", { params: { query: { brand_id: brandId, ...(q ? { q } : {}), ...(mine ? { mine: true } : {}), ...(status ? { status } : {}), ...(archived ? { archived: true } : {}) } } });
      if (!data) throw new Error("load");
      return data;
    },
  });
  const total = useQuery({
    enabled: me !== undefined,
    queryKey: ["videos", { brandId, mine, all: true }],
    queryFn: async () => (await api.GET("/projects", { params: { query: { brand_id: brandId, ...(mine ? { mine: true } : {}) } } })).data ?? [],
  });
  const filtered = !!(q || status || archived || (owner && mine));
  const clear = () => {
    setText("");
    setParams({ view: "videos" }, { replace: true });
  };
  const brand = brands?.find((b) => b.id === brandId);
  const rows = videos.data ?? [];

  const search = (
    <div className="w-full sm:w-[360px]">
      <label className="relative block">
        <span className="sr-only">Search videos</span>
        <Search size={20} strokeWidth={1.75} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
        <input type="search" value={text} onChange={(e) => setText(e.target.value)} placeholder="Search videos" className="min-h-control w-full rounded-md border border-border-strong bg-surface pl-10 pr-3 text-base text-text placeholder:text-muted" />
      </label>
    </div>
  );
  const controls = (
    <>
      <div className="w-full lg:w-44">
        <Select label="Status" value={status} onChange={(e) => set("status", e.target.value)}>
          <option value="">Any</option>
          <option value="making">Making</option>
          <option value="done">Finished</option>
        </Select>
      </div>
      <Button variant={archived ? "primary" : "secondary"} aria-pressed={archived} onClick={() => set("archived", archived ? "" : "1")}>
        Archived
      </Button>
      {owner && (
        <Button variant={mine ? "primary" : "secondary"} aria-pressed={mine} onClick={() => set("mine", mine ? "" : "1")}>
          Mine
        </Button>
      )}
      {filtered && rows.length > 0 && (
        <Button variant="ghost" onClick={clear}>
          Clear filters
        </Button>
      )}
    </>
  );
  const active = [!!status, archived, owner && mine].filter(Boolean).length;
  const filters = rail ? (
    <div className="flex flex-wrap items-end gap-3">
      {search}
      {controls}
    </div>
  ) : (
    <div className="flex items-center gap-3">
      {search}
      <Button variant={active > 0 ? "primary" : "secondary"} className="shrink-0 whitespace-nowrap" onClick={() => setSheet(true)}>
        Filters{active > 0 ? ` (${active})` : ""}
      </Button>
    </div>
  );

  return (
    <main className="mx-auto max-w-content space-y-5 p-4 sm:p-6">
      <div>
        <p className="type-eyebrow text-muted">{brand?.name}</p>
        <h1 className="type-page">Scripts</h1>
      </div>
      <ViewSwitch />
      {filters}
      {videos.isError && (
        <Banner tone="danger" title="Couldn't load your videos. Check your connection." action={<Button variant="secondary" onClick={() => videos.refetch()}>Try again</Button>} />
      )}
      {videos.isPending && (
        <div role="status" aria-label="Loading" className="space-y-3">
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-[120px]" />
          ))}
        </div>
      )}
      {videos.data && (
        <>
          <p className="text-sm text-muted tabular-nums" role="status">
            {filtered && total.data ? `${rows.length} of ${total.data.length} video${total.data.length === 1 ? "" : "s"}` : `${rows.length} video${rows.length === 1 ? "" : "s"}`}
          </p>
          {rows.length === 0 ? (
            filtered ? (
              <EmptyState icon={Film} title="Nothing matches these filters." action={<Button variant="ghost" onClick={clear}>Clear filters</Button>} />
            ) : (
              <EmptyState icon={Film} title={owner ? "No videos yet." : "You haven't started a video yet."} action={<Link to="?" className="inline-flex min-h-control items-center text-accent-text hover:underline">Show scripts</Link>}>
                {owner ? "Videos made from your scripts show up here." : "Pick a version that's Ready to make."}
              </EmptyState>
            )
          ) : (
            <Card className="p-0 sm:p-0">
              <ul className="divide-y divide-border">
                {rows.map((p) => (
                  <Row key={p.id} p={p} mineView={mine} />
                ))}
              </ul>
            </Card>
          )}
        </>
      )}
      {sheet && (
        <Sheet title="Filters" onClose={() => setSheet(false)}>
          <div className="space-y-3">{controls}</div>
        </Sheet>
      )}
    </main>
  );
}
