import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const owner = { id: 1, email: "reed@b.co", name: "Reed", role: "owner", workspace_id: 1 };
const brands = [{ id: 1, name: "Iron Paws", colours: [], end_line: "Get Iron Paws through the link in my bio." }];
const version = (o: object = {}) => ({ slot: 0, status: "draft", title: "Bowl song", seconds: 0, project_id: null, text: "", words: 0, target_seconds: null, premise: "", changes: [], problems: [], has_breakdown: false, approved_at: null, style_line: "", singer: "", spoken_end_line: "", song_directions: [], song_study: null, ...o });
const song = (v: object = {}) => ({
  id: 7, brand_id: 1, kind: "song", title: "Bowl song", description: "", reference_id: null, published: false, status: "draft", created_by_id: 1, created_by_name: "Reed", created_at: "2026-10-28T10:00:00Z", versions_left: 0,
  notes: "", reference_replace: "", cast: [], versions: [version(v)],
});
const base: Record<string, [number, unknown]> = { "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /references": [200, []], "GET /projects": [200, []], "GET /jobs": [200, []], "GET /scripts/7/drafts/0/songs": [200, { songs_on: true, estimate_credits: 1, video_estimate_credits: 40, keep_lines: null, takes: [] }] };

function open() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/b/1/scripts/7"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const done = (o: object = {}) => ({
  status: "done", job: null, source: "link", link: "https://www.instagram.com/reel/x", seconds: 31, bpm: 98.4, use_as_guide: true, problem: "",
  sections: [{ name: "Verse", start: 0, end: 12, lines: ["Bo would never touch his bowl"], guessed: false }, { name: "Bridge", start: 12, end: 20, lines: [], guessed: true }],
  lines: [{ text: "Bo would never touch his bowl", start: 1.2, end: 3.4 }], words: [], frames: [{ file_id: 77, t: 2.1 }], ...o,
});

test("empty: Study it is free and sends the reel link", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, song()], "POST /scripts/7/drafts/0/song-study": [201, { id: 5 }] });
  open();
  expect(await screen.findByText("Paste a song ad to learn its shape: its words, beat and parts. Free.")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Reel link"), "https://www.instagram.com/reel/abc");
  await userEvent.click(screen.getByRole("button", { name: "Study it · free" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/drafts/0/song-study")).toBe(true));
});

test("studying: in words with Cancel before it starts", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, song({ song_study: { ...done(), status: "studying", seconds: null, sections: [], lines: [], frames: [], job: { id: 5, status: "queued", started_at: new Date().toISOString() } } })] });
  open();
  expect(await screen.findByText(/Studying the song ad…/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
});

test("done: length, BPM, sections with their own guessed mark, the words, frames, the guide switch, and Remove with Undo", async () => {
  setViewport(390);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, song({ song_study: done() })], "PATCH /scripts/7/drafts/0/song-study": [204, null], "DELETE /scripts/7/drafts/0/song-study": [204, null], "POST /scripts/7/drafts/0/song-study/restore": [204, null] });
  open();
  const card = await screen.findByRole("region", { name: "Study a song ad" });
  expect(within(card).getByText("Song ad studied · 0:31 · 98 BPM")).toBeInTheDocument();
  const sections = within(card).getByRole("list", { name: "Sections" });
  expect(within(sections).getAllByText("guessed")).toHaveLength(1); // only the Bridge
  expect(within(card).getByAltText("Frame at 0:02")).toBeInTheDocument();
  expect(within(card).getByText("A guide only: the directions copy its shape, never its words.")).toBeInTheDocument();
  await userEvent.click(within(card).getByRole("checkbox", { name: "Use as a guide for the song directions" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /scripts/7/drafts/0/song-study")?.body).toEqual({ use_as_guide: false }));
  await userEvent.click(within(card).getByRole("button", { name: "Remove" }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/drafts/0/song-study/restore")).toBe(true));
});

test("no steady beat says so instead of 0 BPM", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, song({ song_study: done({ bpm: 0 }) })] });
  open();
  expect(await screen.findByText("Song ad studied · 0:31 · no steady beat")).toBeInTheDocument();
});

test("failed: the reason in plain words, nothing charged, and Try another", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, song({ song_study: done({ status: "failed", problem: "it's private or was removed", seconds: null, sections: [], lines: [], frames: [] }) })] });
  open();
  expect(await screen.findByText("We couldn't open that reel: it's private or was removed. Nothing was charged.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Try another · free" })).toBeInTheDocument();
});

test("a refused start shows the server's sentence", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, song()], "POST /scripts/7/drafts/0/song-study": [409, { detail: "A study is already running on this version." }] });
  open();
  await userEvent.type(await screen.findByLabelText("Reel link"), "https://x.co/r");
  await userEvent.click(screen.getByRole("button", { name: "Study it · free" }));
  expect(await screen.findByText("A study is already running on this version.")).toBeInTheDocument();
});

test("before the server offers studies, the box isn't shown", async () => {
  setViewport(1440);
  const v = version();
  const old = Object.fromEntries(Object.entries(v).filter(([k]) => k !== "song_study"));
  fakeServer({ ...base, "GET /scripts/7": [200, { ...song(), versions: [old] }] });
  open();
  expect(await screen.findByLabelText("Lyrics")).toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "Study a song ad" })).toBeNull();
});

test("Or upload the video sends the file instead of a link", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, song()], "POST /scripts/7/drafts/0/song-study": [201, { id: 5 }] });
  open();
  await userEvent.upload(await screen.findByLabelText("Upload the video"), new File(["x"], "ad.mp4", { type: "video/mp4" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/drafts/0/song-study")).toBe(true));
});
