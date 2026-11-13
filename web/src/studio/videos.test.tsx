import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { owner } from "../test/people";
import { renderApp } from "../test/render";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

// The brand's videos in the new look (/s/b/1/videos): what it shows, and exactly what each press sends. Every request
// is one the current site sends for the same press, with the same body (the PR lists them side by side). Opening the
// page, on any of its states, only reads.
const NOW = new Date("2026-11-13T12:30:00Z");
const midnight = new Date(NOW);
midnight.setHours(0, 0, 0, 0);
const at = (ms: number) => new Date(ms).toISOString();
const TODAY = at(NOW.getTime() - 60_000), YESTERDAY = at(midnight.getTime() - 3_600_000), EARLIER = at(midnight.getTime() - 5 * 86_400_000);

const status = (kind: string, words: string, reason: string | null = null, made = 0, total = 0) => ({ kind, words, reason, at: kind === "archived" ? EARLIER : null, made, total });
const idea = (id: number, title: string, o: object = {}) => ({ id, title, folder_id: null, status: status("delivered", "Delivered"), still_file_id: null, look: "movie", style: "Movie", seconds: 30, made_by: null, created_at: EARLIER, updated_at: EARLIER, cost: null, can_manage: true, from_script: false, ...o });
const target = idea(366, "Three men at Target", { folder_id: 4, status: status("working", "Working", "9 of 23", 9, 23), still_file_id: 81, seconds: 398, updated_at: TODAY, cost: { kind: "so_far", credits: 401, usd: 41.2 } });
const stroller = idea(505, "The stroller in aisle nine", { status: status("needs_you", "Needs you", "Approve the plan"), updated_at: TODAY, cost: { kind: "up_to", credits: 164, usd: 16.86 } });
const dad = idea(501, "A dad on the border", { look: "ugc", style: "UGC", seconds: 19, updated_at: TODAY, cost: { kind: "total", credits: 70, usd: 7.2 } });
const dana = idea(373, "Dana gets the call", { folder_id: 4, look: "pixar", style: "Pixar", updated_at: YESTERDAY });
const boot = idea(377, "The boot by the cart");
const gone = idea(390, "An early cut", { status: status("archived", "Archived") });
const ALL = [target, stroller, dad, dana, boot];

const page = (list: object[], o: object = {}) => ({ total: list.length, counts: { all: list.length, needs_you: 0, working: 0, delivered: 0 }, archived: 0, folders_inside: 0, makers: [], ideas: list, ...o });
const branch = (id: number | null, name: string, count: number) => ({ id, parent_id: null, name, count, can_manage: id != null, ideas: [], more: 0, folders: [] });
const TREE = { folders: [branch(4, "Target ads", 2), branch(7, "Winter", 0)], unsorted: branch(null, "Unsorted", 3) };
/** The list's own request, as the current site's hook asks it: a folder ("all": the brand), a page of 60, then what narrows it. */
const list = (folder: string, more = "", offset = 0, brand = 1) => `GET /brands/${brand}/ideas?folder=${folder}&tab=all&sort=newest&offset=${offset}&limit=60${more}`;
type Routes = Record<string, [number, unknown]>;
const routes = (extra: Routes = {}): Routes => ({
  "GET /auth/me": [200, owner],
  "GET /brands": [200, [{ id: 1, name: "Palace Guard", colours: ["#ef8a3c"] }, { id: 2, name: "Iron Paws", colours: [] }]],
  "GET /workspace": [200, { id: 1, name: "Night Shift Studio" }],
  "GET /brands/1/tree": [200, TREE],
  [list("all")]: [200, page(ALL, { archived: 1 })],
  [list("all", "&archived=true")]: [200, page([gone], { counts: { all: 5, needs_you: 0, working: 0, delivered: 0 }, archived: 1 })],
  [list("all", "&q=rose")]: [200, page([], { counts: { all: 5, needs_you: 0, working: 0, delivered: 0 } })],
  [list("4")]: [200, page([target, dana])],
  [list("7")]: [200, page([])],
  "GET /brands/2/tree": [200, { folders: [], unsorted: branch(null, "Unsorted", 0) }],
  [list("all", "", 0, 2)]: [200, page([])],
  ...extra,
});
async function open(path = "", extra: Routes = {}) {
  const calls = fakeServer(routes(extra));
  renderApp(`/s/b/1/videos${path}`);
  await within(await screen.findByRole("main")).findByRole("group", { name: "Group by" });
  return calls;
}
/** Everything the page has sent that isn't a read: its method and path, and its body. */
const sent = (calls: ReturnType<typeof fakeServer>) => calls.filter((c) => !c.key.startsWith("GET ")).map((c) => (c.body === undefined ? [c.key] : [c.key, c.body]));
const main = () => within(screen.getByRole("main"));
const rail = () => within(screen.getByRole("navigation", { name: "Main" }));
const group = (name: string) => within(main().getByRole("region", { name }));
const card = (name: RegExp) => main().findByRole("link", { name });
const more = async (title: string) => userEvent.click(await main().findByRole("button", { name: `More for ${title}` }));
const item = (name: string) => userEvent.click(screen.getByRole("menuitem", { name }));
const undo = () => userEvent.click(screen.getByRole("button", { name: "Undo" }));
/** The groups on the page, in order, once it has them (a press that changes the address is drawn a moment later). */
const groups = (names: string[]) => waitFor(() => expect(main().getAllByRole("region").map((r) => r.getAttribute("aria-label"))).toEqual(names));

beforeEach(() => {
  localStorage.clear();
  setViewport(1440);
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

test("the brand's videos are poster cards under Being made, Today, Yesterday and Earlier; each has its look, cost and when as the list gives them, and opens the video in the new look", async () => {
  await open();
  expect(await card(/Three men at Target/)).toHaveAttribute("href", "/s/b/1/videos/366");
  const making = group("Being made");
  expect(making.getByRole("heading")).toHaveTextContent("Being made2 videos");
  expect(making.getByRole("link", { name: /Three men at Target/ })).toHaveTextContent("6:38Three men at TargetWorking · 9 of 23Movie · $41.20 so far · 1 min ago"); // its progress, in the server's words
  expect(making.getByRole("link", { name: /The stroller in aisle nine/ })).toHaveTextContent("Needs you · Approve the planMovie · up to $16.86 · 1 min ago");
  expect(making.getByRole("link", { name: /Three men at Target/ }).querySelector("img")).toHaveAttribute("src", "/api/files/81");
  expect(group("Today").getByRole("link", { name: /A dad on the border/ })).toHaveTextContent("0:19A dad on the borderUGC · $7.20 · 1 min ago"); // delivered: no status line
  expect(group("Yesterday").getByRole("link", { name: /Dana gets the call/ })).toHaveTextContent(/^0:30Dana gets the callPixar · /); // no cost given: none shown
  expect(group("Earlier").getByRole("link", { name: /The boot by the cart/ })).toBeInTheDocument();
  expect(main().getByRole("link", { name: "New video" })).toHaveAttribute("href", "/s/b/1");
  expect(rail().getByRole("link", { name: "Videos", current: "page" })).toHaveAttribute("href", "/s/b/1/videos");
});

test("Being made and Delivered narrow the cards, and Look regroups them by look and is remembered", async () => {
  await open();
  await card(/A dad on the border/);
  const show = within(main().getByRole("group", { name: "Show" }));
  await userEvent.click(show.getByRole("button", { name: "Being made" }));
  await groups(["Being made"]);
  await userEvent.click(show.getByRole("button", { name: "Delivered" }));
  await groups(["Today", "Yesterday", "Earlier"]);
  await userEvent.click(show.getByRole("button", { name: "All" }));
  await userEvent.click(within(main().getByRole("group", { name: "Group by" })).getByRole("button", { name: "Look" }));
  await groups(["Movie", "UGC", "Pixar"]);
  expect(group("Movie").getByRole("heading")).toHaveTextContent("Movie3 videos");
  expect(localStorage.getItem("bs.videos.group")).toBe("look");
});

test("the whole list is read, 60 at a time, so no video is hidden", async () => {
  const sixty = Array.from({ length: 60 }, (_, k) => idea(1000 + k, `Video ${k + 1}`));
  const calls = await open("", { [list("all")]: [200, page(sixty, { total: 61 })], [list("all", "", 60)]: [200, page([boot], { total: 61 })] });
  expect(await card(/The boot by the cart/)).toBeInTheDocument();
  expect(group("Earlier").getByRole("heading")).toHaveTextContent("Earlier61 videos");
  expect(new Set(calls.filter((c) => c.key === "GET /brands/1/ideas").map((c) => new URL(c.url).searchParams.get("offset")))).toEqual(new Set(["0", "60"]));
});

test("search asks the server by title, says so when nothing matches, and clears", async () => {
  const calls = await open();
  await userEvent.type(main().getByRole("searchbox", { name: "Search videos" }), "rose");
  expect(await main().findByText("Nothing matches “rose”.")).toBeInTheDocument();
  expect(calls.some((c) => c.url.endsWith(list("all", "&q=rose").replace("GET ", "/api")))).toBe(true);
  await userEvent.click(main().getByRole("button", { name: "Clear the search" }));
  expect(await card(/A dad on the border/)).toBeInTheDocument();
});

test("a folder picked in the rail shows its own videos under its name", async () => {
  await open("?folder=4");
  expect(main().getByRole("heading", { level: 1, name: "Target ads" })).toBeInTheDocument();
  expect(main().getByRole("link", { name: "Videos" })).toHaveAttribute("href", "/s/b/1/videos");
  expect(await card(/Dana gets the call/)).toBeInTheDocument();
  expect(main().queryByRole("link", { name: /A dad on the border/ })).toBeNull();
  expect(within(rail().getByRole("group", { name: "Folders" })).getByRole("link", { name: /Target ads/, current: "page" })).toHaveTextContent("2");
});

test("a folder that isn't there any more says so, with the way back to every video", async () => {
  fakeServer(routes({ [list("99")]: [404, { detail: "That folder doesn't exist." }] }));
  renderApp("/s/b/1/videos?folder=99");
  expect(await screen.findByRole("alert")).toHaveTextContent("This folder isn’t here any more. It may have been deleted. Open all videos");
  expect(main().getByRole("link", { name: "Open all videos" })).toHaveAttribute("href", "/s/b/1/videos");
});

test("a brand with no videos has one next step: make the first", async () => {
  fakeServer(routes());
  renderApp("/s/b/2/videos");
  expect(await screen.findByText("No videos in Iron Paws yet")).toBeInTheDocument();
  expect(main().getByRole("link", { name: "Make the first video" })).toHaveAttribute("href", "/s/b/2");
  expect(main().queryByRole("searchbox")).toBeNull();
});

test("an empty folder says how to fill it", async () => {
  await open("?folder=7");
  expect(await main().findByText("Nothing in Winter yet")).toBeInTheDocument();
  expect(main().getByText(/Pick it under/)).toHaveTextContent("Pick it under “Move to” in a video’s menu, or drag a video onto the folder on the left. When you make a video, choose it under “Save in”.");
});

test("a new folder is typed straight into the rail: Enter makes it at the top level", async () => {
  const calls = await open("", { "POST /brands/1/folders": [201, { id: 9, brand_id: 1, parent_id: null, name: "Winter ads", created_by_id: 1, items: { scripts: 0, videos: 0, clips: 0, footage: 0 }, can_manage: true }] });
  await userEvent.click(rail().getByRole("button", { name: "New folder" }));
  await userEvent.type(rail().getByRole("textbox", { name: "New folder name" }), " Winter ads {Enter}");
  expect(await screen.findByText("“Winter ads” is ready. Drag a video onto it, or use “Move to” in a video’s menu.")).toBeInTheDocument();
  expect(sent(calls)).toEqual([["POST /brands/1/folders", { name: "Winter ads", parent_id: null }]]);
  await waitFor(() => expect(rail().queryByRole("textbox")).toBeNull());
});

test("a new folder the server refuses shows the server's own words and keeps what was typed", async () => {
  await open("", { "POST /brands/1/folders": [409, { detail: "There's already a folder called Winter here." }] });
  await userEvent.click(rail().getByRole("button", { name: "New folder" }));
  await userEvent.type(rail().getByRole("textbox", { name: "New folder name" }), "Winter{Enter}");
  expect(await screen.findByText("There's already a folder called Winter here.")).toBeInTheDocument();
  expect(rail().getByRole("textbox", { name: "New folder name" })).toHaveValue("Winter");
});

test("a folder's menu renames it", async () => {
  const calls = await open("?folder=4", { "PATCH /folders/4": [200, {}] });
  await userEvent.click(main().getByRole("button", { name: "More for this folder" }));
  await item("Rename…");
  const name = within(screen.getByRole("dialog", { name: "Rename this folder" })).getByRole("textbox", { name: "Name" });
  expect(name).toHaveValue("Target ads");
  await userEvent.clear(name);
  await userEvent.type(name, "Target{Enter}");
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(sent(calls)).toEqual([["PATCH /folders/4", { name: "Target" }]]);
});

test("a folder's menu deletes it: its videos go to Unsorted, the page goes back to every video, and Undo restores it", async () => {
  const calls = await open("?folder=4", { "DELETE /folders/4": [200, { moved: 2, ideas: 2 }], "POST /folders/4/restore": [200, {}] });
  await userEvent.click(main().getByRole("button", { name: "More for this folder" }));
  await userEvent.click(screen.getByRole("menuitem", { name: /Delete folder/ }));
  expect(await screen.findByText("“Target ads” is gone. Its 2 videos moved to Unsorted.")).toBeInTheDocument();
  expect(await main().findByRole("heading", { level: 1, name: "Videos" })).toBeInTheDocument();
  await undo();
  await waitFor(() => expect(sent(calls)).toEqual([["DELETE /folders/4"], ["POST /folders/4/restore"]]));
});

test("a card's menu renames the video: one made from a paste by its send's title, an earlier one by its own name, and Undo puts the name back", async () => {
  const calls = await open("", { "GET /projects/501": [200, { id: 501, freestyle_id: 9 }], "GET /projects/377": [200, { id: 377, freestyle_id: null }], "PATCH /freestyles/9": [200, {}], "PATCH /projects/377": [200, {}] });
  const rename = async (title: string, to: string) => {
    await more(title);
    await item("Rename…");
    const name = within(await screen.findByRole("dialog", { name: "Rename this video" })).getByRole("textbox", { name: "Name" });
    expect(name).toHaveValue(title);
    await userEvent.clear(name);
    await userEvent.type(name, `${to}{Enter}`);
    expect(await screen.findByText(`Renamed to “${to}”.`)).toBeInTheDocument();
  };
  await rename("A dad on the border", "A dad at the wall");
  await undo();
  await rename("The boot by the cart", "The boot");
  expect(sent(calls)).toEqual([
    ["PATCH /freestyles/9", { title: "A dad at the wall" }],
    ["PATCH /freestyles/9", { title: "A dad on the border" }],
    ["PATCH /projects/377", { name: "The boot" }],
  ]);
});

test("a card's menu moves the video to a folder, the one it is in ticked, and Undo moves it back", async () => {
  const calls = await open("", { "POST /folders/file": [200, { folder_id: 4, was: [{ id: 501, folder_id: null }] }] });
  await more("A dad on the border");
  expect(screen.getByRole("menuitemradio", { name: "Unsorted" })).toHaveAttribute("aria-checked", "true");
  await userEvent.click(screen.getByRole("menuitemradio", { name: "Target ads" }));
  expect(await screen.findByText('Moved "A dad on the border".')).toBeInTheDocument();
  await undo();
  await waitFor(() =>
    expect(sent(calls)).toEqual([
      ["POST /folders/file", { kind: "video", ids: [501], folder_id: 4 }],
      ["POST /folders/file", { kind: "video", ids: [501], folder_id: null }],
    ]),
  );
});

test("a card dragged onto a folder in the rail is filed there, and Undo files it back", async () => {
  const calls = await open("", { "POST /folders/file": [200, { folder_id: 4, was: [{ id: 501, folder_id: null }] }] });
  const carried: Record<string, string> = {};
  const data = { get types() { return Object.keys(carried); }, setData: (k: string, v: string) => void (carried[k] = v), getData: (k: string) => carried[k] ?? "", dropEffect: "", effectAllowed: "" };
  const folder = rail().getByRole("link", { name: /Target ads/ });
  fireEvent.dragStart(await card(/A dad on the border/), { dataTransfer: data });
  expect(rail().getByRole("group", { name: "Folders" })).toHaveClass("drop"); // every folder lights up as a place to drop it
  fireEvent.dragOver(folder, { dataTransfer: data });
  expect(folder).toHaveClass("over");
  fireEvent.drop(folder, { dataTransfer: data });
  expect(await screen.findByText("Moved “A dad on the border” to Target ads.")).toBeInTheDocument();
  expect(folder).not.toHaveClass("over");
  await undo();
  await waitFor(() =>
    expect(sent(calls)).toEqual([
      ["POST /folders/file", { kind: "video", ids: [501], folder_id: 4 }],
      ["POST /folders/file", { kind: "video", ids: [501], folder_id: null }],
    ]),
  );
});

test("a card's menu archives the video after a yes, the list is read again, and Undo restores it", async () => {
  const calls = await open("", { "POST /projects/501/archive": [200, {}], "POST /projects/501/restore": [200, {}] });
  await more("A dad on the border");
  await item("Archive");
  const ask = within(screen.getByRole("dialog", { name: "Archive “A dad on the border”?" }));
  expect(ask.getByText(/It leaves the lists\. Its clips and downloads are kept, and you can restore it\./)).toBeInTheDocument();
  expect(sent(calls)).toEqual([]); // nothing until the yes
  const reads = () => calls.filter((c) => c.key === "GET /brands/1/ideas").length;
  const before = reads();
  await userEvent.click(ask.getByRole("button", { name: "Archive" }));
  expect(await screen.findByText('Archived "A dad on the border".')).toBeInTheDocument();
  expect(reads()).toBeGreaterThan(before);
  await undo();
  expect(await screen.findByText('Brought back "A dad on the border".')).toBeInTheDocument();
  expect(sent(calls)).toEqual([["POST /projects/501/archive"], ["POST /projects/501/restore"]]);
});

test("Archived is one quiet press: its videos each have Restore, and Undo archives it again", async () => {
  const calls = await open("", { "POST /projects/390/restore": [200, {}], "POST /projects/390/archive": [200, {}] });
  const quiet = await main().findByRole("button", { name: "Archived 1" });
  await userEvent.click(quiet);
  expect(await card(/An early cut/)).toHaveTextContent(/Archived \d+ Nov/);
  expect(main().queryByRole("button", { name: "More for An early cut" })).toBeNull();
  await userEvent.click(main().getByRole("button", { name: "Restore" }));
  expect(await screen.findByText('Brought back "An early cut".')).toBeInTheDocument();
  await undo();
  await waitFor(() => expect(sent(calls)).toEqual([["POST /projects/390/restore"], ["POST /projects/390/archive"]]));
});

test.each([
  ["every video", "/s/b/1/videos", "A dad on the border"],
  ["being made", "/s/b/1/videos?show=making", "Three men at Target"],
  ["a folder", "/s/b/1/videos?folder=4", "Dana gets the call"],
  ["an empty folder", "/s/b/1/videos?folder=7", "Nothing in Winter yet"],
  ["a brand with no videos", "/s/b/2/videos", "No videos in Iron Paws yet"],
  ["the archived", "/s/b/1/videos?show=archived", "An early cut"],
  ["a search with no results", "/s/b/1/videos?q=rose", "Nothing matches “rose”."],
])("opening the page on %s only reads: nothing is sent without a press", async (_name, path, shows) => {
  const calls = fakeServer(routes());
  renderApp(path);
  expect(await within(await screen.findByRole("main")).findByText(shows)).toBeInTheDocument();
  await rail().findByRole("link", { name: /Unsorted/ });
  await new Promise((r) => setTimeout(r, 400)); // past the search's pause, and any read that follows the first
  expect(calls.length).toBeGreaterThan(3);
  expect(sent(calls)).toEqual([]);
});
