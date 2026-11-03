import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, must } from "../api/client";
import { Banner, Button, Card, PageTop, Skeleton, creditsLabel, wholeCredits } from "../components";
import { MonthPicker, useMonth } from "./parts";

// D_MyCredits: a dot and words, whole credits.
const STATE = {
  making: ["Making", "bg-accent"],
  delivered: ["Delivered", "bg-success"],
  waiting: ["Waiting for the owner's OK", "bg-warning"],
  declined: ["Declined", "bg-danger"],
  stopped: ["Stopped", "bg-faint"],
  failed: ["Didn't finish", "bg-danger"],
} as const;
const whole = (n: number) => {
  const c = wholeCredits(n);
  return `${c.toLocaleString("en-US")} credit${c === 1 ? "" : "s"}`;
};
function Status({ dot, children }: { dot: string; children: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm text-muted">
      <span aria-hidden className={`size-2 rounded-full ${dot}`} />
      {children}
    </span>
  );
}

/** An editor's own credits (flows OR4, v5 D_MyCredits): one month at a time across every brand. What they spent,
 *  their week's allowance and what waits for the owner's OK, then their videos, sends, quick clips and script writing,
 *  in credits only (never dollars, never someone else's). The owner keeps Usage. */
export function MinePage() {
  const { month, label, thisMonth, options, set } = useMonth();
  const mine = useQuery({
    queryKey: ["usage", "mine", month],
    queryFn: async () => (await must(api.GET("/usage/mine", { params: { query: { month } } }))).data!,
  });
  const m = mine.data;
  const waiting = (m?.sends ?? []).filter((x) => x.status === "waiting");
  const week = m?.week;
  const when = thisMonth ? "this month" : `in ${label}`;
  return (
    <main className="mx-auto max-w-content space-y-4 p-4 sm:p-6">
      <PageTop title="My credits">
        <MonthPicker value={month} options={options} onChange={set} />
      </PageTop>
      {mine.isError && <Banner title="Couldn't load your credits." action={<Button variant="secondary" onClick={() => void mine.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      <div className="grid gap-3 lg:grid-cols-3">
      <Card className="space-y-2">
        <h2 className="type-section">Spent {when}</h2>
        {!m ? (
          <Skeleton className="h-12" />
        ) : (
          <>
            <p className="font-medium tabular-nums">{whole(m.credits)}</p>
            <p className="text-sm text-muted">On {m.videos_and_freestyles} video{m.videos_and_freestyles === 1 ? "" : "s"} and freestyles</p>
          </>
        )}
      </Card>
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
      {!m ? (
        !mine.isError && <Skeleton className="h-40" />
      ) : (
        <>
          <Card className="space-y-2">
            <h2 className="type-section">Videos</h2>
            {m.videos.length === 0 ? (
              <p className="text-sm text-muted">No videos of yours {when}.</p>
            ) : (
              <ul aria-label="My videos" className="divide-y divide-border">
                {m.videos.map((v) => (
                  <li key={v.project_id}>
                    <Link to={`/b/${v.brand_id}/videos/${v.project_id}`} className="flex min-h-control flex-wrap items-center justify-between gap-x-3 gap-y-1 py-2 hover:bg-surface-2">
                      <span className="min-w-0 break-words font-medium">{v.title}</span>
                      <span className="flex items-center gap-2 text-sm">
                        <Status dot={STATE[v.state][1]}>{STATE[v.state][0]}</Status>
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
                <li key={s.script_id} className="flex justify-between gap-3 py-2">
                  <span className="min-w-0 break-words">Writing "{s.title}"</span>
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
