import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { owner, editor } from "../test/people";

const november = { id: 4, brand_id: 1, name: "November launch", created_by_id: 1, items: { scripts: 2, videos: 3, clips: 1 }, can_manage: true };
const video = {
  id: 9, brand_id: 1, name: "Bo tries salmon · B", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "", cast_ids: [], reference_file_id: null,
  estimate_credits: 30, budget_credits: 600, credits_used: 0, budget_pct: 0, created_by_id: 1, created_by_name: "Reed", script_draft_id: 4, own_script: false, archived_at: null, finished_at: null, product_variants: {}, folder_id: null,
};
const base = (me: object, folders: object[] | null, extra: Record<string, [number, unknown]> = {}): Record<string, [number, unknown]> => ({
  "GET /auth/me": [200, me],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /references": [200, []],
  "GET /scripts": [200, []],
  "GET /projects": [200, [video]],
  "GET /jobs": [200, []],
  ...(folders ? { "GET /brands/1/folders": [200, folders] as [number, unknown] } : {}),
  ...extra,
});
function Where() {
  const l = useLocation();
  return <span data-testid="where" hidden>{l.pathname + l.search}</span>;
}
const where = () => screen.getByTestId("where").textContent;
function open(at = "/b/1/scripts") { // the Videos page is a folder now (v6 S1); Scripts keeps Project ▾
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[at]}>
        <App />
        <Where />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
const urls = () => (fetch as unknown as { mock: { calls: [Request | string][] } }).mock.calls.map(([r]) => (typeof r === "string" ? r : r.url));
afterEach(() => vi.unstubAllGlobals());
// The rail has no Projects list any more (nav A): the list opens from "Project: All ▾" at every width.
async function openList() {
  await userEvent.click(await screen.findByRole("button", { name: /^Project: / }));
  return screen.findByRole("region", { name: "Projects" });
}

test("Project: All ▾ opens the list: All, each project with its count, and No project; picking one filters the list it's on (flows OR1)", async () => {
  setViewport(1440);
  fakeServer(base(owner, [november]));
  open();
  const list = await openList();
  expect(within(list).getByRole("button", { name: "All" })).toBeInTheDocument();
  expect(within(list).getByRole("button", { name: "November launch · 6 items" })).toBeInTheDocument();
  expect(within(list).getByRole("button", { name: "No project" })).toBeInTheDocument();
  await userEvent.click(within(list).getByRole("button", { name: "November launch · 6 items" }));
  expect(where()).toBe("/b/1/scripts?folder=4");
  await vi.waitFor(() => expect(urls().some((u) => u.includes("/scripts?") && u.includes("folder=4"))).toBe(true));
  await userEvent.click(within(await openList()).getByRole("button", { name: "No project" })); // picking closes the panel
  expect(where()).toBe("/b/1/scripts?folder=none");
  expect(document.body.textContent!.replace(where()!, "")).not.toMatch(/folder/i); // people only ever see "Project"
});

test("with no projects yet it says everything works without one, and New project makes one; a name in use says so", async () => {
  setViewport(1440);
  const calls = fakeServer(base(owner, [], { "POST /brands/1/folders": [409, { detail: "A project called November launch already exists. Rename one first." }] }));
  open();
  const list = await openList();
  expect(within(list).getByText("No projects yet. Everything works without one.")).toBeInTheDocument();
  await userEvent.click(within(list).getByRole("button", { name: "New project" }));
  const ask = await screen.findByRole("alertdialog", { name: "New project" });
  await userEvent.type(within(ask).getByLabelText("Name"), "November launch");
  await userEvent.click(within(ask).getByRole("button", { name: "Make the project" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /brands/1/folders")?.body).toEqual({ name: "November launch" }));
  expect(await within(ask).findByText("A project called November launch already exists. Rename one first.")).toBeInTheDocument();
  expect(within(ask).getByRole("button", { name: "Make the project" })).toBeDisabled();
});

test("Delete says where its items go, nothing inside is deleted, and Undo restores it", async () => {
  setViewport(1440);
  const calls = fakeServer(base(owner, [november], { "DELETE /folders/4": [200, { moved: 6 }], "POST /folders/4/restore": [200, november] }));
  open();
  await openList();
  await userEvent.click(await screen.findByRole("button", { name: "More for November launch" }));
  await userEvent.click(await screen.findByRole("menuitem", { name: "Delete" }));
  const ask = await screen.findByRole("alertdialog", { name: "Delete November launch?" });
  expect(ask).toHaveTextContent("Its 6 items move to No project. Nothing inside is deleted.");
  await userEvent.click(within(ask).getByRole("button", { name: "Delete" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /folders/4")).toBe(true));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /folders/4/restore")).toBe(true));
});

test("on a phone the list opens from Project: All ▾ in a sheet", async () => {
  setViewport(390);
  fakeServer(base(owner, [november]));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Project: All" }));
  const sheet = await screen.findByRole("dialog", { name: "Projects" });
  await userEvent.click(within(sheet).getByRole("button", { name: "November launch · 6 items" }));
  expect(where()).toBe("/b/1/scripts?folder=4");
  expect(await screen.findByRole("button", { name: "Project: November launch" })).toBeInTheDocument();
});

test("without the server's projects nothing about projects shows", async () => {
  setViewport(1440);
  fakeServer(base(owner, null));
  open();
  await screen.findByRole("heading", { name: "Scripts" });
  expect(screen.queryByRole("button", { name: /^Project: / })).toBeNull();
});

test("Scripts ask the server for the picked project too", async () => {
  setViewport(1440);
  fakeServer(base(owner, [november]));
  open("/b/1/scripts?folder=4");
  await screen.findByRole("heading", { name: "Scripts" });
  await vi.waitFor(() => expect(urls().some((u) => u.includes("/scripts?") && u.includes("folder=4"))).toBe(true));
});

const script = (o: object = {}) => ({
  id: 7, brand_id: 1, kind: "story", format: "dialogue", title: "Bowl story", description: "", reference_id: null, published: true, status: "published", created_by_id: 1, created_by_name: "Reed", created_at: "2026-10-28T10:00:00Z", versions_left: 0,
  notes: "", reference_replace: "", cast: [], look: "house", folder_id: null, ...o,
  versions: [{ slot: 0, status: "draft", title: "Bowl story", seconds: 0, project_id: null, text: "Bo eats.", words: 2, target_seconds: null, premise: "", changes: [], problems: [], has_breakdown: false, approved_at: null, style_line: "", singer: "", spoken_end_line: "", song_directions: [] }],
});

test("an editor gets no project picker on a script someone else made (the server would refuse it)", async () => {
  setViewport(1440);
  fakeServer(base(editor, [november], { "GET /scripts/7": [200, script()] }));
  open("/b/1/scripts/7");
  expect(await screen.findByRole("navigation", { name: "Breadcrumb" })).toHaveTextContent("Bowl story");
  await new Promise((r) => setTimeout(r, 200)); // let the projects load (the next test shows the picker does appear on your own script)
  expect(screen.queryByRole("button", { name: /^Project:/ })).toBeNull();
});

test("an editor gets the project picker on their own script", async () => {
  setViewport(1440);
  fakeServer(base(editor, [november], { "GET /scripts/7": [200, script({ created_by_id: 2, published: false, status: "draft" })] }));
  open("/b/1/scripts/7?step=script");
  expect(await screen.findByRole("button", { name: "Project: none" })).toBeInTheDocument();
});
