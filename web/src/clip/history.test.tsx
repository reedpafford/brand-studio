import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const editor = { id: 2, email: "e@b.co", name: "Eli", role: "editor", workspace_id: 1 };
const seedance = { id: "seedance-2.5", name: "Seedance 2.5", kind: "video", default: true, duration: { min: 4, max: 30 }, resolutions: ["480p"], aspect_ratios: ["9:16"], max_reference_images: 4, credits_per_unit: { "480p": 1 } };
const job = (o: object = {}) => ({ id: 12, kind: "video", status: "succeeded", project_id: null, credits: 9, prompt_summary: "Bo noses the salmon", created_at: "2026-10-25T10:00:00Z", output: { file_ids: [5] }, duration: 8, aspect_ratio: "9:16", resolution: "480p", created_by_id: 2, created_by_name: "Eli", error: "", ...o });
const base = (o: Record<string, [number, unknown]> = {}): Record<string, [number, unknown]> => ({
  "GET /auth/me": [200, editor],
  "GET /brands": [200, [{ id: 1, name: "fomo", colours: [] }]],
  "GET /models": [200, [seedance]],
  "GET /library/character": [200, []],
  "GET /library/place": [200, []],
  "GET /library/prop": [200, []],
  "GET /brands/1/screens": [200, []],
  "GET /credits/me": [200, { quick_clip_credits_used: 10, quick_clip_credits_allowed: 150 }],
  "GET /jobs": [200, [job()]],
  "POST /clips/estimate": [200, { credits: 9, needs_owner_approval: false, reason: "", auto_screen_ids: [], reference_images: 0, reference_videos: 0, reference_audios: 0 }],
  ...o,
});
function open(path = "/b/1/clip") {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
afterEach(() => vi.unstubAllGlobals());

test("a finished clip can be removed from history at once, with the words that credits stay used, and Undo brings it back", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "DELETE /jobs/12": [204, null], "POST /jobs/12/restore": [200, {}] }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "More for clip 12" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Remove from history" }));
  expect(await screen.findByText("Removed from your history. Its credits stay used.")).toBeInTheDocument();
  expect(screen.queryByRole("alertdialog")).toBeNull();
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /jobs/12")).toBe(true));
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /jobs/12/restore")).toBe(true));
  expect(await screen.findByText("Clip back in your history.")).toBeInTheDocument();
});

test("a clip removed in this visit shows under Removed straight away, without a reload", async () => {
  setViewport(1440);
  fakeServer(base({ "DELETE /jobs/12": [204, null], "GET /jobs?removed=true": [200, [job()]] }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "More for clip 12" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Remove from history" }));
  await screen.findByText("Removed from your history. Its credits stay used.");
  await userEvent.selectOptions(screen.getByLabelText("Show"), "removed");
  expect(await screen.findByRole("button", { name: "Restore clip 12" })).toBeInTheDocument();
});

test("a clip still being made has no remove item, and someone else's clip has no menu for an editor", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /jobs": [200, [job({ id: 13, status: "running" }), job({ id: 14, created_by_id: 9, created_by_name: "Sam" })]] }));
  open();
  await screen.findAllByText("Bo noses the salmon");
  expect(screen.queryByRole("button", { name: "More for clip 13" })).toBeNull();
  expect(screen.queryByRole("button", { name: "More for clip 14" })).toBeNull();
});

test("a refused remove says why in a toast and the clip stays", async () => {
  setViewport(1440);
  fakeServer(base({ "DELETE /jobs/12": [409, { detail: "Wait for it to finish first." }] }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "More for clip 12" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Remove from history" }));
  expect(await screen.findByText("Wait for it to finish first.")).toBeInTheDocument();
  expect(await screen.findByRole("button", { name: "More for clip 12" })).toBeInTheDocument();
});

test("search goes to the server after typing stops and lives in the address; no match says so with Clear search", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /jobs?q=salmon": [200, []] }));
  open();
  await userEvent.type(await screen.findByRole("searchbox", { name: "Search your clips" }), "salmon");
  expect(await screen.findByText('No clips match "salmon".')).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Clear search" }));
  expect(await screen.findAllByText("Bo noses the salmon")).not.toHaveLength(0);
});

test("the Removed filter lists removed clips, muted, each with Restore", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "GET /jobs?removed=true": [200, [job({ id: 20, prompt_summary: "Old clip" })]], "POST /jobs/20/restore": [200, {}] }));
  open();
  await userEvent.selectOptions(await screen.findByLabelText("Show"), "removed");
  expect(await screen.findByText("Old clip")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "More for clip 20" })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Restore clip 20" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /jobs/20/restore")).toBe(true));
  expect(await screen.findByText("Clip back in your history.")).toBeInTheDocument();
});

test("a clip held from before the allowance change reads Not started, with Cancel and nothing about Reed", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /jobs": [200, [job({ id: 30, status: "needs_owner_approval" })]] }));
  open();
  expect(await screen.findByText("Not started")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Cancel clip 30" })).toBeInTheDocument();
  expect(screen.queryByText(/Reed/)).toBeNull();
});

test("the allowance line reads This week: used of allowed credits", async () => {
  setViewport(1440);
  fakeServer(base());
  open();
  expect(await screen.findByText("This week: 10 of 150 credits")).toBeInTheDocument();
});
