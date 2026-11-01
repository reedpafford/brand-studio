import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";
import { ToastProvider } from "../toast";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { MemoryRouter } from "react-router-dom";
import { HeldRequests, askedAgo, stepOf, type HeldWhere } from "./HeldRequests";
import { PLURAL, STEPS } from "./ApprovalsPage";
import type { Job } from "./useHeld";

const job = (o: object = {}) => ({ id: 50, kind: "video", project_id: 9, script_id: null, credits: 27, status: "needs_owner_approval", created_at: new Date().toISOString(), finished_at: null, prompt_summary: "", step: "clip_take", error: "", held: "That's more than this video's budget.", declined: false, created_by_name: "Eli", waiting: "", auto: false, output: null, ...o });
function show(where: HeldWhere) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ToastProvider>
        <MemoryRouter>
          <HeldRequests where={where} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}
afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

test("at 390, a held press on this video says Waiting for approval with why, and Withdraw cancels it for nothing", async () => {
  setViewport(390);
  const calls = fakeServer({ "GET /jobs": [200, [job(), job({ id: 51, project_id: 10 })]], "POST /jobs/50/cancel": [200, job({ status: "cancelled" })] });
  show({ projectId: 9 });
  const banner = (await screen.findByText("Waiting for approval")).closest("[role]") ?? document.body;
  expect(screen.getAllByText("Waiting for approval")).toHaveLength(1); // the other video's request isn't here
  expect(document.body).toHaveTextContent("A new take · 27 credits · Asked just now. That's more than this video's budget.");
  expect(document.body.textContent).not.toMatch(/ask (Reed|the owner)/i);
  await userEvent.click(within(banner as HTMLElement).getByRole("button", { name: "Withdraw" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /jobs/50/cancel")).toBe(true));
  expect(await screen.findByText("Withdrawn. Nothing was charged.")).toBeInTheDocument();
});

test("a declined request says the owner said no, with their reason, until OK", async () => {
  setViewport(1440);
  fakeServer({ "GET /jobs": [200, [job({ status: "cancelled", declined: true, held: "", error: "Over budget this week" })]] });
  show({ projectId: 9 });
  expect(await screen.findByText("The owner said no: Over budget this week")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "OK" }));
  expect(screen.queryByText(/The owner said no/)).toBeNull();
});

test("a decline with no reason doesn't repeat the server's own words", async () => {
  fakeServer({ "GET /jobs": [200, [job({ status: "cancelled", declined: true, held: "", error: "The owner said no this time. Nothing was charged." })]] });
  show({ projectId: 9 });
  expect(await screen.findByText("The owner said no")).toBeInTheDocument();
});

const song = (o: object = {}) => job({ id: 60, kind: "music", project_id: null, script_id: 7, step: "song_take", held: "Songs, narration and music on a script wait for the owner's OK.", ...o });
const clip = job({ id: 61, project_id: null, script_id: null, step: null, held: "That's more than this week's 97 credits." });

test("a held song take on a script shows on that script, named as a song; Quick clips show only on Quick clip", async () => {
  fakeServer({ "GET /jobs": [200, [song(), clip]] });
  show({ scriptId: 7 });
  expect(await screen.findByText(/Songs, narration and music on a script wait for the owner's OK\./)).toBeInTheDocument(); // the server's line, as is
  expect(document.body).toHaveTextContent("Your song or music · 27 credits · Asked just now.");
  expect(screen.queryByText(/97 credits/)).toBeNull();
});

test("Quick clip shows only real Quick clips: never a script's song or narration, even one with no script on it (QA on #1088)", async () => {
  fakeServer({ "GET /jobs": [200, [song({ script_id: null }), song({ id: 62, kind: "speech", script_id: null }), clip]] });
  show({ quick: true });
  expect(await screen.findByText(/97 credits/)).toBeInTheDocument();
  expect(screen.getAllByText("Waiting for approval")).toHaveLength(1);
  expect(document.body).toHaveTextContent("Your Quick clip · 27 credits · Asked just now.");
});

test("Asked … ago reads in plain words", () => {
  const now = Date.parse("2026-11-01T12:00:00Z");
  expect(askedAgo("2026-11-01T11:59:40Z", now)).toBe("Asked just now");
  expect(askedAgo("2026-11-01T11:58:00Z", now)).toBe("Asked 2 min ago");
  expect(askedAgo("2026-11-01T09:00:00Z", now)).toBe("Asked 3 h ago");
  expect(askedAgo("2026-10-30T12:00:00Z", now)).toBe("Asked 2 days ago");
});

test("when the owner approves, it says so once: The owner said yes: a new take is being made", async () => {
  let jobs = [job()];
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(jobs), { status: 200, headers: { "content-type": "application/json" } })));
  const client = new QueryClient();
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter>
          <HeldRequests where={{ projectId: 9 }} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  expect(await screen.findByText("Waiting for approval")).toBeInTheDocument();
  jobs = [job({ status: "queued", held: "" })];
  await client.refetchQueries({ queryKey: ["jobs", "mine"] });
  expect(await screen.findByText("The owner said yes: a new take is being made.")).toBeInTheDocument();
  expect(screen.queryByText("Waiting for approval")).toBeNull();
});

test("a withdrawn request never says the owner said yes", async () => {
  let jobs = [job()];
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(jobs), { status: 200, headers: { "content-type": "application/json" } })));
  const client = new QueryClient();
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter>
          <HeldRequests where={{ projectId: 9 }} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  expect(await screen.findByText("Waiting for approval")).toBeInTheDocument();
  jobs = [job({ status: "cancelled" })];
  await client.refetchQueries({ queryKey: ["jobs", "mine"] });
  await vi.waitFor(() => expect(screen.queryByText("Waiting for approval")).toBeNull());
  expect(screen.queryByText(/The owner said yes/)).toBeNull();
});

test("a declined take offers Change this…, which goes to its step (Clips) and clears the line", async () => {
  fakeServer({ "GET /jobs": [200, [job({ status: "cancelled", declined: true, held: "", error: "Over budget this week" })]] });
  show({ projectId: 9 });
  const change = await screen.findByRole("link", { name: "Change this…" });
  expect(change).toHaveAttribute("href", "/?step=clips");
  await userEvent.click(change);
  expect(screen.queryByText(/The owner said no/)).toBeNull();
});

test("a declined Plan press is named and its Change this… goes to Plan; the yes-toast agrees in number (QA-5 on #1114)", async () => {
  fakeServer({ "GET /jobs": [200, [job({ step: "plan", status: "cancelled", declined: true, held: "", error: "" })]] });
  show({ projectId: 9 });
  expect(await screen.findByText("The owner said no")).toBeInTheDocument();
  expect(document.body).toHaveTextContent("The scene plan wasn't made.");
  expect(screen.getByRole("link", { name: "Change this…" })).toHaveAttribute("href", "/?step=plan");
});

test("every step a video press can be held on has a name and a step for Change this…; a change goes where its still or clip is", () => {
  for (const step of ["plan", "plan_scene", "breakdown", "song_breakdown", "narrated_breakdown", "sheet", "storyboard", "frame", "stills", "clip_prompts", "clip_take", "improve", "change"]) {
    expect(STEPS[step], step).toBeTruthy();
    expect(stepOf(job({ step }) as Job), step).toBeTruthy();
  }
  expect(stepOf(job({ step: "change", frame_id: 3, project_clip_id: null }) as Job)).toBe("storyboard");
  expect(stepOf(job({ step: "change", frame_id: null, project_clip_id: 4 }) as Job)).toBe("clips");
  expect(PLURAL.has("The clip prompts")).toBe(true);
});

test("the yes-toast says are for a plural: The owner said yes: the clip prompts are being made", async () => {
  let jobs = [job({ step: "clip_prompts" })];
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(jobs), { status: 200, headers: { "content-type": "application/json" } })));
  const client = new QueryClient();
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter>
          <HeldRequests where={{ projectId: 9 }} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  expect(await screen.findByText("Waiting for approval")).toBeInTheDocument();
  jobs = [job({ step: "clip_prompts", status: "running", held: "" })];
  await client.refetchQueries({ queryKey: ["jobs", "mine"] });
  expect(await screen.findByText("The owner said yes: the clip prompts are being made.")).toBeInTheDocument();
});

test("the owner sees what an editor asked on this video, one press from that request in Approvals; no Withdraw", async () => {
  fakeServer({ "GET /auth/me": [200, { id: 1, email: "o@b.co", name: "Olu", role: "owner", workspace_id: 1 }], "GET /jobs": [200, [job(), job({ id: 51, project_id: 10 })]] });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ToastProvider>
        <MemoryRouter>
          <HeldRequests where={{ projectId: 9 }} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  expect(await screen.findByText("Waiting for your OK")).toBeInTheDocument();
  expect(document.body).toHaveTextContent("Eli asked for a new take · 27 credits · Asked just now.");
  expect(screen.getByRole("link", { name: "Open in Approvals" })).toHaveAttribute("href", "/approvals?job=50");
  expect(screen.queryByRole("button", { name: "Withdraw" })).toBeNull();
  expect(screen.getAllByText("Waiting for your OK")).toHaveLength(1);
});

test("the owner approving a request on this video never sees the editor's 'The owner said yes' toast", async () => {
  let jobs = [job()];
  const ownerMe = { id: 1, email: "o@b.co", name: "Olu", role: "owner", workspace_id: 1 };
  vi.stubGlobal("fetch", vi.fn(async (r: Request) => new Response(JSON.stringify(new URL(r.url).pathname.endsWith("/auth/me") ? ownerMe : jobs), { status: 200, headers: { "content-type": "application/json" } })));
  const client = new QueryClient();
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter>
          <HeldRequests where={{ projectId: 9 }} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  expect(await screen.findByText("Waiting for your OK")).toBeInTheDocument();
  jobs = [job({ status: "queued", held: "" })];
  await client.refetchQueries({ queryKey: ["held-jobs"] });
  await vi.waitFor(() => expect(screen.queryByText("Waiting for your OK")).toBeNull());
  expect(screen.queryByText(/The owner said yes/)).toBeNull();
});
