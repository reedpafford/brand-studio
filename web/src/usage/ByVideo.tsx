import { useState } from "react";
import { Link } from "react-router-dom";
import { keepPreviousData, useInfiniteQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { Banner, Button, Segmented, Skeleton } from "../components";
import { useRail } from "../useMedia";
import { Money, money, lastText } from "./parts";
import type { Period } from "./useUsage";
import { VideoSpend } from "./VideoSpend";

type Row = components["schemas"]["VideoSpend"];
type Sort = "spend" | "recent" | "title";
const SORTS: { id: Sort; name: string }[] = [
  { id: "spend", name: "Most spent" },
  { id: "recent", name: "Latest" },
  { id: "title", name: "Name" },
];

const link = (v: Row) => (v.freestyle_id ? `/freestyle/${v.freestyle_id}` : `/b/${v.brand_id}/videos/${v.project_id}`);
const part = (v: Row, kind: string) => v.kinds.find((k) => k.name === kind);

/** Spend per video (Reed, 9 Nov): each video worked on in the period, with its whole life's dollars split by what was made.
 *  Details opens the same panel as the video's header: by service, by what was made and by run. */
export function ByVideo({ query, words }: { query: { period?: Period; month?: string }; words: string }) {
  const rail = useRail();
  const [sort, setSort] = useState<Sort>("spend");
  const [open, setOpen] = useState<number | null>(null);
  const rows = useInfiniteQuery({
    queryKey: ["usage", "videos", query, sort],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const { data } = await api.GET("/usage/videos", { params: { query: { ...query, sort, cursor: pageParam, limit: 25 } } });
      if (!data) throw new Error("load");
      return data;
    },
    getNextPageParam: (last) => last.next_cursor,
    placeholderData: keepPreviousData,
    retry: false,
  });
  const items = rows.data?.pages.flatMap((p) => p.items) ?? [];
  const kinds = rows.data?.pages[0]?.kinds ?? [];
  const details = (v: Row, full?: boolean) => (
    <Button variant="secondary" dense={!full} className={full ? "w-full" : undefined} aria-label={`What ${v.title} cost`} onClick={() => setOpen(v.project_id)}>
      Details
    </Button>
  );
  return (
    <section aria-label="By video" className="space-y-3 lg:max-w-[1100px]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="type-section">By video</h2>
          <p className="text-sm text-muted">Videos worked on {words}, each with everything it has cost so far.</p>
        </div>
        <Segmented label="Sort videos" items={SORTS} value={sort} onChange={setSort} fill={!rail} />
      </div>
      {rows.isError && <Banner title="Couldn't load the videos." action={<Button variant="secondary" onClick={() => void rows.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      {rows.isPending && <Skeleton className="h-32" />}
      {rows.data && items.length === 0 && <p className="text-sm text-muted">No video has cost anything {words}.</p>}
      {items.length > 0 &&
        (rail ? (
          <div className="overflow-x-auto">
            <table aria-label="By video" className="w-full text-sm tabular-nums">
              <thead className="text-muted">
                <tr className="border-b border-border text-right">
                  <th scope="col" className="px-4 py-3 text-left font-medium">Video</th>
                  <th scope="col" className="px-3 py-3 text-left font-medium">Brand</th>
                  <th scope="col" className="px-3 py-3 font-medium">Spent</th>
                  {kinds.map((k) => (
                    <th key={k} scope="col" className="px-3 py-3 font-medium">{k}</th>
                  ))}
                  <th scope="col" className="w-24"><span className="sr-only">Details</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border border-b border-border">
                {items.map((v) => (
                  <tr key={v.project_id} className="text-right">
                    <th scope="row" className="max-w-[280px] px-4 py-3 text-left font-medium">
                      <Link to={link(v)} className="block truncate hover:underline">{v.title}</Link>
                    </th>
                    <td className="px-3 py-3 text-left text-muted">{v.brand}</td>
                    <td className="px-3 py-3 font-medium"><Money value={v.spend_usd} estimated={v.spend_estimated} /></td>
                    {kinds.map((k) => {
                      const p = part(v, k);
                      return <td key={k} className="px-3 py-3 text-muted">{p ? <Money value={p.usd} estimated={p.estimated} /> : "—"}</td>;
                    })}
                    <td className="pr-3">{details(v)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <ul className="space-y-3">
            {items.map((v) => (
              <li key={v.project_id} className="space-y-2 rounded-lg border border-border bg-surface p-4">
                <Link to={link(v)} className="flex min-h-control items-center font-medium hover:underline">
                  <span className="min-w-0 break-words">{v.title}</span>
                </Link>
                <p className="text-sm text-muted">{v.brand} · last charge {lastText(v.last_at)}</p>
                <p className="text-lg font-semibold tabular-nums"><Money value={v.spend_usd} estimated={v.spend_estimated} /> <span className="text-sm font-normal text-muted">spent</span></p>
                <p className="text-sm tabular-nums text-muted">{v.kinds.map((k) => `${k.name} ${money(k.usd)}`).join(" · ")}</p>
                {details(v, true)}
              </li>
            ))}
          </ul>
        ))}
      {rows.hasNextPage && (
        <Button variant="secondary" busy={rows.isFetchingNextPage} onClick={() => void rows.fetchNextPage()} className="w-full lg:w-auto">
          Show more videos
        </Button>
      )}
      {open !== null && <VideoSpend projectId={open} onClose={() => setOpen(null)} />}
    </section>
  );
}
