import createClient from "openapi-fetch";
import type { paths } from "./schema";

export const api = createClient<paths>({ baseUrl: `${location.origin}/api`, credentials: "include", fetch: (req) => fetch(req) });

/** Turn a server error body into one plain sentence. */
export function errorText(error: unknown): string {
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  return "Something went wrong. Please try again.";
}

/** Await a call and throw the server's plain-language message if it was refused. */
export async function must<T extends { response: Response; error?: unknown }>(call: Promise<T>): Promise<T> {
  const result = await call;
  if (!result.response.ok) throw new Error(errorText(result.error));
  return result;
}

/** Sent when a read finds the session gone (401): the app reads who's signed in again, so the sign-in screen shows. */
export const SIGNED_OUT = "bs:signed-out";

/** A polled read (a run card, the header, the clips): its data, or `none` when there is nothing (404), or nothing this
 *  person may read (401, 403: polling stops there, and a gone session brings up sign-in). Any other refusal throws, so
 *  polling goes on with the last data shown: one 502 during a deploy never empties or freezes the page. */
export async function polled<T, N>(call: Promise<{ data?: T; response: Response; error?: unknown }>, none: N): Promise<T | N> {
  const { data, response, error } = await call;
  if (response.ok) return data ?? none;
  if (response.status === 401) window.dispatchEvent(new Event(SIGNED_OUT));
  if ([401, 403, 404].includes(response.status)) return none;
  throw new Error(errorText(error));
}

const unchanged = new Map<string, { data: unknown; at: number; n: number }>();

/** A poll's interval that backs off while nothing changes (video 240: /director read every 5 s while a run waited,
 *  each read slow, so the reads piled up): `base`, doubled each read that brought the same data, up to `most`; the
 *  first change (or a press's own data) brings it back to `base`. */
export function backoff(q: { queryHash: string; state: { data: unknown; dataUpdatedAt: number } }, base: number, most = 30_000): number {
  const { data, dataUpdatedAt: at } = q.state;
  const was = unchanged.get(q.queryHash);
  const now = !was || was.data !== data ? { data, at, n: 0 } : was.at !== at ? { data, at, n: was.n + 1 } : was;
  unchanged.set(q.queryHash, now);
  return Math.min(most, base * 2 ** now.n);
}
