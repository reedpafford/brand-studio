import { useQuery } from "@tanstack/react-query";
import { api, must } from "../api/client";
import type { components } from "../api/schema";
import { Banner, Button, Card, Skeleton } from "../components";
import { useLooks } from "../scripts/Looks";
import { useFormatName } from "../scripts/useFormats";

type Row = components["schemas"]["PairRow"];

const key = (r: Row) => `${r.format} · ${r.look}`;
const rate = (r: Row) => Math.round(r.credits_per_second * 10) / 10; // "14.4", never "14.419" (polish)
const perSecond = (r: Row) => `${rate(r)} credits`;
const redo = (r: Row) => (r.redo_rate === null ? "—" : `${r.redo_rate} takes a clip`);
const score = (r: Row) => (r.average_score === null ? "—" : `${r.average_score} of 5`);

/** The owner's "By format and style": what a finished second costs in credits, and how well each pair goes. */
export function ByFormat() {
  const formatName = useFormatName();
  const looks = useLooks().data;
  // "Dialogue · House", as the pickers name them, never the ids ("dialogue · house")
  const lookName = (id: string) => looks?.find((l) => l.id === id)?.name ?? looks?.flatMap((l) => l.lanes ?? []).find((x) => x.id === id)?.name ?? id;
  const pair = (r: Row) => `${formatName(r.format)} · ${lookName(r.look)}`;
  const rows = useQuery({
    queryKey: ["usage", "by-format-and-style"],
    retry: false,
    queryFn: async () => (await must(api.GET("/usage/by-format-and-style"))).data!,
  });
  return (
    <section aria-label="By format and style" className="space-y-3">
      <h2 className="type-section">By format and style</h2>
      {rows.isError && <Banner title="Couldn't load this table." action={<Button variant="secondary" onClick={() => void rows.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      {rows.isPending && <Skeleton className="h-24" />}
      {rows.data && rows.data.length === 0 && <p className="text-sm text-muted">Nothing here until a video is finished.</p>}
      {rows.data && rows.data.length > 0 && (
        <>
          <div className="hidden overflow-x-auto lg:block">
            <table className="w-full text-sm tabular-nums">
              <thead className="text-muted">
                <tr className="border-b border-border text-right">
                  <th scope="col" className="px-4 py-3 text-left font-medium">Format · style</th>
                  <th scope="col" className="px-3 py-3 font-medium">Videos</th>
                  <th scope="col" className="px-3 py-3 font-medium">Credits per second</th>
                  <th scope="col" className="px-3 py-3 font-medium">Redo rate</th>
                  <th scope="col" className="px-3 py-3 font-medium">Average score</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border border-b border-border">
                {rows.data.map((r) => (
                  <tr key={key(r)} className="text-right">
                    <th scope="row" className="px-4 py-3 text-left font-medium">{pair(r)}</th>
                    <td className="px-3 py-3">{r.videos}</td>
                    <td className="px-3 py-3">{rate(r)}</td>
                    <td className="px-3 py-3">{redo(r)}</td>
                    <td className="px-3 py-3">{score(r)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="space-y-2 lg:hidden">
            {rows.data.map((r) => (
              <li key={key(r)}>
                <Card className="space-y-1">
                  <p className="font-medium">{pair(r)}</p>
                  <p className="text-sm text-muted tabular-nums">{r.videos} video{r.videos === 1 ? "" : "s"} · {perSecond(r)} a second</p>
                  <p className="text-sm text-muted tabular-nums">{redo(r)} · score {score(r)}</p>
                </Card>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
