import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const owner = { id: 1, email: "reed@b.co", name: "Reed", role: "owner", workspace_id: 1 };
const editor = { ...owner, id: 2, name: "Sam", role: "editor" };
const script = (o: object = {}) => ({
  id: 7, brand_id: 1, title: "Bo tries salmon", description: "Show a picky dog.", reference_id: null, reel_imported: false, new_lines: false, published: false, status: "draft", created_by_id: 1, created_by_name: "Reed", created_at: "2026-10-24T10:00:00Z", versions_left: 0,
  notes: "", reference_replace: "", cast: [], versions: [{ slot: 0, status: "draft", title: "Bo tries salmon", seconds: 0, project_id: null, text: "", words: 0, target_seconds: null, premise: "", changes: [], problems: [], has_breakdown: false, approved_at: null }], ...o,
});
const base = (o: Record<string, [number, unknown]> = {}): Record<string, [number, unknown]> => ({
  "GET /auth/me": [200, owner],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /references": [200, []],
  "GET /projects": [200, []],
  "GET /jobs": [200, []],
  "GET /scripts/7": [200, script()],
  "GET /scripts/7/write/estimate": [200, { credits: 6 }],
  "GET /scripts/7/import": [404, { detail: "none" }],
  ...o,
});
function open() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/b/1/scripts/7?step=script"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
afterEach(() => vi.unstubAllGlobals());

test("an empty script with no reel offers Write with Claude at its price, and the paste box as the other way", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "POST /scripts/7/write": [201, { id: 90, kind: "write-claude", status: "queued", script_id: 7 }] }));
  open();
  const write = await screen.findByRole("button", { name: "Write with Claude · 6 credits" });
  expect(screen.getByRole("heading", { name: "Write with Claude" })).toBeInTheDocument();
  expect(screen.queryByRole("switch")).toBeNull();
  expect(screen.getByText("Includes finding the roles.")).toBeInTheDocument();
  expect(screen.queryByText(/Ask Reed/)).toBeNull();
  await userEvent.click(write);
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/write")).toBe(true));
  expect(await screen.findByText("Claude is writing the script…")).toBeInTheDocument();
});

test("a script with a reel offers Write from the reference, and the same-style switch is saved before writing", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "GET /scripts/7": [200, script({ reference_id: "altar" })], "PATCH /scripts/7": [200, script({ reference_id: "altar", new_lines: true })] }));
  open();
  expect(await screen.findByRole("heading", { name: "Write from the reference" })).toBeInTheDocument();
  expect(await screen.findByRole("button", { name: "Write from the reference · 6 credits" })).toBeInTheDocument();
  expect(screen.getByText("Keeps the reel's lines word for word and rewrites only what the brand swap needs.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("switch", { name: "Write new lines in the same style" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /scripts/7")?.body).toEqual({ new_lines: true }));
  expect(await screen.findByText("Writes new lines in the reel's voice and pacing. The shots and beats still follow the reel.")).toBeInTheDocument();
});

test("an editor past this week's allowance gets a disabled button and the reason, never Ask Reed", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /auth/me": [200, editor], "GET /scripts/7": [200, script({ created_by_id: 2 })], "GET /credits/me": [200, { quick_clip_credits_used: 145, quick_clip_credits_allowed: 145 }] }));
  open();
  const write = await screen.findByRole("button", { name: "Write with Claude · 6 credits" });
  await vi.waitFor(() => expect(write).toBeDisabled());
  expect(write).toHaveAccessibleDescription("You've used this week's 145 credits. It resets on Monday.");
  expect(screen.queryByText(/Ask Reed/)).toBeNull();
});

test("a write that didn't finish says so, says credits came back, and offers Try again; the paste box opens on request", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /jobs": [200, [{ id: 90, kind: "write-claude", status: "failed", script_id: 7 }]] }));
  open();
  expect(await screen.findByText("The last try didn't finish. Credits were returned.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Try again · 6 credits" })).toBeEnabled();
  await userEvent.click(screen.getByRole("button", { name: "Paste or write it yourself" }));
  expect(screen.getByLabelText("Your script")).toBeInTheDocument();
});

test("a script that already has words shows them, not the writing options", async () => {
  setViewport(1440);
  const withText = script({ versions: [{ ...script().versions[0], text: "BO: Salmon?" }] });
  fakeServer(base({ "GET /scripts/7": [200, withText] }));
  open();
  expect(await screen.findByRole("button", { name: "Edit" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Write with Claude" })).toBeNull();
});

test("an imported reel that isn't read yet offers Read this reel, never a paid Write with Claude", async () => {
  setViewport(1440);
  const reel = { script_id: 7, status: "ready", source: "link", url: "https://www.instagram.com/reel/Abc123/", seconds: 45, shots: 50, transcript: [], video_file_id: 3, contact_file_id: 4, problem: "", problem_code: null, estimate: { credits: 7, credits_left: null } };
  fakeServer(base({ "GET /scripts/7": [200, script({ reel_imported: true })], "GET /scripts/7/import": [200, reel] }));
  open();
  expect(await screen.findByRole("heading", { name: "Read the reel first" })).toBeInTheDocument();
  expect(await screen.findByRole("button", { name: "Read this reel · 7 credits" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^Write with Claude/ })).toBeNull();
  expect(screen.getByRole("button", { name: "Paste or write it yourself" })).toBeInTheDocument();
});

test("the paste box on an empty script has a way back to the choices", async () => {
  setViewport(1440);
  fakeServer(base());
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Paste or write it yourself" }));
  await userEvent.click(screen.getByRole("button", { name: "Back to the choices" }));
  expect(await screen.findByRole("heading", { name: "Write with Claude" })).toBeInTheDocument();
});

test("when the paid reel read finishes, the open Script step brings in the new words and stops offering to write", async () => {
  setViewport(1440);
  const reel = (status: string) => ({ script_id: 7, status, source: "link", url: "https://www.instagram.com/reel/Abc123/", seconds: 45, shots: 50, transcript: [], video_file_id: 3, contact_file_id: 4, problem: "", problem_code: null, estimate: { credits: 7, credits_left: null } });
  fakeServer(base({ "GET /scripts/7": [200, script({ reel_imported: true })], "GET /scripts/7/import": [200, reel("reading")] }));
  // The read finishes: the import now says "done", and the script now has the words the read wrote.
  const inner = (fetch as unknown as { getMockImplementation: () => (r: Request | string, i?: RequestInit) => Promise<Response> }).getMockImplementation()!;
  let imports = 0;
  const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
  const written = script({ reel_imported: true, versions: [{ ...script().versions[0], text: "BO: Salmon? Again?", words: 3, status: "approved" }] });
  vi.stubGlobal("fetch", vi.fn(async (input: Request | string, init?: RequestInit) => {
    const req = input instanceof Request ? input : new Request(new URL(input, "http://x"), init);
    const path = new URL(req.url).pathname.replace(/^\/api/, "");
    if (req.method === "GET" && path === "/scripts/7/import") return json(reel(++imports < 2 ? "reading" : "done"));
    if (req.method === "GET" && path === "/scripts/7" && imports >= 2) return json(written);
    return inner(req.clone(), init);
  }));
  open();
  expect(await screen.findByText("BO: Salmon? Again?", {}, { timeout: 8000 })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^Write with Claude/ })).toBeNull();
});
