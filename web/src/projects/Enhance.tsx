import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText, must } from "../api/client";
import type { components } from "../api/schema";
import { useJobs } from "../clip/History";
import { btnPrimary, btnSecondary, card, errorText as errorClass, linkText } from "../ui";

export type Mark = components["schemas"]["SuggestionOut"];

const KIND: Record<string, string> = {
  camera: "Camera",
  action: "Movement",
  reaction: "Reaction",
  brand_screen: "Brand screen",
  scene_break: "Scene break",
  cut: "Cut",
};
const GOING = ["queued", "running", "needs_owner_approval"];

/** Everything about Enhance for one project: the run, its marks and notes, and what you do with them. */
export function useEnhance(projectId: number, scriptVersion: number | undefined) {
  const queryClient = useQueryClient();
  const path = { project_id: projectId };
  const jobs = useJobs();
  const last = jobs.data?.filter((j) => j.kind === "write-claude" && j.project_id === projectId).sort((a, b) => b.id - a.id)[0];
  const running = !!last && GOING.includes(last.status);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["enhance", projectId] });

  const has = scriptVersion !== undefined;
  const marks = useQuery({
    enabled: has,
    queryKey: ["enhance", projectId, "marks", scriptVersion, last?.status],
    queryFn: async () => (await api.GET("/projects/{project_id}/script/suggestions", { params: { path } })).data ?? [],
  });
  const notes = useQuery({
    enabled: has,
    queryKey: ["enhance", projectId, "notes", scriptVersion, last?.status],
    queryFn: async () => (await api.GET("/projects/{project_id}/script/notes", { params: { path } })).data ?? [],
  });
  const rates = useQuery({ queryKey: ["rates"], queryFn: async () => (await api.GET("/credits/rates")).data ?? [] });
  const cost = rates.data?.find((r) => r.kind === "write-claude")?.credits_per_unit;

  const start = useMutation({
    mutationFn: async () => {
      const { error, response } = await api.POST("/projects/{project_id}/script/enhance", { params: { path } });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });
  const decide = useMutation({
    mutationFn: ({ id, verb }: { id: number; verb: "accept" | "reject" }) =>
      must(api.POST(verb === "accept" ? "/projects/{project_id}/script/suggestions/{suggestion_id}/accept" : "/projects/{project_id}/script/suggestions/{suggestion_id}/reject", {
        params: { path: { ...path, suggestion_id: id } },
      })),
    onSuccess: refresh,
  });
  const apply = useMutation({
    mutationFn: () => must(api.POST("/projects/{project_id}/script/apply", { params: { path } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["script", projectId] }),
  });
  return { marks: marks.data ?? [], notes: notes.data ?? [], last, running, cost, start, decide, apply };
}

export type EnhanceState = ReturnType<typeof useEnhance>;

export function EnhanceBar({ e }: { e: EnhanceState }) {
  const pending = e.marks.filter((m) => m.status === "pending").length;
  const accepted = e.marks.filter((m) => m.status === "accepted").length;
  const failed = e.last?.status === "failed" && e.marks.length === 0;
  const problem = e.start.error ?? e.decide.error ?? e.apply.error;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <button
          className={btnPrimary}
          disabled={e.running || e.start.isPending}
          onClick={() => (pending === 0 || window.confirm(`Replace the ${pending} waiting suggestions?`)) && e.start.mutate()}
        >
          ✦ Enhance{e.cost !== undefined && ` · ${e.cost} credits`}
        </button>
        {accepted > 0 && (
          <button className={btnSecondary} disabled={e.apply.isPending} onClick={() => e.apply.mutate()}>
            Apply {accepted} accepted
          </button>
        )}
        {e.running && <span className="text-sm text-muted">{e.last?.status === "needs_owner_approval" ? "Waiting for Reed to approve" : "Reading your script…"}</span>}
        {e.marks.length > 0 && <span className="text-sm text-muted">{pending} suggestions waiting · {accepted} accepted</span>}
      </div>
      {accepted > 0 && pending > 0 && <p className="text-sm text-muted">Applying adds the accepted notes as a new version. Suggestions you haven't decided on are dropped.</p>}
      {failed && (
        <p role="alert" className={errorClass}>
          Enhance didn't finish. Your script is unchanged. Press Enhance to try again.
        </p>
      )}
      {problem && <p role="alert" className={errorClass}>{problem.message}</p>}
      {!e.running && e.last?.status === "succeeded" && e.marks.length === 0 && <p className="text-sm text-muted">This script already reads well. Nothing to suggest.</p>}
    </div>
  );
}

/** One direction note, shown on its own indented line, never merged into the script's words. */
export function MarkLine({ mark, e }: { mark: Mark; e: EnhanceState }) {
  if (mark.status === "rejected") return null;
  const accepted = mark.status === "accepted";
  return (
    <li className={`ml-4 flex flex-wrap items-baseline gap-x-3 gap-y-1 py-0.5 text-sm sm:ml-10 ${accepted ? "text-muted" : ""}`} data-kind={mark.kind}>
      {/* Phone: the words first, then the kind and the buttons on a second line. */}
      <span className="basis-full sm:basis-0 sm:flex-1">
        {/* Only the suggestion's own words are marked, never the row or the buttons. */}
        <span className={accepted ? "" : "bg-mark underline decoration-mark-line decoration-2 underline-offset-2"}>
          {mark.kind === "brand_screen" ? "★ " : "▸ "}
          {mark.text}
        </span>
        {!accepted && mark.reason && <span className="block text-xs text-muted">Why: {mark.reason}</span>}
      </span>
      <span className="text-xs text-muted">{KIND[mark.kind] ?? mark.kind}</span>
      <span className="ml-auto flex gap-3 sm:ml-0">
        {!accepted && (
          <button className={`${btnSecondary} min-h-11 sm:min-h-8`} aria-label={`Accept: ${mark.text}`} onClick={() => e.decide.mutate({ id: mark.id, verb: "accept" })}>
            Accept
          </button>
        )}
        <button className={`${btnSecondary} min-h-11 sm:min-h-8`} aria-label={`${accepted ? "Remove" : "Reject"}: ${mark.text}`} onClick={() => e.decide.mutate({ id: mark.id, verb: "reject" })}>
          {accepted ? "Remove" : "Reject"}
        </button>
      </span>
    </li>
  );
}

/** Things Claude noticed but must not fix. The only action is "Got it". */
export function Notes({ e, version }: { e: EnhanceState; version: number }) {
  const [gone, setGone] = useState<string[]>([]);
  const key = (n: { line: number; text: string }) => `${version}:${n.line}:${n.text}`;
  const shown = e.notes.filter((n) => !gone.includes(key(n)));
  if (shown.length === 0) return null;
  return (
    <section className={`${card} space-y-2 text-sm`} aria-label="Notes">
      <h3 className="font-semibold">Notes ({shown.length})</h3>
      <p className="text-muted">Claude noticed these. Nothing here changes your script.</p>
      <ul className="space-y-2">
        {shown.map((n) => (
          <li key={key(n)} className="flex items-start gap-3">
            <span className="flex-1">Line {n.line}: {n.text}</span>
            <button className={linkText} aria-label={`Got it: line ${n.line}`} onClick={() => setGone([...gone, key(n)])}>
              Got it
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
