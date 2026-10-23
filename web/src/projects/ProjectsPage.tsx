import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useBrands } from "../shell/useBrands";
import { btnPrimary, card, pageTitle } from "../ui";
import { Meter } from "./Meter";

export function ProjectsPage() {
  const brandId = Number(useParams().brandId);
  const { data: brands } = useBrands();
  const name = brands?.find((b) => b.id === brandId)?.name ?? "this brand";
  const projects = useQuery({
    queryKey: ["projects", brandId],
    queryFn: async () => {
      const { data } = await api.GET("/projects", { params: { query: { brand_id: brandId } } });
      if (!data) throw new Error("load");
      return data;
    },
  });
  const newButton = (
    <Link to={`/b/${brandId}/projects/new`} className={`${btnPrimary} inline-block`}>
      New video
    </Link>
  );

  return (
    <main className="mx-auto max-w-5xl space-y-4 p-4 sm:p-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className={pageTitle}>Projects</h1>
        {projects.data && projects.data.length > 0 && newButton}
      </div>
      {projects.isError && (
        <p role="alert" className="text-sm text-danger">
          Could not load the projects. Try again.
        </p>
      )}
      {projects.data?.length === 0 && (
        <div className={`${card} space-y-3`}>
          <p className="text-[length:var(--text-xl)] font-semibold">No videos for {name} yet.</p>
          <p className="text-muted">Start from a brief or a script.</p>
          {newButton}
        </div>
      )}
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {projects.data?.map((p) => (
          <li key={p.id}>
            <Link to={`/b/${brandId}/projects/${p.id}`} className={`${card} block space-y-2 hover:border-border-strong`}>
              <span className="block text-[length:var(--text-md)] font-semibold">{p.name}</span>
              <span className="block text-sm text-muted">
                {p.planned_seconds}s · {p.aspect_ratio || "9:16"}
                {p.status === "needs_owner_approval" && " · Waiting for the owner to approve"}
              </span>
              <Meter used={p.credits_used} budget={p.budget_credits} pct={p.budget_pct} />
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
