import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";
import { owner } from "../test/people";

const brands = [{ id: 1, name: "fomo", colours: [] }, { id: 2, name: "Iron Paws", colours: [] }];
const kit = { id: 1, name: "fomo", colours: [], fonts: [], tone_notes: "", never_say: [], legal_line: "", end_line: "" };
const base = (o: Record<string, [number, unknown]> = {}): Record<string, [number, unknown]> => ({
  "GET /auth/me": [200, owner],
  "GET /brands": [200, brands],
  "GET /brands/1": [200, kit],
  "GET /brands/2": [200, { ...kit, id: 2, name: "Iron Paws" }],
  "GET /brands/1/screens": [200, []],
  "GET /brands/2/screens": [200, []],
  "GET /scripts": [200, []],
  "GET /projects": [200, []],
  ...o,
});
function open(path: string) {
  renderApp(path);
}
afterEach(() => vi.unstubAllGlobals());

test("Archive brand asks first, moves to the other brand, and Undo brings the brand back", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "DELETE /brands/1": [204, null], "POST /brands/1/restore": [200, {}] }));
  open("/b/1/brand");
  await userEvent.click(await screen.findByRole("button", { name: "More for fomo" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Archive brand" }));
  const dialog = await screen.findByRole("alertdialog", { name: "Archive fomo?" });
  expect(dialog).toHaveTextContent("It leaves the brand menu. Its scripts, videos and screens are kept, and you can bring it back from Usage.");
  expect(calls.some((c) => c.key === "DELETE /brands/1")).toBe(false);
  await userEvent.click(within(dialog).getByRole("button", { name: "Archive" }));
  expect(await screen.findByText("Archived fomo.")).toBeInTheDocument();
  expect(await screen.findByRole("heading", { name: "Scripts", level: 1 })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /brands/1/restore")).toBe(true));
});

test("an editor sees no Archive brand menu", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /auth/me": [200, { ...owner, id: 2, role: "editor" }] }));
  open("/b/1/brand");
  await screen.findByRole("heading", { name: "Brand", level: 1 });
  expect(screen.queryByRole("button", { name: "More for fomo" })).toBeNull();
});

test("Usage → Show archived has Restore on an archived brand's row", async () => {
  setViewport(1440);
  const row = { brand_id: 3, name: "Night Owl", colour: null, archived: true, spend_usd: 0, spend_estimated: false, finished: 0, cost_per_finished_usd: null, in_progress: 0, scripts: 2, versions_left: 0, last_activity_at: null };
  const calls = fakeServer(base({
    "GET /usage/summary": [200, { period: "week", starts_at: "2026-10-19T00:00:00Z", previous: null, spend_usd: 0, spend_estimated: false, finished: 0, cost_per_finished_usd: null, in_progress: 0, unassigned_spend_usd: 0 }],
    "GET /usage/brands": [200, { total: 1, next_cursor: null, items: [row] }],
    "GET /usage/charges": [200, { total: 0, next_cursor: null, items: [] }],
    "POST /brands/3/restore": [200, {}],
  }));
  open("/usage?archived=1");
  await userEvent.click(await screen.findByRole("button", { name: "Restore Night Owl" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /brands/3/restore")).toBe(true));
  expect(await screen.findByText("Brought back Night Owl.")).toBeInTheDocument();
});
