import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const owner = { id: 1, email: "reed@b.co", name: "Reed", role: "owner", workspace_id: 1 };
const daysAgo = (n: number) => new Date(Date.now() - n * 86_400_000).toISOString();
const row = (o: object = {}) => ({
  id: 7, brand_id: 1, title: "Bo tries salmon", description: "Show a picky dog.", reference_id: null, published: false, status: "draft", created_by_id: 1, created_by_name: "Reed", created_at: "2026-10-24T10:00:00Z", versions_left: 0,
  versions: [{ slot: 0, status: "draft", title: "x", seconds: 0, project_id: null }], removed_at: daysAgo(2), purge_on: "2026-11-24T10:00:00Z", ...o,
});
const base = (o: Record<string, [number, unknown]> = {}): Record<string, [number, unknown]> => ({
  "GET /auth/me": [200, owner],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /references": [200, []],
  "GET /projects": [200, []],
  "GET /jobs": [200, []],
  "GET /scripts": [200, [row()]],
  ...o,
});
function open(path = "/b/1/scripts?removed=1") {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
afterEach(() => vi.unstubAllGlobals());

test("Deleted and archived lists removed scripts with when, the removal date, and Restore; nothing opens", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "POST /scripts/7/restore": [200, {}] }));
  open();
  expect(await screen.findByText("Deleted · 2 days ago")).toBeInTheDocument();
  expect(screen.getByText(/^Removed for good on \d+ Nov$/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Deleted and archived" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.queryByRole("link", { name: "Bo tries salmon" })).toBeNull();
  expect(screen.queryByRole("button", { name: /^More for / })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Restore Bo tries salmon" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/restore")).toBe(true));
  expect(await screen.findByText('Restored "Bo tries salmon".')).toBeInTheDocument();
});

test("a removed script that kept its videos reads Archived, and an empty view says so with a way back", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts": [200, [row({ removed_at: null, purge_on: null })]] }));
  open();
  expect(await screen.findByText("Archived")).toBeInTheDocument();
  expect(screen.getByText("Its videos are kept")).toBeInTheDocument();
});

test("nothing removed says so and Show all scripts turns the filter off", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts": [200, []] }));
  open();
  expect(await screen.findByText("Nothing deleted or archived.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Show all scripts" }));
  expect(screen.getByRole("button", { name: "Deleted and archived" })).toHaveAttribute("aria-pressed", "false");
});

test("on a phone the filter is in the Filters sheet", async () => {
  setViewport(390);
  fakeServer(base({ "GET /scripts": [200, []] }));
  open("/b/1/scripts");
  await userEvent.click(await screen.findByRole("button", { name: "Filters" }));
  expect(await screen.findByRole("button", { name: "Deleted and archived" })).toBeInTheDocument();
});
