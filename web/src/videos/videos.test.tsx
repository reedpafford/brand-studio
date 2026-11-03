import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { owner, editor } from "../test/people";

const video = (o: object) => ({
  id: 9, brand_id: 1, name: "Bo tries salmon · B", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "", cast_ids: [], reference_file_id: null,
  estimate_credits: 30, budget_credits: 600, credits_used: 120, budget_pct: 20, created_by_id: 2, created_by_name: "Eli", script_draft_id: 4, own_script: false, archived_at: null, finished_at: null, product_variants: {}, ...o,
});
const base = (me: object, rows: object[], extra: Record<string, [number, unknown]> = {}): Record<string, [number, unknown]> => ({
  "GET /auth/me": [200, me],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /references": [200, []],
  "GET /scripts": [200, []],
  "GET /projects": [200, rows],
  "GET /jobs": [200, []],
  ...extra,
});
const urls = () => (fetch as unknown as { mock: { calls: [Request | string][] } }).mock.calls.map(([r]) => (typeof r === "string" ? r : r.url)).filter((u) => u.includes("/projects?"));
function open(at = "/b/1/videos") {
  render(
    <StrictMode>
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={[at]}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>
    </StrictMode>,
  ); // as in the app: StrictMode renders twice
}
afterEach(() => vi.unstubAllGlobals());
const row = (name: RegExp) => screen.getByRole("link", { name }).closest("li") as HTMLElement;

test("Videos lists the brand's videos with who made them, what they spent, and where each opens", async () => {
  setViewport(1440);
  fakeServer(base(editor, [video({ freestyle_id: 3 }), video({ id: 10, name: "Bo tries tuna · A", finished_at: "2026-10-24T10:00:00Z" }), video({ id: 11, name: "Old video", script_draft_id: null, archived_at: "2026-10-25T10:00:00Z" })]));
  open();
  expect(await screen.findByRole("link", { name: /Bo tries salmon · B/ })).toHaveAttribute("href", "/b/1/videos/9");
  expect(screen.getByRole("link", { name: /Bo tries tuna · A/ })).toHaveAttribute("href", "/b/1/videos/10?step=downloads"); // a done video opens at Downloads
  expect(within(row(/Bo tries salmon · B/)).getByText("Director")).toBeInTheDocument(); // began as a Freestyle
  expect(within(row(/Bo tries salmon · B/)).getByText("Eli")).toBeInTheDocument();
  expect(within(row(/Bo tries salmon · B/)).getByText("spent 120 credits")).toBeInTheDocument(); // never "120 / 600"
  expect(within(row(/Bo tries tuna · A/)).getByText(/Delivered 24 Oct/)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Videos" })).toBeInTheDocument();
  expect(within(screen.getByRole("main")).getByRole("link", { name: "New video" })).toHaveAttribute("href", "/b/1/videos/new");
  expect(within(screen.getByRole("navigation", { name: "Main" })).getByRole("link", { name: "Videos" })).toHaveAttribute("aria-current", "page");
});

test("a finished video whose clips changed since says Finished · changes waiting and opens at Clips (#749 LW2)", async () => {
  setViewport(390);
  fakeServer(base(editor, [video({ id: 10, name: "Bo tries tuna · A", finished_at: "2026-10-24T10:00:00Z", final_out_of_date: true }), video({ id: 12, name: "Bo tries cod · C", finished_at: "2026-10-24T10:00:00Z", final_out_of_date: false })]));
  open();
  expect(await screen.findByRole("link", { name: /Bo tries tuna · A/ })).toHaveAttribute("href", "/b/1/videos/10?step=clips");
  expect(within(row(/Bo tries tuna · A/)).getByText("Finished · changes waiting")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Bo tries cod · C/ })).toHaveAttribute("href", "/b/1/videos/12?step=downloads");
});

test("a row shows its newest still as the poster and its step as four bars (Plan · Cast · Clips · Final cut)", async () => {
  setViewport(1440);
  fakeServer(base(editor, [video({ step: "storyboard", poster_file_id: 77 }), video({ id: 10, name: "Bo tries tuna · A", step: "done", finished_at: "2026-10-24T10:00:00Z" }), video({ id: 12, name: "No stills yet", step: "breakdown" }), video({ id: 13, name: "Earlier way", script_draft_id: null, step: "breakdown" })]));
  open();
  await screen.findByRole("link", { name: /Bo tries salmon · B/ });
  const salmon = row(/Bo tries salmon · B/);
  expect(within(salmon).getByRole("img", { name: "Step 3 of 4: Clips" })).toBeInTheDocument(); // a storyboard counts as Clips
  expect(salmon.querySelector("img[src]")?.getAttribute("src")).toContain("/files/77");
  expect(within(row(/Bo tries tuna · A/)).getByRole("img", { name: "All 4 steps done" })).toBeInTheDocument();
  expect(within(row(/No stills yet/)).getByRole("img", { name: "Step 1 of 4: Plan" })).toBeInTheDocument();
  expect(within(row(/Earlier way/)).queryByRole("img", { name: /Step/ })).toBeNull(); // a video from before scripts has no such steps
});

test("an editor only ever asks for their own videos; Reed sees everyone's and narrows by Maker", async () => {
  setViewport(1440);
  fakeServer(base(editor, [video({})]));
  open();
  await screen.findByRole("link", { name: /Bo tries salmon · B/ });
  expect(urls().every((u) => u.includes("mine=true"))).toBe(true);
  expect(screen.queryByRole("button", { name: /Maker/ })).toBeNull();
  cleanup();
  vi.unstubAllGlobals();
  setViewport(1440);
  fakeServer(base(owner, [video({}), video({ id: 10, name: "Dee's video", created_by_id: 5, created_by_name: "Dee" })]));
  open();
  await screen.findByRole("link", { name: /Dee's video/ });
  expect(urls().every((u) => !u.includes("mine="))).toBe(true);
  await userEvent.click(screen.getByRole("button", { name: /Maker/ }));
  await userEvent.click(screen.getByRole("menuitemradio", { name: "Dee" }));
  expect(screen.queryByRole("link", { name: /Bo tries salmon · B/ })).toBeNull();
  expect(screen.getByRole("link", { name: /Dee's video/ })).toBeInTheDocument();
});

test("Archived asks the server for the archive; an empty list offers the way on", async () => {
  setViewport(1440);
  fakeServer(base(owner, [video({}), video({ id: 10 })]));
  open("/b/1/videos?archived=1");
  await screen.findByRole("region", { name: "Archived" });
  await vi.waitFor(() => expect(urls().some((u) => u.includes("archived=true"))).toBe(true));
  expect(screen.getByRole("button", { name: "Back to videos" })).toBeInTheDocument();
  cleanup();
  vi.unstubAllGlobals();
  setViewport(1440);
  fakeServer(base(editor, []));
  open();
  expect(await screen.findByText("You haven't started a video yet.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Show scripts" })).toBeInTheDocument();
  cleanup();
  vi.unstubAllGlobals();
  setViewport(1440);
  fakeServer(base(editor, []));
  open("/b/1/videos?folder=none");
  expect(await screen.findByText("Nothing matches these filters.")).toBeInTheDocument();
});

test("Scripts is scripts only: no Scripts · Videos switch, and Reed's brand opens on it", async () => {
  setViewport(1440);
  fakeServer(base(owner, []));
  open("/b/1");
  expect(await screen.findByRole("heading", { name: "Scripts" })).toBeInTheDocument();
  expect(screen.queryByRole("navigation", { name: "View" })).toBeNull();
  expect(screen.queryByRole("searchbox", { name: "Search videos" })).toBeNull();
});

test("videos are grouped Needs you, Making, Done; a video that needs you says what it waits on", async () => {
  setViewport(390);
  fakeServer(base(editor, [
    video({ id: 9, name: "Waits on me · A", needs_you: true, waiting_on: "2 stills and 1 clip ready to check" }),
    video({ id: 10, name: "Being made · B", needs_you: false }),
    video({ id: 11, name: "All done · C", needs_you: false, finished_at: "2026-10-24T10:00:00Z" }),
  ]));
  open();
  const needs = await screen.findByRole("region", { name: "Needs you" });
  expect(within(needs).getByRole("link", { name: /Waits on me · A/ }).closest("li")).toHaveTextContent("2 stills and 1 clip ready to check");
  expect(within(screen.getByRole("region", { name: "Making" })).getByRole("link", { name: /Being made · B/ })).toBeInTheDocument();
  expect(within(screen.getByRole("region", { name: "Done" })).getByRole("link", { name: /All done · C/ })).toBeInTheDocument();
});

// A real held Freestyle send: no brand on the job, a hidden project (not in /projects), the brand on the freestyle.
const heldSend = { id: 60, kind: "video", project_id: 99, brand_id: null, script_id: null, credits: 12, status: "needs_owner_approval", created_at: new Date().toISOString(), step: null, declined: false, created_by_id: 5, created_by_name: "Dee", freestyle: { id: 8, title: "freestyle 5", brand_id: 1, script_title: "Bo tries salmon", slot: 1, type: "dialogue", said: "", change: false, up_to: 190, spent: 0, hidden: true } };

test("a held send whose video is hidden is a Request row in Needs you: Reed opens it in Needs you, the editor sees it waits for the owner", async () => {
  setViewport(1440);
  fakeServer(base(owner, [], { "GET /jobs?status=needs_owner_approval": [200, [heldSend]] }));
  open();
  const needs = await screen.findByRole("region", { name: "Needs you" });
  expect(within(needs).getByText("Bo tries salmon · B")).toBeInTheDocument(); // the script's title and the version letter, never "freestyle 5"
  expect(within(needs).queryByText(/freestyle 5/)).toBeNull();
  expect(within(needs).getByText("Request")).toBeInTheDocument();
  expect(within(needs).getByText("up to 190 credits")).toBeInTheDocument();
  expect(within(needs).getByText("Starts at your OK")).toBeInTheDocument();
  expect(within(needs).getByRole("link", { name: "Open in Needs you" })).toHaveAttribute("href", "/approvals");
  cleanup();
  vi.unstubAllGlobals();
  setViewport(1440);
  fakeServer(base(editor, [], { "GET /jobs?mine=true": [200, [heldSend]] }));
  open();
  expect(await screen.findByText("Waiting for the owner's OK")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Open in Needs you" })).toBeNull();
});

test("a delivered video with a change waiting for the owner says so, not Delivered", async () => {
  setViewport(1440);
  const change = { ...heldSend, id: 61, project_id: 9, freestyle: null, step: "change" };
  fakeServer(base(owner, [video({ finished_at: "2026-10-24T10:00:00Z", needs_you: true })], { "GET /jobs?status=needs_owner_approval": [200, [change]] }));
  open();
  const line = await screen.findByRole("link", { name: /Bo tries salmon · B/ });
  expect(await within(line.closest("li") as HTMLElement).findByRole("link", { name: "Open in Needs you" })).toHaveAttribute("href", "/approvals");
  expect(within(line.closest("li") as HTMLElement).queryByText(/Delivered/)).toBeNull();
});

test("a video with my request waiting says so on its row: 1 request waiting for the owner", async () => {
  setViewport(390);
  const waiting = { id: 50, kind: "video", project_id: 9, script_id: null, credits: 27, status: "needs_owner_approval", created_at: new Date().toISOString(), step: "clip_take", declined: false };
  fakeServer(base(editor, [video({}), video({ id: 10, name: "Bo tries tuna · A" })], { "GET /jobs?mine=true": [200, [waiting]] }));
  open();
  await screen.findByRole("link", { name: /Bo tries salmon · B/ });
  expect(await within(row(/Bo tries salmon · B/)).findByText("1 request waiting for the owner")).toBeInTheDocument();
  expect(within(row(/Bo tries tuna · A/)).queryByText(/waiting for the owner/)).toBeNull();
});

test("spent counts everything the video used, the director's own time too, in whole credits", async () => {
  setViewport(390);
  fakeServer(base(editor, [video({ script_draft_id: null, credits_used: 93.4, budget_credits: 600, director_credits: 70.4 })]));
  open();
  expect(await screen.findByText("spent 94 credits")).toBeInTheDocument();
});
