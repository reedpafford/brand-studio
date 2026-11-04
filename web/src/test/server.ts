import { vi } from "vitest";

/** The guides' formats (GET /formats), faked for every test unless it fakes its own. */
const FORMATS = [
  { id: "dialogue", name: "Dialogue", engine: "story", on: true, blurb: "People speak their lines on camera." },
  { id: "song", name: "Song", engine: "song", on: true, blurb: "An animated music video: the song plays over B-roll." },
  { id: "narrated", name: "Narrated", engine: "narrated", on: true, blurb: "One voice will read it; Cast keeps its roles but nobody speaks on camera." },
  { id: "zack-d", name: "Zack D", engine: "narrated", on: false, blurb: "One continuous 3D camera journey." },
];

/** Fake the server: map "METHOD /path" to a status and JSON body. Returns the calls made. */
export function fakeServer(routes: Record<string, [number, unknown]>) {
  const calls: { key: string; body: unknown; url: string }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: Request | string, init?: RequestInit) => {
      const req = input instanceof Request ? input : new Request(new URL(input, "http://x"), init);
      const key = `${req.method} ${new URL(req.url).pathname.replace(/^\/api/, "")}`;
      const text = await req.text();
      const isJson = req.headers.get("content-type")?.includes("json");
      calls.push({ key, body: text && isJson ? JSON.parse(text) : undefined, url: req.url });
      // A route can be faked with its query ("GET /team/members?removed=true") ahead of the plain path.
      const [status, body] = routes[`${key}${new URL(req.url).search}`] ?? routes[key] ?? (key === "GET /formats" ? [200, FORMATS] : [404, { detail: "not faked" }]);
      return new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
    }),
  );
  return calls;
}
