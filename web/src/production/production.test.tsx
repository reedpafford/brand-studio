import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { owner } from "../test/people";

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

test("In production: a row per video links to it, flagged rows say why, and the rail's Needs you counts what Needs you lists", async () => {
  setViewport(1440);
  fakeServer({ ...base(), "GET /needs-you": [200, { total: 3, brands: [], questions: [], money: [], sends: [], stuck: [] }] });
  open();
  expect(await screen.findByText("Every brand · 4 videos making · 3 need attention")).toBeInTheDocument();
  const link = await screen.findByRole("link", { name: "Bo tries salmon, version B, Sam, at Clips, didn't finish" });
  expect(link).toHaveAttribute("href", "/b/1/projects/11");
  expect(within(link).getByText("Clips: take 2 of clip 3 didn't finish. Credits were returned.")).toBeInTheDocument();
  expect(screen.getByText("Drawing the frames for 52 min")).toBeInTheDocument();
  expect(screen.getByText("Nothing for 3 days")).toBeInTheDocument();
  expect(within(screen.getByRole("link", { name: /Midnight snack/ })).queryByText(/Stuck|Didn't|No activity/)).toBeNull();
  expect(within(link).getByText("spent 380")).toBeInTheDocument(); // the Producer, 3 Nov: one line, whole credits
  expect(within(link).queryByText(/\$|of director time/)).toBeNull();
  const rail = screen.getByRole("navigation", { name: "Main" });
  expect(await within(rail).findByRole("link", { name: /^Needs you/ })).toHaveTextContent("3 waiting"); // GET /needs-you's total
  expect(within(rail).getByRole("link", { name: "In production" })).toBeInTheDocument(); // its own count went to Needs you
});

test("In production: filters go in the address and to the server; the Brand column goes when one brand is chosen", async () => {
  setViewport(1440);
  fakeServer(base());
  open("/production?brand=2&attention=1");
  await screen.findByRole("link", { name: /Bo tries salmon/ });
  expect(screen.getByRole("tab", { name: /^Needs attention/ })).toHaveAttribute("aria-selected", "true"); // v5 D_Production: Making and Needs attention are tabs
  expect(screen.getByRole("combobox", { name: "Brand" })).toHaveValue("2");
  const main = screen.getByRole("main");
  expect(within(main).queryByText("Brand", { selector: "span" })).toBeNull();
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Brand" }), "");
  await userEvent.click(screen.getByRole("tab", { name: /^Making/ }));
  expect(await within(main).findByText("Brand", { selector: "span" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: /^Making/ })).toHaveAttribute("aria-selected", "true");
});

test("In production on a computer (v5 D_Production): each row shows its step as bars and what it's doing now", async () => {
  setViewport(1440);
  fakeServer(base());
  open();
  const link = await screen.findByRole("link", { name: /Midnight snack/ });
  expect(within(link).getByRole("img", { name: /: step \d of 4$/ })).toBeInTheDocument();
  expect(within(link).getByText(/^(Making the plan|Casting|Drawing the storyboard|Making clips|Making the final cut)/)).toBeInTheDocument();
  expect(screen.getByText("Steps: Plan · Cast · Clips · Final cut. A row opens its video on the director thread.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^More for / })).toBeNull(); // no row menu: Release is on the video page
});

test("In production: on a phone the rows are cards with Brand in the top bar, and no search, sort or Filters (v5 D_Production)", async () => {
  setViewport(390);
  fakeServer(base());
  open();
  const card = await screen.findByRole("link", { name: /Altar remake/ });
  expect(card).toHaveTextContent("Storyboard · 3 h ago");
  expect(card).toHaveTextContent("spent 96");
  expect(screen.getByRole("combobox", { name: "Brand" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^Filters/ })).toBeNull();
  expect(screen.queryByRole("searchbox")).toBeNull();
});

test("In production counts finished videos with changes waiting, so nothing reads as all done (#749 LW2)", async () => {
  setViewport(390);
  fakeServer({ ...base([]), "GET /production/summary": [200, { in_production: 0, needs_attention: 0, changes_waiting: 2 }] });
  open();
  expect(await screen.findByRole("link", { name: "2 finished videos have changes waiting" })).toHaveAttribute("href", "/usage"); // listed by brand in Usage
  expect(screen.getByText(/Every brand · 0 videos making ·/)).toBeInTheDocument();
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

test("In production (#1232): a video at Clips says how many are made, and Delivered today is a tab that asks the server for today's", async () => {
  setViewport(1440);
  const making = row({ project_id: 21, script: { id: 9, title: "Walk day" }, letter: "C", clips_made: 4, clips_total: 6, last_activity_at: minutesAgo(5) });
  const done = row({ project_id: 22, script: { id: 10, title: "Market open" }, letter: "B", step: "downloads", finished_at: minutesAgo(30), last_activity_at: minutesAgo(30) });
  const calls = fakeServer({ ...base([making]), "GET /production/summary": [200, { in_production: 1, needs_attention: 0, changes_waiting: 0, delivered_today: 1 }], "GET /production?delivered=today&sort=activity&limit=25&offset=0": [200, [done]] });
  open();
  const link = await screen.findByRole("link", { name: /Walk day/ });
  expect(within(link).getByText(/^Making clips: 4 of 6/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("tab", { name: /^Delivered today\s*1$/ }));
  const shipped = await screen.findByRole("link", { name: /Market open/ });
  expect(within(shipped).getByText(/^Delivered/)).toBeInTheDocument();
  expect(calls.some((c) => c.key === "GET /production")).toBe(true);
});

test("In production on a phone (QA-3 on #1241): the three tabs are there, cards read like the computer's Now, and Delivered today counts its own list", async () => {
  setViewport(390);
  const making = row({ project_id: 21, script: { id: 9, title: "Walk day" }, letter: "C", clips_made: 1, clips_total: 3, last_activity_at: minutesAgo(5) });
  const done = row({ project_id: 22, script: { id: 10, title: "Market open" }, letter: "B", step: "downloads", finished_at: minutesAgo(1), last_activity_at: minutesAgo(1) });
  fakeServer({ ...base([making, making]), "GET /production/summary": [200, { in_production: 2, needs_attention: 0, changes_waiting: 0, delivered_today: 1 }], "GET /production?delivered=today&sort=activity&limit=25&offset=0": [200, [done]] });
  open();
  const card = (await screen.findAllByRole("link", { name: /Walk day/ }))[0];
  expect(within(card).getByText(/^Making clips: 1 of 3/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("tab", { name: /^Delivered\s*1$/ }));
  const shipped = await screen.findByRole("link", { name: /Market open/ });
  expect(within(shipped).getByText(/^Delivered/)).toBeInTheDocument();
  expect(screen.getByText(/^Every brand · \d+ videos? making/)).toBeInTheDocument(); // v5 D_Production: the same line on every tab
});

test("In production's spend is one line, the director's time included, in whole credits; 'up to N approved' only where the owner approved a run (the Producer, 3 Nov)", async () => {
  setViewport(1440);
  fakeServer(base([{ ...failed, credits_used: 97.33, director_credits: 70.4, budget_credits: 729 }, { ...fine, credits_used: 20.06, approved_up_to: 204 }]));
  open();
  const director = await screen.findByRole("link", { name: /Bo tries salmon, version B/ });
  expect(within(director).getByText("spent 98")).toBeInTheDocument();
  expect(within(director).queryByText(/director time|approved/)).toBeNull();
  const approved = screen.getByRole("link", { name: /Midnight snack/ });
  expect(within(approved).getByText("spent 21")).toBeInTheDocument();
  expect(within(approved).getByText("up to 204 approved")).toBeInTheDocument();
});

test("In production's Brand picker is a 44 px press on a phone (QA-3 on #1246)", async () => {
  setViewport(390);
  fakeServer(base());
  open();
  expect(await screen.findByRole("combobox", { name: "Brand" })).toHaveClass("min-h-control");
});

test("In production's spend is one line, the director's time included, in whole credits; 'up to N approved' only where the owner approved a run (the Producer, 3 Nov)", async () => {
  setViewport(1440);
  fakeServer(base([{ ...failed, credits_used: 97.33, director_credits: 70.4, budget_credits: 729 }, { ...fine, credits_used: 20.06, approved_up_to: 204 }]));
  open();
  const director = await screen.findByRole("link", { name: /Bo tries salmon, version B/ });
  expect(within(director).getByText("spent 98")).toBeInTheDocument();
  expect(within(director).queryByText(/director time|approved/)).toBeNull();
  const approved = screen.getByRole("link", { name: /Midnight snack/ });
  expect(within(approved).getByText("spent 21")).toBeInTheDocument();
  expect(within(approved).getByText("up to 204 approved")).toBeInTheDocument();
});

test("In production's Brand picker is a 44 px press on a phone (QA-3 on #1246)", async () => {
  setViewport(390);
  fakeServer(base());
  open();
  expect(await screen.findByRole("combobox", { name: "Brand" })).toHaveClass("min-h-control");
});
