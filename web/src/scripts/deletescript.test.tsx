import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";
import { owner } from "../test/people";

const editor = { ...owner, id: 2, name: "Sam", role: "editor" };
const v = (slot: number, o: object = {}) => ({ slot, status: "draft", title: "x", seconds: 0, project_id: null, text: "", words: 0, target_seconds: null, premise: "", changes: [], problems: [], has_breakdown: false, approved_at: null, ...o });
const script = (o: object = {}) => ({
  id: 7, brand_id: 1, title: "Bo tries salmon", description: "Show a picky dog.", reference_id: null, reel_imported: false, running: false, new_lines: false, published: false, status: "draft", created_by_id: 2, created_by_name: "Sam", created_at: "2026-10-24T10:00:00Z", versions_left: 0,
  notes: "", reference_replace: "", cast: [], versions: [v(0)], ...o,
});
const base = (o: Record<string, [number, unknown]> = {}): Record<string, [number, unknown]> => ({
  "GET /auth/me": [200, owner],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /references": [200, []],
  "GET /projects": [200, []],
  "GET /jobs": [200, []],
  ...o,
});
function open(path: string) {
  renderApp(path);
}
afterEach(() => vi.unstubAllGlobals());

const rows = [script({ id: 1, title: "Mine", created_by_id: 2 }), script({ id: 2, title: "Reeds", created_by_id: 1 }), script({ id: 3, title: "Published", created_by_id: 2, published: true, status: "published" })];

test("an editor can delete only their own unpublished drafts; other rows get no menu at all", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /auth/me": [200, editor], "GET /scripts": [200, rows] }));
  open("/b/1/scripts?status=any");
  await screen.findAllByRole("heading", { name: "Published" });
  expect(screen.getAllByRole("button", { name: "More for Mine" }).length).toBeGreaterThan(0);
  expect(screen.queryByRole("button", { name: "More for Reeds" })).toBeNull();
  expect(screen.queryByRole("button", { name: "More for Published" })).toBeNull();
});

test("Reed can delete any script", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts": [200, rows] }));
  open("/b/1/scripts?status=any");
  expect(await screen.findAllByRole("button", { name: /^More for / })).toHaveLength(3);
});

test("Delete asks first with its own wording, deletes, then Undo restores it", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "GET /scripts": [200, [script()]], "DELETE /scripts/7": [204, null], "POST /scripts/7/restore": [200, {}] }));
  open("/b/1/scripts?status=any");
  await userEvent.click(await screen.findByRole("button", { name: "More for Bo tries salmon" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Delete script" }));
  const dialog = await screen.findByRole("alertdialog", { name: 'Delete "Bo tries salmon"?' });
  expect(dialog).toHaveTextContent("Its versions and cast go too.");
  expect(calls.some((c) => c.key === "DELETE /scripts/7")).toBe(false);
  await userEvent.click(within(dialog).getByRole("button", { name: "Delete" }));
  expect(await screen.findByText('Deleted "Bo tries salmon".')).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/restore")).toBe(true));
  expect(await screen.findByText('Restored "Bo tries salmon".')).toBeInTheDocument();
});

test("a script with a video made from it says it will be archived and the videos kept", async () => {
  setViewport(1440);
  const made = script({ published: true, status: "published", versions: [v(0, { status: "done", project_id: 5 })] });
  fakeServer(base({ "GET /scripts": [200, [made]], "DELETE /scripts/7": [204, null] }));
  open("/b/1/scripts?status=any");
  await userEvent.click(await screen.findByRole("button", { name: "More for Bo tries salmon" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Delete script" }));
  const dialog = await screen.findByRole("alertdialog", { name: 'Archive "Bo tries salmon"?' });
  expect(dialog).toHaveTextContent("The videos made from it stay, with their clips and downloads.");
  await userEvent.click(within(dialog).getByRole("button", { name: "Archive" }));
  expect(await screen.findByText('Archived "Bo tries salmon".')).toBeInTheDocument();
});

test("from the script's own page, Delete script goes back to Scripts", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "GET /scripts/7": [200, script({ created_by_id: 1 })], "GET /scripts": [200, []], "DELETE /scripts/7": [204, null] }));
  open("/b/1/scripts/7");
  await userEvent.click(await screen.findByRole("button", { name: "More for Bo tries salmon" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Delete script" }));
  await userEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Delete" }));
  expect(await screen.findByRole("heading", { name: "Scripts", level: 1 })).toBeInTheDocument();
  expect(calls.some((c) => c.key === "DELETE /scripts/7")).toBe(true);
});

test("a refused delete keeps the dialog open and says nothing changed", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts/7": [200, script({ created_by_id: 1 })], "DELETE /scripts/7": [403, { detail: "Only its author can remove it." }] }));
  open("/b/1/scripts/7");
  await userEvent.click(await screen.findByRole("button", { name: "More for Bo tries salmon" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Delete script" }));
  await userEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Delete" }));
  expect(await screen.findByText(/Nothing changed\. Only its author can remove it\./)).toBeInTheDocument();
});

test("Delete and Archive say anything still being made for the script stops, only when the script says it is running", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts": [200, [script({ running: true })]] }));
  open("/b/1/scripts?status=any");
  await userEvent.click(await screen.findByRole("button", { name: "More for Bo tries salmon" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Delete script" }));
  const dialog = await screen.findByRole("alertdialog", { name: 'Delete "Bo tries salmon"?' });
  expect(dialog).toHaveTextContent("Its versions and cast go too. Anything still being made for this script stops and isn't brought back.");
});

test("the Archive confirm says it too, and it shows for work by someone else (Reed deleting an editor's script)", async () => {
  setViewport(1440);
  const made = script({ running: true, created_by_id: 2, versions: [v(0, { project_id: 5 })] });
  fakeServer(base({ "GET /scripts": [200, [made]], "GET /jobs": [200, []] })); // the jobs list is empty: it only lists the signed-in person's own
  open("/b/1/scripts?status=any");
  await userEvent.click(await screen.findByRole("button", { name: "More for Bo tries salmon" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Delete script" }));
  const dialog = await screen.findByRole("alertdialog", { name: 'Archive "Bo tries salmon"?' });
  expect(dialog).toHaveTextContent("Anything still being made for this script stops and isn't brought back.");
});

test("with nothing running for the script, the line is left out", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts": [200, [script({ running: false })]] }));
  open("/b/1/scripts?status=any");
  await userEvent.click(await screen.findByRole("button", { name: "More for Bo tries salmon" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Delete script" }));
  const dialog = await screen.findByRole("alertdialog", { name: 'Delete "Bo tries salmon"?' });
  expect(dialog).not.toHaveTextContent("Anything still being made");
});
