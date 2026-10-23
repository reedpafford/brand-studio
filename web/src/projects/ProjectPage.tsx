import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { card, linkText, pageTitle } from "../ui";
import { Meter } from "./Meter";

/** The project workspace. The script tabs build on this page next. */
export function ProjectPage() {
  const { brandId, projectId } = useParams();
  const project = useQuery({
    queryKey: ["project", Number(projectId)],
    queryFn: async () => (await api.GET("/projects/{project_id}", { params: { path: { project_id: Number(projectId) } } })).data ?? null,
  });
  if (project.isPending) return <p className="p-6 text-muted">Loading…</p>;
  const p = project.data;
  if (!p) return <p className="p-6">That project doesn't exist.</p>;
  return (
    <main className="mx-auto max-w-3xl space-y-4 p-4 sm:p-6">
      <Link to={`/b/${brandId}/projects`} className={linkText}>
        ← Projects
      </Link>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className={pageTitle}>{p.name}</h1>
        <Meter used={p.credits_used} budget={p.budget_credits} pct={p.budget_pct} />
      </div>
      {p.status === "needs_owner_approval" && <p className="text-warning">Waiting for the owner to approve this project.</p>}
      <section className={`${card} space-y-1 text-sm`} aria-label="Brief">
        <h2 className="text-[length:var(--text-md)] font-semibold">Brief</h2>
        {p.goal && <p>{p.goal}</p>}
        <p className="text-muted">
          {[p.platform, p.aspect_ratio, p.format, `${p.planned_seconds}s planned`].filter(Boolean).join(" · ")}
        </p>
      </section>
    </main>
  );
}
