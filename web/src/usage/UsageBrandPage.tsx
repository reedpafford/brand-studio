import { ChevronLeft } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { Banner, Button } from "../components";
import { BrandLists } from "./BrandLists";
import { PeriodControl, Stats, periodLine } from "./parts";
import { periodFrom, useBrandUsage, useSummary } from "./useUsage";

/** One brand's tracker: the same four figures. Its videos and scripts come with the lists. */
export function UsageBrandPage() {
  const brandId = Number(useParams().brandId);
  const [params, setParams] = useSearchParams();
  const period = periodFrom(params.get("period"));
  const brand = useBrandUsage(brandId, period);
  const summary = useSummary(period); // for the period's start date
  if (brand.error?.message === "404") return <p className="p-6">Page not found.</p>;
  const b = brand.data;
  return (
    <main className="mx-auto max-w-content space-y-5 p-4 sm:p-6">
      <Link to="/usage" className="inline-flex min-h-control items-center gap-1 text-accent-text hover:underline lg:min-h-control-dense">
        <ChevronLeft size={20} strokeWidth={1.75} aria-hidden />
        Usage
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-3 type-page">
            {b && <span aria-hidden className="size-4 shrink-0 rounded-full bg-faint" style={b.colour ? { background: b.colour } : undefined} />}
            {b?.name ?? " "}
          </h1>
          <p className="text-sm text-muted">{b ? periodLine(period, summary.data?.starts_at ?? null) : " "}</p>
        </div>
        <PeriodControl value={period} onChange={(p) => setParams(p === "week" ? {} : { period: p }, { replace: true })} />
      </div>
      {brand.isError && <Banner title="Couldn't load usage." action={<Button variant="secondary" onClick={() => void brand.refetch()}>Try again</Button>}>Check your connection.</Banner>}
      <Stats figures={b} period={period} />
      {b && (
        <p className="text-sm text-muted">
          {b.scripts} script{b.scripts === 1 ? "" : "s"} · {b.versions_left} version{b.versions_left === 1 ? "" : "s"} left to make · {b.editors_active} {b.editors_active === 1 ? "person" : "people"} made videos {period === "all" ? "so far" : period === "week" ? "this week" : "this month"}
        </p>
      )}
      {b && <BrandLists brandId={brandId} period={period} />}
    </main>
  );
}
