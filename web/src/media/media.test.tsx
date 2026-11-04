import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";

const owner = { id: 1, email: "reed@b.co", name: "Reed", role: "owner", workspace_id: 1 };
const editor = { id: 2, email: "e@b.co", name: "Eli", role: "editor", workspace_id: 1 };
const item = (o: object = {}) => ({
  key: "take:3", kind: "take", file_id: 30, content_type: "video/mp4", poster_file_id: 20, made_at: "2026-10-28T10:00:00Z", made_by: { id: 2, name: "Eli" },
  project_id: 9, folder_id: null, video_name: "Bo tries salmon", script_id: null, open_step: "clips", from_deleted_video: false, ...o,
});
const page = (items: object[], next: string | null = null) => ({ items, next });
const base = (me: object, media: object, extra: Record<string, [number, unknown]> = {}): Record<string, [number, unknown]> => ({
  "GET /auth/me": [200, me],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /team/members": [200, [{ id: 1, name: "Reed", email: "reed@b.co", role: "owner" }, { id: 2, name: "Eli", email: "e@b.co", role: "editor" }]],
  "GET /brands/1/media": [200, media],
  ...extra,
});
function open(at = "/b/1/media") {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[at]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
const urls = () => (fetch as unknown as { mock: { calls: [Request | string][] } }).mock.calls.map(([r]) => (typeof r === "string" ? r : r.url));
afterEach(() => vi.unstubAllGlobals());

test("each tile shows its picture, kind chip, when and who, and opens the item (flows OR2)", async () => {
  setViewport(1440);
  fakeServer(base(owner, page([
    item(),
    item({ key: "still:4", kind: "still", file_id: 40, content_type: "image/png", poster_file_id: null, open_step: "storyboard", made_by: { id: 1, name: "Reed" } }),
    item({ key: "quick:5:0", kind: "take", project_id: null, video_name: null, open_step: "quick" }),
    item({ key: "quick:6:0", kind: "take", project_id: null, video_name: null, open_step: "quick", freestyle_id: 4 }),
    item({ key: "song:6", kind: "song", file_id: 60, content_type: "audio/mpeg", poster_file_id: null, project_id: null, video_name: null, script_id: 7, open_step: "song" }),
    item({ key: "sheet:8:0", kind: "sheet", file_id: 80, content_type: "image/png", poster_file_id: null, project_id: null, video_name: null, open_step: "cast", made_by: null }),
  ])));
  open();
  const list = await screen.findByRole("list", { name: "Media" });
  const tiles = within(list).getAllByRole("listitem");
  expect(tiles).toHaveLength(6);
  expect(tiles[0]).toHaveTextContent("Bo tries salmon");
  expect(tiles[0]).toHaveTextContent(/Take · .+ · Eli/);
  expect(tiles[0]).toHaveTextContent("Clip"); // the kind chip on the picture
  expect(tiles[1]).toHaveTextContent("Still");
  expect(tiles[4]).toHaveTextContent("Song");
  expect(tiles[5]).toHaveTextContent("Sheet");
  // A tile is one press to its own page (it has Open in {step} and Download); no buttons on the tile itself.
  expect(within(tiles[0]).getByRole("link", { name: /^Open Bo tries salmon/ })).toHaveAttribute("href", "/b/1/media/take%3A3");
  expect(within(tiles[0]).queryByRole("link", { name: /Download/ })).toBeNull();
  expect(document.body.textContent).not.toMatch(/\$/);
});

test("with nothing made yet it says so and offers New video", async () => {
  setViewport(1440);
  fakeServer(base(editor, page([])));
  open();
  expect(await screen.findByRole("heading", { name: "Nothing made yet in Iron Paws." })).toBeInTheDocument();
  expect(within(screen.getByRole("main")).getByRole("link", { name: "New video" })).toHaveAttribute("href", expect.stringMatching(/^\/b\/\d+\/videos\/new$/));
});

test("the kind tabs ask the server; Video narrows to one video's own media and Oldest first reverses; Clear filters puts them back", async () => {
  setViewport(1440);
  fakeServer(base(owner, page([
    item({ key: "take:3", made_at: "2026-10-28T10:00:00Z" }),
    item({ key: "take:4", made_at: "2026-10-27T10:00:00Z", project_id: 10, video_name: "Cat buys the dip" }),
    item({ key: "quick:5:0", made_at: "2026-10-26T10:00:00Z", project_id: null, video_name: "Haunted fridge", freestyle_id: 4, open_step: "quick" }),
  ])));
  open();
  const names = async () => within(await screen.findByRole("list", { name: "Media" })).getAllByRole("listitem").map((li) => li.querySelector("p")?.textContent);
  expect(await names()).toEqual(["Bo tries salmon", "Cat buys the dip", "Haunted fridge"]);
  await userEvent.click(screen.getByRole("button", { name: "Stills" }));
  await vi.waitFor(() => expect(urls().some((u) => u.includes("/brands/1/media?") && u.includes("kind=still"))).toBe(true));
  expect(screen.getByRole("button", { name: "Stills" })).toHaveAttribute("aria-pressed", "true");
  await userEvent.click(screen.getByRole("button", { name: "All" }));
  await userEvent.click(screen.getByRole("button", { name: "Video" }));
  expect(screen.getAllByRole("menuitemradio").map((o) => o.textContent)).toEqual(["All videos", "Bo tries salmon", "Cat buys the dip", "Haunted fridge"]); // a Freestyle counts as a video
  await userEvent.click(screen.getByRole("menuitemradio", { name: "Haunted fridge" }));
  expect(await names()).toEqual(["Haunted fridge"]);
  await userEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  await userEvent.click(screen.getByRole("button", { name: "Newest first" }));
  await userEvent.click(screen.getByRole("menuitemradio", { name: "Oldest first" }));
  expect(await names()).toEqual(["Haunted fridge", "Cat buys the dip", "Bo tries salmon"]);
  await userEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  expect(await names()).toEqual(["Bo tries salmon", "Cat buys the dip", "Haunted fridge"]);
});

test("Media has no Project or Made by filter (the board draws Video and Newest first only)", async () => {
  setViewport(1440);
  fakeServer(base(owner, page([item()])));
  open();
  await screen.findByRole("list", { name: "Media" });
  expect(screen.queryByRole("button", { name: /^Project/ })).toBeNull();
  expect(screen.queryByRole("button", { name: /Made by/ })).toBeNull();
});

test("a deleted video's media names its maker, and the owner can restore the video", async () => {
  setViewport(1440);
  const calls = fakeServer(base(owner, page([item({ from_deleted_video: true, deleted_video_by: { id: 3, name: "Sam" } })]), { "POST /projects/9/restore": [200, {}] }));
  open();
  const tile = within(await screen.findByRole("list", { name: "Media" })).getByRole("listitem");
  expect(tile).toHaveTextContent("From Sam's deleted video");
  expect(within(tile).queryByRole("link", { name: /Open in/ })).toBeNull();
  await userEvent.click(within(tile).getByRole("button", { name: "Restore the video" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/restore")).toBe(true));
  expect(await screen.findByText("Bo tries salmon is back.")).toBeInTheDocument();
});

test("Restore on Media has Undo: it deletes the video again, the same press as Delete", async () => {
  setViewport(390);
  const calls = fakeServer(base(owner, page([item({ from_deleted_video: true, deleted_video_by: { id: 3, name: "Sam" } })]), { "POST /projects/9/restore": [200, {}], "POST /projects/9/archive": [200, {}] }));
  open();
  await userEvent.click(await within(await screen.findByRole("list", { name: "Media" })).findByRole("button", { name: "Restore the video" }));
  await screen.findByText("Bo tries salmon is back.");
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/archive")).toBe(true));
});

test("Restore on Media of a released video has Undo that releases it again, so its version is back to Ready to make", async () => {
  setViewport(1440);
  const calls = fakeServer(base(owner, page([item({ from_deleted_video: true, deleted_video_by: { id: 3, name: "Sam" }, deleted_video_released: true })]), { "POST /projects/9/restore": [200, {}], "POST /projects/9/release": [200, {}] }));
  open();
  await userEvent.click(await within(await screen.findByRole("list", { name: "Media" })).findByRole("button", { name: "Restore the video" }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/release")).toBe(true));
  expect(calls.some((c) => c.key === "POST /projects/9/archive")).toBe(false);
});

test("the video's maker can restore it from Media too, even on a take someone else made in it", async () => {
  setViewport(390);
  const calls = fakeServer(base(editor, page([item({ from_deleted_video: true, made_by: { id: 3, name: "Sam" }, deleted_video_by: { id: 2, name: "Eli" } })]), { "POST /projects/9/restore": [200, {}] }));
  open();
  const list = await screen.findByRole("list", { name: "Media" });
  expect(within(list).getByText("From your deleted video")).toBeInTheDocument();
  await userEvent.click(within(list).getByRole("button", { name: "Restore the video" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/restore")).toBe(true));
});

test("an editor sees no Restore on someone else's deleted video, even on a take they made in it", async () => {
  setViewport(390);
  fakeServer(base(editor, page([item({ from_deleted_video: true, made_by: { id: 2, name: "Eli" }, deleted_video_by: { id: 3, name: "Sam" } })])));
  open();
  const list = await screen.findByRole("list", { name: "Media" });
  expect(within(list).getByText("From Sam's deleted video")).toBeInTheDocument();
  expect(within(list).queryByRole("button", { name: "Restore the video" })).toBeNull();
});

test("a Video filter with nothing in the pages loaded so far still offers Show more (no dead end)", async () => {
  setViewport(1440);
  fakeServer(base(owner, page([item()], "2026-10-28T10:00:00+00:00|take:3")));
  open("/b/1/media?video=p5");
  expect(await screen.findByText("Nothing matches these filters.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Show more" }));
  await vi.waitFor(() => expect(urls().some((u) => u.includes("before="))).toBe(true));
});

test("Show more asks for the next page", async () => {
  setViewport(1440);
  fakeServer(base(owner, page([item()], "2026-10-28T10:00:00+00:00|take:3")));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Show more" }));
  await vi.waitFor(() => expect(urls().some((u) => u.includes("before="))).toBe(true));
});

test("on a phone the filters open in a sheet, the tabs stay five, and Media opens from the Videos header with < Videos back", async () => {
  setViewport(390);
  fakeServer({ ...base(owner, page([item()])), "GET /projects": [200, []], "GET /scripts": [200, []], "GET /references": [200, []] });
  open("/b/1/videos");
  const tabs = await screen.findByRole("navigation", { name: "Tabs" });
  await vi.waitFor(() => expect(within(tabs).getAllByRole("link")).toHaveLength(5));
  expect(within(tabs).queryByRole("link", { name: /Media/ })).toBeNull();
  await userEvent.click(await screen.findByRole("link", { name: "Media" }));
  await screen.findByRole("list", { name: "Media" });
  expect(within(screen.getByRole("main")).getByRole("link", { name: "Videos" })).toHaveAttribute("href", "/b/1/videos");
  expect(within(screen.getByRole("navigation", { name: "Kinds" })).getByRole("button", { name: "Stills" })).toBeInTheDocument();
});

test("a song tile says which script or video it's from (Next-Layout's 390 walk)", async () => {
  setViewport(390);
  fakeServer(base(owner, page([
    item({ key: "song:6", kind: "song", file_id: 60, content_type: "audio/mpeg", poster_file_id: null, project_id: null, video_name: null, script_id: 7, open_step: "song" }),
    item({ key: "song:9", kind: "song", file_id: 61, content_type: "audio/mpeg", poster_file_id: null, video_name: "Bo tries salmon", open_step: "final" }),
  ]), { "GET /scripts/7": [200, { id: 7, title: "Bowl song", versions: [] }] }));
  open();
  const tiles = within(await screen.findByRole("list", { name: "Media" })).getAllByRole("listitem");
  expect(await within(tiles[0]).findByText("Bowl song")).toBeInTheDocument();
  expect(tiles[0]).toHaveTextContent(/Song from the script/);
  expect(tiles[1]).toHaveTextContent("Bo tries salmon");
  expect(tiles[1]).toHaveTextContent(/Song from the video/);
});

test("a tile opens the item's own page at 390 and desktop: the item, who made it, one press to its video, and Download (v5 G_MediaItem)", async () => {
  for (const width of [1440, 390]) {
    setViewport(width);
    const final = item({ key: "final:3", kind: "final", content_type: "video/mp4", video_name: "Bo tries salmon · A", open_step: "final" });
    fakeServer({ ...base(owner, page([final])), "GET /brands/1/media/final%3A3": [200, final] });
    const { unmount } = renderApp("/b/1/media");
    await userEvent.click(await screen.findByRole("link", { name: /^Open Bo tries salmon · A/ }));
    expect(await screen.findByRole("heading", { name: "Final video", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open its video: Bo tries salmon · A" })).toHaveAttribute("href", "/b/1/videos/9?step=downloads");
    expect(screen.getByRole("link", { name: "Download MP4" })).toHaveAttribute("href", "/api/files/30");
    expect(screen.getByRole("link", { name: "Close" })).toHaveAttribute("href", "/b/1/media");
    expect(within(screen.getByRole("navigation", { name: "Breadcrumb" })).getByRole("link", { name: "Media" })).toHaveAttribute("href", "/b/1/media");
    unmount();
  }
});

test("an item no longer in Media says so in the server's words, with the way back (#1212)", async () => {
  fakeServer({ ...base(owner, page([])), "GET /brands/1/media/final%3A99": [404, { detail: "That's no longer in Media." }] });
  renderApp("/b/1/media/final%3A99");
  expect(await screen.findByText("That's no longer in Media.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Back to Media" })).toHaveAttribute("href", "/b/1/media");
});

test("the owner deletes a final cut from its page, after a check that says its video keeps a copy (#1212)", async () => {
  setViewport(1440);
  const final = item({ key: "final:3", kind: "final", content_type: "video/mp4", video_name: "Bo tries salmon · A", open_step: "final" });
  const calls = fakeServer({ ...base(owner, page([final])), "GET /brands/1/media/final%3A3": [200, final], "DELETE /brands/1/media/final%3A3": [204, null] });
  renderApp("/b/1/media/final%3A3");
  expect(await screen.findByText("Deleting removes it from Media. Its video keeps its own copy.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Delete" }));
  const ask = await screen.findByRole("alertdialog", { name: "Delete this final cut?" });
  await userEvent.click(within(ask).getByRole("button", { name: "Delete" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /brands/1/media/final%3A3")).toBe(true));
  expect(await screen.findByText("Deleted from Media.")).toBeInTheDocument();
});

test("a refused delete says why in plain words; a still has no Delete, and an editor never sees it (#1212)", async () => {
  setViewport(1440);
  const song = item({ key: "song:4", kind: "song", content_type: "audio/mpeg", video_name: null, open_step: "song" });
  fakeServer({ ...base(owner, page([song])), "GET /brands/1/media/song%3A4": [200, song], "DELETE /brands/1/media/song%3A4": [409, { detail: "A video still uses this song." }] });
  const first = renderApp("/b/1/media/song%3A4");
  await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
  await userEvent.click(within(await screen.findByRole("alertdialog", { name: "Delete this song?" })).getByRole("button", { name: "Delete" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("A video still uses this song.");
  first.unmount();
  const still = item({ key: "still:5", kind: "still", content_type: "image/png", open_step: "storyboard" });
  fakeServer({ ...base(owner, page([still])), "GET /brands/1/media/still%3A5": [200, still] });
  const second = renderApp("/b/1/media/still%3A5");
  await screen.findByRole("link", { name: /^Download PNG/ });
  expect(screen.queryByRole("button", { name: "Delete" })).toBeNull();
  second.unmount();
  fakeServer({ ...base(editor, page([song])), "GET /brands/1/media/song%3A4": [200, song] });
  renderApp("/b/1/media/song%3A4");
  await screen.findByRole("link", { name: /^Download MP3/ });
  expect(screen.queryByRole("button", { name: "Delete" })).toBeNull();
});

test("a quick clip's Delete asks about a clip, not a take (QA-3 on #1225)", async () => {
  setViewport(1440);
  const clip = item({ key: "take:7", kind: "take", content_type: "video/mp4", video_name: null, open_step: "quick" });
  fakeServer({ ...base(owner, page([clip])), "GET /brands/1/media/take%3A7": [200, clip] });
  renderApp("/b/1/media/take%3A7");
  await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
  expect(await screen.findByRole("alertdialog", { name: "Delete this clip?" })).toBeInTheDocument();
});
