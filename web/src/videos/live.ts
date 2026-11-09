import { useEffect } from "react";
import { useQueryClient, type Query } from "@tanstack/react-query";

/** What each kind of change the server tells (server/app/live.py) reads again. "made" (a job finished: a still, a take,
 *  a cut or a director's move) reads every part of the page that's open. */
const PARTS: Record<string, string[]> = {
  jobs: ["jobs", "run-progress", "idea", "held-jobs"], // a job queued, started or held: the live card and the header
  cards: ["asks"],
  moves: ["director", "freestyle"], // the chat
  video: ["project", "idea", "director", "freestyle", "run-progress"], // a move's words, the run's end, a note, a setting
};
const UNKEYED = ["freestyle", "held-jobs"]; // the page's reads not keyed by the video
export const FALLBACK = 30_000; // while the stream is down, the whole page is read this often
const BUNCH = 400; // changes this close together are read once (a worker step makes several at once)
const WHOLE = 5_000; // the whole page at most this often (the chat was read every 5 s): stills landing together, read once

/** The video page hears each change the moment it lands, and reads again only that part (it used to ask every 3 to
 *  10 s). If the stream drops, the page reads everything every 30 s and opens it again, waiting a little longer each time
 *  (1 s, 2 s, 4 s … up to 30 s), then reads everything once it's back, for what it missed. */
export function useLive(projectId: number) {
  const queryClient = useQueryClient();
  useEffect(() => {
    if (projectId <= 0) return;
    const ours = (q: Query) => q.queryKey.includes(projectId) || UNKEYED.includes(String(q.queryKey[0]));
    const read = (kinds: string[]) =>
      void queryClient.invalidateQueries({ predicate: (q) => ours(q) && kinds.some((k) => k === "made" || PARTS[k]?.includes(String(q.queryKey[0]))) });
    let source: EventSource | null = null;
    let tries = 0;
    let fallback: number | undefined;
    let retry: number | undefined;
    let bunch: number | undefined;
    let due: number | undefined;
    let whole = 0; // when the whole page was last read
    const heard = new Set<string>();
    const readWhole = () => ((due = undefined), (whole = Date.now()), read(["made"]));
    const flush = () => {
      bunch = undefined;
      const kinds = [...heard];
      heard.clear();
      if (!kinds.includes("made")) return read(kinds);
      if (whole + WHOLE <= Date.now()) return readWhole();
      // the whole page was read moments ago: the run's live parts now, the rest once it's due
      read([...kinds.filter((k) => k !== "made"), "jobs", "moves"]);
      due ??= window.setTimeout(readWhole, whole + WHOLE - Date.now());
    };
    const down = () => {
      source?.close();
      source = null;
      fallback ??= window.setInterval(() => read(["made"]), FALLBACK);
      if (typeof EventSource !== "undefined") retry = window.setTimeout(open, Math.min(FALLBACK, 1000 * 2 ** tries++));
    };
    const open = () => {
      const s = (source = new EventSource(`/api/projects/${projectId}/live`));
      s.onopen = () => {
        tries = 0;
        if (fallback === undefined) return;
        window.clearInterval(fallback);
        fallback = undefined;
        read(["made"]); // back after a drop: what it missed
      };
      s.onmessage = (e: MessageEvent<string>) => {
        heard.add(e.data);
        bunch ??= window.setTimeout(flush, BUNCH);
      };
      s.addEventListener("bye", () => (s.close(), open())); // the server's planned end: straight back
      s.onerror = down;
    };
    if (typeof EventSource === "undefined") down();
    else open();
    return () => {
      source?.close();
      window.clearInterval(fallback);
      window.clearTimeout(retry);
      window.clearTimeout(bunch);
      window.clearTimeout(due);
    };
  }, [projectId, queryClient]);
}
