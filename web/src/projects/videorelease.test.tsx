import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const owner = { id: 1, email: "reed@b.co", name: "Reed", role: "owner", workspace_id: 1 };
const project = (o: object = {}) => ({
  id: 9, brand_id: 1, name: "Bo tries salmon · B", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "", cast_ids: [], reference_file_id: null,
  estimate_credits: 30, budget_credits: 600, credits_used: 84, budget_pct: 14, product_variants: {}, created_by_id: 2, script_draft_id: 5, ...o,
});
const base = (o: Record<string, [number, unknown]> = {}): Record<string, [number, unknown]> => ({
  "GET /auth/me": [200, owner],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /projects/9": [200, project()],
  "GET /projects/9/script": [200, { version: 5, source: "paste", words: 9, created_by_id: 2, created_at: "2026-10-23T10:00:00Z", text: "Bo eats." }],
  "GET /projects/9/breakdown": [404, { detail: "none" }],
  "GET /projects/9/storyboard": [200, []],
  "GET /projects/9/clips": [200, []],
  "GET /projects/9/video": [404, { detail: "none" }],
  "GET /projects/9/assets": [200, []],
  "GET /library/character": [200, []],
  "GET /brands/1/screens": [200, []],
  "GET /credits/rates": [200, []],
  "GET /jobs": [200, []],
  "GET /scripts": [200, []],
  "GET /projects": [200, []],
  ...o,
});
function open() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/b/1/videos/9"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
afterEach(() => vi.unstubAllGlobals());

test("on the video page a version in production offers Release only; Release asks, goes back to Scripts and Undo restores", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "POST /projects/9/release": [200, {}], "POST /projects/9/restore": [200, {}] }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "More for Bo tries salmon · B" }));
  expect(screen.queryByRole("menuitem", { name: "Archive video" })).toBeNull();
  await userEvent.click(screen.getByRole("menuitem", { name: "Release this version" }));
  const dialog = await screen.findByRole("alertdialog", { name: "Release this version?" });
  expect(dialog).toHaveTextContent("The 84 credits already used stay used.");
  await userEvent.click(within(dialog).getByRole("button", { name: "Release" }));
  expect(await screen.findByText("The version is ready to make again.")).toBeInTheDocument();
  expect(await screen.findByRole("heading", { name: "Scripts", level: 1 })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/restore")).toBe(true));
});

test("once the video is done the menu offers Archive video, not Release", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /projects/9/video": [200, { file_id: 90, take_ids: [4], out_of_date: false }] }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "More for Bo tries salmon · B" }));
  expect(screen.queryByRole("menuitem", { name: "Release this version" })).toBeNull();
  expect(screen.getByRole("menuitem", { name: "Archive video" })).toBeInTheDocument();
});

test("an archived video says so with Restore, and has no menu; an editor who didn't make it sees no menu at all", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "GET /projects/9": [200, project({ archived_at: "2026-10-25T10:00:00Z" })], "POST /projects/9/restore": [200, {}] }));
  open();
  expect(await screen.findByText("It's out of the lists. Its clips and downloads are kept. Restore it to keep working.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^More for / })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Restore" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/restore")).toBe(true));
});

test("an editor who didn't make the video sees no menu", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /auth/me": [200, { ...owner, id: 3, role: "editor" }] }));
  open();
  await screen.findByRole("heading", { name: "Bo tries salmon · B", level: 1 });
  expect(screen.queryByRole("button", { name: /^More for / })).toBeNull();
});
