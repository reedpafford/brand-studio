import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

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
    item({ key: "song:6", kind: "song", file_id: 60, content_type: "audio/mpeg", poster_file_id: null, project_id: null, video_name: null, script_id: 7, open_step: "song" }),
    item({ key: "sheet:8:0", kind: "sheet", file_id: 80, content_type: "image/png", poster_file_id: null, project_id: null, video_name: null, open_step: "cast", made_by: null }),
  ])));
  open();
  const list = await screen.findByRole("list", { name: "Media" });
  const tiles = within(list).getAllByRole("listitem");
  expect(tiles).toHaveLength(5);
  expect(tiles[0]).toHaveTextContent("Bo tries salmon");
  expect(tiles[0]).toHaveTextContent(/Take · .+ · Eli/);
  expect(within(tiles[0]).getByRole("link", { name: "Open in Clips" })).toHaveAttribute("href", "/b/1/videos/9?step=clips");
  expect(within(tiles[0]).getByRole("link", { name: /Download take/ })).toHaveAttribute("href", "/api/files/30");
  expect(within(tiles[1]).getByRole("link", { name: "Open in Storyboard" })).toHaveAttribute("href", "/b/1/videos/9?step=storyboard");
  expect(within(tiles[2]).getByRole("link", { name: "Open in Quick clip" })).toHaveAttribute("href", "/b/1/clip");
  expect(within(tiles[3]).getByRole("link", { name: "Open in Takes" })).toHaveAttribute("href", "/b/1/scripts/7?step=takes");
  expect(within(tiles[3]).getByLabelText(/^Play/)).toBeInTheDocument();
  expect(within(tiles[4]).getByRole("link", { name: "Open in Cast & places" })).toHaveAttribute("href", "/b/1/library");
  expect(document.body.textContent).not.toMatch(/\$/);
});

test("with nothing made yet it says so and offers a quick clip", async () => {
  setViewport(1440);
  fakeServer(base(editor, page([])));
  open();
  expect(await screen.findByRole("heading", { name: "Nothing made yet in Iron Paws." })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Make a quick clip" })).toHaveAttribute("href", "/b/1/clip");
});

test("the kind and who-made-it filters ask the server, and Clear filters puts them back", async () => {
  setViewport(1440);
  fakeServer(base(owner, page([item()])));
  open();
  await screen.findByRole("list", { name: "Media" });
  await userEvent.selectOptions(screen.getByLabelText("Kind"), "Stills");
  await vi.waitFor(() => expect(urls().some((u) => u.includes("/brands/1/media?") && u.includes("kind=still"))).toBe(true));
  await screen.findByRole("option", { name: "Eli" });
  await userEvent.selectOptions(screen.getByLabelText("Made by"), "Eli");
  await vi.waitFor(() => expect(urls().some((u) => u.includes("kind=still") && u.includes("by=2"))).toBe(true));
  await userEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  expect(screen.getByLabelText("Kind")).toHaveValue("");
});

test("a project picked in the side list (?folder=) filters Media too", async () => {
  setViewport(1440);
  fakeServer(base(owner, page([item()])));
  open("/b/1/media?folder=none");
  await screen.findByRole("list", { name: "Media" });
  expect(urls().some((u) => u.includes("/brands/1/media?") && u.includes("folder=none"))).toBe(true);
});

test("picking a project in the side list stays on Media and filters it", async () => {
  setViewport(1440);
  fakeServer(base(owner, page([item()]), { "GET /brands/1/folders": [200, [{ id: 4, brand_id: 1, name: "November launch", created_by_id: 1, items: { scripts: 0, videos: 1, clips: 0 }, can_manage: true }]] }));
  open();
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
  expect(screen.queryByLabelText("Kind")).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Filters" }));
  const sheet = await screen.findByRole("dialog", { name: "Filters" });
  expect(within(sheet).getByLabelText("Kind")).toBeInTheDocument();
});
