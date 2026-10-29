import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { Button } from "../components";
import { useToast } from "../toast";
import { useMedia } from "../useMedia";
import { show } from "./ApproveAll";
import { Sheet } from "./Sheet";

/** The advisory check on a still or a take (flows P4; Builder-Server-8's CheckOut, #891). Advice only: it never blocks. */
export type Finding = { index: number; kind: string; text: string; note: string };
export type ItemCheck = { id: number; status: "checking" | "ok" | "advice" | "failed" | "skipped"; findings: Finding[] } | null | undefined;
type Flagged = { kind: "still" | "take"; id: number; clip_id: string; label: string; findings: number };
type Review = { on: boolean; credits_per_check: number; items: Flagged[]; paused?: boolean };

// The routes are Builder-Server-8's; until they are in the generated schema they are called with fetch.
async function call(method: "GET" | "POST", path: string) {
  const r = await fetch(`${location.origin}/api${path}`, { method, credentials: "include" });
  if (r.status === 404 && method === "GET") return null; // no checks on this server yet: nothing shows
  const body = await r.json().catch(() => null);
  if (!r.ok) throw new Error(typeof body?.detail === "string" ? body.detail : "That didn't work. Try again.");
  return body;
}

/** PL5: a clean check is only "✓ checked" inside the item's status chip. */
export const checkedMark = (check: ItemCheck) => (check?.status === "ok" ? " · ✓ checked" : "");

export function useReview(projectId: number) {
  return useQuery({ queryKey: ["checks", projectId], queryFn: () => call("GET", `/projects/${projectId}/checks`) as Promise<Review | null>, retry: false });
}

/** Under a still or a take: "Checking…", "Couldn't check this one.", or the quiet "N notes" chip that opens the findings (PL6). */
export function CheckNotes({ check, projectId, label, onChange }: { check: ItemCheck; projectId: number; label: string; onChange: (note: string) => void }) {
  const [open, setOpen] = useState(false);
  const phone = useMedia("(max-width: 639px)");
  const queryClient = useQueryClient();
  const toast = useToast();
  const fine = useMutation({
    mutationFn: (index: number) => call("POST", `/projects/${projectId}/checks/${check!.id}/findings/${index}/dismiss`),
    onError: (e) => toast(e.message),
    onSettled: () => Promise.all(["storyboard", "project-clips", "checks"].map((k) => queryClient.invalidateQueries({ queryKey: [k, projectId] }))),
  });
  // A check that just ended changes the Review list and the summary line.
  const status = check?.status;
  const was = useRef(status);
  useEffect(() => {
    if (was.current === "checking" && status !== "checking") void queryClient.invalidateQueries({ queryKey: ["checks", projectId] });
    was.current = status;
  }, [status]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!check) return null;
  if (check.status === "checking") return <p className="text-xs text-muted" role="status">Checking…</p>;
  if (check.status === "failed") return <p className="text-xs text-muted">Couldn't check this one.</p>;
  const findings = check.findings;
  if (findings.length === 0) return null;
  const lines = (
    <ul className="space-y-3" aria-label={`Notes for ${label}`}>
      {findings.map((f) => (
        <li key={f.index} className="space-y-1">
          <p>{f.text}</p>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" dense onClick={() => { setOpen(false); onChange(f.note); }}>
              Change this…
            </Button>
            <Button variant="ghost" dense busy={fine.isPending && fine.variables === f.index} onClick={() => fine.mutate(f.index)}>
              Looks fine
            </Button>
          </div>
        </li>
      ))}
    </ul>
  );
  const chip = `${findings.length} note${findings.length === 1 ? "" : "s"}`;
  return (
    <div className="text-sm">
      <button type="button" className="inline-flex min-h-11 items-center rounded-sm bg-surface-2 px-2 text-xs font-medium sm:min-h-0 sm:py-0.5" aria-expanded={open} aria-label={`${chip} on ${label}`} onClick={() => setOpen(!open)}>
        {chip}
      </button>
      {open && !phone && <div className="mt-2 rounded-md border border-border bg-surface-2 p-3">{lines}</div>}
      {open && phone && (
        <Sheet title={`${chip} on ${label}`} onClose={() => setOpen(false)}>
          {lines}
        </Sheet>
      )}
    </div>
  );
}

/** The step summary line: "AI check: 3 notes on 2 clips", or once only "Checks paused: the video is at its budget." (PL7). */
export function CheckSummary({ projectId }: { projectId: number }) {
  const review = useReview(projectId).data;
  if (!review?.on) return null;
  if (review.paused) return <p className="text-sm text-muted">Checks paused: the video is at its budget.</p>;
  const notes = review.items.reduce((n, i) => n + i.findings, 0);
  const clips = new Set(review.items.map((i) => i.clip_id)).size;
  if (notes === 0) return null;
  return (
    <p className="text-sm text-muted tabular-nums">
      AI check: {notes} note{notes === 1 ? "" : "s"} on {clips} clip{clips === 1 ? "" : "s"}
    </p>
  );
}

/** "3 items with Advice ▸": the one Review list, grouped by step, each row going to its card (PL8). Open by default on Final cut. */
export function ReviewChip({ projectId, open: startOpen = false }: { projectId: number; open?: boolean }) {
  const review = useReview(projectId).data;
  const [open, setOpen] = useState(startOpen);
  const [params, setParams] = useSearchParams();
  // The card to go to rides in the address (`to`): a row on Final cut changes step, and this chip on the new step finds the
  // card once it's drawn, scrolls to it and moves focus there (keyboard and screen readers follow), then drops `to`.
  const going = params.get("to");
  useEffect(() => {
    if (!going) return;
    let tries = 0;
    const t = setInterval(() => {
      const card = document.querySelector<HTMLElement>(`[aria-label="${going}"]`);
      if (card || ++tries > 30) {
        clearInterval(t);
        show(going);
        card?.setAttribute("tabindex", "-1");
        card?.focus({ preventScroll: true });
        setParams((p) => { p.delete("to"); return p; }, { replace: true });
      }
    }, 100);
    return () => clearInterval(t);
  }, [going]); // eslint-disable-line react-hooks/exhaustive-deps
  const items = review?.items ?? [];
  if (items.length === 0) return null;
  const go = (i: Flagged) => {
    const step = i.kind === "still" ? "storyboard" : "clips";
    setParams((p) => { p.set("step", step); p.set("to", i.kind === "still" ? `Frame ${i.clip_id}` : `Clip ${i.clip_id}`); return p; }); // other params stay
  };
  const group = (kind: Flagged["kind"], title: string) => {
    const these = items.filter((i) => i.kind === kind);
    return these.length === 0 ? null : (
      <div className="space-y-1">
        <p className="text-xs font-medium text-muted">{title}</p>
        <ul>
          {these.map((i) => (
            <li key={`${i.kind}-${i.id}`}>
              <button type="button" className="inline-flex min-h-11 items-center text-left underline sm:min-h-8" onClick={() => go(i)}>
                {i.label} · {i.findings} note{i.findings === 1 ? "" : "s"}
              </button>
            </li>
          ))}
        </ul>
      </div>
    );
  };
  return (
    <div className="w-full space-y-2 text-sm sm:w-auto">
      <Button variant="ghost" dense aria-expanded={open} onClick={() => setOpen(!open)}>
        {items.length} item{items.length === 1 ? "" : "s"} with Advice {open ? "▾" : "▸"}
      </Button>
      {open && (
        <div className="space-y-2 rounded-md border border-border bg-surface-2 p-3" aria-label="Review">
          {group("still", "Storyboard")}
          {group("take", "Clips")}
        </div>
      )}
    </div>
  );
}
