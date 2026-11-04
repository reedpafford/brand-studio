import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { editor, owner } from "../test/people";
import { IDEA } from "./FolderTree";

const status = (kind: string, words: string) => ({ kind, words, reason: null, at: null, made: 0, total: 0 });
const dot = (id: number, title: string, kind = "working", words = "Working") => ({ id, title, status: status(kind, words) });
const branch = (o: object) => ({ id: 4, parent_id: null, name: "Week of 3 Nov", count: 10, can_manage: true, ideas: [], more: 0, folders: [], ...o });
const tree = {
  folders: [
    branch({ ideas: [dot(9, "Beer gut doctor rant"), dot(10, "Bloated after pizza", "needs_you", "Needs you")], more: 5 }),
    branch({ id: 5, name: "Dr. Pickle rants", count: 124, folders: [branch({ id: 6, parent_id: 5, name: "Hangovers", count: 31 })] }),
    branch({ id: 7, name: "UGC testimonials", count: 9 }),
  ],
  unsorted: branch({ id: null, name: "Unsorted", count: 2, can_manage: false }),
};
const page = { total: 0, counts: { all: 0, needs_you: 0, working: 0, delivered: 0 }, archived: 0, folders_inside: 0, makers: [], ideas: [] };
const base = (me: object, extra: Record<string, [number, unknown]> = {}): Record<string, [number, unknown]> => ({
  "GET /auth/me": [200, me],
  "GET /brands": [200, [{ id: 1, name: "Resilia", colours: ["#1f7a4f"] }]],
  "GET /brands/1/tree": [200, tree],
  "GET /brands/1/ideas": [200, page],
  "GET /jobs": [200, []],
  "GET /projects": [200, []],
  ...extra,
});
function open(at = "/b/1/videos?folder=4") {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[at]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
beforeEach(() => localStorage.clear());
afterEach(() => vi.unstubAllGlobals());
const rail = () => screen.getByRole("navigation", { name: "Main" });

test("the tree (S0-01): folders with counts, the open folder's ideas with their dots and + N more, folders inside on opening, Unsorted", async () => {
  setViewport(1440);
  fakeServer(base(owner));
  open();
  const week = await within(await screen.findByRole("navigation", { name: "Main" })).findByRole("link", { name: "Week of 3 Nov" });
  expect(week).toHaveAttribute("aria-current", "page");
  expect(within(rail()).getByRole("link", { name: /Beer gut doctor rant/ })).toHaveAttribute("href", "/b/1/videos/9");
  expect(within(rail()).getByRole("img", { name: "Needs you" })).toBeInTheDocument(); // a dot alone, its words on hover
  expect(within(rail()).getByRole("link", { name: "+ 5 more" })).toHaveAttribute("href", "/b/1/videos?folder=4");
  expect(within(rail()).queryByRole("link", { name: "Hangovers" })).toBeNull();
  await userEvent.click(within(rail()).getByRole("button", { name: "Open Dr. Pickle rants" }));
  expect(within(rail()).getByRole("link", { name: "Hangovers" })).toHaveAttribute("href", "/b/1/videos?folder=6");
  expect(within(rail()).getByRole("link", { name: /Unsorted/ })).toHaveTextContent("2");
});

test("dragging an idea onto a folder moves it, and Undo at the foot of the rail moves it back", async () => {
  setViewport(1440);
  const calls = fakeServer(base(owner, { "POST /folders/file": [200, { folder_id: 7, was: [{ id: 10, folder_id: 4 }] }] }));
  open();
  const target = (await within(await screen.findByRole("navigation", { name: "Main" })).findByRole("link", { name: "UGC testimonials" })).closest("div[class*='group']")!;
  const data = { types: [IDEA], getData: () => JSON.stringify({ id: 10, title: "Bloated after pizza" }), dropEffect: "" };
  fireEvent.dragOver(target, { dataTransfer: data });
  fireEvent.drop(target, { dataTransfer: data });
  expect(await screen.findByText("Moved “Bloated after pizza” to UGC testimonials.")).toBeInTheDocument();
  expect(calls.find((c) => c.key === "POST /folders/file")?.body).toEqual({ kind: "video", ids: [10], folder_id: 7 });
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /folders/file").at(-1)?.body).toEqual({ kind: "video", ids: [10], folder_id: 4 }));
});

test("a folder's menu (right-click or ⋯): New video here, New folder inside, Rename in place, Move to…, Delete folder… with Undo in the rail", async () => {
  setViewport(1440);
  const calls = fakeServer(base(owner, { "PATCH /folders/7": [200, {}], "DELETE /folders/7": [200, { moved: 9, ideas: 9 }], "POST /folders/7/restore": [200, {}] }));
  open();
  await userEvent.click(await within(await screen.findByRole("navigation", { name: "Main" })).findByRole("button", { name: "More for UGC testimonials" }));
  const menu = screen.getByRole("menu", { name: "UGC testimonials" });
  expect(within(menu).getAllByRole("menuitem").map((m) => m.textContent?.trim())).toEqual(["New video here", "New folder inside", "Rename", "Move to…", "Delete folder…"]);
  await userEvent.click(within(menu).getByRole("menuitem", { name: "Rename" }));
  const box = within(rail()).getByRole("textbox", { name: "Rename UGC testimonials" });
  await userEvent.clear(box);
  await userEvent.type(box, "UGC reviews{Enter}");
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /folders/7")?.body).toEqual({ name: "UGC reviews" }));

  fireEvent.contextMenu(within(rail()).getByRole("link", { name: "UGC testimonials" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Delete folder…" }));
  const ask = screen.getByRole("alertdialog", { name: "Delete UGC testimonials?" });
  await userEvent.click(within(ask).getByRole("button", { name: "Delete folder" }));
  expect(await within(rail()).findByText("Deleted “UGC testimonials”. Its 9 ideas moved to Unsorted.")).toBeInTheDocument();
  await userEvent.click(within(rail()).getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /folders/7/restore")).toBe(true));
});

test("the magnifier searches this brand's ideas and folders; Enter opens the first (S-gaps-04 R2)", async () => {
  setViewport(1440);
  const hit = { id: 10, title: "Bloated after pizza", folder_id: 4, status: status("needs_you", "Needs you"), still_file_id: null, look: "ugc", style: "UGC", seconds: 30, made_by: null, created_at: "2026-11-03T10:00:00Z", updated_at: "2026-11-03T10:00:00Z", cost: null, can_manage: true, from_script: true };
  fakeServer(base(owner, { "GET /brands/1/ideas?folder=all&tab=all&sort=newest&offset=0&limit=60&q=pi": [200, { ...page, total: 1, ideas: [hit] }] }));
  open();
  await userEvent.click(await within(await screen.findByRole("navigation", { name: "Main" })).findByRole("button", { name: "Quick search" }));
  await userEvent.type(screen.getByRole("searchbox", { name: "Search ideas and folders" }), "pi");
  const results = await screen.findByRole("listbox", { name: "Results" });
  expect(await within(results).findByRole("option", { name: /Bloated after pizza.*Week of 3 Nov/ })).toBeInTheDocument();
  expect(within(results).getByRole("option", { name: /Dr. Pickle rants.*folder · 124 ideas/ })).toBeInTheDocument();
});

test("an editor's rail has Mine · My requests, and the page lists what waits with Withdraw and this week's answers (S-gaps-04 R4)", async () => {
  setViewport(1440);
  const job = (o: object) => ({ id: 5, kind: "video", status: "needs_owner_approval", project_id: 9, credits: 20, created_at: new Date().toISOString(), step: "clip_take", held: "Past the budget.", declined: false, approved: false, note: "", ...o });
  fakeServer(base(editor, {
    "GET /jobs": [200, [job({}), job({ id: 6, status: "queued", approved: true, held: "" }), job({ id: 7, status: "cancelled", declined: true, held: "" })]],
    "GET /projects": [200, [{ id: 9, brand_id: 1, name: "Why IPAs hit harder", poster_file_id: null }]],
    "POST /jobs/5/cancel": [200, {}],
  }));
  open("/requests");
  expect(await within(await screen.findByRole("navigation", { name: "Main" })).findByRole("link", { name: /My requests/ })).toHaveTextContent("1");
  expect(await screen.findByRole("link", { name: "Why IPAs hit harder" })).toHaveAttribute("href", "/b/1/videos/9");
  expect(screen.getByText("A new take, past the budget · up to 20 credits")).toBeInTheDocument();
  expect(screen.getByText("Answered this week")).toBeInTheDocument();
  expect(screen.getByText("Approved")).toBeInTheDocument();
  expect(screen.getByText("Declined")).toBeInTheDocument();
  expect(document.body.textContent).not.toContain("$");
  await userEvent.click(screen.getByRole("button", { name: "Withdraw" }));
  expect(await screen.findByText("Withdrawn. Nothing was charged.")).toBeInTheDocument();
});

test("on a phone the Videos tab opens the folder list (P-01): the folder opened last shows its ideas, and New video", async () => {
  setViewport(390);
  localStorage.setItem("bs.lastFolder.1", "4");
  fakeServer(base(owner));
  open("/b/1/videos");
  expect(await screen.findByRole("link", { name: /Week of 3 Nov/ })).toHaveAttribute("href", "/b/1/videos?folder=4");
  expect(screen.getByRole("link", { name: /Beer gut doctor rant/ })).toHaveAttribute("href", "/b/1/videos/9");
  expect(screen.getByRole("link", { name: /Unsorted/ })).toHaveAttribute("href", "/b/1/videos?folder=none");
  expect(screen.getByRole("link", { name: "New video" })).toHaveAttribute("href", "/b/1/videos/new");
  expect(screen.getByRole("button", { name: "Brand: Resilia" })).toBeInTheDocument();
  const sizes = { scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth };
  expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
});

test("Archive brand is in the brand switcher's menu, for the owner, with a confirm and Undo (S-gaps-05)", async () => {
  setViewport(1440);
  const calls = fakeServer(base(owner, { "GET /brands": [200, [{ id: 1, name: "Resilia", colours: [] }, { id: 2, name: "fomo", colours: [] }]], "DELETE /brands/1": [204, null], "POST /brands/1/restore": [200, {}] }));
  open("/b/1/scripts");
  await userEvent.click(await within(await screen.findByRole("navigation", { name: "Main" })).findByRole("button", { name: "Brand: Resilia" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Archive Resilia…" }));
  const ask = screen.getByRole("alertdialog", { name: "Archive Resilia?" });
  await userEvent.click(within(ask).getByRole("button", { name: "Archive" }));
  expect(await screen.findByText("Archived Resilia.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /brands/1/restore")).toBe(true));
});

test("an editor's brand menu has no Archive", async () => {
  setViewport(1440);
  fakeServer(base(editor));
  open("/b/1/scripts");
  await userEvent.click(await within(await screen.findByRole("navigation", { name: "Main" })).findByRole("button", { name: "Brand: Resilia" }));
  expect(screen.queryByRole("menuitem", { name: /^Archive/ })).toBeNull();
});
