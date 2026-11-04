import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { editor, owner } from "../test/people";

const status = (kind: string, words: string, extra: object = {}) => ({ kind, words, reason: null, at: null, made: 0, total: 0, ...extra });
const idea = (o: object) => ({
  id: 9, title: "Beer gut doctor rant", folder_id: 4, status: status("working", "Working", { reason: "14 of 24", made: 14, total: 24 }), still_file_id: null, look: "dr-pickle", style: "Dr. Pickle", seconds: 60,
  made_by: { id: 1, name: "Reed" }, created_at: "2026-11-03T10:00:00Z", updated_at: new Date(Date.now() - 10 * 60_000).toISOString(), cost: { kind: "up_to", credits: 164, usd: 16.86 }, can_manage: true, from_script: true, ...o,
});
const branch = (o: object) => ({ id: 4, parent_id: null, name: "Week of 3 Nov", count: 2, can_manage: true, ideas: [], more: 0, folders: [], ...o });
const tree = { folders: [branch({}), branch({ id: 5, name: "UGC testimonials", count: 0 })], unsorted: branch({ id: null, name: "Unsorted", count: 1 }) };
const page = (ideas: object[], o: object = {}) => ({ total: ideas.length, counts: { all: ideas.length, needs_you: 1, working: 1, delivered: 0 }, archived: 0, folders_inside: 0, makers: [{ id: 1, name: "Reed" }], ideas, ...o });
const two = [idea({}), idea({ id: 10, title: "Bloated after pizza", status: status("needs_you", "Needs you", { reason: "Check the scene plan" }), cost: { kind: "so_far", credits: 4.09, usd: 0.42 }, made_by: { id: 2, name: "Kel" }, can_manage: false })];
const base = (me: object, ideas: object = page(two), extra: Record<string, [number, unknown]> = {}): Record<string, [number, unknown]> => ({
  "GET /auth/me": [200, me],
  "GET /brands": [200, [{ id: 1, name: "Resilia", colours: ["#1f7a4f"], dont_list: [], do_list: [], cta_lines: [], audience: "" }, { id: 2, name: "fomo", colours: [] }]],
  "GET /brands/1/tree": [200, tree],
  "GET /brands/1/ideas": [200, ideas],
  "GET /jobs": [200, []],
  "GET /projects": [200, []],
  ...extra,
});
function open(at = "/b/1/videos?folder=4") {
  render(
    <StrictMode>
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={[at]}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>
    </StrictMode>,
  );
}
afterEach(() => vi.unstubAllGlobals());
const asked = (calls: { key: string; url: string }[]) => calls.filter((c) => c.key === "GET /brands/1/ideas").map((c) => Object.fromEntries(new URL(c.url).searchParams));

test("an open folder (S1-04): the crumb and its counts, tabs, and each idea's still, status with its reason, style · length · who · when and cost", async () => {
  setViewport(1440);
  const calls = fakeServer(base(owner));
  open();
  expect(await screen.findByText("2 video ideas · 1 needs you")).toBeInTheDocument();
  expect(within(screen.getByRole("main")).getByText("Week of 3 Nov")).toBeInTheDocument();
  const card = screen.getByRole("link", { name: /Beer gut doctor rant/ });
  expect(card).toHaveAttribute("href", "/b/1/videos/9");
  expect(within(card).getByText("Working · 14 of 24")).toBeInTheDocument();
  expect(within(card).getByText("Dr. Pickle · 60 s · Reed · 10 min ago")).toBeInTheDocument();
  expect(within(card).getByText("up to $16.86")).toBeInTheDocument();
  expect(within(screen.getByRole("link", { name: /Bloated after pizza/ })).getByText("$0.42 so far")).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "All 2" })).toHaveAttribute("aria-selected", "true");
  expect(within(screen.getByRole("main")).getByRole("link", { name: "New video" })).toHaveAttribute("href", "/b/1/videos/new?folder=4"); // new ideas land in the open folder
  await userEvent.click(screen.getByRole("tab", { name: "Needs you 1" }));
  await vi.waitFor(() => expect(asked(calls).at(-1)).toMatchObject({ folder: "4", tab: "needs_you", sort: "newest" }));
  await userEvent.click(screen.getByRole("button", { name: /Sort/ }));
  await userEvent.click(screen.getByRole("menuitemradio", { name: "Name A–Z" }));
  await vi.waitFor(() => expect(asked(calls).at(-1)).toMatchObject({ sort: "name" }));
});

test("an editor sees credits, never dollars, and only their own ideas can be ticked (S1-08)", async () => {
  setViewport(1440);
  const theirs = [idea({ cost: { kind: "up_to", credits: 163.2, usd: null } }), idea({ id: 10, title: "Kel's own", cost: { kind: "total", credits: 70.04, usd: null }, can_manage: true }), idea({ id: 11, title: "Sam's", cost: { kind: "so_far", credits: 4, usd: null }, can_manage: false })];
  fakeServer(base(editor, page(theirs)));
  open();
  expect(await screen.findByText("up to 164 cr")).toBeInTheDocument(); // a most is never rounded down
  expect(screen.getByText("70 cr")).toBeInTheDocument();
  expect(screen.getByRole("main").textContent).not.toContain("$");
  expect(screen.getByRole("checkbox", { name: "Select Kel's own" })).toBeInTheDocument();
  expect(screen.queryByRole("checkbox", { name: "Select Sam's" })).toBeNull();
});

test("several selected move together with Undo, and archive together (S1-07)", async () => {
  setViewport(1440);
  const calls = fakeServer(base(owner, page(two.map((i) => ({ ...i, can_manage: true }))), {
    "POST /folders/file": [200, { folder_id: 5, was: [{ id: 9, folder_id: 4 }, { id: 10, folder_id: 4 }] }],
    "POST /projects/9/archive": [200, {}],
    "POST /projects/10/archive": [200, {}],
  }));
  open();
  await userEvent.click(await screen.findByRole("checkbox", { name: "Select Beer gut doctor rant" }));
  await userEvent.click(screen.getByRole("checkbox", { name: "Select Bloated after pizza" }));
  const bar = screen.getByRole("region", { name: "Selected ideas" });
  expect(within(bar).getByText("2 selected")).toBeInTheDocument();
  await userEvent.click(within(bar).getByRole("button", { name: "Move to…" }));
  const menu = screen.getByRole("menu", { name: "Move 2 ideas to" });
  expect(within(menu).queryByRole("menuitem", { name: "Week of 3 Nov" })).toBeNull(); // not where they are
  await userEvent.click(within(menu).getByRole("menuitem", { name: "UGC testimonials" }));
  expect(await screen.findByText("Moved 2 ideas to UGC testimonials.")).toBeInTheDocument();
  expect(calls.find((c) => c.key === "POST /folders/file")?.body).toEqual({ kind: "video", ids: [9, 10], folder_id: 5 });
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /folders/file").at(-1)?.body).toEqual({ kind: "video", ids: [9, 10], folder_id: 4 }));

  await userEvent.click(screen.getByRole("checkbox", { name: "Select Beer gut doctor rant" }));
  await userEvent.click(within(screen.getByRole("region", { name: "Selected ideas" })).getByRole("button", { name: "Archive" }));
  expect(await screen.findByText("Archived 1 idea.")).toBeInTheDocument();
});

test("a big folder opens as a list with Made by, and pages as it scrolls (S1-05)", async () => {
  setViewport(1440);
  fakeServer(base(owner, page(two, { total: 124, counts: { all: 124, needs_you: 3, working: 1, delivered: 112 }, folders_inside: 2 })));
  open();
  expect(await screen.findByText("124 video ideas · 2 folders inside")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Made by/ })).toHaveTextContent("Made by Anyone");
  expect(screen.getByPlaceholderText("Search 124 ideas")).toBeInTheDocument();
  expect(screen.getByText("Showing 1–2 of 124")).toBeInTheDocument();
  expect(screen.getByText("Scroll for more · the list loads as you go")).toBeInTheDocument();
});

test("the folder's ⋯ holds its actions and Archived ideas; Archived lists them with Restore (S1-06, S-gaps-02)", async () => {
  setViewport(1440);
  const gone = idea({ id: 12, title: "Old hangover cure", status: status("archived", "Archived", { at: "2026-10-28T10:00:00Z" }) });
  fakeServer({ ...base(owner, page(two, { archived: 1 })), "GET /brands/1/ideas?folder=4&tab=all&sort=newest&offset=0&limit=60&archived=true": [200, page([gone], { archived: 1 })], "POST /projects/12/restore": [200, {}] });
  open();
  await userEvent.click(await within(await screen.findByRole("main")).findByRole("button", { name: "More for Week of 3 Nov" }));
  const menu = screen.getByRole("menu", { name: "Week of 3 Nov" });
  expect(within(menu).getAllByRole("menuitem").map((m) => m.textContent?.trim())).toEqual(["New folder inside", "Rename", "Move to…", "Delete folder…", "Archived ideas1"]);
  await userEvent.click(within(menu).getByRole("menuitem", { name: /Archived ideas/ }));
  expect(await screen.findByText("Archived 28 Oct")).toBeInTheDocument();
  expect(screen.getByText("1 idea · kept, not shown in the folder · their files stay downloadable")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Restore" }));
  await userEvent.click(screen.getByRole("button", { name: "Back to the folder" }));
  expect(await screen.findByRole("tab", { name: "All 2" })).toBeInTheDocument();
});

test("deleting a folder says where its ideas go, and Undo brings it back", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base(owner), "DELETE /folders/4": [200, { moved: 2, ideas: 2 }], "POST /folders/4/restore": [200, {}] });
  open();
  await userEvent.click(await within(await screen.findByRole("main")).findByRole("button", { name: "More for Week of 3 Nov" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Delete folder…" }));
  const ask = screen.getByRole("alertdialog", { name: "Delete Week of 3 Nov?" });
  expect(ask).toHaveTextContent("Its 2 ideas move to Unsorted. Nothing is deleted, and Undo brings it back.");
  await userEvent.click(within(ask).getByRole("button", { name: "Delete folder" }));
  expect(await screen.findByText("Deleted “Week of 3 Nov”. Its 2 ideas moved to Unsorted.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /folders/4/restore")).toBe(true));
});

test("an empty folder offers a video or a folder inside (S1-03); no folder picked opens Unsorted", async () => {
  setViewport(1440);
  fakeServer(base(owner, page([], { counts: { all: 0, needs_you: 0, working: 0, delivered: 0 } })));
  open("/b/1/videos?folder=5");
  expect(await screen.findByRole("heading", { name: "Nothing in UGC testimonials yet" })).toBeInTheDocument();
  expect(screen.getByText("Empty")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "New video in UGC testimonials" })).toHaveAttribute("href", "/b/1/videos/new?folder=5");
  expect(screen.getByRole("button", { name: "New folder inside" })).toBeInTheDocument();
});

test("a brand with no ideas and no folders shows its set-up list, ticked from what it has (S1-02)", async () => {
  setViewport(1440);
  fakeServer(base(owner, page([], { counts: { all: 0, needs_you: 0, working: 0, delivered: 0 } }), { "GET /brands/1/tree": [200, { folders: [], unsorted: branch({ id: null, name: "Unsorted", count: 0 }) }], "GET /library/character": [200, [{ id: 1 }]], "GET /library/place": [200, []], "GET /brands/1/screens": [200, []] }));
  open("/b/1/videos");
  expect(await screen.findByRole("heading", { name: "Set up Resilia" })).toBeInTheDocument();
  expect(screen.getByText("Resilia · green")).toBeInTheDocument();
  await vi.waitFor(() => expect(screen.getAllByRole("img", { name: "Done" })).toHaveLength(2)); // name and colour, characters
  expect(screen.getByRole("link", { name: "Make the first video" })).toHaveAttribute("href", "/b/1/videos/new");
  expect(screen.getByText("Each brand is separate: nothing saved here shows up in fomo.")).toBeInTheDocument();
});

test("on a phone (P-02): the folder's name over its counts, all four tabs, two cards a row with style · cost", async () => {
  setViewport(390);
  fakeServer(base(owner));
  open();
  expect(await screen.findByRole("heading", { name: "Week of 3 Nov" })).toBeInTheDocument();
  expect(screen.getByText("Resilia · 2 ideas · 1 needs you")).toBeInTheDocument();
  expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual(["All", "Needs you 1", "Working 1", "Delivered 0"]);
  expect(screen.getByText("Dr. Pickle · up to $16.86")).toBeInTheDocument();
  const sizes = { scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth };
  expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
});

test("Reed's brand still opens on Scripts", async () => {
  setViewport(1440);
  fakeServer({ ...base(owner), "GET /scripts": [200, []], "GET /references": [200, []] });
  open("/b/1");
  expect(await screen.findByRole("heading", { name: "Scripts" })).toBeInTheDocument();
});

test("a folder that's gone says so, with a way to Unsorted (QA on #1304)", async () => {
  setViewport(1440);
  fakeServer({ ...base(owner), "GET /brands/1/ideas": [404, { detail: "No such folder." }] });
  open("/b/1/videos?folder=99");
  expect(await screen.findByText("This folder isn't here any more. It may have been deleted.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open Unsorted" })).toHaveAttribute("href", "/b/1/videos");
});

test("on a phone, press and hold a card to select it, tap more; the dark bar takes the tabs' place (S-gaps-06, 12)", async () => {
  setViewport(390);
  fakeServer(base(owner, page(two.map((i) => ({ ...i, can_manage: true })))));
  open();
  const card = await screen.findByRole("link", { name: /Beer gut doctor rant/ });
  vi.useFakeTimers({ shouldAdvanceTime: true });
  fireEvent.pointerDown(card);
  vi.advanceTimersByTime(600);
  fireEvent.pointerUp(card);
  fireEvent.click(card);
  vi.useRealTimers();
  const bar = await screen.findByRole("region", { name: "Selected ideas" });
  expect(within(bar).getByText("1 selected")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("link", { name: /Bloated after pizza/ })); // a tap adds while selecting
  expect(within(bar).getByText("2 selected")).toBeInTheDocument();
  await userEvent.click(within(bar).getByRole("button", { name: "Clear the selection" }));
  expect(screen.queryByRole("region", { name: "Selected ideas" })).toBeNull();
});

test("an empty Unsorted says where new ideas land, with New video and no folder inside (S-gaps-06, 14)", async () => {
  setViewport(1440);
  fakeServer(base(owner, page([], { counts: { all: 0, needs_you: 0, working: 0, delivered: 0 } })));
  open("/b/1/videos?folder=none");
  expect(await screen.findByRole("heading", { name: "Nothing in Unsorted" })).toBeInTheDocument();
  expect(screen.getByText("New ideas land here until you put them in a folder.")).toBeInTheDocument();
  expect(within(screen.getByRole("main")).getAllByRole("link", { name: "New video" }).length).toBeGreaterThan(0);
  expect(screen.queryByRole("button", { name: "New folder inside" })).toBeNull();
});

test("on a phone, the folder's ⋯ opens under it and Rename edits the name in the top bar (S-gaps-06, 19)", async () => {
  setViewport(390);
  const calls = fakeServer({ ...base(owner), "PATCH /folders/4": [200, {}] });
  open();
  await userEvent.click(await within(await screen.findByRole("main")).findByRole("button", { name: "More for Week of 3 Nov" }));
  expect(screen.getByRole("menu", { name: "Week of 3 Nov" })).toBeInTheDocument(); // a popover, not a sheet
  expect(screen.queryByRole("dialog", { name: "Week of 3 Nov" })).toBeNull();
  await userEvent.click(screen.getByRole("menuitem", { name: "Rename" }));
  const box = screen.getByRole("textbox", { name: "Rename Week of 3 Nov" });
  await userEvent.clear(box);
  await userEvent.type(box, "Week of 10 Nov{Enter}");
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /folders/4")?.body).toEqual({ name: "Week of 10 Nov" }));
});
