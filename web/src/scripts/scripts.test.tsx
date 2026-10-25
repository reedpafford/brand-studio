import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const owner = { id: 1, email: "reed@b.co", name: "Reed", role: "owner", workspace_id: 1 };
const editor = { id: 2, email: "sam@b.co", name: "Sam", role: "editor", workspace_id: 1 };
const brands = [{ id: 1, name: "Iron Paws", colours: [] }, { id: 2, name: "fomo", colours: [] }];
const v = (slot: number, status: string, o: object = {}) => ({ slot, status, title: "Bo tries salmon", seconds: 0, project_id: null, ...o });
const script = (o: object = {}) => ({
  id: 7, brand_id: 1, title: "Bo tries salmon", description: "Show a picky dog finally loving Iron Paws salmon.", reference_id: "altar", published: true, status: "published",
  created_by_id: 1, created_by_name: "Reed", created_at: "2026-10-24T10:00:00Z", versions_left: 2, versions: [v(0, "done", { seconds: 24, project_id: 5 }), v(1, "approved", { seconds: 30 }), v(2, "in_production")], ...o,
});
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, owner],
  "GET /brands": [200, brands],
  "GET /references": [200, [{ id: "altar", name: "The altar reel", logline: "", seconds: 45, style: "", brand: "", has_thumbnail: false }]],
  "GET /projects": [200, []],
};

function open(path = "/b/1/scripts") {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

test("a script is one row: its title, description, reference, length range and a chip for every version in words", async () => {
  fakeServer({ ...base, "GET /scripts": [200, [script()]] });
  open();
  expect(await screen.findByRole("heading", { name: "Bo tries salmon" })).toBeInTheDocument();
  expect(screen.getByText("Show a picky dog finally loving Iron Paws salmon.")).toBeInTheDocument();
  expect(screen.getByText(/Ref: The altar reel · 24–30 s · 2 versions left to make/)).toBeInTheDocument();
  expect(screen.getByText("A · Video done")).toBeInTheDocument();
  expect(screen.getByText("B · Ready to make")).toBeInTheDocument();
  expect(screen.getByText("C · In production")).toBeInTheDocument();
  expect(screen.getByLabelText("Version A, video done").closest("a")).toHaveAttribute("href", "/b/1/projects/5");
  expect(screen.getByText("1 script")).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/\bv\d\b|project/i);
});

test("an editor starts on Ready to make, and Reed on everything; the brand home is the library", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /auth/me": [200, editor], "GET /scripts": [200, []] });
  open("/b/1");
  await screen.findByRole("heading", { name: "Scripts" });
  await vi.waitFor(() => expect(calls.some((c) => c.key === "GET /scripts")).toBe(true));
  expect(screen.getByLabelText("Status")).toHaveValue("published");
  expect(await screen.findByText("No scripts ready to make yet.")).toBeInTheDocument();
});

test("filters and search are sent to the server and live in the address; Clear filters resets them", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts": [200, []] });
  open("/b/1/scripts?status=in_production&len=15-30");
  await screen.findByRole("heading", { name: "Scripts" });
  await vi.waitFor(() => expect(calls.some((c) => c.key === "GET /scripts")).toBe(true));
  expect(screen.getByLabelText("Status")).toHaveValue("in_production");
  expect(screen.getByLabelText("Length")).toHaveValue("15-30");
  expect(await screen.findByText("Nothing matches these filters.")).toBeInTheDocument();
  await userEvent.click(screen.getAllByRole("button", { name: "Clear filters" })[0]);
  expect(screen.getByLabelText("Status")).toHaveValue("");
  expect(await screen.findByText("No scripts for Iron Paws yet.")).toBeInTheDocument();
});

test("search waits for typing to stop, then asks the server", async () => {
  const calls = fakeServer({ ...base, "GET /scripts": [200, [script()]] });
  open();
  await userEvent.type(await screen.findByRole("searchbox"), "salmon");
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "GET /scripts").length).toBeGreaterThan(1));
});

test("a failed load says so with Try again", async () => {
  fakeServer({ ...base, "GET /scripts": [500, { detail: "boom" }] });
  open();
  expect(await screen.findByText("Couldn't load your scripts.", {}, { timeout: 10_000 })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
}, 20_000);

test("videos made before scripts stay reachable under a closed disclosure", async () => {
  const old = { id: 9, brand_id: 1, name: "Old reel", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "", cast_ids: [], reference_file_id: null, estimate_credits: 30, budget_credits: 60, credits_used: 5, budget_pct: 8 };
  fakeServer({ ...base, "GET /scripts": [200, []], "GET /projects": [200, [old]] });
  open();
  const section = await screen.findByRole("region", { name: "Videos made before scripts" });
  expect(await within(section).findByText("Videos made before scripts (1)")).toBeInTheDocument();
  expect(within(section).getByRole("link", { name: "New video (the earlier way)" })).toHaveAttribute("href", "/b/1/projects/new");
});

test("on a phone the filters sit behind one Filters button that opens a sheet, and says how many are on", async () => {
  fakeServer({ ...base, "GET /scripts": [200, []] });
  open("/b/1/scripts?status=done");
  const button = await screen.findByRole("button", { name: "Filters (1)" });
  await userEvent.click(button);
  const sheet = await screen.findByRole("dialog", { name: "Filters" });
  expect(within(sheet).getByLabelText("Status")).toHaveValue("done");
});

const full = (o: object = {}) => ({
  id: 7, brand_id: 1, title: "Bo tries salmon", description: "Show a picky dog.", reference_id: null, published: false, status: "draft", created_by_id: 1, created_by_name: "Reed", created_at: "2026-10-24T10:00:00Z", versions_left: 0,
  notes: "Keep it warm.", reference_replace: "", cast: [], versions: [{ slot: 0, status: "draft", title: "Bo tries salmon", seconds: 0, project_id: null, text: "", words: 0, target_seconds: null, premise: "", changes: [], problems: [], has_breakdown: false, approved_at: null }], ...o,
});

test("New script asks for a title and what it's for, then makes the draft and opens the script step", async () => {
  const calls = fakeServer({ ...base, "GET /scripts": [200, []], "POST /scripts": [201, full()], "GET /scripts/7": [200, full()] });
  open("/b/1/scripts/new");
  const button = await screen.findByRole("button", { name: "Create script" });
  expect(button).toBeDisabled();
  expect(button).toHaveAccessibleDescription("Add a title first");
  await userEvent.type(screen.getByLabelText("Title"), "Bo tries salmon");
  expect(screen.getByRole("button", { name: "Create script" })).toHaveAccessibleDescription("Say what it's for first");
  await userEvent.type(screen.getByLabelText("What it's for"), "Show a picky dog.");
  await userEvent.click(screen.getByRole("button", { name: "Create script" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts")?.body).toMatchObject({ brand_id: 1, title: "Bo tries salmon", description: "Show a picky dog.", text: "" }));
  expect(await screen.findByRole("heading", { name: "Script", level: 2 })).toBeInTheDocument();
});

test("a draft script's page: title, a draft badge, seven steps with the unbuilt ones locked, and the description to read or edit", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, full()], "PATCH /scripts/7": [200, full({ title: "Bo tries tuna" })] });
  open("/b/1/scripts/7");
  expect(await screen.findByRole("heading", { level: 1, name: /Bo tries salmon/ })).toBeInTheDocument();
  expect(screen.getByText("Draft · only you can see it")).toBeInTheDocument();
  const steps = screen.getByRole("list", { name: "Steps" });
  expect(within(steps).getAllByRole("button").map((b) => b.textContent?.replace(/^\d+/, ""))).toEqual(["Description", "Script", "Directions", "Variations", "Characters", "Breakdown", "Publish"]);
  expect(within(steps).getByRole("button", { name: "Variations" })).toHaveAccessibleDescription("Coming soon");
  expect(screen.getByText("Keep it warm.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Edit description" }));
  await userEvent.clear(screen.getByLabelText("Title"));
  await userEvent.type(screen.getByLabelText("Title"), "Bo tries tuna");
  await userEvent.click(screen.getByRole("button", { name: "Save description" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /scripts/7")?.body).toMatchObject({ title: "Bo tries tuna", description: "Show a picky dog." }));
});

test("the script step saves the words as the original; Next needs them", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, full()], "PUT /scripts/7/drafts/0": [200, full()] });
  open("/b/1/scripts/7?step=script");
  const next = await screen.findByRole("button", { name: "Next: Directions" });
  expect(next).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Your script"), "BO: Salmon?");
  await userEvent.click(screen.getByRole("button", { name: "Save script" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /scripts/7/drafts/0")?.body).toEqual({ text: "BO: Salmon?" }));
});

test("a published script is final: a lock badge, and no rename or edit buttons", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, full({ published: true, status: "published" })] });
  open("/b/1/scripts/7");
  expect(await screen.findByText("Published · final")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Rename" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Edit description" })).not.toBeInTheDocument();
});

test("the library has a New script button, and a draft's title opens its page", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts": [200, [script({ id: 7, published: false, status: "draft", versions: [v(0, "draft")] })]] });
  open();
  expect(await screen.findByRole("link", { name: "New script" })).toHaveAttribute("href", "/b/1/scripts/new");
  expect(await screen.findByRole("link", { name: "Bo tries salmon" })).toHaveAttribute("href", "/b/1/scripts/7");
});
