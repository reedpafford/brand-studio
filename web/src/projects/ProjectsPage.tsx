import { useQuery } from "@tanstack/react-query";
import { Bell, Clapperboard, Plus } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useHeld } from "../approvals/useHeld";
import { Badge, Banner, Button, EmptyState, MediaCard, Skeleton, buttonClass } from "../components";
import { useBrands } from "../shell/useBrands";
import { ActionBar } from "../shell/ActionBar";
import { useMedia } from "../useMedia";
import { Meter } from "./Meter";

export function ProjectsPage() {
  const brandId = Number(useParams().brandId);
  const { data: brands } = useBrands();
  const held = useHeld();
  const name = brands?.find((b) => b.id === brandId)?.name ?? "this brand";
  const projects = useQuery({
    queryKey: ["projects", brandId],
    queryFn: async () => {
      const { data } = await api.GET("/projects", { params: { query: { brand_id: brandId } } });
      if (!data) throw new Error("load");
      return data;
    },
  });
  const list = projects.data;
  const phone = !useMedia("(min-width: 1024px)");
  const newVideo = (
    <Link to={`/b/${brandId}/projects/new`} className={buttonClass("primary")}>
      <Plus size={20} strokeWidth={1.75} aria-hidden />
      New video
    </Link>
  );

  return (
    <main className="mx-auto max-w-content space-y-6 p-4 sm:p-6">
      {held.owner && held.count > 0 && (
        <Banner tone="info" title={`${held.count} ${held.count === 1 ? "request is" : "requests are"} waiting for you`} action={<Link to="/approvals" className={buttonClass("secondary")}><Bell size={20} strokeWidth={1.75} aria-hidden />Review</Link>} />
      )}
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="type-eyebrow text-muted">{name}</p>
          <h1 className="type-page">Videos</h1>
        </div>
        {list && list.length > 0 && !phone && newVideo}
      </div>
      {projects.isError && (
        <Banner title="Couldn't load your videos." action={<Button variant="secondary" onClick={() => void projects.refetch()}>Try again</Button>}>
          Check your connection.
        </Banner>
      )}
      {projects.isPending && (
        <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3 xl:grid-cols-4" aria-label="Loading">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="aspect-[9/14] rounded-lg" />
          ))}
        </div>
      )}
      {list?.length === 0 && (
        <EmptyState icon={Clapperboard} title={`No videos for ${name} yet`} action={newVideo}>
          Start from a brief: what it's for, who's in it and how long. Claude helps with the script.
        </EmptyState>
      )}
      {list && list.length > 0 && (
        <>
          <ul className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3 xl:grid-cols-4">
            {list.map((p) => (
              <li key={p.id}>
                <MediaCard
                  to={`/b/${brandId}/projects/${p.id}`}
                  label={`${p.name}, ${p.planned_seconds} s, ${p.aspect_ratio || "9:16"}`}
                  title={p.name}
                  meta={`${p.planned_seconds}s · ${p.aspect_ratio || "9:16"}`}
                  aspect="9 / 14"
                  icon={Clapperboard}
                  badge={p.status === "needs_owner_approval" ? <Badge tone="warning">Waiting for Reed to approve</Badge> : undefined}
                >
                  <Meter used={p.credits_used} budget={p.budget_credits} pct={p.budget_pct} />
                </MediaCard>
              </li>
            ))}
          </ul>
          {phone && <ActionBar phone>{newVideo}</ActionBar>}
        </>
      )}
    </main>
  );
}
