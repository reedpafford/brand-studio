import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText, must } from "../api/client";
import type { components } from "../api/schema";
import { useJobs } from "../clip/History";
import { useToast } from "../toast";
import { Check, ChevronDown, Sparkles, X } from "lucide-react";
import { Button, Menu, MenuItem } from "../components";
import { Elapsed } from "../clip/History";
import { card, errorText as errorClass } from "../ui";
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
  const last = jobs.data?.filter((j) => j.kind === "write-claude" && j.step === "enhance" && j.project_id === projectId).sort((a, b) => b.id - a.id)[0];
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
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["script", projectId] });
      toast(`Added ${acceptedCount} direction${acceptedCount === 1 ? "" : "s"}.`, async () => {
        await putScript(scriptText);
        queryClient.invalidateQueries({ queryKey: ["script", projectId] });
      });
    },
  });
  // Which kind you're looking at (null = all) and which suggestion the keys act on.
  const [filter, setFilter] = useState<string | null>(null);
  const [focusId, setFocusId] = useState<number | null>(null);
  const shown = (marks.data ?? []).filter((m) => m.status !== "rejected" && (!filter || m.kind === filter));
  const visibleNotes = (notes.data ?? []).filter((n) => !gone.includes(`${scriptVersion}:${n.line}:${n.text}`));
  const dismiss = (n: { line: number; text: string }) => setGone((g) => [...g, `${scriptVersion}:${n.line}:${n.text}`]);
  return { marks: marks.data ?? [], notes: visibleNotes, last, running, cost, start, decide, apply, acceptMany, dismiss, filter, setFilter, focusId, setFocusId, shown };
}

export type EnhanceState = ReturnType<typeof useEnhance>;

function AcceptAll({ e }: { e: EnhanceState }) {
  const pending = e.marks.filter((m) => m.status === "pending");
  if (pending.length === 0) return null;
  const kinds = [...new Set(pending.map((m) => m.kind))];
  const run = (kind?: string) => {
    const ids = pending.filter((m) => !kind || m.kind === kind).map((m) => m.id);
    if (ids.length > 5 && !window.confirm(`Accept ${ids.length} suggestions?`)) return;
    e.acceptMany.mutate(ids);
  };
  return (
    <Menu title="Accept all" trigger={(t) => <Button variant="ghost" {...t} trailing={ChevronDown} aria-label="Accept all options">Accept all</Button>}>
      {(close) => (
        <>
          <MenuItem onClick={() => { close(); run(); }}>Accept all ({pending.length})</MenuItem>
          {kinds.length > 1 &&
            kinds.map((k) => (
              <MenuItem key={k} onClick={() => { close(); run(k); }}>
                Accept all {KIND[k] ?? k} ({pending.filter((m) => m.kind === k).length})
              </MenuItem>
            ))}
        </>
      )}
    </Menu>
  );
}

/** Filter chips: All and each kind that is waiting, with counts. They scroll sideways on a phone. */
function Chips({ e }: { e: EnhanceState }) {
  const live = e.marks.filter((m) => m.status !== "rejected");
  const kinds = [...new Set(live.map((m) => m.kind))];
  if (live.length === 0 || kinds.length < 2) return null;
  const chip = (on: boolean) => `min-h-control shrink-0 rounded-full border px-3 text-sm lg:min-h-control-dense ${on ? "border-accent bg-accent-soft text-accent-text" : "border-border-strong bg-surface"}`;
  return (
    <div className="flex gap-2 overflow-x-auto" role="group" aria-label="Show">
      <button className={chip(e.filter === null)} aria-pressed={e.filter === null} onClick={() => e.setFilter(null)}>
        All {live.length}
      </button>
      {kinds.map((k) => (
        <button key={k} className={chip(e.filter === k)} aria-pressed={e.filter === k} onClick={() => e.setFilter(e.filter === k ? null : k)}>
          {KIND[k] ?? k} {live.filter((m) => m.kind === k).length}
        </button>
      ))}
    </div>
  );
}

/** J / K move between suggestions, A accepts, R rejects, Esc lets go. Typing in a box is never hijacked. */
function useKeys(e: EnhanceState) {
  const latest = useRef(e);
  useEffect(() => {
    latest.current = e;
  });
  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      const t = ev.target as HTMLElement | null;
      if (ev.metaKey || ev.ctrlKey || ev.altKey || t?.closest("input, textarea, select, [contenteditable], [role=dialog]")) return;
      const { shown, focusId, setFocusId, decide } = latest.current;
      const at = shown.findIndex((m) => m.id === focusId);
      const key = ev.key.toLowerCase();
      if (key === "j" || key === "k") {
        if (shown.length === 0) return;
        const next = key === "j" ? (at + 1) % shown.length : (at <= 0 ? shown.length : at) - 1;
        setFocusId(shown[next].id);
      } else if (key === "escape") setFocusId(null);
      else if ((key === "a" || key === "r") && at >= 0) {
        const mark = shown[at];
        if (key === "a" && mark.status !== "pending") return;
        decide.mutate({ id: mark.id, verb: key === "a" ? "accept" : "reject" });
        // Carry on with the next waiting suggestion (wrapping round), so A / R can be pressed again straight away.
        const waiting = shown.filter((m) => m.status === "pending" && m.id !== mark.id);
        setFocusId((waiting.find((m) => shown.indexOf(m) > at) ?? waiting[0])?.id ?? null);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);
}

export function EnhanceBar({ e, stop }: { e: EnhanceState; stop?: string | null }) {
  useKeys(e);
  const [notesOpen, setNotesOpen] = useState(false);
  const pending = e.marks.filter((m) => m.status === "pending").length;
  const accepted = e.marks.filter((m) => m.status === "accepted").length;
  const failed = e.last?.status === "failed" && e.marks.length === 0;
  const problem = e.start.error ?? e.decide.error ?? e.apply.error;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="secondary"
          icon={Sparkles}
          price={e.cost}
          disabled={e.running || e.start.isPending || !!stop}
          reason={stop}
          onClick={() => (pending === 0 || window.confirm(`Replace the ${pending} waiting suggestions?`)) && e.start.mutate()}
        >
          Suggest directions
        </Button>
        {e.marks.length > 0 && (
          <span className="text-sm text-muted">
            {pending + accepted} suggestion{pending + accepted === 1 ? "" : "s"}
            {e.notes.length > 0 && ` · ${e.notes.length} note${e.notes.length === 1 ? "" : "s"}`}
          </span>
        )}
        <AcceptAll e={e} />
        {e.notes.length > 0 && (
          <Button variant="ghost" className="lg:hidden" onClick={() => setNotesOpen(true)}>
            Notes ({e.notes.length})
          </Button>
        )}
        {e.running && <span className="text-sm text-muted">{e.last?.status === "needs_owner_approval" ? "Waiting for the owner's OK" : <>Reading your script… <Elapsed since={e.last?.created_at ?? new Date().toISOString()} /></>}</span>}
        {accepted > 0 && (
          <span className="ml-auto">
            <Button disabled={e.apply.isPending} busy={e.apply.isPending} onClick={() => e.apply.mutate()}>
              Add {accepted} direction{accepted === 1 ? "" : "s"}
            </Button>
          </span>
        )}
      </div>
      <Chips e={e} />
      {e.marks.length > 0 && <p className="hidden text-xs text-muted sm:block">Keys: J / K next and previous, A accept, R reject, Esc to let go.</p>}
      {accepted > 0 && pending > 0 && <p className="text-sm text-muted">Adding keeps your accepted directions in the script. Suggestions you haven't decided on are dropped.</p>}
      {failed && (
        <p role="alert" className={errorClass}>
          Suggestions didn't finish. Your script is unchanged. Press Suggest directions to try again.
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
  const row = useRef<HTMLLIElement>(null);
  const focused = e.focusId === mark.id;
  useEffect(() => {
    if (focused) row.current?.scrollIntoView?.({ block: "nearest" });
  }, [focused]);
  if (mark.status === "rejected") return null;
  const accepted = mark.status === "accepted";
  return (
    <li ref={row} aria-current={focused ? "true" : undefined} className={`ml-4 flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded-sm py-0.5 text-sm sm:ml-10 ${accepted ? "text-muted" : ""} ${focused ? "outline outline-2 outline-accent" : ""}`} data-kind={mark.kind}>
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
          <Button variant="secondary" dense icon={Check} aria-label={`Accept: ${mark.text}`} onClick={() => e.decide.mutate({ id: mark.id, verb: "accept" })}>
            Accept
          </Button>
        )}
        <Button variant="ghost" dense icon={X} aria-label={`${accepted ? "Remove" : "Reject"}: ${mark.text}`} onClick={() => e.decide.mutate({ id: mark.id, verb: "reject" })}>
          {accepted ? "Remove" : "Reject"}
        </Button>
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
          <Button variant="ghost" dense aria-label={`Got it: line ${n.line}`} onClick={() => e.dismiss(n)}>
            Got it
          </Button>
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
