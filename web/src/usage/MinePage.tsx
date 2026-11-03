import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api, must } from "../api/client";
import { Badge, Banner, Button, Card, PageTop, Select, Skeleton, creditsLabel, creditsText } from "../components";
import { lastBrand, useBrands } from "../shell/useBrands";
import { PeriodControl, periodWord } from "./parts";
import { periodFrom } from "./useUsage";

const director = (v: { director_credits?: number }) => v.director_credits ?? 0;
const used = (v: { credits: number; director_credits?: number }) => Math.max(0, v.credits - director(v));
const VIDEO_STATUS = { in_production: "Being made", done: "Finished", failed: "Didn't finish" } as const;

/** An editor's own credits (flows OR4): this week as the allowance counts it, then their videos, quick clips
 *  and script writing in one brand, in credits only (never dollars, never someone else's). The owner keeps Usage. */
export function MinePage() {
  const brands = useBrands().data ?? [];
  const [params, setParams] = useSearchParams();
  const period = periodFrom(params.get("period"));
  const [picked, setPicked] = useState<number | null>(null);
  const brandId = picked ?? (brands.some((b) => b.id === lastBrand()) ? lastBrand() : brands[0]?.id) ?? null; // the brand in the top bar
  const mine = useQuery({
    enabled: brandId !== null,
    queryKey: ["usage", "mine", brandId, period],
    queryFn: async () => (await must(api.GET("/usage/mine", { params: { query: { brand_id: brandId!, period } } }))).data!,
  });
  const m = mine.data;
  const waiting = (m?.sends ?? []).filter((x) => x.status === "waiting");
  const week = m?.week;
  const filters = (
    <>
      {brands.length > 1 && (
        <div className="lg:w-48">
          <Select label="Brand" value={brandId ?? ""} onChange={(e) => setPicked(Number(e.target.value))}>
            {brands.map((b) => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </Select>
        </div>
      )}
      <PeriodControl value={period} onChange={(p) => setParams((s) => (s.set("period", p), s), { replace: true })} />
    </>
  );
  return (
    <main className="mx-auto max-w-content space-y-4 p-4 sm:p-6">
      <PageTop title="My credits" line="What your work has used, in credits." />
      {mine.isError && <Banner title="Couldn't load your credits." action={<Button variant="secondary" onClick={() => void mine.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      <div className="grid gap-3 lg:grid-cols-2">
      <Card className="space-y-2">
        <h2 className="type-section">Your allowance this week</h2>
        {!week ? (
          <Skeleton className="h-16" />
        ) : (
          <>
            <p className="font-medium">
              {week.allowance === null ? `${creditsText(week.used)} used` : `${creditsText(week.used)} of ${creditsText(week.allowance)} used`}
              {week.allowance !== null && <span className="text-sm font-normal text-muted"> · resets on Monday</span>}
            </p>
            {week.lines.length === 0 ? (
              <p className="text-sm text-muted">Nothing used yet this week.</p>
            ) : (
              <ul aria-label="This week's charges" className="divide-y divide-border text-sm">
                {week.lines.map((l) => (
                  <li key={l.label} className="flex justify-between gap-3 py-2">
                    <span>{l.label}</span>
                    <span className="tabular-nums">{creditsText(l.credits)}</span>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </Card>
      {/* D_MyCredits: my sends waiting for the owner's OK, every one counted by the server across brands (#1232). */}
      <Card className="space-y-2">
        <h2 className="type-section">Waiting for the owner's OK</h2>
        {!m ? (
          <Skeleton className="h-12" />
        ) : waiting.length === 0 ? (
          <p className="text-sm text-muted">Nothing waiting.</p>
        ) : (
          <>
            <p className="font-medium tabular-nums">up to {creditsLabel(m.waiting_credits)}</p>
            <p className="text-sm text-muted">{waiting.length} send{waiting.length === 1 ? "" : "s"}. Nothing is spent until it's approved.</p>
          </>
        )}
      </Card>
      </div>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end">{filters}</div>
      {!m ? (
        !mine.isError && <Skeleton className="h-40" />
      ) : (
        <>
          <p className="font-medium">
            {creditsText(m.credits)} {periodWord(period)}
            <span className="text-sm font-normal text-muted"> · videos, quick clips and writing scripts</span>
          </p>
          <Card className="space-y-2">
            <h2 className="type-section">Videos</h2>
            {m.videos.length === 0 ? (
              <p className="text-sm text-muted">No videos of yours {periodWord(period)}.</p>
            ) : (
              <ul aria-label="My videos" className="divide-y divide-border">
                {m.videos.map((v) => (
                  <li key={v.project_id}>
                    <Link to={`/b/${brandId}/videos/${v.project_id}`} className="flex min-h-control flex-wrap items-center justify-between gap-x-3 gap-y-1 py-2 hover:bg-surface-2">
                      <span className="min-w-0 break-words font-medium">{v.title}</span>
                      <span className="flex items-center gap-2 text-sm">
                        <Badge tone={v.status === "failed" ? "danger" : v.status === "done" ? "success" : "neutral"}>{VIDEO_STATUS[v.status]}</Badge>
                        <span className="text-right tabular-nums text-muted">
                          {/* The director's own time is apart from the budget (#1216, QA-3 on #1218): a director-run video
                              reads against what the owner approved, the rest against the budget. */}
                          {v.approved_up_to != null
                            ? `${creditsText(used(v))} used of up to ${creditsText(v.approved_up_to)} approved`
                            : `${creditsText(used(v))} of ${creditsText(v.budget_credits)}`}
                          {director(v) > 0 && <span className="block text-xs">{creditsText(director(v))} of director time</span>}
                        </span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          {m.sends.length > 0 && (
            <Card className="space-y-2">
              <h2 className="type-section">Sends</h2>
              <ul aria-label="My sends" className="divide-y divide-border text-sm">
                {m.sends.map((x) => (
                  <li key={`${x.job_id ?? ""}-${x.freestyle_id ?? ""}-${x.created_at}`} className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1 py-2">
                    <span className="min-w-0 break-words">
                      {x.freestyle_id ? <Link to={`/freestyle/${x.freestyle_id}`} className="font-medium hover:underline">{x.title}</Link> : <span className="font-medium">{x.title}</span>}
                      {x.brand && <span className="text-muted"> · {x.brand}</span>}
                      {x.status === "declined" && x.reason && <span className="block text-muted">"{x.reason}"</span>}
                    </span>
                    <span className="flex items-center gap-2">
                      <Badge tone={x.status === "declined" ? "danger" : "warning"}>{x.status === "declined" ? "Declined" : "Waiting for the owner's OK"}</Badge>
                      <span className="tabular-nums text-muted">{x.status === "declined" ? "0 credits" : `up to ${creditsLabel(x.up_to_credits)}`}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
          <Card className="space-y-2">
            <h2 className="type-section">Quick clips and scripts</h2>
            <ul className="divide-y divide-border text-sm">
              <li className="flex justify-between gap-3 py-2">
                <span>Quick clips</span>
                <span className="tabular-nums">{creditsText(m.quick_clip_credits)}</span>
              </li>
              {m.scripts.map((s) => (
                <li key={s.script_id} className="flex items-center justify-between gap-3">
                  <Link to={`/b/${brandId}/scripts/${s.script_id}`} className="flex min-h-control min-w-0 items-center break-words underline-offset-2 hover:underline">
                    Writing "{s.title}"
                  </Link>
                  <span className="tabular-nums">{creditsText(s.credits)}</span>
                </li>
              ))}
            </ul>
          </Card>
        </>
      )}
    </main>
  );
}
