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
      calls.push({ key, body: text ? JSON.parse(text) : undefined });
      const [status, body] = routes[key] ?? [404, { detail: "not faked" }];
      return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
    }),
  );
  return calls;
}
