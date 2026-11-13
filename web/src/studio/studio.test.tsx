import { readFileSync } from "node:fs";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { owner } from "../test/people";
import { renderApp } from "../test/render";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { Dialog } from "./Dialog";
import { Choice, Popover } from "./Popover";

const status = (kind: string, words: string, reason: string | null = null) => ({ kind, words, reason, at: null, made: 0, total: 0 });
const idea = (id: number, title: string, s: object) => ({ id, title, folder_id: null, status: s, still_file_id: null, look: "movie", style: "Movie", seconds: 30, made_by: null, created_at: "2026-11-12T10:00:00", updated_at: "2026-11-12T10:00:00", cost: null, can_manage: true, from_script: false });
const branch = (o: object) => ({ id: 4, parent_id: null, name: "Target ads", count: 3, can_manage: true, ideas: [], more: 0, folders: [], ...o });
const ideas = [idea(366, "Three men at Target", status("needs_you", "Needs you", "Approve the plan")), idea(365, "A dad on the border", status("working", "Working", "4 of 9")), idea(360, "Dana gets the call", status("delivered", "Delivered"))];
const page = (list: object[]) => ({ total: list.length, counts: { all: list.length, needs_you: 0, working: 0, delivered: 0 }, archived: 0, folders_inside: 0, makers: [], ideas: list });
const server = (extra: Record<string, [number, unknown]> = {}) =>
  fakeServer({
    "GET /auth/me": [200, owner],
    "GET /brands": [200, [{ id: 1, name: "Palace Guard", colours: ["#ef8a3c"] }, { id: 2, name: "Iron Paws", colours: [] }]],
    "GET /workspace": [200, { id: 1, name: "Night Shift Studio" }],
    "GET /brands/1/tree": [200, { folders: [branch({ folders: [branch({ id: 6, parent_id: 4, name: "Hooks", count: 1 })] })], unsorted: branch({ id: null, name: "Unsorted", count: 2, can_manage: false }) }],
    "GET /brands/1/ideas": [200, page(ideas)],
    "GET /brands/2/tree": [200, { folders: [], unsorted: branch({ id: null, name: "Unsorted", count: 0, can_manage: false }) }],
    "GET /brands/2/ideas": [200, page([])],
    ...extra,
  });
const rail = () => within(screen.getByRole("navigation", { name: "Main" }));

beforeEach(() => {
  localStorage.clear();
  setViewport(1440);
});
afterEach(() => vi.unstubAllGlobals());

test("the shell shows the studio, the brand, the four pages, what is being made and the folders, from the server", async () => {
  server();
  renderApp("/s/b/1");
  expect(await screen.findByRole("button", { name: "Brand: Palace Guard" })).toBeInTheDocument();
  expect(await rail().findByText("Night Shift Studio")).toBeInTheDocument();
  expect(rail().getByRole("link", { name: "Create", current: "page" })).toHaveAttribute("href", "/s/b/1");
  for (const [name, to] of [["Videos", "videos"], ["Library", "library"], ["Spend", "spend"]]) expect(rail().getByRole("link", { name })).toHaveAttribute("href", `/s/b/1/${to}`);
  const making = within(rail().getByRole("group", { name: "Being made" }));
  expect(await making.findByRole("link", { name: /Three men at Target/ })).toHaveAttribute("href", "/b/1/videos/366");
  expect(making.getByRole("link", { name: /A dad on the border/ })).toHaveTextContent("Working · 4 of 9");
  expect(making.queryByRole("link", { name: /Dana gets the call/ })).toBeNull(); // delivered: no longer being made
  const folders = within(rail().getByRole("group", { name: "Folders" }));
  expect(folders.getByRole("link", { name: /Target ads/ })).toHaveTextContent("3");
  expect(folders.getByRole("link", { name: /Hooks/ })).toHaveAttribute("href", "/s/b/1/videos?folder=6");
  expect(folders.getByRole("link", { name: /Unsorted/ })).toHaveAttribute("href", "/s/b/1/videos?folder=none");
  expect(rail().getByText("Reed")).toBeInTheDocument();
  expect(rail().getByRole("link", { name: "Settings" })).toHaveAttribute("href", "/settings");
  expect(screen.getByRole("heading", { name: "New video" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "open New video on the current site" })).toHaveAttribute("href", "/b/1");
});

test("the brand menu switches brand and stays in the new look, on the same page", async () => {
  server();
  renderApp("/s/b/1/library");
  await userEvent.click(await screen.findByRole("button", { name: "Brand: Palace Guard" }));
  expect(screen.getByRole("menuitemradio", { name: "Palace Guard" })).toHaveAttribute("aria-checked", "true");
  await userEvent.click(screen.getByRole("menuitemradio", { name: "Iron Paws" }));
  expect(await screen.findByRole("button", { name: "Brand: Iron Paws" })).toBeInTheDocument();
  expect(rail().getByRole("link", { name: "Library", current: "page" })).toHaveAttribute("href", "/s/b/2/library");
  expect(await rail().findByText("Nothing right now.")).toBeInTheDocument();
});

test("/s opens the brand you were last in", async () => {
  localStorage.setItem("bs.lastBrand", "2");
  server();
  renderApp("/s");
  expect(await screen.findByRole("heading", { name: "New video" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Brand: Iron Paws" })).toBeInTheDocument();
  expect(rail().getByRole("link", { name: "Create", current: "page" })).toHaveAttribute("href", "/s/b/2");
});

test("Search or jump (⌘K) lists the places and the brand's videos, narrows as you type, and Enter opens the marked one", async () => {
  server();
  renderApp("/s/b/1");
  await screen.findByRole("link", { name: /Three men at Target/ });
  await userEvent.keyboard("{Meta>}k{/Meta}");
  const box = within(screen.getByRole("dialog", { name: "Search or jump" }));
  expect(box.getByRole("textbox", { name: "Search or jump" })).toHaveFocus();
  expect(box.getByRole("link", { name: /Three men at Target/, current: true })).toHaveAttribute("href", "/b/1/videos/366");
  expect(box.getByRole("link", { name: /Dana gets the call/ })).toHaveTextContent("Delivered");
  expect(box.getByRole("link", { name: "Iron Paws" })).toHaveAttribute("href", "/s/b/2");
  await userEvent.keyboard("spen");
  expect(box.getAllByRole("link")).toHaveLength(1);
  await userEvent.keyboard("{Enter}");
  expect(await screen.findByRole("heading", { name: "Spend" })).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).toBeNull();
});

function menu() {
  const picked = vi.fn();
  render(
    <Popover label="Shape" button={(p) => <button type="button" {...p}>Shape</button>}>
      {(close) => ["Tall", "Square", "Wide"].map((s) => <Choice key={s} checked={s === "Square"} onPick={() => (picked(s), close())}>{s}</Choice>)}
    </Popover>,
  );
  return picked;
}

test("the popover opens from its button on the picked choice, the arrow keys move through it, and a choice closes it", async () => {
  const picked = menu();
  const button = screen.getByRole("button", { name: "Shape" });
  await userEvent.click(button);
  expect(button).toHaveAttribute("aria-expanded", "true");
  expect(within(screen.getByRole("menu", { name: "Shape" })).getByRole("menuitemradio", { name: "Square" })).toHaveFocus();
  await userEvent.keyboard("{ArrowDown}");
  expect(screen.getByRole("menuitemradio", { name: "Wide" })).toHaveFocus();
  await userEvent.keyboard("{ArrowDown}");
  expect(screen.getByRole("menuitemradio", { name: "Tall" })).toHaveFocus(); // round to the top
  await userEvent.keyboard("{ArrowUp}{Enter}");
  expect(picked).toHaveBeenCalledWith("Wide");
  expect(screen.queryByRole("menu")).toBeNull();
});

test("Escape closes the popover and puts focus back on its button", async () => {
  menu();
  await userEvent.click(screen.getByRole("button", { name: "Shape" }));
  await userEvent.keyboard("{Escape}");
  expect(screen.queryByRole("menu")).toBeNull();
  expect(screen.getByRole("button", { name: "Shape" })).toHaveFocus();
  expect(screen.getByRole("button", { name: "Shape" })).toHaveAttribute("aria-expanded", "false");
});

test("a click outside closes the popover", async () => {
  menu();
  await userEvent.click(screen.getByRole("button", { name: "Shape" }));
  await userEvent.click(document.body);
  expect(screen.queryByRole("menu")).toBeNull();
});

function rename() {
  const said = { confirm: vi.fn(), close: vi.fn() };
  render(
    <Dialog title="Rename the folder" confirm="Rename" onConfirm={said.confirm} onClose={said.close}>
      <input data-autofocus aria-label="Folder name" />
    </Dialog>,
  );
  return said;
}

test("the dialog starts in its field, and Enter confirms", async () => {
  const said = rename();
  expect(within(screen.getByRole("dialog", { name: "Rename the folder" })).getByRole("textbox", { name: "Folder name" })).toHaveFocus();
  await userEvent.keyboard("Winter{Enter}");
  expect(said.confirm).toHaveBeenCalledTimes(1);
  expect(said.close).not.toHaveBeenCalled();
});

test("Escape cancels the dialog", async () => {
  const said = rename();
  await userEvent.keyboard("{Escape}");
  expect(said.close).toHaveBeenCalledTimes(1);
  expect(said.confirm).not.toHaveBeenCalled();
});

test("Settings' Try the new look sets bs.ui and opens the studio; Back to the current site clears it and leaves", async () => {
  server();
  renderApp("/settings");
  await userEvent.click(await screen.findByRole("button", { name: "Open the new look" }));
  expect(localStorage.getItem("bs.ui")).toBe("new");
  expect(await screen.findByRole("heading", { name: "New video" })).toBeInTheDocument();
  await userEvent.click(rail().getByRole("link", { name: "Back to the current site" }));
  expect(localStorage.getItem("bs.ui")).toBeNull();
  expect(await screen.findByRole("button", { name: "Account menu" })).toBeInTheDocument(); // the current site's rail
  expect(document.querySelector(".studio")).toBeNull();
});

test("with bs.ui set, / opens the new look", async () => {
  localStorage.setItem("bs.ui", "new");
  server();
  renderApp("/");
  expect(await screen.findByRole("heading", { name: "New video" })).toBeInTheDocument();
  expect(rail().getByRole("link", { name: "Create", current: "page" })).toHaveAttribute("href", "/s/b/1");
});

test("without it, / stays on the current site and nothing of the new look is on the page", async () => {
  server();
  renderApp("/");
  expect(await screen.findByRole("button", { name: "Account menu" })).toBeInTheDocument();
  expect(document.querySelector(".studio")).toBeNull();
});

/** The selectors at the top of a stylesheet, and at the top of each @media block in it. */
function tops(sheet: string): string[] {
  const out: string[] = [];
  let depth = 0;
  let from = 0;
  let body = 0;
  [...sheet].forEach((c, i) => {
    if (c === "{" && depth++ === 0) body = i + 1;
    else if (c === "}" && --depth === 0) {
      const head = sheet.slice(from, body - 1).trim();
      out.push(...(head.startsWith("@media") ? tops(sheet.slice(body, i)) : [head]));
      from = i + 1;
    } else if (c === ";" && depth === 0) from = i + 1; // the font's @import
  });
  return out;
}

test("every style of the new look is under .studio, so none can reach a current screen", () => {
  const rules = tops(readFileSync("src/studio/studio.css", "utf8").replace(/\/\*[\s\S]*?\*\//g, ""));
  expect(rules.length).toBeGreaterThan(5);
  expect(rules.filter((r) => !/^(\.studio(\s|$)|body:has\(\.studio\.app\)$|@keyframes studio-)/.test(r))).toEqual([]);
});
