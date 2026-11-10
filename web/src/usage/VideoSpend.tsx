import { useQuery } from "@tanstack/react-query";
import { api, must } from "../api/client";
import type { components } from "../api/schema";
import { Banner, Button, Panel, Skeleton } from "../components";
import { serverTime } from "../time";
import { Money } from "./parts";

type Part = components["schemas"]["Part"];

/** One video's spend (Reed, 9 Nov), owner only: read when the panel opens. */
export function useVideoSpend(projectId: number) {
  return useQuery({
    queryKey: ["usage", "video", projectId],
    retry: false,
    queryFn: async () => (await must(api.GET("/usage/videos/{project_id}", { params: { path: { project_id: projectId } } }))).data!,
  });
}

/** A labelled list of dollars: each row's name on the left, its dollars on the right. */
function Rows({ title, rows }: { title: string; rows: (Part & { note?: string })[] }) {
  if (rows.length === 0) return null;
  return (
    <section aria-label={title} className="space-y-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      <dl className="divide-y divide-border border-y border-border text-sm tabular-nums">
        {rows.map((r) => (
          <div key={r.name} className="flex items-baseline justify-between gap-3 py-2">
            <dt>
              {r.name}
              {r.note && <span className="ml-2 text-muted">{r.note}</span>}
            </dt>
            <dd className="font-medium">
              <Money value={r.usd} estimated={r.estimated} />
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

const day = (iso: string) => serverTime(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });

/** "What this video cost": its whole life in dollars, by service, by what was made and by the director's runs. */
export function VideoSpend({ projectId, onClose }: { projectId: number; onClose: () => void }) {
  const spend = useVideoSpend(projectId);
  const v = spend.data;
  return (
    <Panel title="What this video cost" onClose={onClose}>
      <div className="space-y-6 pb-2">
        {spend.isError && <Banner title="Couldn't load what it cost." action={<Button variant="secondary" onClick={() => void spend.refetch()}>Try again</Button>}>Check your connection.</Banner>}
        {spend.isPending && <Skeleton className="h-48" />}
        {v && (
          <>
            <div>
              <p className="text-sm text-muted">{v.title} · whole video so far</p>
              <p className="text-2xl font-semibold tabular-nums">
                <Money value={v.spend_usd} estimated={v.spend_estimated} />
              </p>
              {(v.spend_estimated || v.unreported) && (
                <p className="text-sm text-muted">{[v.spend_estimated && "≈ some of it at list price (the service didn't say)", v.unreported && "more not reported yet"].filter(Boolean).join(" · ")}</p>
              )}
            </div>
            {v.spend_usd === 0 && <p className="text-sm text-muted">Nothing spent on this video yet.</p>}
            <Rows title="By service" rows={v.providers} />
            <Rows title="By what was made" rows={v.kinds} />
            <Rows title="By run" rows={v.runs.map((r) => ({ name: r.name, usd: r.usd, estimated: r.estimated, note: r.started_at ? day(r.started_at) : undefined }))} />
          </>
        )}
      </div>
    </Panel>
  );
}
