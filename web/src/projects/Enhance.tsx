import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText, must } from "../api/client";
import type { components } from "../api/schema";
import { useJobs } from "../clip/History";
import { useToast } from "../toast";
import { btnPrimary, btnSecondary, card, errorText as errorClass, linkText } from "../ui";
import { Sheet } from "./Sheet";

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
export function useEnhance(projectId: number, scriptVersion: number | undefined, scriptText = "") {
  const queryClient = useQueryClient();
  const toast = useToast();
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
  // Accept many at once (one call each); the server keeps accept/reject separate from the script.
  const acceptMany = useMutation({
    mutationFn: async (ids: number[]) => {
      for (const suggestion_id of ids) {
        await must(api.POST("/projects/{project_id}/script/suggestions/{suggestion_id}/accept", { params: { path: { ...path, suggestion_id } } }));
      }
    },
    onSettled: refresh,
  });
  const putScript = async (text: string) => {
    const { error, response } = await api.PUT("/projects/{project_id}/script", { params: { path }, body: { text } });
    if (!response.ok) throw new Error(errorText(error));
  };
  // Notes you've dismissed with "Got it" stay hidden, wherever they're shown.
  const [gone, setGone] = useState<string[]>([]);
  const acceptedCount = (marks.data ?? []).filter((m) => m.status === "accepted").length;
  // Apply adds the accepted directions as a new version. Undo saves the words from before as the next version.
  const apply = useMutation({
    mutationFn: async () => {
      const { data } = await must(api.POST("/projects/{project_id}/script/apply", { params: { path } }));
      return data?.script.version;
    },
    onSuccess: async (made) => {
      await queryClient.invalidateQueries({ queryKey: ["script", projectId] });
      toast(`Added ${acceptedCount} direction${acceptedCount === 1 ? "" : "s"} as v${made}.`, async () => {
        await putScript(scriptText);
        queryClient.invalidateQueries({ queryKey: ["script", projectId] });
      });
    },
  });
  const visibleNotes = (notes.data ?? []).filter((n) => !gone.includes(`${scriptVersion}:${n.line}:${n.text}`));
  const dismiss = (n: { line: number; text: string }) => setGone((g) => [...g, `${scriptVersion}:${n.line}:${n.text}`]);
  return { marks: marks.data ?? [], notes: visibleNotes, last, running, cost, start, decide, apply, acceptMany, dismiss };
}

export type EnhanceState = ReturnType<typeof useEnhance>;

function AcceptAll({ e }: { e: EnhanceState }) {
  const [open, setOpen] = useState(false);
  const pending = e.marks.filter((m) => m.status === "pending");
  if (pending.length === 0) return null;
  const kinds = [...new Set(pending.map((m) => m.kind))];
  const run = (kind?: string) => {
    const ids = pending.filter((m) => !kind || m.kind === kind).map((m) => m.id);
    setOpen(false);
    if (ids.length > 5 && !window.confirm(`Accept ${ids.length} suggestions?`)) return;
    e.acceptMany.mutate(ids);
  };
  return (
    <span className="relative">
      <button className={btnSecondary} aria-haspopup="menu" aria-expanded={open} aria-label="Accept all options" onClick={() => setOpen(!open)}>
        <span className="hidden sm:inline">Accept all ▾</span>
        <span className="sm:hidden" aria-hidden>⋯</span>
      </button>
      {open && (
        <ul role="menu" className="absolute left-0 z-10 mt-1 w-56 rounded-md border border-border bg-surface p-1 text-sm shadow-md">
          <li role="none">
            <button role="menuitem" className="min-h-11 w-full rounded-sm px-3 text-left sm:min-h-9" onClick={() => run()}>
              Accept all ({pending.length})
            </button>
          </li>
          {kinds.length > 1 &&
            kinds.map((k) => (
              <li key={k} role="none">
                <button role="menuitem" className="min-h-11 w-full rounded-sm px-3 text-left sm:min-h-9" onClick={() => run(k)}>
                  Accept all {KIND[k] ?? k} ({pending.filter((m) => m.kind === k).length})
                </button>
              </li>
            ))}
        </ul>
      )}
    </span>
  );
}

export function EnhanceBar({ e }: { e: EnhanceState }) {
  const [notesOpen, setNotesOpen] = useState(false);
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
        <AcceptAll e={e} />
        {accepted > 0 && (
          <button className={btnSecondary} disabled={e.apply.isPending} onClick={() => e.apply.mutate()}>
            Apply {accepted} accepted
          </button>
        )}
        {e.notes.length > 0 && (
          <button className={`${btnSecondary} sm:hidden`} onClick={() => setNotesOpen(true)}>
            Notes ({e.notes.length})
          </button>
        )}
        {e.running && <span className="text-sm text-muted">{e.last?.status === "needs_owner_approval" ? "Waiting for Reed to approve" : "Reading your script…"}</span>}
        {e.marks.length > 0 && <span className="text-sm text-muted">{pending} suggestions waiting · {accepted} accepted</span>}
      </div>
      {accepted > 0 && pending > 0 && <p className="text-sm text-muted">Applying adds the accepted directions as a new version. Suggestions you haven't decided on are dropped.</p>}
      {failed && (
        <p role="alert" className={errorClass}>
          Enhance didn't finish. Your script is unchanged. Press Enhance to try again.
        </p>
      )}
      {problem && <p role="alert" className={errorClass}>{problem.message}</p>}
      {e.acceptMany.isError && <p role="alert" className={errorClass}>{e.acceptMany.error.message}</p>}
      {notesOpen && (
        <Sheet title="Notes" onClose={() => setNotesOpen(false)}>
          <NoteList e={e} />
        </Sheet>
      )}
      {!e.running && e.last?.status === "succeeded" && e.marks.length === 0 && <p className="text-sm text-muted">This script already reads well. Nothing to suggest.</p>}
    </div>
  );
}

/** One direction note, shown on its own indented line, never merged into the script's words. */
export function MarkLine({ mark, e }: { mark: Mark; e: EnhanceState }) {
  const [open, setOpen] = useState(false);
  if (mark.status === "rejected") return null;
  const accepted = mark.status === "accepted";
  return (
    <li className={`ml-4 flex flex-wrap items-baseline gap-x-3 gap-y-1 py-0.5 text-sm sm:ml-10 ${accepted ? "text-muted" : ""}`} data-kind={mark.kind}>
      {/* Phone: the words first, then the kind and the buttons on a second line. */}
      <span className="basis-full sm:basis-0 sm:flex-1">
        {/* Only the suggestion's own words are marked, never the row or the buttons. */}
        <button type="button" aria-haspopup="dialog" className="text-left" onClick={() => setOpen(true)}>
          <span className={accepted ? "" : "bg-mark underline decoration-mark-line decoration-2 underline-offset-2"}>
            {mark.kind === "brand_screen" ? "★ " : "▸ "}
            {mark.text}
          </span>
          {!accepted && mark.reason && <span className="ml-2 text-xs text-muted sm:hidden">Why?</span>}
        </button>
        {!accepted && mark.reason && <span className="hidden text-xs text-muted sm:block">Why: {mark.reason}</span>}
        {open && (
          <Sheet title={KIND[mark.kind] ?? mark.kind} onClose={() => setOpen(false)}>
            <p>{mark.text}</p>
            {mark.reason && <p className="text-sm text-muted">Why: {mark.reason}</p>}
          </Sheet>
        )}
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

/** The notes themselves, with only "Got it". Used in the side card and in the phone sheet. */
function NoteList({ e }: { e: EnhanceState }) {
  if (e.notes.length === 0) return <p className="text-sm text-muted">No notes.</p>;
  return (
    <ul className="space-y-2 text-sm">
      {e.notes.map((n) => (
        <li key={`${n.line}:${n.text}`} className="flex items-start gap-3">
          <span className="flex-1">Line {n.line}: {n.text}</span>
          <button className={linkText} aria-label={`Got it: line ${n.line}`} onClick={() => e.dismiss(n)}>
            Got it
          </button>
        </li>
      ))}
    </ul>
  );
}

/** Things Claude noticed but must not fix. The only action is "Got it". */
export function Notes({ e }: { e: EnhanceState }) {
  if (e.notes.length === 0) return null;
  return (
    <section className={`${card} space-y-2 text-sm`} aria-label="Notes">
      <h3 className="font-semibold">Notes ({e.notes.length})</h3>
      <p className="text-muted">Claude noticed these. Nothing here changes your script.</p>
      <NoteList e={e} />
    </section>
  );
}
