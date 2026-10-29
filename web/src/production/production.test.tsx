import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const owner = { id: 1, email: "reed@b.co", name: "Reed", role: "owner", workspace_id: 1 };
const minutesAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString();
const row = (o: object = {}) => ({
  project_id: 11, brand: { id: 1, name: "Iron Paws" }, script: { id: 5, title: "Bo tries salmon" }, letter: "B", editor: { id: 3, name: "Sam" }, step: "clips",
  last_activity_at: minutesAgo(180), credits_used: 380, budget_credits: 420, spent_usd: 39.06, poster_file_id: null, flag: null, flag_since: null, flag_job: null, flag_problem: null, ...o,
});
const failed = row({ flag: "failed", flag_since: minutesAgo(180), flag_problem: "take 2 of clip 3 didn't finish. Credits were returned." });
const stuck = row({ project_id: 12, brand: { id: 2, name: "fomo" }, script: { id: 6, title: "Altar remake" }, letter: "A", editor: { id: 4, name: "Ana" }, step: "storyboard", credits_used: 96, budget_credits: 210, spent_usd: 9.87, flag: "stuck", flag_since: minutesAgo(52), flag_job: "Drawing the frames" });
const idle = row({ project_id: 13, script: { id: 7, title: "Gut check" }, letter: "C", step: "assets", last_activity_at: minutesAgo(3 * 1440), credits_used: 12, budget_credits: 180, spent_usd: 1.23, flag: "idle", flag_since: minutesAgo(3 * 1440) });
const fine = row({ project_id: 14, script: { id: 8, title: "Midnight snack" }, letter: "A", editor: { id: 1, name: "Reed" }, step: "breakdown", last_activity_at: minutesAgo(4), credits_used: 0, budget_credits: 120, spent_usd: 0 });
const base = (rows: object[] = [failed, stuck, idle, fine]): Record<string, [number, unknown]> => ({
  "GET /auth/me": [200, owner],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }, { id: 2, name: "fomo", colours: [] }]],
  "GET /scripts": [200, []],
  "GET /projects": [200, []],
  "GET /production/summary": [200, { in_production: rows.length, needs_attention: rows.filter((r) => (r as { flag: string | null }).flag).length }],
  "GET /production": [200, rows],
});

function open(path = "/production", client = new QueryClient()) {
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}
afterEach(() => vi.unstubAllGlobals());

test("In production: a row per video links to it, flagged rows say why, and the rail badge counts what needs attention", async () => {
  setViewport(1440);
  fakeServer(base());
  open();
  expect(await screen.findByText("4 videos being made · 3 need attention")).toBeInTheDocument();
  const link = await screen.findByRole("link", { name: "Bo tries salmon, version B, Sam, at Clips, didn't finish" });
  expect(link).toHaveAttribute("href", "/b/1/projects/11");
  expect(within(link).getByText("Clips: take 2 of clip 3 didn't finish. Credits were returned.")).toBeInTheDocument();
  expect(screen.getByText("Drawing the frames for 52 min")).toBeInTheDocument();
  expect(screen.getByText("Nothing for 3 days")).toBeInTheDocument();
  expect(within(screen.getByRole("link", { name: /Midnight snack/ })).queryByText(/Stuck|Didn't|No activity/)).toBeNull();
  expect(within(link).getByText("380 of 420")).toHaveAttribute("title", "Close to the budget. Going over needs your approval.");
  expect(screen.getByText("96 of 210")).not.toHaveAttribute("title");
  const rail = screen.getByRole("navigation", { name: "Main" });
  expect(within(rail).getByRole("link", { name: /^In production/ })).toHaveTextContent("3 need attention");
});

test("In production: filters go in the address and to the server; the Brand column goes when one brand is chosen", async () => {
  setViewport(1440);
  fakeServer(base());
  open("/production?brand=2&attention=1");
  await screen.findByRole("link", { name: /Bo tries salmon/ });
  expect(screen.getByRole("button", { name: "Needs attention" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.queryByText("Brand", { selector: "span" })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  expect(await screen.findByText("Brand", { selector: "span" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Needs attention" })).toHaveAttribute("aria-pressed", "false");
});

test("In production: on a phone the rows are cards and the filters are in a sheet", async () => {
  setViewport(390);
  fakeServer(base());
  open();
  const card = await screen.findByRole("link", { name: /Altar remake/ });
  expect(card).toHaveTextContent("Storyboard · 3 h ago");
  expect(card).toHaveTextContent("96 of 210 credits · $9.87");
  await userEvent.click(screen.getByRole("button", { name: "Filters" }));
  const sheet = await screen.findByRole("dialog", { name: "Filters" });
  expect(within(sheet).getByRole("combobox", { name: "Brand" })).toBeInTheDocument();
  expect(within(sheet).getByRole("combobox", { name: "Sort" })).toBeInTheDocument();
});

test("In production counts finished videos with changes waiting, so nothing reads as all done (#749 LW2)", async () => {
  setViewport(390);
  fakeServer({ ...base([]), "GET /production/summary": [200, { in_production: 0, needs_attention: 0, changes_waiting: 2 }] });
  open();
  expect(await screen.findByRole("link", { name: "2 finished videos have changes waiting" })).toHaveAttribute("href", "/usage"); // listed by brand in Usage
  expect(screen.getByText(/0 videos being made ·/)).toBeInTheDocument();
});

test("In production: each empty state says what is true", async () => {
  setViewport(1440);
  fakeServer(base([]));
  open();
  expect(await screen.findByText("Nothing is being made right now.")).toBeInTheDocument();
  vi.unstubAllGlobals();
  fakeServer(base([]));
  open("/production?attention=1");
  expect(await screen.findByText("Nothing needs attention.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Show all" })).toBeInTheDocument();
});

test("In production: a failed load keeps a banner with Try again; an editor sees Page not found", async () => {
  setViewport(1440);
  fakeServer({ ...base(), "GET /production": [500, { detail: "x" }] });
  open();
  expect(await screen.findByText("Couldn't load the videos being made.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  vi.unstubAllGlobals();
  fakeServer({ ...base(), "GET /auth/me": [200, { ...owner, id: 2, role: "editor" }], "GET /production": [404, { detail: "Not found" }] });
  open();
  expect(await screen.findByText("Page not found.")).toBeInTheDocument();
});

test("In production: a refresh updates rows in place and never reorders them", async () => {
  setViewport(1440);
  const routes = base([failed, fine]);
  fakeServer(routes);
  const client = open();
  await screen.findByRole("link", { name: /Bo tries salmon/ });
  routes["GET /production"] = [200, [{ ...fine, flag: "stuck", flag_since: minutesAgo(40), flag_job: "Making the takes" }, failed]];
  await client.invalidateQueries({ queryKey: ["production", "rows"] });
  expect(await screen.findByText("Making the takes for 40 min")).toBeInTheDocument();
  const titles = screen.getAllByRole("link", { name: /version/ }).map((l) => l.getAttribute("aria-label")?.split(",")[0]);
  expect(titles).toEqual(["Bo tries salmon", "Midnight snack"]);
});

test("In production: a video whose editor is gone still lists, as Someone's", async () => {
  setViewport(1440);
  fakeServer(base([row({ editor: null })]));
  open();
  expect(await screen.findByRole("link", { name: "Bo tries salmon, version B, Someone, at Clips" })).toBeInTheDocument();
});

test("In production: a row's menu releases the version, with the letter and the credits that stay used", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base([failed]), "POST /projects/11/release": [200, {}] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "More for Bo tries salmon · B" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Release this version" }));
  const dialog = await screen.findByRole("alertdialog", { name: "Release version B?" });
  expect(dialog).toHaveTextContent("The 380 credits already used stay used.");
  await userEvent.click(within(dialog).getByRole("button", { name: "Release" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/11/release")).toBe(true));
  expect(await screen.findByText("Version B is ready to make again.")).toBeInTheDocument();
});
