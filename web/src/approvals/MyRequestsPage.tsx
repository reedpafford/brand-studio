import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Film } from "lucide-react";
import { Link } from "react-router-dom";
import { api, errorText } from "../api/client";
import { fileUrl } from "../api/upload";
import { Button, EmptyState, pressLabel, useToast } from "../components";
import { refreshJobs } from "../jobs/refresh";
import { serverTime } from "../time";
import { useMyRequests, what, type Job } from "./HeldRequests";

const time = (iso: string) => serverTime(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const weekAgo = () => Date.now() - 7 * 24 * 3600_000;
const dot = (tone: string) => <span aria-hidden className={`size-[7px] shrink-0 rounded-full ${tone}`} />;

/** An editor's presses waiting for the owner, each with Withdraw, and this week's answers (S-gaps-04 R4). Credits only:
 *  nothing is charged while they wait. */
export function MyRequestsPage() {
  const mine = useMyRequests().data ?? [];
  const videos = useQuery({ queryKey: ["projects", "all"], queryFn: async () => (await api.GET("/projects")).data ?? [] }).data ?? [];
  const video = new Map(videos.map((p) => [p.id, p]));
  const toast = useToast();
  const queryClient = useQueryClient();
  const withdraw = useMutation({
    mutationFn: async (j: Job) => {
      const { error, response } = await api.POST("/jobs/{job_id}/cancel", { params: { path: { job_id: j.id } } });
      if (!response.ok) throw new Error(errorText(error));
    },
    onSuccess: () => (toast("Withdrawn. Nothing was charged."), refreshJobs(queryClient)),
    onError: (e: Error) => toast(e.message, undefined, "error"),
  });
  const waiting = mine.filter((j) => j.status === "needs_owner_approval");
  const answered = mine.filter((j) => (j.approved || j.declined) && serverTime(j.created_at).getTime() > weekAgo());
  const name = (j: Job) => (j.project_id != null ? (video.get(j.project_id)?.name ?? "A video") : (j.freestyle?.title ?? "A Quick clip"));
  const said = (j: Job) => {
    const w = what(j).replace(/^Your /, "");
    return (j.note || w.charAt(0).toUpperCase() + w.slice(1)) + (j.held ? `, ${j.held.charAt(0).toLowerCase()}${j.held.slice(1).replace(/\.$/, "")}` : "");
  };
  return (
    <main className="mx-auto max-w-[760px] space-y-3 p-4 lg:p-8">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-semibold">My requests</h1>
        {waiting.length > 0 && <span className="inline-grid h-[18px] min-w-[18px] place-items-center rounded-full bg-surface-3 px-1.5 text-[11px] font-semibold text-muted tabular-nums">{waiting.length}</span>}
      </div>
      <p className="text-sm text-muted">Presses waiting for the owner’s OK. Nothing is charged while they wait. Withdraw cancels one.</p>
      {waiting.length === 0 ? (
        <EmptyState title="Nothing is waiting for the owner." />
      ) : (
        <ul className="overflow-hidden rounded-lg border border-border bg-surface">
          {waiting.map((j) => {
            const v = j.project_id != null ? video.get(j.project_id) : undefined;
            return (
              <li key={j.id} className="flex flex-wrap items-center gap-3 border-t border-border px-3 py-2.5 first:border-t-0">
                <span aria-hidden className="grid h-[53px] w-[30px] shrink-0 place-items-center overflow-hidden rounded-sm bg-surface-2 text-faint">
                  {v?.poster_file_id ? <img src={fileUrl(v.poster_file_id)} alt="" className="size-full object-cover" /> : <Film size={14} strokeWidth={1.75} />}
                </span>
                <span className="flex min-w-0 flex-1 basis-[calc(100%-42px)] flex-col lg:basis-auto">
                  {v ? (
                    <Link to={`/b/${v.brand_id}/videos/${v.id}`} className="truncate text-sm font-semibold hover:underline">
                      {name(j)}
                    </Link>
                  ) : (
                    <span className="truncate text-sm font-semibold">{name(j)}</span>
                  )}
                  <span className="text-xs text-muted">
                    {said(j)} · {pressLabel(j.credits, "estimate")}
                  </span>
                </span>
                <span className="ml-[42px] text-xs text-muted lg:ml-0 lg:w-[70px]">Sent {time(j.created_at)}</span>
                <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted">
                  <span aria-hidden className="size-[7px] rounded-full bg-need-dot shadow-[inset_0_0_0_2px_var(--surface)] outline outline-[1.5px] outline-need-dot" />
                  Waiting
                </span>
                <span className="flex-1 lg:hidden" />
                <Button variant="secondary" busy={withdraw.isPending && withdraw.variables?.id === j.id} onClick={() => withdraw.mutate(j)}>
                  Withdraw
                </Button>
              </li>
            );
          })}
        </ul>
      )}
      {answered.length > 0 && (
        <>
          <h2 className="pt-2 text-xs font-semibold text-muted">Answered this week</h2>
          <ul className="overflow-hidden rounded-lg border border-border bg-surface">
            {answered.map((j) => (
              <li key={j.id} className="flex items-center gap-3 border-t border-border px-3 py-2 text-sm first:border-t-0">
                <span className="min-w-0 flex-1 truncate">
                  {name(j)} · <span className="text-muted">{said(j).toLowerCase()}</span>
                </span>
                {j.approved ? (
                  <span className="inline-flex items-center gap-1.5 text-xs font-medium text-success">{dot("bg-success")}Approved</span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 text-xs font-medium text-danger">{dot("bg-danger")}Declined</span>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </main>
  );
}
