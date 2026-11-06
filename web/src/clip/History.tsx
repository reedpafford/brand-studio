import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, polled } from "../api/client";
import { serverTime } from "../time";

// Job clocks and the caller's jobs, shared by the video and script steps (Freestyle replaced Quick clip and its History).

/** A job still going: waiting, running, or held for the owner's OK. */
export const GOING = ["queued", "running", "needs_owner_approval"];

/** The caller's jobs. Polls while anything is still going. */
export function useJobs() {
  return useQuery({
    queryKey: ["jobs"],
    queryFn: () => polled(api.GET("/jobs"), []),
    refetchInterval: (q) => (q.state.data?.some((j) => GOING.includes(j.status)) ? 3000 : false),
  });
}

/** "45s" or "1m 20s". */
export function elapsed(ms: number) {
  const total = Math.max(0, Math.floor(ms / 1000));
  return total < 60 ? `${total}s` : `${Math.floor(total / 60)}m ${total % 60}s`;
}

/** The time now, ticking every second while it is on screen. */
function useNow() {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  return now;
}

/** How long a clip has been going. */
export function Elapsed({ since }: { since: string }) {
  return <span>{elapsed(useNow() - serverTime(since).getTime())}</span>;
}

/** How long a job has been going, as "1:05". */
export function Stopwatch({ since }: { since: string }) {
  const s = Math.max(0, Math.round((useNow() - serverTime(since).getTime()) / 1000));
  return <span className="tabular-nums">{Math.floor(s / 60)}:{String(s % 60).padStart(2, "0")}</span>;
}
/** A job's line while it waits or runs (flows, Waiting): "Waiting to start · 0:12", then "Making… 1:05". */
export function JobClock({ queued, making, since }: { queued: boolean; making: string; since: string | null | undefined }) {
  return (
    <>
      {queued ? "Waiting to start" : making}
      {since && <>{queued ? " · " : " "}<Stopwatch since={since} /></>}
    </>
  );
}
