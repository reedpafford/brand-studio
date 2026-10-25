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
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, owner],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /scripts": [200, []],
  "GET /projects": [200, []],
};
const summary = { period: "week", starts_at: "2026-10-19T00:00:00Z", previous: { spend_usd: 71.72, finished: 4, cost_per_finished_usd: 12.25 }, spend_usd: 84.12, spend_estimated: false, finished: 6, cost_per_finished_usd: 11.4, in_progress: 9, unassigned_spend_usd: 1.2 };
const row = (o: object = {}) => ({ brand_id: 1, name: "Iron Paws", colour: "#3a7", archived: false, spend_usd: 52.3, spend_estimated: false, finished: 4, cost_per_finished_usd: 11.05, in_progress: 3, scripts: 12, versions_left: 7, last_activity_at: new Date(Date.now() - 2 * 3600_000).toISOString(), ...o });
const brands = (items: object[], total = items.length, next: string | null = null) => ({ total, next_cursor: next, items });

function open(path = "/usage") {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
afterEach(() => vi.unstubAllGlobals());

test("Usage: four totals with the comparison, and a row per brand that links to it; a new brand shows zeros and a dash", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /usage/summary": [200, summary],
    "GET /usage/brands": [200, brands([row(), row({ brand_id: 2, name: "fomo", spend_usd: 30.62, spend_estimated: true, finished: 2, cost_per_finished_usd: 12.1 }), row({ brand_id: 3, name: "Night Owl", spend_usd: 0, finished: 0, cost_per_finished_usd: null, in_progress: 0, scripts: 0, versions_left: 0, last_activity_at: null })])],
  });
  open();
  const totals = await screen.findByRole("group", { name: "Totals" });
  expect(await within(totals).findByText("$84.12")).toBeInTheDocument();
  expect(within(totals).getByText("+$12.40 on last week")).toBeInTheDocument();
  expect(within(totals).getByText("6 videos")).toBeInTheDocument();
  expect(within(totals).getByText("+2 on last week")).toBeInTheDocument();
  expect(within(totals).getByText("−$0.85 on last week")).toBeInTheDocument();
  expect(screen.getByText(/^Week of \d+ Oct$/)).toBeInTheDocument();
  const link = await screen.findByRole("link", { name: "Iron Paws: $52.30 spent, 4 finished" });
  expect(link).toHaveAttribute("href", "/usage/brands/1");
  expect(screen.getByText("≈ $30.62")).toHaveAttribute("title", expect.stringMatching(/estimate/));
  const owl = screen.getByRole("link", { name: "Night Owl: $0.00 spent, 0 finished" }).closest("tr")!;
  expect(within(owl).getAllByText("—")).toHaveLength(2); // no cost per video, no last activity
  expect(screen.getByText("3 brands")).toBeInTheDocument();
  expect(screen.getByText("Not tied to one brand: $1.20 · character looks used by several brands")).toBeInTheDocument();
});

test("Usage: the period, search and sort live in the address and go to the server; Show more asks for the next 25", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /usage/summary": [200, { ...summary, previous: null, period: "all" }],
    "GET /usage/brands": [200, brands([row()], 40, "c2")],
  });
  open("/usage?period=all&sort=name");
  await screen.findByRole("link", { name: /Iron Paws/ });
  expect(screen.getByLabelText("Sort")).toHaveValue("name");
  expect(screen.queryByText(/on last/)).not.toBeInTheDocument(); // All time compares with nothing
  await userEvent.type(screen.getByRole("searchbox"), "iron");
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "GET /usage/brands").length).toBeGreaterThan(1));
  await userEvent.click(screen.getByRole("button", { name: "Show more" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "GET /usage/brands").length).toBeGreaterThan(2));
});

test("Usage on a phone: brand cards with the sentence, and one Filters button for sort and archived", async () => {
  fakeServer({ ...base, "GET /usage/summary": [200, summary], "GET /usage/brands": [200, brands([row()])] });
  open();
  const card = await screen.findByRole("link", { name: "Iron Paws: $52.30 spent, 4 finished" });
  expect(within(card).getByText(/\$52\.30 spent · 4 finished · \$11\.05 each/)).toBeInTheDocument();
  expect(within(card).getByText("3 in progress · 12 scripts · 7 versions left")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Filters" }));
  const sheet = await screen.findByRole("dialog", { name: "Filters" });
  expect(within(sheet).getByLabelText("Sort")).toHaveValue("spend");
  expect(within(sheet).getByLabelText("Show archived")).not.toBeChecked();
});

test("Usage: an editor gets Page not found and never sees a dollar", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /auth/me": [200, editor], "GET /usage/summary": [404, { detail: "Not found" }], "GET /usage/brands": [404, { detail: "Not found" }] });
  open();
  expect(await screen.findByText("Page not found.")).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/\$/);
  expect(screen.queryByRole("link", { name: "Usage" })).not.toBeInTheDocument();
});

test("Usage: nothing spent says so, and no brands has its own words", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /usage/summary": [200, { ...summary, spend_usd: 0, finished: 0, cost_per_finished_usd: null, in_progress: 0, unassigned_spend_usd: 0, previous: null }], "GET /usage/brands": [200, brands([])] });
  open();
  expect(await screen.findByText("Nothing was spent this week.")).toBeInTheDocument();
  expect(await screen.findByText("No brands yet.")).toBeInTheDocument();
});

test("One brand's Usage: its own totals and the line under them", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /usage/summary": [200, summary], "GET /usage/brands/1": [200, { ...row(), previous: { spend_usd: 44.2, finished: 3, cost_per_finished_usd: 12.25 }, editors_active: 3 }] });
  open("/usage/brands/1");
  expect(await screen.findByRole("heading", { name: "Iron Paws" })).toBeInTheDocument();
  expect(await within(screen.getByRole("group", { name: "Totals" })).findByText("$52.30")).toBeInTheDocument();
  expect(screen.getByText("12 scripts · 7 versions left to make · 3 people made videos this week")).toBeInTheDocument();
  expect(within(screen.getByRole("main")).getByRole("link", { name: "Usage" })).toHaveAttribute("href", "/usage");
});

test("the rail has Usage for Reed", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /usage/summary": [200, summary], "GET /usage/brands": [200, brands([])] });
  open("/b/1/scripts");
  expect(await screen.findByRole("link", { name: "Usage" })).toHaveAttribute("href", "/usage");
});
