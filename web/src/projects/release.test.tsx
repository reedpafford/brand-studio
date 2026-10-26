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
  id: 9, brand_id: 1, name: "Bo tries salmon — B", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "", cast_ids: [], reference_file_id: null,
  estimate_credits: 30, budget_credits: 60, credits_used: 84, budget_pct: 40, created_by_id: 2, created_by_name: "Sam", script_draft_id: 5, ...o,
});
const base = (o: Record<string, [number, unknown]> = {}): Record<string, [number, unknown]> => ({
  "GET /auth/me": [200, owner],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /projects/9": [200, project()],
  "GET /projects/9/script": [200, { version: 1, source: "paste", words: 3, created_by_id: 1, created_at: "2026-10-23T10:00:00Z", text: "BO: Salmon?" }],
  "GET /projects/9/script/suggestions": [200, []],
  "GET /projects/9/script/notes": [200, []],
  "GET /projects/9/breakdown": [404, { detail: "none" }],
  "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 6 }]],
  "GET /jobs": [200, []],
  "GET /scripts": [200, []],
  "GET /projects": [200, []],
  ...o,
});
function open() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/b/1/projects/9"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
afterEach(() => vi.unstubAllGlobals());

test("Release this version asks first, says what stays used, goes back to Scripts, and Undo brings the video back", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "POST /projects/9/release": [200, {}], "POST /projects/9/restore": [200, {}] }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "More for Bo tries salmon — B" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Release this version" }));
  const dialog = await screen.findByRole("alertdialog", { name: "Release this version?" });
  expect(dialog).toHaveTextContent("It goes back to Ready to make, so it can be started fresh. This video and its clips are archived, not deleted. The 84 credits already used stay used.");
  expect(calls.some((c) => c.key === "POST /projects/9/release")).toBe(false);
  await userEvent.click(within(dialog).getByRole("button", { name: "Release" }));
  expect(await screen.findByText("The version is ready to make again.")).toBeInTheDocument();
  expect(await screen.findByRole("heading", { name: "Scripts", level: 1 })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/restore")).toBe(true));
});

test("when nothing was spent the release text leaves the credits sentence out, and a version video offers Release only, not Archive", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /projects/9": [200, project({ credits_used: 0 })] }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "More for Bo tries salmon — B" }));
  expect(screen.queryByRole("menuitem", { name: "Archive video" })).toBeNull();
  await userEvent.click(screen.getByRole("menuitem", { name: "Release this version" }));
  const release = await screen.findByRole("alertdialog");
  expect(release).not.toHaveTextContent("credits already used");
});

test("a video made before scripts offers Archive video, with its own wording, and no Release", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /projects/9": [200, project({ script_draft_id: null })], "POST /projects/9/archive": [200, {}] }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "More for Bo tries salmon — B" }));
  expect(screen.queryByRole("menuitem", { name: "Release this version" })).toBeNull();
  await userEvent.click(screen.getByRole("menuitem", { name: "Archive video" }));
  const archive = await screen.findByRole("alertdialog", { name: 'Archive "Bo tries salmon — B"?' });
  expect(archive).toHaveTextContent("It leaves the lists. Its clips and downloads are kept, and you can restore it.");
});

test("an editor sees no menu on a video they didn't make, and a refused release keeps the dialog with the reason", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /auth/me": [200, { ...owner, id: 3, role: "editor" }] }));
  open();
  await screen.findByRole("heading", { name: "Bo tries salmon — B", level: 1 });
  expect(screen.queryByRole("button", { name: /^More for / })).toBeNull();
});

test("a refused release says so and nothing changed", async () => {
  setViewport(1440);
  fakeServer(base({ "POST /projects/9/release": [409, { detail: "This video is done, so it can't be released." }] }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "More for Bo tries salmon — B" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Release this version" }));
  await userEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Release" }));
  expect(await screen.findByText(/Nothing changed\. This video is done, so it can't be released\./)).toBeInTheDocument();
});
