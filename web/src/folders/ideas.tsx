import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { wholeCredits } from "../components";
import { serverTime } from "../time";

/** A brand's folders and video ideas (v6 S0-01, S1): the rail's tree and an open folder read the server's words. */
export type Branch = components["schemas"]["Branch"];
export type Idea = components["schemas"]["Idea"];
export type Status = components["schemas"]["Status"];
export type Cost = components["schemas"]["Cost"];
export type Tab = "all" | "needs_you" | "working" | "delivered";
export type Sort = "newest" | "oldest" | "name";
/** ?folder=: a folder's id, or "none" for Unsorted. */
export const UNSORTED = "none";

export function useTree(brandId: number) {
  return useQuery({
    enabled: brandId > 0,
    queryKey: ["tree", brandId],
    queryFn: async () => {
      const { data } = await api.GET("/brands/{brand_id}/tree", { params: { path: { brand_id: brandId } } });
      if (!data) throw new Error("load");
      return data;
    },
  });
}

export type IdeasAsk = { folder: string; tab: Tab; q: string; sort: Sort; madeBy: number | null; archived: boolean };
const PAGE = 60;
/** The folder asked for isn't there (deleted, or another brand's). */
export const GONE = "gone";

/** One folder's ideas a page at a time; the list loads the next page as you scroll (S1-05). */
export function useIdeas(brandId: number, ask: IdeasAsk) {
  return useInfiniteQuery({
    queryKey: ["ideas", brandId, ask],
    initialPageParam: 0,
    queryFn: async ({ pageParam }) => {
      const query = { folder: ask.folder, tab: ask.tab, sort: ask.sort, offset: pageParam, limit: PAGE, ...(ask.q ? { q: ask.q } : {}), ...(ask.madeBy ? { made_by: ask.madeBy } : {}), ...(ask.archived ? { archived: true } : {}) };
      const { data, response } = await api.GET("/brands/{brand_id}/ideas", { params: { path: { brand_id: brandId }, query } });
      if (!data) throw new Error(response.status === 404 ? GONE : "load");
      return data;
    },
    retry: (n, e) => e.message !== GONE && n < 3, // a gone folder won't come back by asking again
    // Another tab, search or sort in the same folder keeps the cards and counts up while it loads.
    placeholderData: (previous, query) => ((query?.queryKey[2] as IdeasAsk | undefined)?.folder === ask.folder && (query?.queryKey[2] as IdeasAsk).archived === ask.archived ? previous : undefined),
    getNextPageParam: (last, pages) => {
      const shown = pages.reduce((n, p) => n + p.ideas.length, 0);
      return shown < last.total ? shown : undefined;
    },
  });
}

/** After a move, an archive or a folder change: the tree and every open folder read again. */
export function useRefreshIdeas() {
  const client = useQueryClient();
  return () => Promise.all(["tree", "ideas", "folders"].map((k) => client.invalidateQueries({ queryKey: [k] })));
}

/** The folders in tree order, each with its depth: for "Move to…" menus. */
export function flatten(branches: Branch[], depth = 0): { id: number; name: string; depth: number }[] {
  return branches.flatMap((b) => [{ id: b.id!, name: b.name, depth }, ...flatten(b.folders ?? [], depth + 1)]);
}

/** The folder and the folders above it, top first (the header's crumb). */
export function pathTo(branches: Branch[], id: number): Branch[] {
  for (const b of branches) {
    if (b.id === id) return [b];
    const below = pathTo(b.folders ?? [], id);
    if (below.length) return [b, ...below];
  }
  return [];
}

// S0-01's dots: Working is the accent with a halo, Waiting for the owner a ringed amber, Needs you amber, Needs a fix red,
// Delivered green, Stopped and Archived grey.
const DOT: Record<Status["kind"], string> = {
  working: "bg-accent shadow-[0_0_0_3px_rgb(94_99_214/0.16)]",
  needs_you: "bg-need-dot",
  waiting: "bg-need-dot shadow-[inset_0_0_0_2px_var(--surface)] outline outline-[1.5px] outline-need-dot",
  needs_fix: "bg-danger",
  delivered: "bg-success",
  stopped: "bg-faint",
  archived: "bg-faint",
};
const WORDS: Record<Status["kind"], string> = { working: "text-accent-text", needs_you: "text-warning", waiting: "text-muted", needs_fix: "text-danger", delivered: "text-success", stopped: "text-muted", archived: "text-muted" };

export function StatusDot({ status, label }: { status: Status; label?: boolean }) {
  return <span aria-hidden={!label || undefined} aria-label={label ? said(status) : undefined} title={said(status)} className={`size-[7px] shrink-0 rounded-full ${DOT[status.kind]}`} />;
}

const time = (iso: string) => serverTime(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
/** "28 Oct", as the boards write a date. */
export const day = (iso: string) => serverTime(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });

/** The status in words with its reason: "Working · 14 of 24", "Stopped · by Reed at 10:14", "Archived 28 Oct". */
export function said(status: Status) {
  if (status.kind === "archived") return status.at ? `${status.words} ${day(status.at)}` : status.words;
  const reason = status.reason && status.at ? `${status.reason} at ${time(status.at)}` : status.reason;
  return reason ? `${status.words} · ${reason}` : status.words;
}

/** A dot plus words (S0-01): the reason follows the status on cards, in the list and in the header (S-gaps-01). */
export function StatusLine({ status, reason = true }: { status: Status; reason?: boolean }) {
  return (
    <span className={`inline-flex min-w-0 items-center gap-1.5 text-xs font-medium ${WORDS[status.kind]}`}>
      <StatusDot status={status} />
      <span className="truncate">{reason ? said(status) : status.kind === "archived" ? said(status) : status.words}</span>
    </span>
  );
}

/** "up to $16.86", "$0.42 so far", "$7.20"; an editor's in credits: "up to 164 cr" (rule 4). Nothing before a price exists. */
export function costText(cost: Cost | null | undefined) {
  if (!cost) return "";
  const credits = cost.kind === "up_to" ? wholeCredits(cost.credits) : Math.round(cost.credits); // a most is never rounded down
  const amount = cost.usd != null ? `$${cost.usd.toFixed(2)}` : `${credits} cr`;
  return cost.kind === "up_to" ? `up to ${amount}` : cost.kind === "so_far" ? `${amount} so far` : amount;
}
