import { useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { card, linkText, pageTitle } from "../ui";
import { Meter, WaitingBadge } from "./Meter";
import { ScriptTab } from "./ScriptTab";

/** The project workspace. The script tabs build on this page next. */
export function ProjectPage() {
  const { brandId, projectId } = useParams();
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "script" ? "script" : "brief";
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
        <div className="w-full sm:w-72">
          <Meter used={p.credits_used} budget={p.budget_credits} pct={p.budget_pct} />
        </div>
      </div>
      {p.status === "needs_owner_approval" && <WaitingBadge />}
      <div role="tablist" className="flex gap-1 text-sm">
        {(["brief", "script"] as const).map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            className={`min-h-11 rounded-sm px-3 sm:min-h-9 ${tab === t ? "bg-accent-soft font-medium text-accent-text" : "text-muted"}`}
            onClick={() => setParams(t === "brief" ? {} : { tab: t })}
          >
            {t === "brief" ? "Brief" : "Script"}
          </button>
        ))}
      </div>
      {tab === "script" ? (
        <ScriptTab projectId={p.id} />
      ) : (
        <section className={`${card} space-y-1 text-sm`} aria-label="Brief">
          <h2 className="text-[length:var(--text-md)] font-semibold">Brief</h2>
          {p.goal && <p>{p.goal}</p>}
          <p className="text-muted">{[p.platform, p.aspect_ratio, p.format, `${p.planned_seconds}s planned`].filter(Boolean).join(" · ")}</p>
        </section>
      )}
    </main>
  );
}
