import { cleanup, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";

const owner = { id: 1, email: "reed@b.co", name: "Reed", role: "owner", workspace_id: 1 };
const editor = { ...owner, id: 2, name: "Eli", role: "editor" };
const brands = [
  { id: 1, name: "fomo", colours: ["#ff5500"] },
  { id: 2, name: "Iron Paws", colours: [] },
];
const members = [
  { id: 1, email: "reed@b.co", name: "Reed", role: "owner" },
  { id: 2, email: "eli@b.co", name: "Eli", role: "editor" },
];

function renderAt(path: string) {
  renderApp(path); // a data router, as the app runs (Brand asks before leaving with unsaved changes)
}

beforeEach(() => (localStorage.clear(), localStorage.setItem("bs.ui", "old"))); // the current site's shell: "/" opens the new look otherwise
afterEach(() => vi.unstubAllGlobals());

const pickBrand = async (name: string) => {
  await userEvent.click(screen.getByRole("button", { name: /^Brand: / }));
  await userEvent.click(await screen.findByRole("menuitemradio", { name }));
};

test("the switcher menu changes brand and keeps the section", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []], "GET /library/character": [200, []] });
  renderAt("/b/1/scripts");
  expect(await screen.findByRole("heading", { name: "Scripts" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Brand: fomo" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Brand: fomo" }));
  expect(screen.getByRole("menuitemradio", { name: "fomo" })).toHaveAttribute("aria-checked", "true");
  expect(screen.getByRole("menuitem", { name: "New brand" })).toBeInTheDocument();
  expect(screen.queryByText("Brands are set up by the owner.")).toBeNull();
  await userEvent.click(screen.getByRole("menuitemradio", { name: "Iron Paws" }));
  expect(await screen.findByText("No scripts for Iron Paws yet.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Brand: Iron Paws" })).toBeInTheDocument();
  // Cast in one brand becomes Cast in the other.
  await userEvent.click(within(screen.getByRole("navigation", { name: "Main" })).getByRole("link", { name: "Cast" }));
  await screen.findByRole("navigation", { name: "Library" });
  await pickBrand("fomo");
  expect(await screen.findByRole("heading", { name: "No characters in fomo yet" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Cast", current: "page" })).toHaveAttribute("href", "/b/1/library/characters");
});

test("the brand's colour is applied, and cleared for a brand without one", async () => {
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []] });
  renderAt("/b/1/scripts");
  await screen.findByRole("heading", { name: "Scripts" });
  expect(document.documentElement.style.getPropertyValue("--brand")).toBe("#ff5500");
  await pickBrand("Iron Paws");
  await screen.findByText("No scripts for Iron Paws yet.");
  expect(document.documentElement.style.getPropertyValue("--brand")).toBe("");
});

test("the team page keeps the brand you were in", async () => {
  setViewport(1440);
  localStorage.setItem("bs.lastBrand", "2");
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /team/members": [200, members], "GET /team/invites": [200, []] });
  renderAt("/team");
  expect(await screen.findByRole("button", { name: "Brand: Iron Paws" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Brand" })).toHaveAttribute("href", "/b/2/brand");
});

test("the last brand you used opens next time", async () => {
  localStorage.setItem("bs.lastBrand", "2");
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []] });
  renderAt("/");
  expect(await screen.findByRole("button", { name: "Brand: Iron Paws" })).toBeInTheDocument(); // its open folder (S1)
});

test("an editor sees the team but cannot invite or remove", async () => {
  const calls = fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, brands], "GET /team/members": [200, members] });
  renderAt("/team");
  expect(await screen.findByText("Reed")).toBeInTheDocument();
  expect(screen.queryByLabelText("Email to invite")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Remove/ })).not.toBeInTheDocument();
  expect(calls.some((c) => c.key === "GET /team/invites")).toBe(false);
});

test("signing out returns to sign in", async () => {
  setViewport(1440); // a phone signs out from More
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "POST /auth/logout": [204, null] });
  renderAt("/");
  await userEvent.click(await screen.findByRole("button", { name: "Account menu" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Sign out" }));
  expect(await screen.findByRole("heading", { name: "Sign in to Brand Studio" })).toBeInTheDocument();
});

test("an unknown brand in the address does not pretend to be selected", async () => {
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands] });
  renderAt("/b/999");
  expect(await screen.findByRole("button", { name: "Choose a brand" })).toBeInTheDocument();
});

test("a failed remove tells you", async () => {
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /team/members": [200, members], "GET /team/invites": [200, []], "DELETE /team/members/2": [500, {}] });
  renderAt("/team");
  await userEvent.click(await screen.findByRole("button", { name: "Remove Eli" }));
  const ask = await screen.findByRole("alertdialog", { name: "Remove Eli from the team?" });
  expect(within(ask).getByText("Their videos stay.")).toBeInTheDocument();
  await userEvent.click(within(ask).getByRole("button", { name: "Remove" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't remove that person.");
});

const tree = { folders: [], unsorted: { id: null, parent_id: null, name: "Unsorted", count: 0, can_manage: false, ideas: [], more: 0, folders: [] } };

test("on a phone there are four tabs (v6 P-01): Videos, Library, Needs you with its count, More; Library and More are short lists", async () => {
  setViewport(390);
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /needs-you": [200, { total: 1, brands: [], questions: [], money: [], sends: [], stuck: [] }], "GET /scripts": [200, []], "GET /projects": [200, []], "GET /brands/1/tree": [200, tree] });
  renderAt("/b/1/scripts");
  const tabs = await screen.findByRole("navigation", { name: "Tabs" });
  expect(within(tabs).getAllByRole("link").map((l) => l.textContent?.replace(/\d+ waiting$/, ""))).toEqual(["Videos", "Library", "Needs you", "More"]);
  expect(within(tabs).getByRole("link", { name: "Library" })).toHaveAttribute("href", "/b/1/more/library");
  expect(await within(tabs).findByRole("link", { name: /^Needs you/ })).toHaveTextContent("1");
  await userEvent.click(within(tabs).getByRole("link", { name: "Library" }));
  expect(await screen.findByRole("link", { name: "Scripts" })).toHaveAttribute("href", "/b/1/scripts");
  expect(screen.getByRole("link", { name: "Brand kit" })).toHaveAttribute("href", "/b/1/brand");
  await userEvent.click(within(tabs).getByRole("link", { name: "More" }));
  expect(await screen.findByRole("link", { name: "Settings" })).toHaveAttribute("href", "/settings");
  expect(screen.getByRole("button", { name: "Your account" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  expect(screen.queryByRole("navigation", { name: "Main" })).not.toBeInTheDocument();
});

test("Needs you is a rail row only while something waits: with nothing waiting, or before its count is read, there is no row and never a 0 (rule 33); the account menu still opens it, and the phone keeps its tab with no count", async () => {
  for (const answer of [[200, { total: 0, brands: [], questions: [], money: [], sends: [], stuck: [] }], [500, { detail: "busy" }]] as [number, unknown][]) {
    for (const width of [390, 1440]) {
      setViewport(width);
      const calls = fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /needs-you": answer, "GET /scripts": [200, []], "GET /projects": [200, []] });
      renderAt("/b/1/scripts");
      await screen.findByRole("heading", { name: "Scripts" });
      await vi.waitFor(() => expect(calls.some((c) => c.key === "GET /needs-you")).toBe(true));
      if (width === 390) {
        const needs = screen.getByRole("link", { name: /^Needs you/ });
        expect(needs).toHaveAttribute("href", "/approvals");
        expect(needs.textContent).toBe("Needs you");
      } else {
        expect(screen.queryByRole("link", { name: /^Needs you/ })).toBeNull();
        await userEvent.click(screen.getByRole("button", { name: "Account menu" }));
        expect(within(screen.getByRole("menu", { name: "Account" })).getByRole("link", { name: "Needs you" })).toHaveAttribute("href", "/approvals");
      }
      cleanup();
      vi.unstubAllGlobals();
    }
  }
});

test("when only a stuck video waits, Reed still reaches Needs you: the tab and the rail row count everything it lists (S9-01)", async () => {
  for (const width of [390, 1440]) {
    setViewport(width);
    fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []], "GET /needs-you": [200, { total: 1, brands: [], questions: [], money: [], sends: [], stuck: [{}] }] });
    renderAt("/b/1/scripts");
    await vi.waitFor(() => expect(screen.getByRole("link", { name: /^Needs you/ })).toHaveTextContent("1"));
    cleanup();
    vi.unstubAllGlobals();
  }
});

test("an editor's third tab is My requests, not Needs you (S-gaps-04 R3)", async () => {
  setViewport(390);
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []], "GET /jobs": [200, []] });
  renderAt("/b/1/scripts");
  const tabs = await screen.findByRole("navigation", { name: "Tabs" });
  expect(within(tabs).getByRole("link", { name: "My requests" })).toHaveAttribute("href", "/requests");
  expect(screen.queryByRole("link", { name: /Needs you/ })).not.toBeInTheDocument();
});

test("the account menu (bottom of the rail) has the owner's Studio pages, which are no longer rail rows, Sign out and no theme choice (light only, rule 33); Escape closes it", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /projects": [200, []], "POST /auth/logout": [204, null] });
  renderAt("/b/1/projects");
  const menu = await screen.findByRole("button", { name: "Account menu" });
  await userEvent.click(menu);
  expect(screen.getByText("reed@b.co")).toBeInTheDocument();
  const list = screen.getByRole("menu", { name: "Account" });
  expect(within(list).getAllByRole("link").map((l) => [l.textContent, l.getAttribute("href")])).toEqual([["Needs you", "/approvals"], ["In production", "/production"], ["Usage", "/usage"], ["Team", "/team"], ["Settings", "/settings"]]);
  expect(within(screen.getByRole("navigation", { name: "Main" })).getAllByRole("link", { name: /In production|Usage|Team|Settings/ })).toHaveLength(4); // the menu's own, inside the rail: no rows
  expect(screen.queryByRole("group", { name: "Theme" })).toBeNull(); // light only for now
  expect(screen.queryByRole("menuitemradio", { name: "Dark" })).toBeNull();
  await userEvent.keyboard("{Escape}");
  expect(screen.queryByRole("menuitem", { name: "Sign out" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Team" })).toBeNull();
  expect(menu).toHaveFocus();
});

test("an editor's account menu has no Studio pages: My credits, never dollars", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []] });
  renderAt("/b/1/projects");
  await userEvent.click(await screen.findByRole("button", { name: "Account menu" }));
  const list = screen.getByRole("menu", { name: "Account" });
  expect(within(list).getAllByRole("link").map((l) => l.getAttribute("href"))).toEqual(["/usage/mine"]);
  expect(within(list).getByRole("link", { name: /^My credits/ })).toBeInTheDocument();
  expect(list.textContent).not.toContain("$");
  expect(screen.getByRole("menuitem", { name: "Sign out" })).toBeInTheDocument();
});

const ideas = (n: number) => ({ total: n, counts: { all: n, needs_you: 0, working: n, delivered: 0 }, archived: 0, folders_inside: 0, makers: [], ideas: Array.from({ length: n }, (_, i) => ({ id: 40 + i, title: `Video ${i + 1}`, folder_id: null, status: { kind: "working", words: "Working", reason: "3 of 8", at: null, made: 3, total: 8 }, still_file_id: null, look: "ugc", style: "UGC", seconds: 30, made_by: null, created_at: "2026-11-03T10:00:00Z", updated_at: "2026-11-03T10:00:00Z", cost: null, can_manage: true, from_script: false })) });
const railLinks = (rail: HTMLElement) => within(rail).getAllByRole("link").map((l) => l.textContent?.replace(/\d+ waiting$/, "").trim());

test("on desktop one rail: the brand switcher, Home and search, All videos, Needs you while something waits, Assets (Brand, Products, Cast), Projects (New video, the folders), the account at the bottom; no Studio group, no Media or Scripts row, no top bar", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []], "GET /brands/1/tree": [200, tree], "GET /needs-you": [200, { total: 1, brands: [], questions: [], money: [], sends: [], stuck: [] }] });
  renderAt("/b/1/projects");
  const rail = await screen.findByRole("navigation", { name: "Main" });
  expect(await within(rail).findByText("fomo")).toBeInTheDocument();
  await within(rail).findByRole("link", { name: /Unsorted/ });
  await within(rail).findByRole("link", { name: /Needs you/ });
  expect(railLinks(rail)).toEqual(["HomeN", "All videos", "Needs you", "Brand", "Products", "Cast", "New video", "Unsorted0"]);
  for (const group of ["Assets", "Projects"]) expect(within(rail).getByRole("button", { name: group })).toHaveAttribute("aria-expanded", "true");
  expect(within(rail).queryByText("Studio")).toBeNull();
  expect(within(rail).getByRole("link", { name: "Home" })).toHaveAttribute("href", "/b/1");
  expect(within(rail).getByRole("link", { name: "All videos" })).toHaveAttribute("href", "/b/1/videos");
  expect(within(rail).getByRole("link", { name: "Brand" })).toHaveAttribute("href", "/b/1/brand");
  expect(within(rail).getByRole("link", { name: "Products" })).toHaveAttribute("href", "/b/1/library/products"); // the library's own Products tab
  expect(within(rail).getByRole("link", { name: "Cast" })).toHaveAttribute("href", "/b/1/library/characters");
  expect(within(rail).getByRole("link", { name: "New video" })).toHaveAttribute("href", "/b/1"); // Projects' New video is Home
  expect(within(rail).getByRole("button", { name: "Quick search" })).toBeInTheDocument();
  expect(within(rail).getByRole("button", { name: "New folder" })).toBeInTheDocument();
  expect(within(rail).getByRole("button", { name: "Brand: fomo" })).toBeInTheDocument();
  expect(within(rail).getByRole("button", { name: "Account menu" })).toBeInTheDocument();
  expect(screen.queryByRole("banner", { name: "Top bar" })).not.toBeInTheDocument(); // the shell's own top bar; a page's PageTop is a header too
  await vi.waitFor(() => expect(within(rail).getByRole("link", { name: /Unsorted/ })).toHaveAttribute("aria-current", "page")); // the old list lands on the brand's videos
  expect(within(rail).getByRole("link", { name: /Needs you/ })).toHaveTextContent("1");
  expect(screen.getAllByRole("link", { name: /Needs you/ })).toHaveLength(1); // only the rail row: no top bar on desktop
  expect(screen.queryByRole("navigation", { name: "Tabs" })).not.toBeInTheDocument();
});

test("Projects' Recent lists the brand's six most recently active videos, each a link to its video with its status; none yet, no list", async () => {
  setViewport(1440);
  const routes: Record<string, [number, unknown]> = { "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /brands/1/tree": [200, tree], "GET /brands/1/ideas": [200, ideas(8)], "GET /projects/41": [404, {}] };
  const calls = fakeServer(routes);
  renderAt("/b/1/videos");
  const rail = await screen.findByRole("navigation", { name: "Main" });
  const recent = await within(rail).findByRole("list", { name: "Recent" });
  expect(calls.find((c) => c.key === "GET /brands/1/ideas" && c.url.includes("folder=all"))?.url).toContain("sort=newest"); // the brand's, newest activity first
  const links = within(recent).getAllByRole("link");
  expect(links.map((l) => l.getAttribute("href"))).toEqual([40, 41, 42, 43, 44, 45].map((id) => `/b/1/videos/${id}`));
  expect(links[1]).toHaveTextContent("Video 2");
  expect(links[1]).toHaveAttribute("title", "Video 2 · Working · 3 of 8"); // the whole name and its status, when the row is cut short
  expect(within(links[1]).getByRole("img", { name: "Working · 3 of 8" })).toBeInTheDocument();
  expect(links[1].querySelector(".truncate")).toHaveTextContent("Video 2"); // one line
  cleanup();
  fakeServer({ ...routes, "GET /brands/1/ideas": [200, ideas(0)] });
  renderAt("/b/1/videos");
  await within(await screen.findByRole("navigation", { name: "Main" })).findByRole("link", { name: /Unsorted/ });
  expect(screen.queryByRole("list", { name: "Recent" })).toBeNull();
  expect(screen.queryByText("Recent")).toBeNull();
});

test("Assets and Projects fold away from their headers and stay folded next time; New folder stays on Projects' header", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /brands/1/tree": [200, tree], "GET /brands/1/ideas": [200, ideas(2)] });
  renderAt("/b/1/videos");
  const rail = await screen.findByRole("navigation", { name: "Main" });
  await within(rail).findByRole("link", { name: /Unsorted/ });
  await within(rail).findByRole("list", { name: "Recent" });
  await userEvent.click(within(rail).getByRole("button", { name: "Assets" }));
  expect(within(rail).getByRole("button", { name: "Assets" })).toHaveAttribute("aria-expanded", "false");
  expect(within(rail).queryByRole("link", { name: "Brand" })).toBeNull();
  within(rail).getByRole("button", { name: "Projects" }).focus();
  await userEvent.keyboard("{Enter}"); // a real button: the keyboard folds it too
  expect(within(rail).getByRole("button", { name: "Projects" })).toHaveAttribute("aria-expanded", "false");
  expect(railLinks(rail)).toEqual(["HomeN", "All videos"]);
  expect(within(rail).getByRole("button", { name: "New folder" })).toBeInTheDocument();
  expect([localStorage.getItem("bs.rail.assets"), localStorage.getItem("bs.rail.projects")]).toEqual(["0", "0"]);
  cleanup();
  renderAt("/b/1/videos");
  const again = await screen.findByRole("navigation", { name: "Main" });
  expect(await within(again).findByRole("button", { name: "Assets" })).toHaveAttribute("aria-expanded", "false");
  await userEvent.click(within(again).getByRole("button", { name: "Projects" }));
  expect(await within(again).findByRole("link", { name: /Unsorted/ })).toBeInTheDocument();
  expect(within(again).getByRole("link", { name: "New video" })).toBeInTheDocument();
  expect(within(again).queryByRole("link", { name: "Products" })).toBeNull(); // Assets is still folded
  expect(localStorage.getItem("bs.rail.projects")).toBe("1");
});

const home = { "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /looks": [200, []], "GET /brands/1/tree": [200, tree], "GET /brands/2/tree": [200, tree] } as Record<string, [number, unknown]>;

test("a brand opens on Home, at its own address and at New video's; switching brand there stays on Home", async () => {
  setViewport(1440);
  fakeServer(home);
  renderAt("/");
  expect(await screen.findByRole("heading", { name: "Paste your script, pick a style. We handle the rest." })).toBeInTheDocument();
  const rail = screen.getByRole("navigation", { name: "Main" });
  expect(within(rail).getByRole("link", { name: "Home" })).toHaveAttribute("aria-current", "page");
  expect(within(rail).getByRole("link", { name: "All videos" })).not.toHaveAttribute("aria-current");
  await pickBrand("Iron Paws");
  expect(await within(rail).findByRole("link", { name: "Home", current: "page" })).toHaveAttribute("href", "/b/2");
  cleanup();
  renderAt("/b/1/videos/new");
  expect(await screen.findByRole("link", { name: "Home", current: "page" })).toBeInTheDocument(); // the same page, not a video under All videos
  expect(screen.getByRole("link", { name: "All videos" })).not.toHaveAttribute("aria-current");
  await screen.findByRole("button", { name: "Brand: fomo" });
  await pickBrand("Iron Paws");
  expect(await screen.findByRole("link", { name: "Home", current: "page" })).toHaveAttribute("href", "/b/2");
  expect(screen.getByRole("heading", { name: "Paste your script, pick a style. We handle the rest." })).toBeInTheDocument();
});

test("N opens Home on its words box from another page, and goes back to the words when already there", async () => {
  setViewport(1440);
  fakeServer({ ...home, "GET /scripts": [200, []] });
  renderAt("/b/1/scripts");
  await screen.findByRole("heading", { name: "Scripts" });
  await userEvent.keyboard("n");
  const words = await screen.findByLabelText("Paste a script, or describe the video");
  await vi.waitFor(() => expect(words).toHaveFocus());
  await userEvent.type(words, "nn"); // typing an n is typing, not the shortcut
  expect(words).toHaveValue("nn");
  await userEvent.click(screen.getByRole("heading", { name: /^Paste your script/ })); // focus leaves the box
  expect(words).not.toHaveFocus();
  await userEvent.keyboard("n");
  expect(words).toHaveFocus();
  expect(words).toHaveValue("nn"); // the words typed so far stay
  await userEvent.click(screen.getByRole("heading", { name: /^Paste your script/ }));
  await userEvent.click(within(screen.getByRole("navigation", { name: "Main" })).getByRole("link", { name: "New video" })); // Projects' New video does the same
  expect(words).toHaveFocus();
  expect(words).toHaveValue("nn");
});

test("Products has its own row: on the library's Products tab it is the current one, not Cast, and a brand switch stays there", async () => {
  setViewport(1440);
  fakeServer({ ...home, "GET /library/prop": [200, []], "GET /library/character": [200, []], "GET /library/place": [200, []] });
  renderAt("/b/1/library/products");
  const rail = await screen.findByRole("navigation", { name: "Main" });
  expect(await within(rail).findByRole("link", { name: "Products", current: "page" })).toBeInTheDocument();
  expect(within(rail).getByRole("link", { name: "Cast" })).not.toHaveAttribute("aria-current");
  await pickBrand("Iron Paws");
  expect(await within(rail).findByRole("link", { name: "Products", current: "page" })).toHaveAttribute("href", "/b/2/library/products");
});

test("Cast is the current row on the library's characters, places and presenters; Brand on the brand's page, its footage, Media and Scripts; a brand switch keeps the tab", async () => {
  setViewport(1440);
  fakeServer({ ...home, "GET /library/prop": [200, []], "GET /library/character": [200, []], "GET /library/place": [200, []], "GET /scripts": [200, []], "GET /projects": [200, []] });
  const current = () => within(screen.getByRole("navigation", { name: "Main" })).getAllByRole("link", { current: "page" }).map((l) => l.textContent);
  for (const [path, row] of [["library/characters", "Cast"], ["library/places", "Cast"], ["library/presenters", "Cast"], ["library/characters/7", "Cast"], ["brand", "Brand"], ["library/footage", "Brand"], ["scripts", "Brand"], ["media", "Brand"]]) {
    renderAt(`/b/1/${path}`);
    await screen.findByRole("button", { name: "Brand: fomo" });
    expect([path, current()]).toEqual([path, [row]]);
    cleanup();
  }
  renderAt("/b/1/library/places");
  await screen.findByRole("button", { name: "Brand: fomo" });
  await pickBrand("Iron Paws");
  expect(await screen.findByRole("heading", { name: "No places in Iron Paws yet" })).toBeInTheDocument();
});

test("an editor's rail: Home, All videos, My requests, Assets and Projects; no Needs you and no Studio pages (S0-01)", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []], "GET /jobs": [200, []], "GET /brands/1/tree": [200, tree] });
  renderAt("/b/1/scripts");
  const rail = await screen.findByRole("navigation", { name: "Main" });
  await within(rail).findByRole("link", { name: /Unsorted/ });
  expect(railLinks(rail)).toEqual(["HomeN", "All videos", "My requests", "Brand", "Products", "Cast", "New video", "Unsorted0"]);
  expect(within(rail).getByRole("link", { name: /My requests/ })).toHaveAttribute("href", "/requests");
  expect(within(rail).getByRole("link", { name: /My requests/ })).toHaveTextContent("0 waiting");
  expect(within(rail).queryByRole("link", { name: /Needs you|In production|Usage|Team|Settings/ })).not.toBeInTheDocument();
  expect(rail.textContent).not.toMatch(/Studio|\$/);
});

test("between 1024 and 1279 the rail is icons only, each with a name", async () => {
  setViewport(1100);
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []] });
  renderAt("/b/1/projects");
  const rail = await screen.findByRole("navigation", { name: "Main" });
  expect(within(rail).getByRole("link", { name: "Cast" })).toHaveAttribute("title", "Cast");
  expect(within(rail).getAllByRole("link").map((l) => [l.getAttribute("aria-label"), l.textContent])).toEqual([["Home", ""], ["All videos", ""], ["My requests", ""], ["Brand", ""], ["Products", ""], ["Cast", ""], ["New video", ""]]); // the same rows, as icons
  expect(within(rail).queryByRole("button", { name: /Assets|Projects/ })).toBeNull(); // no headers to fold on the icon rail
});

test("the old Kit and Screens addresses land on the Brand kit", async () => {
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /projects": [200, []] });
  renderAt("/b/1/screens");
  expect(await screen.findByRole("link", { name: "Brand kit", current: "page" })).toBeInTheDocument();
  expect(screen.getByLabelText("Tone and rules")).toBeInTheDocument();
});

test("the Brand page has a quiet row, Also in this brand: Products, Cast & places, B-roll and footage, Media and Scripts, one press away on a computer and a phone", async () => {
  for (const width of [1440, 390]) {
    setViewport(width);
    fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []] });
    renderAt("/b/1/brand");
    const also = await screen.findByRole("navigation", { name: "Also in this brand" });
    expect(within(also).getAllByRole("link").map((l) => [l.textContent, l.getAttribute("href")])).toEqual([["Products", "/b/1/library/products"], ["Cast & places", "/b/1/library/characters"], ["B-roll and footage", "/b/1/library/footage"], ["Media", "/b/1/media"], ["Scripts", "/b/1/scripts"]]);
    for (const link of within(also).getAllByRole("link")) expect(link).toHaveClass("min-h-control"); // 44 px on a phone
    await userEvent.click(within(also).getByRole("link", { name: "Scripts" }));
    expect(await screen.findByRole("heading", { name: "Scripts" })).toBeInTheDocument();
    cleanup();
    vi.unstubAllGlobals();
  }
});

test("with no brands there is an empty state, not a blank page", async () => {
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, []] });
  renderAt("/b/1");
  expect(await screen.findByRole("heading", { name: "No brands yet" })).toBeInTheDocument();
  expect(screen.getByText(/The owner adds brands/)).toBeInTheDocument();
});

test("offline, a banner says nothing was lost", async () => {
  vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []] });
  renderAt("/b/1/projects");
  expect(await screen.findByText("You're offline.")).toBeInTheDocument();
  expect(screen.getByText("Reconnect to keep working; nothing was lost.")).toBeInTheDocument();
});

test("a waiting invite has Copy a new link: it asks for a fresh link and copies it, and says the old one stops working", async () => {
  const calls = fakeServer({
    "GET /auth/me": [200, owner],
    "GET /brands": [200, brands],
    "GET /team/members": [200, members],
    "GET /team/invites": [200, [{ id: 3, email: "jo@b.co", role: "editor", expires_at: "2026-10-31T12:00:00Z" }]],
    "POST /team/invites/3/link": [200, { id: 3, email: "jo@b.co", role: "editor", expires_at: "2026-11-01T12:00:00Z", token: "fresh9" }],
  });
  renderAt("/team");
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.assign(navigator, { clipboard: { writeText } });
  await userEvent.click(await screen.findByRole("button", { name: "Copy a new link for jo@b.co" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /team/invites/3/link")).toBe(true));
  await vi.waitFor(() => expect(writeText).toHaveBeenCalledWith(`${location.origin}/invite/fresh9`));
  expect(await screen.findByText("Link copied. The old link no longer works.")).toBeInTheDocument();
});

test("if the clipboard says no, the fresh link is shown in a read-only field to copy by hand", async () => {
  fakeServer({
    "GET /auth/me": [200, owner],
    "GET /brands": [200, brands],
    "GET /team/members": [200, members],
    "GET /team/invites": [200, [{ id: 3, email: "jo@b.co", role: "editor", expires_at: "2026-10-31T12:00:00Z" }]],
    "POST /team/invites/3/link": [200, { id: 3, email: "jo@b.co", role: "editor", expires_at: "2026-11-01T12:00:00Z", token: "fresh9" }],
  });
  renderAt("/team");
  Object.assign(navigator, { clipboard: { writeText: vi.fn().mockRejectedValue(new Error("no")) } });
  await userEvent.click(await screen.findByRole("button", { name: "Copy a new link for jo@b.co" }));
  const field = await screen.findByLabelText("Invite link for jo@b.co");
  expect(field).toHaveValue(`${location.origin}/invite/fresh9`);
  expect(field).toHaveAttribute("readonly");
});

test("an editor's brand menu lists the brands, with no New brand and no owner-only note", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []] });
  renderAt("/");
  await userEvent.click(await screen.findByRole("button", { name: /^Brand: / }));
  expect(await within(screen.getByRole("menu")).findByText("Iron Paws")).toBeInTheDocument();
  expect(screen.queryByText("Brands are set up by the owner.")).toBeNull();
  expect(screen.queryByRole("menuitem", { name: "New brand" })).toBeNull();
});

test("Reed's New brand is its own page: a name, a colour, and it opens the Brand kit", async () => {
  setViewport(1440);
  const calls = fakeServer({
    "GET /auth/me": [200, owner],
    "GET /brands": [200, brands],
    "GET /scripts": [200, []],
    "GET /projects": [200, []],
    "POST /brands": [201, { id: 9, name: "Night Owl", colours: ["#2F6B4F"] }],
    "GET /brands/9/screens": [200, []],
  });
  renderAt("/");
  await userEvent.click(await screen.findByRole("button", { name: /^Brand: / }));
  await userEvent.click(screen.getByRole("menuitem", { name: "New brand" }));
  const form = await screen.findByRole("form", { name: "New brand" });
  expect(within(form).getByRole("button", { name: "Make the brand" })).toHaveAccessibleDescription("Give it a name first");
  await userEvent.type(within(form).getByLabelText("Name"), "Night Owl");
  const colour = within(form).getByLabelText("Colour");
  await userEvent.clear(colour);
  await userEvent.type(colour, "#2f6b4f");
  await userEvent.click(within(form).getByRole("button", { name: "Make the brand" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /brands")?.body).toMatchObject({ name: "Night Owl", colours: ["#2F6B4F"] }));
  expect(await screen.findByText("Night Owl is ready. Add its look next.")).toBeInTheDocument();
});

test("a brand name that is taken shows the server's words under the field", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "POST /brands": [409, { detail: "A brand with that name already exists." }] });
  renderAt("/brands/new");
  const form = await screen.findByRole("form", { name: "New brand" });
  await userEvent.type(within(form).getByLabelText("Name"), "fomo");
  await userEvent.click(within(form).getByRole("button", { name: "Make the brand" }));
  expect(await within(form).findByText("A brand with that name already exists.")).toBeInTheDocument();
});

test("Studio pages and an editor's My credits keep the full rail, on the first brand when none was picked yet (v5 A_Shell)", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /team/members": [200, members], "GET /team/invites": [200, []] });
  renderAt("/team");
  const nav = await screen.findByRole("navigation", { name: "Main" });
  expect(await within(nav).findByRole("button", { name: "Brand: fomo" })).toBeInTheDocument();
  expect(within(nav).getByRole("link", { name: "Brand" })).toHaveAttribute("href", "/b/1/brand");
  expect(within(nav).getByRole("link", { name: "Cast" })).toBeInTheDocument();
  cleanup();
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, brands], "GET /usage/mine": [200, { credits: 0, quick_clip_credits: 0, script_credits: 0, videos: [], projects: [], scripts: [], sends: [], waiting_credits: 0, week: { used: 0, allowance: 100, lines: [] } }] });
  renderAt("/usage/mine");
  const editorNav = await screen.findByRole("navigation", { name: "Main" });
  expect(await within(editorNav).findByRole("link", { name: "Brand" })).toBeInTheDocument();
  expect(within(editorNav).queryByRole("button", { name: "Choose a brand" })).toBeNull();
});

test("an editor's account menu names their role and how much of the week is left (v5 A_Account)", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, brands], "GET /projects": [200, []], "GET /credits/me": [200, { quick_clip_credits_used: 58, quick_clip_credits_allowed: 200, resets_on: "2026-11-09", projects: [] }] });
  renderAt("/b/1/projects");
  await userEvent.click(await screen.findByRole("button", { name: "Account menu" }));
  const menu = screen.getByRole("menu", { name: "Account" });
  expect(within(menu).getByText("· Editor")).toBeInTheDocument();
  expect(await within(menu).findByText("142 of 200 left")).toBeInTheDocument();
});

test("the rail's account row says Owner, and the brand menu has a Brands heading over colour squares (v5 A_Shell, A_Account)", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []] });
  renderAt("/b/1/projects");
  const rail = await screen.findByRole("navigation", { name: "Main" });
  expect(await within(rail).findByRole("button", { name: "Account menu" })).toHaveTextContent("Reed"); // S0-01: the name and a gear
  await userEvent.click(within(rail).getByRole("button", { name: "Brand: fomo" }));
  const menu = await screen.findByRole("menu", { name: "Brands" });
  expect(within(menu).getByText("Brands")).toBeInTheDocument();
  expect(menu.querySelector("span[aria-hidden].rounded-\\[3px\\]")).toHaveStyle({ background: "#ff5500" });
  const squares = menu.querySelectorAll("span[aria-hidden].rounded-\\[3px\\]");
  expect((squares[1] as HTMLElement).style.background).toBe("var(--accent)"); // Iron Paws has no colour: the accent, as the Brand page
});
