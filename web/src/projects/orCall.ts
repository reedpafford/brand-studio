/** OR3's routes (Builder-Server-8's #957); until they are in the generated schema they are called with fetch. A GET the
 *  server doesn't have yet (404) reads as nothing, so its list stays hidden. */
export async function orCall<T>(method: "GET" | "POST", path: string, body?: object): Promise<T | null> {
  const r = await fetch(`${location.origin}/api${path}`, { method, credentials: "include", ...(body ? { body: JSON.stringify(body), headers: { "Content-Type": "application/json" } } : {}) });
  if (r.status === 404 && method === "GET") return null;
  const json = await r.json().catch(() => null);
  if (!r.ok) throw new Error(typeof json?.detail === "string" ? json.detail : "That didn't go through. Try again.");
  return json as T;
}
