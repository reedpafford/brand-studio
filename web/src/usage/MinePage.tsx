import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api, must } from "../api/client";
import { Banner, Button, Card, PageTop, Select, Skeleton, creditsLabel, wholeCredits } from "../components";
import { lastBrand, useBrands } from "../shell/useBrands";
import { PeriodControl, periodWord } from "./parts";
import { periodFrom } from "./useUsage";

// D_MyCredits: a dot and words, whole credits.
const VIDEO_STATUS = { in_production: ["Making", "bg-accent"], done: ["Delivered", "bg-success"], failed: ["Didn't finish", "bg-danger"] } as const;
const whole = (n: number) => {
  const c = wholeCredits(n);
  return `${c} credit${c === 1 ? "" : "s"}`;
};
function Status({ dot, children }: { dot: string; children: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm text-muted">
      <span aria-hidden className={`size-2 rounded-full ${dot}`} />
      {children}
    </span>
  );
}

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
      <PageTop title="My credits" />
      {mine.isError && <Banner title="Couldn't load your credits." action={<Button variant="secondary" onClick={() => void mine.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      <div className="grid gap-3 lg:grid-cols-2">
      <Card className="space-y-2">
        <h2 className="type-section">Your allowance this week</h2>
        {!week ? (
          <Skeleton className="h-16" />
        ) : (
          <>
            <p className="font-medium">
              {week.allowance === null ? `${whole(week.used)} used` : `${whole(week.used)} of ${whole(week.allowance)} used`}
              {week.allowance !== null && <span className="text-sm font-normal text-muted"> · resets on Monday</span>}
            </p>
            {week.lines.length === 0 ? (
              <p className="text-sm text-muted">Nothing used yet this week.</p>
            ) : (
              <ul aria-label="This week's charges" className="divide-y divide-border text-sm">
                {week.lines.map((l) => (
                  <li key={l.label} className="flex justify-between gap-3 py-2">
                    <span>{l.label}</span>
                    <span className="tabular-nums">{whole(l.credits)}</span>
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
            {whole(m.credits)} {periodWord(period)}
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
                        <Status dot={VIDEO_STATUS[v.status][1]}>{VIDEO_STATUS[v.status][0]}</Status>
                        <span className="text-right tabular-nums text-muted">
                          {/* The Producer, 3 Nov: "spent N", the director's time included; what the owner approved, muted,
                              where there is one (rule 34). The director's split is on Usage only. */}
                          spent {wholeCredits(v.credits).toLocaleString("en-US")}
                          {v.approved_up_to != null && <span className="block text-xs">up to {wholeCredits(v.approved_up_to).toLocaleString("en-US")} approved</span>}
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
                      {x.freestyle_id ? <Link to={`/freestyle/${x.freestyle_id}`} className="inline-flex min-h-11 items-center font-medium hover:underline lg:min-h-0">{x.title}</Link> : <span className="font-medium">{x.title}</span>}
                      {x.brand && <span className="text-muted"> · {x.brand}</span>}
                      {x.status === "declined" && x.reason && <span className="block text-muted">"{x.reason}"</span>}
                    </span>
                    <span className="flex items-center gap-2">
                      <Status dot={x.status === "declined" ? "bg-danger" : "bg-warning"}>{x.status === "declined" ? "Declined" : "Waiting for the owner's OK"}</Status>
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
                <span className="tabular-nums">{whole(m.quick_clip_credits)}</span>
              </li>
              {m.scripts.map((s) => (
                <li key={s.script_id} className="flex items-center justify-between gap-3">
                  <Link to={`/b/${brandId}/scripts/${s.script_id}`} className="flex min-h-control min-w-0 items-center break-words underline-offset-2 hover:underline">
                    Writing "{s.title}"
                  </Link>
                  <span className="tabular-nums">{whole(s.credits)}</span>
                </li>
              ))}
            </ul>
          </Card>
        </>
      )}
    </main>
  );
}
