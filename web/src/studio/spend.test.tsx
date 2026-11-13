import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { owner } from "../test/people";
import { renderApp } from "../test/render";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const part = (name: string, usd: number) => ({ name, usd, estimated: false });
const figures = { spend_usd: 53.37, spend_estimated: false, finished: 13, cost_per_finished_usd: 4.11, in_progress: 2, providers: [part("Replicate", 40.76), part("Claude", 12.61)] };
const summary = { ...figures, period: "month", starts_at: "2026-11-01T00:00:00", previous: null, unassigned_spend_usd: 0, freestyle_spend_usd: 1.4, director_spend_usd: 8.71, spend_credits: 0, unassigned_credits: 0, freestyle: { credits: 0, spend_usd: 1.4, videos: 1, providers: [], spend_estimated: false }, unassigned_providers: [], unassigned_estimated: false };
const brandRow = (brand_id: number, name: string, spend_usd: number, videos: number, o: object = {}) => ({ brand_id, name, colour: null, archived: false, spend_usd, spend_estimated: false, finished: videos, cost_per_finished_usd: null, in_progress: 0, scripts: 0, versions_left: 0, last_activity_at: null, credits: 0, videos, providers: [], ...o });
const BRANDS = [{ id: 1, name: "Palace Guard", colours: ["#ef8a3c"] }, { id: 2, name: "Iron Paws", colours: [] }];
const video = (project_id: number, brand_id: number, brand: string, title: string, spend_usd: number) => ({ project_id, brand_id, brand, title, freestyle_id: null, spend_usd, spend_estimated: false, providers: [], kinds: [], last_at: "2026-11-12T10:00:00" });
const own = (project_id: number, title: string, status: string, spend_usd: number, finished_at: string | null = null) => ({ project_id, title, script_id: null, version_letter: null, legacy: false, person: null, status, spend_usd, spend_estimated: false, credits: 0, finished_at, last_activity_at: "2026-11-13T08:00:00", final_out_of_date: false });

function server(routes: Record<string, [number, unknown]> = {}) {
  return fakeServer({
    "GET /auth/me": [200, owner],
    "GET /brands": [200, BRANDS],
    "GET /usage/summary": [200, summary],
    "GET /usage/brands": [200, { total: 2, next_cursor: null, items: [brandRow(1, "Palace Guard", 28.97, 7, { colour: "#ef8a3c" }), brandRow(2, "Iron Paws", 13.27, 3)] }],
    "GET /usage/videos": [200, { total: 2, next_cursor: null, kinds: [], items: [video(366, 1, "Palace Guard", "Three men at Target", 5.82), video(41, 2, "Iron Paws", "Bo tries salmon", 4.12)] }],
    "GET /usage/brands/1": [200, { ...brandRow(1, "Palace Guard", 28.97, 7), ...figures, spend_usd: 28.97, finished: 7, in_progress: 1, previous: null, editors_active: 1 }],
    "GET /usage/brands/1/videos": [200, { total: 2, next_cursor: null, people: [], items: [own(367, "A dad on the border", "in_production", 2.98), own(366, "Three men at Target", "done", 5.82, "2026-11-12T10:00:00")] }],
    "GET /usage/brands/2": [200, { ...brandRow(2, "Iron Paws", 0, 0), ...figures, spend_usd: 0, finished: 0, cost_per_finished_usd: null, in_progress: 0, providers: [], previous: null, editors_active: 0 }],
    "GET /usage/brands/2/videos": [200, { total: 0, next_cursor: null, people: [], items: [] }],
    ...routes,
  });
}
type Calls = ReturnType<typeof server>;
const asked = (calls: Calls, path: string) => calls.filter((c) => c.key === `GET ${path}`).map((c) => new URL(c.url).search);
const hero = () => screen.findByText(/^Spent on /);

beforeEach(() => {
  localStorage.clear();
  setViewport(1440);
});
afterEach(() => vi.unstubAllGlobals());

test("Spend shows this month's total as the server gives it, where it went, each brand's part and every video with its cost, each number named", async () => {
  const calls = server();
  renderApp("/s/b/1/spend");
  expect(await hero()).toHaveTextContent("Spent on all brands, this month");
  expect(screen.getByText("$53.37")).toBeInTheDocument();
  expect(screen.getByText("13 finished videos · $4.11 a finished video")).toBeInTheDocument();
  expect(screen.getByText("2 videos not finished")).toBeInTheDocument();
  expect(screen.getByText("Of this, $8.71 was the director’s own thinking and watching.")).toBeInTheDocument();
  const services = within(screen.getByRole("list", { name: "Where it went, by service" })).getAllByRole("listitem");
  expect(services.map((li) => li.textContent)).toEqual(["Replicate$40.76", "Claude$12.61"]);
  const brands = within(await screen.findByRole("list", { name: "By brand" }));
  expect(brands.getByRole("button", { name: "Palace Guard, 7 videos, $28.97" })).toBeInTheDocument();
  expect(brands.getByRole("button", { name: "Iron Paws, 3 videos, $13.27" })).toBeInTheDocument();
  expect(brands.getByText("No brand picked").closest("li")).toHaveTextContent("No brand picked1 video$1.40"); // so the rows add up to the total
  const table = within(await screen.findByRole("table"));
  expect(table.getAllByRole("columnheader").map((th) => th.textContent)).toEqual(["Video", "Brand", "Last charge", "Cost so far"]);
  expect(table.getByRole("row", { name: "Bo tries salmon Iron Paws 12 Nov $4.12" })).toBeInTheDocument();
  expect(table.getByRole("link", { name: "Three men at Target" })).toHaveAttribute("href", "/s/b/1/videos/366");
  for (const path of ["/usage/summary", "/usage/brands", "/usage/videos"]) expect(asked(calls, path)[0]).toContain("period=month");
});

test("a brand's row shows that brand alone: its total, what is still being made with its cost so far, what is finished; Clear goes back to every brand", async () => {
  const calls = server();
  renderApp("/s/b/1/spend");
  await userEvent.click(await screen.findByRole("button", { name: "Palace Guard, 7 videos, $28.97" }));
  expect(await hero()).toHaveTextContent("Spent on Palace Guard, this month");
  expect(screen.getByText("$28.97")).toBeInTheDocument();
  expect(screen.getByText("1 video not finished")).toBeInTheDocument();
  const making = within(await screen.findByRole("region", { name: "Still being made" }));
  expect(making.getAllByRole("columnheader").map((th) => th.textContent)).toEqual(["Video", "Last worked on", "Cost so far"]);
  expect(making.getByRole("row", { name: "A dad on the border 13 Nov $2.98" })).toBeInTheDocument();
  const finished = within(screen.getByRole("region", { name: "Finished, this month" }));
  expect(finished.getByRole("row", { name: "Three men at Target 12 Nov $5.82" })).toBeInTheDocument();
  expect(finished.getByRole("link", { name: "Three men at Target" })).toHaveAttribute("href", "/s/b/1/videos/366");
  expect(screen.queryByRole("list", { name: "By brand" })).toBeNull();
  expect(asked(calls, "/usage/brands/1/videos")).toEqual(["?period=month&status=any&sort=activity&limit=25"]);
  await userEvent.click(screen.getByRole("button", { name: "Clear" }));
  expect(await hero()).toHaveTextContent("Spent on all brands, this month");
});

test("the brand menu and the time buttons ask the server for that brand and that time", async () => {
  const calls = server();
  renderApp("/s/b/1/spend");
  await userEvent.click(await screen.findByRole("button", { name: "All time" }));
  expect(await screen.findByText("Spent on all brands, all time")).toBeInTheDocument();
  expect(asked(calls, "/usage/summary").at(-1)).toBe("?period=all");
  await userEvent.click(screen.getByRole("button", { name: "All brands" }));
  await userEvent.click(screen.getByRole("menuitemradio", { name: "Palace Guard" }));
  expect(await screen.findByText("Spent on Palace Guard, all time")).toBeInTheDocument();
  expect(asked(calls, "/usage/brands/1").at(-1)).toBe("?period=all");
});

test("Update now reads the figures again, and the page says when they were read", async () => {
  const calls = server();
  renderApp("/s/b/1/spend");
  await hero();
  expect(screen.getByText(/^Updated \d/)).toBeInTheDocument();
  const before = asked(calls, "/usage/summary").length;
  await userEvent.click(screen.getByRole("button", { name: "Update now" }));
  await vi.waitFor(() => expect(asked(calls, "/usage/summary")).toHaveLength(before + 1));
  expect(asked(calls, "/usage/videos").length).toBeGreaterThan(1);
});

test("a brand with nothing spent says so and offers its first video", async () => {
  server();
  renderApp("/s/b/1/spend?brand=2&period=all");
  expect(await screen.findByText("Nothing spent on Iron Paws yet")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Make its first video" })).toHaveAttribute("href", "/s/b/2");
  expect(screen.queryByText(/^\$/)).toBeNull(); // no figure the server did not give
});

test("a studio with one brand has no brand menu and no By brand list", async () => {
  server({ "GET /brands": [200, BRANDS.slice(0, 1)], "GET /usage/brands": [200, { total: 1, next_cursor: null, items: [brandRow(1, "Palace Guard", 28.97, 7)] }], "GET /usage/summary": [200, { ...summary, freestyle: { ...summary.freestyle, spend_usd: 0, videos: 0 } }] });
  renderApp("/s/b/1/spend");
  await hero();
  await screen.findByRole("table");
  expect(screen.queryByRole("button", { name: "All brands" })).toBeNull();
  expect(screen.queryByRole("list", { name: "By brand" })).toBeNull();
});

test("someone who isn't the owner is told so, with the way to their own credits", async () => {
  server({ "GET /usage/summary": [404, { detail: "Not found" }] });
  renderApp("/s/b/1/spend");
  expect(await screen.findByRole("link", { name: "Your own credits are on the current site" })).toHaveAttribute("href", "/usage/mine");
});

test("Spend only reads: opening it, filtering and coming back to the window send nothing but GETs", async () => {
  const calls = server();
  renderApp("/s/b/1/spend");
  await userEvent.click(await screen.findByRole("button", { name: "Palace Guard, 7 videos, $28.97" }));
  await screen.findByRole("region", { name: "Still being made" });
  fireEvent.focus(window);
  await userEvent.click(screen.getByRole("button", { name: "Update now" }));
  await hero();
  expect(calls.filter((c) => !c.key.startsWith("GET "))).toEqual([]);
});
