import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorText } from "../api/client";
import { Banner, Button, creditsText } from "../components";
import { useToast } from "../toast";
import { STEPS } from "./ApprovalsPage";
import type { Job } from "./useHeld";

/** Which of my requests belong on this page: a video's, a script's, or my Quick clips (no video, no script). */
export type HeldWhere = { projectId: number } | { scriptId: number } | { quick: true };
const here = (j: Job, w: HeldWhere) =>
  "projectId" in w ? j.project_id === w.projectId : "scriptId" in w ? j.script_id === w.scriptId && j.project_id == null : j.project_id == null && j.script_id == null;
// The server words a decline without a reason itself ("The owner said no this time…"); only a reason the owner typed is shown.
const reasonOf = (j: Job) => (j.error && !j.error.startsWith("The owner said no") ? j.error : "");
const seenKey = "declines-seen";
const readSeen = (): number[] => {
  try {
    return JSON.parse(localStorage.getItem(seenKey) ?? "[]");
  } catch {
    return [];
  }
};

/** My presses held for the owner (Hold requests, Reed 30 Oct): each says "Waiting for approval" with why, and Withdraw
 *  (nothing is charged). An approved one just runs; a declined one says so once, with the owner's reason, until dismissed. */
export function HeldRequests({ where }: { where: HeldWhere }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [seen, setSeen] = useState(readSeen);
  const mine = useQuery({
    queryKey: ["jobs", "mine"],
    queryFn: async () => (await api.GET("/jobs", { params: { query: { mine: true } } })).data ?? [],
    refetchInterval: (q) => (q.state.data?.some((j) => j.status === "needs_owner_approval") ? 15_000 : false),
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
  const jobs = (mine.data ?? []).filter((j) => here(j, where));
  const held = jobs.filter((j) => j.status === "needs_owner_approval");
  const declined = jobs.filter((j) => j.declined && !seen.includes(j.id));
  if (held.length === 0 && declined.length === 0) return null;
  const what = (j: Job) => (j.step ? (STEPS[j.step] ?? "Your request") : j.project_id == null && j.script_id == null ? "Your Quick clip" : "Your request");
  return (
    <div className="space-y-2" aria-label="Your requests">
      {held.map((j) => (
        <Banner key={j.id} tone="info" title="Waiting for approval" action={<Button variant="secondary" busy={withdraw.isPending && withdraw.variables?.id === j.id} onClick={() => withdraw.mutate(j)}>Withdraw</Button>}>
          {what(j)} · {creditsText(j.credits)}. {j.held || "It goes past the budget."} The owner sees it in Approvals; nothing is charged unless they approve.
        </Banner>
      ))}
      {declined.map((j) => (
        <Banner key={j.id} tone="warning" title={reasonOf(j) ? `The owner said no: ${reasonOf(j)}` : "The owner said no"} action={<Button variant="ghost" onClick={() => dismiss(j.id)}>OK</Button>}>
          {what(j)} wasn't made. Nothing was charged.
        </Banner>
      ))}
    </div>
  );
}
