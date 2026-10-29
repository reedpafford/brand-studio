import { useState } from "react";
import { Check, ChevronRight, CircleAlert, Clock, FileText, Search } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { Badge, Banner, Button, Card, EmptyState, Select, Sheet, Skeleton, Tabs, type Tone } from "../components";
import { STATUS as SCRIPT_STATUS, age, useDebounced } from "../scripts/ScriptsPage";
import { useRail } from "../useMedia";
import { Money, lastText, periodWord } from "./parts";
import { useBrandScripts, useBrandVideos, type Period, type ScriptFilters, type VideoFilters } from "./useUsage";

const LETTER = ["A", "B", "C"];
/** "Bo tries salmon · B"; the server may already put the letter in the title. */
const videoTitle = (v: { title: string; version_letter: string | null }) => (v.version_letter && !v.title.endsWith(` · ${v.version_letter}`) ? `${v.title} · ${v.version_letter}` : v.title);

const VIDEO_STATUS: Record<string, { label: string; tone: Tone; icon: typeof Check }> = {
  in_production: { label: "In production", tone: "warning", icon: Clock },
  done: { label: "Video done", tone: "success", icon: Check },
  failed: { label: "Didn't finish", tone: "danger", icon: CircleAlert },
};
// A finished video whose clips changed since isn't "done" any more, but it isn't being made either (#749 LW2).
const WAITING = { label: "Finished · changes waiting", tone: "warning" as Tone, icon: Clock };
const statusOf = (v: { status: string; final_out_of_date?: boolean }) => (v.status === "done" && v.final_out_of_date ? WAITING : VIDEO_STATUS[v.status]);

/** A small hook for one list's filters, kept in the address under its own names. */
function useParam(key: string, fallback: string) {
  const [params, setParams] = useSearchParams();
  const value = params.get(key) ?? fallback;
  const set = (v: string) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (v && v !== fallback) next.set(key, v);
        else next.delete(key);
        return next;
      },
      { replace: true },
    );
  return [value, set] as const;
}

/** Videos and Scripts for one brand, in tabs kept in the address. */
export function BrandLists({ brandId, period }: { brandId: number; period: Period }) {
  const [tab, setTab] = useParam("tab", "videos");
  const videoCount = useBrandVideos(brandId, { period, status: "any", person: null, q: "", sort: "activity" }).data?.pages[0]?.total;
  const scriptCount = useBrandScripts(brandId, { status: "any", author: null, q: "", sort: "changed" }).data?.pages[0]?.total;
  return (
    <section aria-label="Videos and scripts" className="space-y-4">
      <Tabs
        label="Brand lists"
        value={tab}
        onChange={setTab}
        tabs={[
          { id: "videos", label: `Videos${videoCount === undefined ? "" : ` ${videoCount}`}` },
          { id: "scripts", label: `Scripts${scriptCount === undefined ? "" : ` ${scriptCount}`}` },
        ]}
      />
      {tab === "scripts" ? <ScriptsTab brandId={brandId} /> : <VideosTab brandId={brandId} period={period} />}
    </section>
  );
}

function Search_({ value, onChange, label }: { value: string; onChange: (v: string) => void; label: string }) {
  return (
    <label className="relative block min-w-0 flex-1 lg:w-64 lg:flex-none">
      <span className="sr-only">{label}</span>
      <Search size={20} strokeWidth={1.75} aria-hidden className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
      <input type="search" role="searchbox" placeholder={label} value={value} onChange={(e) => onChange(e.target.value)} className="min-h-control w-full rounded-md border border-border bg-surface pl-10 pr-3 lg:min-h-control-dense" />
    </label>
  );
}

function VideosTab({ brandId, period }: { brandId: number; period: Period }) {
  const rail = useRail();
  const [status, setStatus] = useParam("vstatus", "any");
  const [who, setWho] = useParam("who", "");
  const [sort, setSort] = useParam("vsort", "activity");
  const [text, setText] = useState("");
  const [sheet, setSheet] = useState(false);
  const q = useDebounced(text.trim());
  const f: VideoFilters = { period, status: status as VideoFilters["status"], person: who ? Number(who) : null, q, sort: sort as VideoFilters["sort"] };
  const videos = useBrandVideos(brandId, f);
  const items = videos.data?.pages.flatMap((p) => p.items) ?? [];
  const total = videos.data?.pages[0]?.total;
  const people = videos.data?.pages[0]?.people ?? [];
  const selects = (
    <>
      <Select label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="any">Any</option>
        <option value="in_production">In production</option>
        <option value="done">Video done</option>
        <option value="failed">Didn't finish</option>
      </Select>
      <Select label="Who" value={who} onChange={(e) => setWho(e.target.value)}>
        <option value="">Anyone</option>
        {people.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </Select>
      <Select label="Sort" value={sort} onChange={(e) => setSort(e.target.value)}>
        <option value="activity">Last activity</option>
        <option value="spend">Most spent</option>
        <option value="finished">Finished (newest)</option>
        <option value="title">Title A–Z</option>
      </Select>
    </>
  );
  const active = (status !== "any" ? 1 : 0) + (who ? 1 : 0) + (sort !== "activity" ? 1 : 0);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <Search_ label="Search videos" value={text} onChange={setText} />
        {rail ? (
          <div className="flex items-end gap-3 [&>*]:w-44">{selects}</div>
        ) : (
          <Button variant={active > 0 ? "primary" : "secondary"} onClick={() => setSheet(true)}>
            {active > 0 ? `Filters (${active})` : "Filters"}
          </Button>
        )}
      </div>
      {total !== undefined && <p className="text-sm text-muted">{status === "done" ? `Videos finished ${periodWord(period)}` : `Videos with activity ${periodWord(period)}`} · {total}</p>}
      {videos.isError && <Banner title="Couldn't load the videos." action={<Button variant="secondary" onClick={() => void videos.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      {videos.isPending && <Skeleton className="h-40" />}
      {videos.data && items.length === 0 && (
        <EmptyState icon={FileText} title={q || status !== "any" || who ? "No videos match." : "No videos yet."}>
          {q || status !== "any" || who ? "Try other filters." : "They show up here when someone starts a version."}
        </EmptyState>
      )}
      {items.length > 0 && (rail ? (
        <Card className="overflow-x-auto p-0 sm:p-0">
          <table className="w-full text-sm tabular-nums">
            <thead className="text-muted">
              <tr className="border-b border-border text-right align-bottom">
                <th scope="col" className="px-4 py-3 text-left font-medium">Video</th>
                <th scope="col" className="px-3 py-3 text-left font-medium">Who</th>
                <th scope="col" className="px-3 py-3 text-left font-medium">Status</th>
                <th scope="col" className="px-3 py-3 font-medium">Spent<span className="block text-xs font-normal">whole video</span></th>
                <th scope="col" className="px-3 py-3 font-medium">Credits</th>
                <th scope="col" className="px-3 py-3 font-medium">Finished / last</th>
                <th scope="col" className="w-8" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {items.map((v) => {
                const s = statusOf(v);
                return (
                  <tr key={v.project_id} className="relative text-right hover:bg-surface-2">
                    <th scope="row" className="px-4 py-3 text-left font-medium">
                      <Link to={`/b/${brandId}/projects/${v.project_id}`} className="after:absolute after:inset-0">
                        {videoTitle(v)}
                      </Link>
                      {v.legacy && <span className="ml-1 font-normal text-muted">(earlier way)</span>}
                    </th>
                    <td className="px-3 py-3 text-left">{v.person?.name ?? "—"}</td>
                    <td className="px-3 py-3 text-left">{s && <Badge tone={s.tone} icon={s.icon}>{s.label}</Badge>}</td>
                    <td className="px-3 py-3"><Money value={v.spend_usd} estimated={v.spend_estimated} /></td>
                    <td className="px-3 py-3">{v.credits}</td>
                    <td className="px-3 py-3">{lastText(v.finished_at ?? v.last_activity_at)}</td>
                    <td className="pr-3 text-muted"><ChevronRight size={20} strokeWidth={1.75} aria-hidden /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      ) : (
        <ul className="space-y-3">
          {items.map((v) => {
            const s = statusOf(v);
            return (
              <li key={v.project_id}>
                <Link to={`/b/${brandId}/projects/${v.project_id}`} className="block space-y-2 rounded-lg border border-border bg-surface p-4 hover:bg-surface-2">
                  <span className="flex items-center gap-2 font-display text-md font-bold">
                    <span className="min-w-0 flex-1 break-words">{videoTitle(v)}</span>
                    <ChevronRight size={20} strokeWidth={1.75} aria-hidden className="shrink-0 text-muted" />
                  </span>
                  {s && <Badge tone={s.tone} icon={s.icon}>{s.label}</Badge>}
                  <span className="block text-sm text-muted">
                    {v.person ? `${v.person.name} · ` : ""}
                    <Money value={v.spend_usd} estimated={v.spend_estimated} /> · {lastText(v.finished_at ?? v.last_activity_at)}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      ))}
      {videos.hasNextPage && (
        <Button variant="secondary" busy={videos.isFetchingNextPage} onClick={() => void videos.fetchNextPage()} className="w-full lg:w-auto">
          Show more
        </Button>
      )}
      {sheet && (
        <Sheet title="Filters" onClose={() => setSheet(false)}>
          <div className="space-y-3 pb-2">{selects}</div>
        </Sheet>
      )}
    </div>
  );
}

function ScriptsTab({ brandId }: { brandId: number }) {
  const rail = useRail();
  const [status, setStatus] = useParam("sstatus", "any");
  const [author, setAuthor] = useParam("author", "");
  const [sort, setSort] = useParam("ssort", "changed");
  const [text, setText] = useState("");
  const [sheet, setSheet] = useState(false);
  const q = useDebounced(text.trim());
  const f: ScriptFilters = { status: status as ScriptFilters["status"], author: author ? Number(author) : null, q, sort: sort as ScriptFilters["sort"] };
  const scripts = useBrandScripts(brandId, f);
  const items = scripts.data?.pages.flatMap((p) => p.items) ?? [];
  const authors = scripts.data?.pages[0]?.authors ?? [];
  const selects = (
    <>
      <Select label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="any">Any</option>
        <option value="writing">Writing</option>
        <option value="ready">Ready to make</option>
        <option value="in_production">In production</option>
        <option value="done">Video done</option>
      </Select>
      <Select label="Author" value={author} onChange={(e) => setAuthor(e.target.value)}>
        <option value="">Anyone</option>
        {authors.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </Select>
      <Select label="Sort" value={sort} onChange={(e) => setSort(e.target.value)}>
        <option value="changed">Recently changed</option>
        <option value="spend">Most spent</option>
        <option value="title">Title A–Z</option>
      </Select>
    </>
  );
  const active = (status !== "any" ? 1 : 0) + (author ? 1 : 0) + (sort !== "changed" ? 1 : 0);
  const chips = (r: (typeof items)[number]) => (
    <ul className="flex flex-wrap gap-2" aria-label="Versions">
      {r.versions.map((v) => {
        const s = SCRIPT_STATUS[v.status] ?? { label: v.status, tone: "neutral" as Tone };
        const letter = LETTER[v.slot] ?? String(v.slot + 1);
        const to = v.status === "approved" ? `/b/${brandId}/scripts?make=${r.id}.${v.slot}` : v.project_id ? `/b/${brandId}/projects/${v.project_id}` : v.status === "draft" ? `/b/${brandId}/scripts/${r.id}` : null;
        const by = v.status === "in_production" && v.editor ? ` · ${v.editor.name}` : "";
        const chip = (
          <Badge tone={s.tone} icon={s.icon}>
            {letter} · {s.label}
            {by}
          </Badge>
        );
        const label = `Version ${letter}, ${s.label.toLowerCase()}${v.editor && by ? ` by ${v.editor.name}` : ""}`;
        return (
          <li key={v.slot}>
            {to ? (
              <Link to={to} aria-label={label} className={`inline-flex items-center ${rail ? "min-h-9" : "min-h-control"} rounded-md`}>
                {chip}
              </Link>
            ) : (
              <span aria-label={label} className="inline-flex">{chip}</span>
            )}
          </li>
        );
      })}
    </ul>
  );
  const open = (r: (typeof items)[number]) => `/b/${brandId}/scripts/${r.id}${r.published ? "?step=publish" : ""}`;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <Search_ label="Search scripts" value={text} onChange={setText} />
        {rail ? (
          <div className="flex items-end gap-3 [&>*]:w-44">{selects}</div>
        ) : (
          <Button variant={active > 0 ? "primary" : "secondary"} onClick={() => setSheet(true)}>
            {active > 0 ? `Filters (${active})` : "Filters"}
          </Button>
        )}
      </div>
      {scripts.isError && <Banner title="Couldn't load the scripts." action={<Button variant="secondary" onClick={() => void scripts.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      {scripts.isPending && <Skeleton className="h-40" />}
      {scripts.data && items.length === 0 && (
        <EmptyState icon={FileText} title={q || status !== "any" || author ? "No scripts match." : "No scripts yet."} action={<Link to={`/b/${brandId}/scripts`} className="text-accent-text underline">Open Scripts</Link>}>
          {q || status !== "any" || author ? "Try other filters." : "Scripts written for this brand show up here."}
        </EmptyState>
      )}
      {items.length > 0 && (
        <Card className="p-0 sm:p-0">
          <ul className="divide-y divide-border">
            {items.map((r) => (
              <li key={r.id} className="relative flex flex-col gap-2 p-4 hover:bg-surface-2 lg:grid lg:grid-cols-[minmax(0,1.4fr)_6rem_minmax(0,2fr)_4rem_6rem_6rem] lg:items-center lg:gap-3">
                <h3 className="font-display text-md font-bold">
                  <Link to={open(r)} className="after:absolute after:inset-0">{r.title}</Link>
                </h3>
                <p className="hidden lg:block lg:text-sm">{r.created_by_name || "—"}</p>
                <div className="relative z-10 w-fit">{chips(r)}</div>
                <p className="hidden lg:block lg:text-right lg:text-sm">{r.versions_left > 0 ? `${r.versions_left} left` : "—"}</p>
                <p className="hidden tabular-nums lg:block lg:text-right lg:text-sm"><Money value={r.spend_usd} estimated={r.spend_estimated} /></p>
                <p className="hidden lg:block lg:text-right lg:text-sm text-muted">{age(r.changed_at)}</p>
                <p className="text-sm text-muted lg:hidden">
                  {r.created_by_name ? `${r.created_by_name} · ` : ""}
                  <Money value={r.spend_usd} estimated={r.spend_estimated} />
                  {r.versions_left > 0 ? ` · ${r.versions_left} left` : ""} · {age(r.changed_at)}
                </p>
              </li>
            ))}
          </ul>
        </Card>
      )}
      {scripts.hasNextPage && (
        <Button variant="secondary" busy={scripts.isFetchingNextPage} onClick={() => void scripts.fetchNextPage()} className="w-full lg:w-auto">
          Show more
        </Button>
      )}
      {sheet && (
        <Sheet title="Filters" onClose={() => setSheet(false)}>
          <div className="space-y-3 pb-2">{selects}</div>
        </Sheet>
      )}
    </div>
  );
}
