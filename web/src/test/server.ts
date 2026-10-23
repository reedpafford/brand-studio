import { vi } from "vitest";

/** Fake the server: map "METHOD /path" to a status and JSON body. Returns the calls made. */
export function fakeServer(routes: Record<string, [number, unknown]>) {
  const calls: { key: string; body: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: Request | string, init?: RequestInit) => {
      const req = input instanceof Request ? input : new Request(new URL(input, "http://x"), init);
      const key = `${req.method} ${new URL(req.url).pathname.replace(/^\/api/, "")}`;
      const text = await req.text();
      const isJson = req.headers.get("content-type")?.includes("json");
      calls.push({ key, body: text && isJson ? JSON.parse(text) : undefined });
      const [status, body] = routes[key] ?? [404, { detail: "not faked" }];
      return new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
    }),
  );
  return calls;
}
