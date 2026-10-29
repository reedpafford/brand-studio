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
const LYRICS = "[Verse]\nBo would never touch his bowl\n[Chorus]\nNow he licks it clean";
const version = (o: object = {}) => ({ slot: 0, status: "draft", title: "Bowl song", seconds: 0, project_id: null, text: LYRICS, words: 10, target_seconds: null, premise: "", changes: [], problems: [], has_breakdown: false, approved_at: null, style_line: "pop, female lead, upbeat", singer: "", spoken_end_line: "", song_directions: [], ...o });
const song = (o: object = {}, v: object = {}) => ({
  id: 7, brand_id: 1, kind: "song", title: "Bowl song", description: "", reference_id: null, published: false, status: "draft", created_by_id: 1, created_by_name: "Reed", created_at: "2026-10-28T10:00:00Z", versions_left: 0,
  notes: "", reference_replace: "", cast: [], versions: [version(v)], ...o,
});
const take = (o: object = {}) => ({ id: 1, number: 1, status: "ready", failed_reason: null, retry_helps: true, file_id: 40, seconds: 31, made_at: "2026-10-28T10:42:00Z", preferred: false, out_of_date: false, peaks: [0.2, 0.8, 0.5], advice: [], timing_guessed: false, refused_for: null, video_credits: 34, over_cap: false, fits_until: null, trim_to: null, ...o });
const songs = (takes: object[] = [], o: object = {}) => ({ songs_on: true, estimate_credits: 1, takes, ...o });
const base: Record<string, [number, unknown]> = { "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /references": [200, []], "GET /projects": [200, []], "GET /jobs": [200, []] };

function open(path: string) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const cast = [{ id: 31, role: "Bo", kind: "Main", appears_in: [0], description: "", position: 0, library_item_id: null, sheet_file_id: null, locked: false }];

test("Cast on a song asks who sings on camera: a role is saved at once with Undo; Nobody on camera says every shot is B-roll", async () => {
  setViewport(1440);
  const preferred = songs([take({ preferred: true })]);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, song({}, { singer: "" })], "GET /scripts/7/drafts/0/songs": [200, preferred], "GET /scripts/7/cast": [200, cast], "GET /brands/1/characters": [200, []], "PUT /scripts/7/drafts/0": [200, song({}, { singer: "Bo" })] });
  open("/b/1/scripts/7?step=cast");
  const card = await screen.findByRole("group", { name: "Who sings on camera?" });
  expect(within(card).getByRole("radio", { name: "Nobody on camera" })).toBeChecked();
  expect(screen.getByText("No shot will lip-sync. The song plays over B-roll only.")).toBeInTheDocument();
  await userEvent.click(await within(card).findByRole("radio", { name: "Bo" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /scripts/7/drafts/0")?.body).toMatchObject({ text: LYRICS, singer: "Bo" }));
  expect(await screen.findByRole("button", { name: "Undo" })).toBeInTheDocument();
});

test("Publish on a song lists the song, its style and the singer, and says the lyrics become final", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, song({}, { singer: "Bo" })], "GET /scripts/7/drafts/0/songs": [200, songs([take({ preferred: true })])], "GET /scripts/7/cast": [200, cast] });
  open("/b/1/scripts/7?step=publish");
  const card = await screen.findByRole("listitem", { name: "Version A" });
  expect(await within(card).findByText("Song: Take 1 · 0:31")).toBeInTheDocument();
  expect(within(card).getByText("pop, female lead, upbeat")).toBeInTheDocument();
  expect(within(card).getByText("Bo")).toBeInTheDocument();
  expect(screen.getByText(/After that the lyrics can't change \(each video still picks its own take\)/)).toBeInTheDocument();
});

test("at 390, Make this version on a song shows its song with a 44px play button, and its length in the price line", async () => {
  setViewport(390);
  const ready = song({ published: true, status: "published" }, { status: "approved", estimate_credits: 40 });
  fakeServer({ ...base, "GET /scripts": [200, [{ ...ready, versions: [{ slot: 0, status: "approved", title: "Bowl song", seconds: 31, project_id: null }] }]], "GET /scripts/7": [200, ready], "GET /scripts/7/drafts/0/songs": [200, songs([take({ preferred: true })])], "GET /scripts/7/cast": [200, []], "GET /credits/rates": [200, []] });
  open("/b/1/scripts?make=7.0");
  const row = await screen.findByRole("region", { name: "Song" });
  expect(await within(row).findByText("Song: Take 1 · 0:31")).toBeInTheDocument();
  expect(within(row).getByRole("button", { name: "Play Take 1" })).toBeInTheDocument();
  expect(screen.getByText(/whole video (costs )?about 40( credits)? · 0:31 song/)).toBeInTheDocument();
});
