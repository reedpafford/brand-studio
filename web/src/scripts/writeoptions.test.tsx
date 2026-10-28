import { render, screen, within } from "@testing-library/react";
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
afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

test("the script editor is open on an empty script, with Have Claude write it for me at its price under it", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "POST /scripts/7/write": [201, { id: 90, kind: "write-claude", status: "queued", script_id: 7 }] }));
  open();
  const write = await screen.findByRole("button", { name: "Have Claude write it for me · 6 credits" });
  expect(screen.getByLabelText("Your script")).toBeInTheDocument();
  expect(screen.queryByRole("switch")).toBeNull();
  expect(screen.getByText(/Includes finding the roles\./)).toBeInTheDocument();
  expect(screen.queryByText(/Ask Reed/)).toBeNull();
  await userEvent.click(write);
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/write")).toBe(true));
  expect(await screen.findByText("Claude is writing the script…")).toBeInTheDocument();
});

test("a script with a reference reel keeps the same-style switch, saved before writing", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "GET /scripts/7": [200, script({ reference_id: "altar" })], "PATCH /scripts/7": [200, script({ reference_id: "altar", new_lines: true })] }));
  open();
  expect(await screen.findByRole("button", { name: "Have Claude write it for me · 6 credits" })).toBeInTheDocument();
  expect(screen.getByText("Keeps the reel's lines word for word and rewrites only what the brand swap needs.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("switch", { name: "Write new lines in the same style" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /scripts/7")?.body).toEqual({ new_lines: true }));
  expect(await screen.findByText("Writes new lines in the reel's voice and pacing. The shots and beats still follow the reel.")).toBeInTheDocument();
});

test("an editor past this week's allowance gets a disabled button and the reason, never Ask Reed", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /auth/me": [200, editor], "GET /scripts/7": [200, script({ created_by_id: 2 })], "GET /credits/me": [200, { quick_clip_credits_used: 145, quick_clip_credits_allowed: 145 }] }));
  open();
  const write = await screen.findByRole("button", { name: "Have Claude write it for me · 6 credits" });
  await vi.waitFor(() => expect(write).toBeDisabled());
  expect(write).toHaveAccessibleDescription("You've used this week's 145 credits. It resets on Monday.");
  expect(screen.queryByText(/Ask Reed/)).toBeNull();
});

test("a write that didn't finish says so, says credits came back, and offers Try again; the editor is still there", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /jobs": [200, [{ id: 90, kind: "write-claude", status: "failed", script_id: 7 }]] }));
  open();
  expect(await screen.findByText("The last try didn't finish. Credits were returned.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Try again · 6 credits" })).toBeEnabled();
  expect(screen.getByLabelText("Your script")).toBeInTheDocument();
});

test("a script that already has words shows them in the editor; Claude's draft asks before replacing them, and Undo after it writes puts them back", async () => {
  setViewport(1440);
  const withText = script({ versions: [{ ...script().versions[0], text: "BO: Salmon?" }] });
  let phase = 0; // 0: the job is queued, 1: it has finished
  const written = script({ versions: [{ ...script().versions[0], text: "BO: Salmon. Again?" }] });
  const routes = base({ "POST /scripts/7/write": [201, { id: 90, kind: "write-claude", status: "queued", script_id: 7 }], "PUT /scripts/7/drafts/0": [200, withText] });
  Object.defineProperty(routes, "GET /scripts/7", { enumerable: true, get: () => [200, phase === 0 ? withText : written] });
  Object.defineProperty(routes, "GET /jobs", { enumerable: true, get: () => [200, phase === 0 ? [] : [{ id: 90, kind: "write-claude", status: "succeeded", script_id: 7 }]] });
  const calls = fakeServer(routes);
  open();
  expect(await screen.findByLabelText("Your script")).toHaveValue("BO: Salmon?");
  await userEvent.click(await screen.findByRole("button", { name: "Have Claude write it for me · 6 credits" }));
  expect(await screen.findByRole("alertdialog", { name: "Write a new script?" })).toBeInTheDocument();
  phase = 1; // the job is done by the time the list is read again
  await userEvent.click(screen.getByRole("button", { name: "Write it" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/write")).toBe(true));
  expect(await screen.findByText("Script written.", {}, { timeout: 8000 })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /scripts/7/drafts/0")?.body).toEqual({ text: "BO: Salmon?" }));
}, 20000);

test("an imported reel that isn't read yet offers Read this reel, never Have Claude write it; pasting stays possible", async () => {
  setViewport(1440);
  const reel = { script_id: 7, status: "ready", source: "link", url: "https://www.instagram.com/reel/Abc123/", seconds: 45, shots: 50, transcript: [], video_file_id: 3, contact_file_id: 4, problem: "", problem_code: null, estimate: { credits: 7, credits_left: null } };
  fakeServer(base({ "GET /scripts/7": [200, script({ reel_imported: true })], "GET /scripts/7/import": [200, reel] }));
  open();
  expect((await screen.findAllByRole("button", { name: "Read this reel · 7 credits" })).length).toBeGreaterThan(0);
  expect(screen.queryByText(/Have Claude write it/)).toBeNull();
  expect(screen.queryByRole("button", { name: /^Have Claude write it/ })).toBeNull();
  expect(screen.getByLabelText("Your script")).toBeInTheDocument();
});

test("a script with a reel that is not read yet (reel_imported still false) shows only Read this reel, never a second paid path", async () => {
  setViewport(1440);
  const reel = { steps_done: [], script_id: 7, status: "ready", source: "link", url: "https://www.instagram.com/reel/Abc123/", seconds: 45, shots: 50, transcript: [], video_file_id: 3, contact_file_id: 4, problem: "", problem_code: null, estimate: { credits: 7, credits_left: null } };
  fakeServer(base({ "GET /scripts/7/import": [200, reel] }));
  open();
  expect((await screen.findAllByRole("button", { name: "Read this reel · 7 credits" })).length).toBeGreaterThan(0);
  expect(screen.queryByRole("button", { name: /Have Claude write it/ })).toBeNull();
});

test("unsaved words come back when the editor returns, so no way out of the page loses them", async () => {
  setViewport(1440);
  sessionStorage.clear();
  fakeServer(base({ "GET /scripts/7": [200, script({ versions: [{ ...script().versions[0], text: "BO: Salmon?" }] })] }));
  const first = render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/b/1/scripts/7?step=script"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  await userEvent.type(await screen.findByLabelText("Your script"), " More.");
  first.unmount(); // left through the tab bar, say
  open();
  expect(await screen.findByLabelText("Your script")).toHaveValue("BO: Salmon? More.");
  expect(screen.getByText("Not saved yet")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Discard changes" }));
  expect(screen.getByLabelText("Your script")).toHaveValue("BO: Salmon?");
});

test("Save script is off until the words change; unsaved words say so, leaving asks first, and Save keeps them", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "PUT /scripts/7/drafts/0": [200, script({ versions: [{ ...script().versions[0], text: "BO: Salmon?" }] })] }));
  open();
  const box = await screen.findByLabelText("Your script");
  expect(screen.getByRole("button", { name: "Save script" })).toBeDisabled();
  await userEvent.type(box, "BO: Salmon?");
  expect(screen.getByText("Not saved yet")).toBeInTheDocument();
  await userEvent.click(within(screen.getByRole("main")).getByRole("link", { name: "Scripts" }));
  expect(await screen.findByRole("alertdialog", { name: "Leave without saving?" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Stay" }));
  expect(screen.getByLabelText("Your script")).toHaveValue("BO: Salmon?");
  await userEvent.click(screen.getByRole("button", { name: "Save script" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /scripts/7/drafts/0")?.body).toEqual({ text: "BO: Salmon?" }));
  expect(await screen.findByText("Saved.")).toBeInTheDocument();
  expect(screen.queryByText("Not saved yet")).toBeNull();
});

test("Discard changes puts the saved words back", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts/7": [200, script({ versions: [{ ...script().versions[0], text: "BO: Salmon?" }] })] }));
  open();
  const box = await screen.findByLabelText("Your script");
  await userEvent.type(box, " More.");
  await userEvent.click(screen.getByRole("button", { name: "Discard changes" }));
  expect(screen.getByLabelText("Your script")).toHaveValue("BO: Salmon?");
});

test("when the paid reel read finishes, the open Script step brings in the new words and stops offering to write", async () => {
  setViewport(1440);
  const reel = (status: string) => ({ steps_done: status === "done" ? ["watch", "write", "cast"] : [], read_again_credits: 6.2, edited_since_fill: false, new_fill_ready: false, script_id: 7, status, source: "link", url: "https://www.instagram.com/reel/Abc123/", seconds: 45, shots: 50, transcript: [], video_file_id: 3, contact_file_id: 4, problem: "", problem_code: null, estimate: { credits: 7, credits_left: null } });
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
  expect(screen.queryByRole("button", { name: /^Have Claude write it/ })).toBeNull();
});
