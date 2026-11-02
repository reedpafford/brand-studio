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

test("each tile shows its picture, kind, when and who, with Open in {step} and Download (flows OR2)", async () => {
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
  expect(within(tiles[0]).getByRole("link", { name: "Open in Clips" })).toHaveAttribute("href", "/b/1/videos/9?step=clips");
  expect(within(tiles[0]).getByRole("link", { name: /Download take/ })).toHaveAttribute("href", "/api/files/30");
  expect(within(tiles[1]).getByRole("link", { name: "Open in Storyboard" })).toHaveAttribute("href", "/b/1/videos/9?step=storyboard");
  expect(within(tiles[2]).getByRole("link", { name: "Open in Freestyle" })).toHaveAttribute("href", "/freestyle");
  expect(within(tiles[3]).getByRole("link", { name: "Open in Freestyle" })).toHaveAttribute("href", "/freestyle/4");
  expect(within(tiles[4]).getByRole("link", { name: "Open in Takes" })).toHaveAttribute("href", "/b/1/scripts/7?step=takes");
  expect(within(tiles[4]).getByLabelText(/^Play/)).toBeInTheDocument();
  expect(within(tiles[5]).getByRole("link", { name: "Open in Cast & places" })).toHaveAttribute("href", "/b/1/library");
  expect(document.body.textContent).not.toMatch(/\$/);
});

test("with nothing made yet it says so and offers New video", async () => {
  setViewport(1440);
  fakeServer(base(editor, page([])));
  open();
  expect(await screen.findByRole("heading", { name: "Nothing made yet in Iron Paws." })).toBeInTheDocument();
  expect(within(screen.getByRole("main")).getByRole("link", { name: "New video" })).toHaveAttribute("href", expect.stringMatching(/^\/b\/\d+\/videos\/new$/));
});

test("the kind and who-made-it filters ask the server, and Clear filters puts them back", async () => {
  setViewport(1440);
  fakeServer(base(owner, page([item()])));
  open();
  await screen.findByRole("list", { name: "Media" });
  await userEvent.click(screen.getByRole("button", { name: "Stills" }));
  await vi.waitFor(() => expect(urls().some((u) => u.includes("/brands/1/media?") && u.includes("kind=still"))).toBe(true));
  expect(screen.getByRole("button", { name: "Stills" })).toHaveAttribute("aria-pressed", "true");
  await screen.findByRole("option", { name: "Eli" });
  await userEvent.selectOptions(screen.getByLabelText("Made by"), "Eli");
  await vi.waitFor(() => expect(urls().some((u) => u.includes("kind=still") && u.includes("by=2"))).toBe(true));
  await userEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  expect(screen.getByRole("button", { name: "Everything" })).toHaveAttribute("aria-pressed", "true");
});

test("a project picked in the side list (?folder=) filters Media too", async () => {
  setViewport(1440);
  fakeServer(base(owner, page([item()])));
  open("/b/1/media?folder=none");
  await screen.findByRole("list", { name: "Media" });
  expect(urls().some((u) => u.includes("/brands/1/media?") && u.includes("folder=none"))).toBe(true);
});

test("picking a project from Project: All ▾ stays on Media and filters it", async () => {
  setViewport(1440);
  fakeServer(base(owner, page([item()]), { "GET /brands/1/folders": [200, [{ id: 4, brand_id: 1, name: "November launch", created_by_id: 1, items: { scripts: 0, videos: 1, clips: 0 }, can_manage: true }]] }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: /^Project: / }));
  const list = await screen.findByRole("region", { name: "Projects" });
  await userEvent.click(within(list).getByRole("button", { name: "November launch · 1 item" }));
  await vi.waitFor(() => expect(urls().some((u) => u.includes("/brands/1/media?") && u.includes("folder=4"))).toBe(true));
  expect(await screen.findByRole("heading", { name: "Media" })).toBeInTheDocument();
});

test("an editor gets no who-made-it filter (the server shows them their own work)", async () => {
  setViewport(1440);
  fakeServer(base(editor, page([item()])));
  open();
  await screen.findByRole("list", { name: "Media" });
  expect(screen.queryByLabelText("Made by")).toBeNull();
});

test("a deleted video's media names its maker; the owner can restore the video, and Download stays", async () => {
  setViewport(1440);
  const calls = fakeServer(base(owner, page([item({ from_deleted_video: true, deleted_video_by: { id: 3, name: "Sam" } })]), { "POST /projects/9/restore": [200, {}] }));
  open();
  const tile = within(await screen.findByRole("list", { name: "Media" })).getByRole("listitem");
  expect(tile).toHaveTextContent("From Sam's deleted video");
  expect(within(tile).queryByRole("link", { name: /Open in/ })).toBeNull();
  expect(within(tile).getByRole("link", { name: /Download/ })).toBeInTheDocument();
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
  expect(within(list).getByRole("link", { name: /Download/ })).toBeInTheDocument();
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
  // The kinds are tabs on the page (W11); who made it sits in the Filters sheet.
  expect(within(screen.getByRole("navigation", { name: "Kinds" })).getByRole("button", { name: "Stills" })).toBeInTheDocument();
  expect(screen.queryByLabelText("Made by")).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Filters" }));
  const sheet = await screen.findByRole("dialog", { name: "Filters" });
  expect(within(sheet).getByLabelText("Made by")).toBeInTheDocument();
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
    fakeServer(base(owner, page([item({ key: "final:3", kind: "final", content_type: "video/mp4", video_name: "Bo tries salmon · A", open_step: "final" })])));
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

test("an item no longer in Media says so, with the way back", async () => {
  fakeServer(base(owner, page([])));
  renderApp("/b/1/media/final%3A99");
  expect(await screen.findByText("That item isn't in Media any more.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Back to Media" })).toHaveAttribute("href", "/b/1/media");
});
