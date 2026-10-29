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

test("Videos lists the brand's videos with their status, who, and where each opens", async () => {
  setViewport(1440);
  fakeServer(base(editor, [video({ own_script: true }), video({ id: 10, name: "Bo tries tuna · A", finished_at: "2026-10-24T10:00:00Z" }), video({ id: 11, name: "Old video", script_draft_id: null, archived_at: "2026-10-25T10:00:00Z" })]));
  open();
  expect(await screen.findByRole("link", { name: /Bo tries salmon · B/ })).toHaveAttribute("href", "/b/1/videos/9");
  expect(screen.getByRole("link", { name: /Bo tries tuna · A/ })).toHaveAttribute("href", "/b/1/videos/10?step=downloads"); // a done video opens at Downloads
  const old = screen.getByRole("link", { name: /Old video/ });
  expect(old).toHaveAttribute("href", "/b/1/projects/11");
  expect(within(old).getByText(/\(earlier way\)/)).toBeInTheDocument();
  expect(within(old).getByText("Archived")).toBeInTheDocument();
  expect(screen.getByText(/On your week/)).toBeInTheDocument();
  expect(screen.getAllByText("In production").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Finished").length).toBeGreaterThan(0);
  expect(screen.getByText("3 videos")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Videos" })).toBeInTheDocument();
  expect(within(screen.getByRole("navigation", { name: "Main" })).getByRole("link", { name: "Videos" })).toHaveAttribute("aria-current", "page"); // its own section in the menu (audit M6)
});

test("a finished video whose clips changed since says Finished · changes waiting, not plain Finished, and opens at Clips (#749 LW2)", async () => {
  setViewport(390);
  fakeServer(base(editor, [video({ id: 10, name: "Bo tries tuna · A", finished_at: "2026-10-24T10:00:00Z", final_out_of_date: true }), video({ id: 12, name: "Bo tries cod · C", finished_at: "2026-10-24T10:00:00Z", final_out_of_date: false })]));
  open();
  const changed = await screen.findByRole("link", { name: /Bo tries tuna · A/ });
  expect(changed).toHaveAttribute("href", "/b/1/videos/10?step=clips");
  expect(within(changed).getByText("Finished · changes waiting")).toBeInTheDocument();
  expect(within(changed).queryByText("Finished")).toBeNull();
  const done = screen.getByRole("link", { name: /Bo tries cod · C/ });
  expect(done).toHaveAttribute("href", "/b/1/videos/12?step=downloads");
  expect(within(done).getByText("Finished")).toBeInTheDocument(); // the badge
  expect(within(done).getByText(/· Finished · /)).toBeInTheDocument(); // the meta line
});

test("a row shows its newest still as the poster and the step it is at, or when it was done", async () => {
  setViewport(1440);
  fakeServer(base(editor, [video({ step: "storyboard", poster_file_id: 77 }), video({ id: 10, name: "Bo tries tuna · A", step: "done", finished_at: "2026-10-24T10:00:00Z" }), video({ id: 12, name: "No stills yet", step: "breakdown" }), video({ id: 13, name: "Earlier way", script_draft_id: null, step: "breakdown" })]));
  open();
  const row = (await screen.findByRole("link", { name: /Bo tries salmon · B/ })) as HTMLElement;
  expect(within(row).getByText(/At Storyboard/)).toBeInTheDocument();
  expect(row.querySelector("img")?.getAttribute("src")).toContain("/files/77");
  expect(within(screen.getByRole("link", { name: /Bo tries tuna · A/ })).getByText(/Finished · /)).toBeInTheDocument();
  const bare = screen.getByRole("link", { name: /No stills yet/ });
  expect(within(bare).getByText(/At Plan/)).toBeInTheDocument();
  expect(bare.querySelector("img")).toBeNull();
  // A video from before scripts has no such steps: it says credits, not "At Plan".
  expect(within(screen.getByRole("link", { name: /Earlier way/ })).queryByText(/At Plan/)).toBeNull();
});

test("an editor only ever asks for their own videos; Reed sees everyone's and can turn Mine on", async () => {
  setViewport(1440);
  fakeServer(base(editor, [video({})]));
  open();
  await screen.findByText("1 video");
  expect(urls().every((u) => u.includes("mine=true"))).toBe(true);
  expect(screen.queryByRole("button", { name: "Mine" })).toBeNull();
  cleanup();
  vi.unstubAllGlobals();
  setViewport(1440);
  fakeServer(base(owner, [video({})]));
  open();
  await screen.findAllByText("1 video");
  expect(urls().some((u) => !u.includes("mine="))).toBe(true);
  await userEvent.click(await screen.findByRole("button", { name: "Mine" }));
  await vi.waitFor(() => expect(urls().some((u) => u.includes("mine=true"))).toBe(true));
});

test("status, Archived and search are sent to the server; filtered shows 'x of y' and Clear filters", async () => {
  setViewport(1440);
  fakeServer(base(owner, [video({}), video({ id: 10 })]));
  open("/b/1/scripts?view=videos&status=making&archived=1"); // an old link lands on Videos with its filters
  await screen.findAllByText(/of 2 videos|2 videos/);
  await vi.waitFor(() => expect(urls().some((u) => u.includes("status=making") && u.includes("archived=true"))).toBe(true));
  expect(screen.getByRole("button", { name: "Clear filters" })).toBeInTheDocument();
  await userEvent.type(screen.getByRole("searchbox", { name: "Search videos" }), "salm");
  await vi.waitFor(() => expect(urls().some((u) => u.includes("q=salm"))).toBe(true), { timeout: 2000 });
});

test("an editor with no videos is pointed back to the scripts; filters with no match offer to clear", async () => {
  setViewport(1440);
  fakeServer(base(editor, []));
  open();
  expect(await screen.findByText("You haven't started a video yet.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Show scripts" })).toBeInTheDocument();
  cleanup();
  vi.unstubAllGlobals();
  setViewport(1440);
  fakeServer(base(editor, []));
  open("/b/1/videos?status=done");
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

test("with no status picked, the videos are grouped Needs you, Making, Done; a video that needs you says what it waits on", async () => {
  setViewport(390);
  fakeServer(base(editor, [
    video({ id: 9, name: "Waits on me · A", needs_you: true, waiting_on: "2 stills and 1 clip ready to check" }),
    video({ id: 10, name: "Being made · B", needs_you: false }),
    video({ id: 11, name: "All done · C", needs_you: false, finished_at: "2026-10-24T10:00:00Z" }),
  ]));
  open();
  const needs = await screen.findByRole("region", { name: "Needs you" });
  expect(within(needs).getByRole("link", { name: /Waits on me · A/ })).toHaveTextContent("2 stills and 1 clip ready to check");
  expect(within(screen.getByRole("region", { name: "Making" })).getByRole("link", { name: /Being made · B/ })).toBeInTheDocument();
  expect(within(screen.getByRole("region", { name: "Done" })).getByRole("link", { name: /All done · C/ })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Needs you · 1" })).toBeInTheDocument();
});

test("Status: Needs you asks the server for just those, in one list", async () => {
  setViewport(1440);
  fakeServer(base(editor, [video({ needs_you: true, waiting_on: "Approve 2 looks" })]));
  open("/b/1/videos?status=needs_you");
  expect(await screen.findByText("Approve 2 looks")).toBeInTheDocument();
  await vi.waitFor(() => expect(urls().some((u) => u.includes("status=needs_you"))).toBe(true));
  expect(screen.queryByRole("region", { name: "Needs you" })).toBeNull();
  expect(screen.getByLabelText("Status")).toHaveValue("needs_you");
});
