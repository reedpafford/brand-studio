import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, errorText } from "../api/client";
import { Banner, Button, buttonClass, creditsText } from "../components";
import { serverTime } from "../time";
import { useMe } from "../auth/useMe";
import { useToast } from "../toast";
import { PLURAL, STEPS } from "./ApprovalsPage";
import type { Job } from "./useHeld";

/** Which of my requests belong on this page: a video's, a script's, or my Quick clips (no video, no script). */
export type HeldWhere = { projectId: number } | { scriptId: number } | { quick: true };
// A Quick clip is a video or an image with no step, video or script; never just "not on a video or script" (QA on #1088).
const quick = (j: Job) => (j.kind === "video" || j.kind === "image") && !j.step && j.project_id == null && j.script_id == null;
const here = (j: Job, w: HeldWhere) =>
  "projectId" in w ? j.project_id === w.projectId : "scriptId" in w ? j.script_id === w.scriptId && j.project_id == null : quick(j);
// The server words a decline without a reason itself ("The owner said no this time…"); only a reason the owner typed is shown.
const reasonOf = (j: Job) => (j.error && !j.error.startsWith("The owner said no") ? j.error : "");
const lower = (t: string) => t.charAt(0).toLowerCase() + t.slice(1);
const what = (j: Job) =>
  j.step === "song_take" ? (j.kind === "speech" ? "Your narration" : "Your song or music") : j.step ? (STEPS[j.step] ?? "Your request") : quick(j) ? "Your Quick clip" : "Your request";
// Where "Change this…" goes for a declined press: the video step it was pressed on (ux-audit §8.4). A change goes where its
// still or clip is.
const VIDEO_STEP: Record<string, string> = {
  plan: "plan", plan_scene: "plan", breakdown: "plan", song_breakdown: "plan", narrated_breakdown: "plan", sheet: "cast",
  storyboard: "storyboard", frame: "storyboard", stills: "storyboard", clip_prompts: "clips", clip_take: "clips", improve: "clips",
};
export const stepOf = (j: Job) => (j.step === "change" ? (j.frame_id != null ? "storyboard" : "clips") : j.step ? VIDEO_STEP[j.step] : undefined);
const seenKey = "declines-seen";
const readSeen = (): number[] => {
  try {
    return JSON.parse(localStorage.getItem(seenKey) ?? "[]");
  } catch {
    return [];
  }
};

/** "Asked just now", "Asked 2 min ago", "Asked 3 h ago", "Asked 2 days ago". */
export function askedAgo(iso: string, now = Date.now()) {
  const min = Math.max(0, Math.floor((now - serverTime(iso).getTime()) / 60_000));
  if (min < 1) return "Asked just now";
  if (min < 60) return `Asked ${min} min ago`;
  if (min < 60 * 24) return `Asked ${Math.floor(min / 60)} h ago`;
  const days = Math.floor(min / (60 * 24));
  return `Asked ${days} day${days === 1 ? "" : "s"} ago`;
}

/** My requests waiting for the owner, everywhere (one read, shared with the banners). */
export function useMyRequests() {
  return useQuery({
    queryKey: ["jobs", "mine"],
    queryFn: async () => (await api.GET("/jobs", { params: { query: { mine: true } } })).data ?? [],
    refetchInterval: (q) => (q.state.data?.some((j) => j.status === "needs_owner_approval") ? 15_000 : false),
  });
}

/** "1 request waiting for the owner" for a video (its header, and its row on Videos); nothing when none waits. */
export function WaitingCount({ projectId, className = "" }: { projectId: number; className?: string }) {
  const n = (useMyRequests().data ?? []).filter((j) => j.project_id === projectId && j.status === "needs_owner_approval").length;
  if (!n) return null;
  return <span className={`text-sm font-medium text-warning ${className}`}>{n} request{n === 1 ? "" : "s"} waiting for the owner</span>;
}

/** My presses held for the owner (Hold requests, Reed 30 Oct; ux-audit §8.4): each says "Waiting for approval", when it was
 *  asked and why, with Withdraw (nothing is charged). An approved one says so once and runs; a declined one says so, with
 *  the owner's reason, until OK or Change this…. */
export function HeldRequests({ where }: { where: HeldWhere }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [seen, setSeen] = useState(readSeen);
  const mine = useMyRequests();
  const owner = useMe().data?.role === "owner";
  // The owner's own presses are never held: on a video or a script they see what anyone asked there, one press from its row
  // in Approvals (no dead end; #1119). Editors' Quick clips wait in Approvals only.
  const asked = useQuery({
    enabled: owner && !("quick" in where),
    queryKey: ["held-jobs"],
    refetchInterval: 30_000,
    queryFn: async () => (await api.GET("/jobs", { params: { query: { status: "needs_owner_approval" } } })).data ?? [],
  });
  const withdraw = useMutation({
    mutationFn: async (j: Job) => {
      const { error, response } = await api.POST("/jobs/{job_id}/cancel", { params: { path: { job_id: j.id } } });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: () => {
      toast("Withdrawn. Nothing was charged.");
      return queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  const dismiss = (id: number) => {
    const next = [...seen, id];
    setSeen(next);
    try {
      localStorage.setItem(seenKey, JSON.stringify(next.slice(-50)));
    } catch {
      /* a private window: it shows again next time */
    }
  };
  const jobs = ((owner ? asked.data : mine.data) ?? []).filter((j) => here(j, where));
  const held = jobs.filter((j) => j.status === "needs_owner_approval");
  const declined = jobs.filter((j) => j.declined && !seen.includes(j.id));
  // A request that was waiting here and now runs was approved: say so once (a withdrawn or declined one is cancelled).
  const waiting = useRef(new Set<number>());
  useEffect(() => {
    if (owner) return; // the owner said yes themselves
    for (const j of jobs) {
      if (waiting.current.has(j.id) && j.status !== "needs_owner_approval" && j.status !== "cancelled" && !j.declined) {
        toast(`The owner said yes: ${lower(what(j))} ${PLURAL.has(what(j)) ? "are" : "is"} being made.`);
        waiting.current.delete(j.id);
      }
    }
    waiting.current = new Set([...waiting.current].filter((id) => jobs.some((j) => j.id === id && j.status === "needs_owner_approval")));
    for (const j of held) waiting.current.add(j.id);
  });
  if (held.length === 0 && declined.length === 0) return null;
  if (owner)
    return (
      <div className="space-y-2" aria-label="Waiting for you">
        {held.map((j) => (
          <Banner key={j.id} tone="info" title="Waiting for your OK" action={<Link className={buttonClass("secondary")} to={`/approvals?job=${j.id}`}>Open in Approvals</Link>}>
            {j.created_by_name || "An editor"} asked for {lower(what(j).replace(/^Your /, ""))} · {creditsText(j.credits)} · {askedAgo(j.created_at)}. {j.held}
          </Banner>
        ))}
      </div>
    );
  const change = (j: Job) => {
    const step = j.project_id != null ? (stepOf(j) ?? "plan") : undefined; // on a video, never a dead end
    if (step)
      return (
        <Link className={buttonClass("secondary")} to={`?step=${step}`} onClick={() => dismiss(j.id)}>
          Change this…
        </Link>
      );
    // Quick clip and a script's song or narration: the words to change are on this page.
    const field = () => document.querySelector<HTMLElement>("main textarea")?.focus();
    return (
      <Button
        variant="secondary"
        onClick={() => {
          dismiss(j.id);
          field();
        }}
      >
        Change this…
      </Button>
    );
  };
  return (
    <div className="space-y-2" aria-label="Your requests">
      {held.map((j) => (
        <Banner key={j.id} tone="info" title="Waiting for approval" action={<Button variant="secondary" busy={withdraw.isPending && withdraw.variables?.id === j.id} onClick={() => withdraw.mutate(j)}>Withdraw</Button>}>
          {what(j)} · {creditsText(j.credits)} · {askedAgo(j.created_at)}. {j.held || "It goes past the budget."} The owner sees it in Approvals; nothing is charged unless they approve.
        </Banner>
      ))}
      {declined.map((j) => (
        <Banner
          key={j.id}
          tone="warning"
          title={reasonOf(j) ? `The owner said no: ${reasonOf(j)}` : "The owner said no"}
          action={
            <div className="flex flex-wrap gap-2">
              {change(j)}
              <Button variant="ghost" onClick={() => dismiss(j.id)}>
                OK
              </Button>
            </div>
          }
        >
          {what(j)} wasn't made. Nothing was charged.
        </Banner>
      ))}
    </div>
  );
}
