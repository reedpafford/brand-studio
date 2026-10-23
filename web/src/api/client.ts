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
