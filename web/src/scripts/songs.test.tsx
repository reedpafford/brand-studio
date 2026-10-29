import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { keepFirst } from "./SongStep";

const owner = { id: 1, email: "reed@b.co", name: "Reed", role: "owner", workspace_id: 1 };
const brands = [{ id: 1, name: "Iron Paws", colours: [], end_line: "Get Iron Paws through the link in my bio." }];
const LYRICS = "[Verse]\nBo would never touch his bowl\n[Chorus]\nNow he licks it clean";
const version = (o: object = {}) => ({ slot: 0, status: "draft", title: "Bowl song", seconds: 0, project_id: null, text: LYRICS, words: 10, target_seconds: null, premise: "", changes: [], problems: [], has_breakdown: false, approved_at: null, style_line: "pop, female lead, upbeat", singer: "", spoken_end_line: "", song_directions: [], ...o });
const song = (o: object = {}, v: object = {}) => ({
  id: 7, brand_id: 1, kind: "song", title: "Bowl song", description: "", reference_id: null, published: false, status: "draft", created_by_id: 1, created_by_name: "Reed", created_at: "2026-10-28T10:00:00Z", versions_left: 0,
  notes: "", reference_replace: "", cast: [], versions: [version(v)], ...o,
});
const take = (o: object = {}) => ({ id: 1, number: 1, status: "ready", failed_reason: null, retry_helps: true, retry_credits: 0, file_id: 40, seconds: 31, made_at: "2026-10-28T10:42:00Z", preferred: false, out_of_date: false, peaks: [0.2, 0.8, 0.5], advice: [], timing_guessed: false, refused_for: null, video_credits: 34, over_cap: false, fits_until: null, trim_to: null, ...o });
const songs = (takes: object[] = [], o: object = {}) => ({ songs_on: true, estimate_credits: 1, video_estimate_credits: 40, keep_lines: null, takes, ...o });
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

test("New script → Song makes a song draft that opens on its Song step: five steps, Next waits for lyrics", async () => {
  setViewport(1440);
  const empty = song({ title: "Untitled script" }, { text: "", style_line: "" });
  const calls = fakeServer({ ...base, "GET /scripts": [200, []], "POST /scripts": [201, empty], "GET /scripts/7": [200, empty], "GET /scripts/7/drafts/0/songs": [200, songs()] });
  open("/b/1/scripts");
  await userEvent.click(await screen.findByRole("button", { name: "New script" }));
  await userEvent.click(screen.getByRole("menuitem", { name: /Song/ }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts")?.body).toMatchObject({ kind: "song" }));
  expect(await screen.findByLabelText("Lyrics")).toHaveValue("");
  const steps = screen.getByRole("list", { name: "Steps" });
  expect(within(steps).getAllByRole("button").map((b) => b.textContent?.replace(/^\d+/, ""))).toEqual(["Song", "Takes", "Cast", "Plan", "Publish"]);
  expect(within(steps).getByRole("button", { name: "Cast" })).toHaveAccessibleDescription("Write or pick the lyrics first");
  expect(screen.getByRole("button", { name: "Next: Takes" })).toBeDisabled();
  expect(screen.getByLabelText("Music style")).toHaveAttribute("placeholder", "pop, female lead, 120 BPM, upbeat, modern polished");
});

test("lyrics: the sung length counts words not tags; over 4,960 characters says how many to cut and keeps the words; Save sends lyrics and style", async () => {
  setViewport(1440);
  const empty = song({}, { text: "", style_line: "" });
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, empty], "GET /scripts/7/drafts/0/songs": [200, songs()], "PUT /scripts/7/drafts/0": [200, song()] });
  open("/b/1/scripts/7");
  const box = await screen.findByLabelText("Lyrics");
  await userEvent.click(box);
  await userEvent.paste("[Verse]\n" + "la ".repeat(25));
  expect(screen.getByText(/25 sung words: a song of about 0:10–0:13/)).toBeInTheDocument();
  await userEvent.paste("x".repeat(4960));
  expect(screen.getAllByText(/Cut \d+ characters/).length).toBeGreaterThan(0);
  expect(screen.getByRole("button", { name: "Save lyrics" })).toBeDisabled();
  expect((box as HTMLTextAreaElement).value.length).toBeGreaterThan(4960); // the words stay
  await userEvent.clear(box);
  await userEvent.paste(LYRICS);
  await userEvent.type(screen.getByLabelText("Music style"), "pop");
  await userEvent.click(screen.getByRole("button", { name: "Save lyrics" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /scripts/7/drafts/0")?.body).toMatchObject({ text: LYRICS, style_line: "pop" }));
  expect(await screen.findByText("Sung word for word")).toBeInTheDocument();
});

test("saved lyrics: Edit lyrics asks first when takes exist; Advice offers Sing the end line, free, with Undo", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs([take({ preferred: true })])], "PUT /scripts/7/drafts/0": [200, song()] });
  open("/b/1/scripts/7");
  await userEvent.click(await screen.findByRole("button", { name: "Edit lyrics" }));
  const ask = screen.getByRole("alertdialog", { name: "Edit the lyrics?" });
  expect(ask).toHaveTextContent("Your take will be out of date.");
  await userEvent.click(within(ask).getByRole("button", { name: "Cancel" }));
  await userEvent.click(screen.getByText(/Advice · /));
  expect(screen.getByText("The song doesn't say Iron Paws or where to find it.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Sing the end line/ }));
  await vi.waitFor(() => expect((calls.find((c) => c.key === "PUT /scripts/7/drafts/0")?.body as { text: string }).text).toBe(`${LYRICS}\n\n[Outro]\nGet Iron Paws through the link in my bio.`));
  expect(await screen.findByRole("button", { name: "Undo" })).toBeInTheDocument();
});

test("Takes, empty: Make 2 takes shows its price and makes one request; Cast stays locked until a take is Preferred", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs()], "POST /scripts/7/drafts/0/songs": [201, songs([take({ status: "making", file_id: null, seconds: null, made_at: null })])] });
  open("/b/1/scripts/7?step=takes");
  const steps = await screen.findByRole("list", { name: "Steps" });
  expect(within(steps).getByRole("button", { name: "Cast" })).toHaveAccessibleDescription("Make the song first");
  await userEvent.click(screen.getByRole("button", { name: /Make 2 takes · 1 credit/ }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /scripts/7/drafts/0/songs")).toHaveLength(1));
});

test("Takes: past the real-song test budget, the step says new takes are stand-in songs", async () => {
  setViewport(1440);
  const note = "Real songs for this test are used up, so new takes are free stand-in songs.";
  fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs([], { songs_note: note })] });
  open("/b/1/scripts/7?step=takes");
  expect(await screen.findByText(note)).toBeInTheDocument();
});

test("Takes: Preferred in words; one being made, one still being timed (can't be Preferred yet); a timing failure a retry won't fix offers the other take, not the even spread", async () => {
  setViewport(1440);
  const list = songs([take({ preferred: true }), take({ id: 2, number: 2, status: "timing" }), take({ id: 3, number: 3, status: "timing_failed", retry_helps: false, failed_reason: "This take's file can't be read, so its timing can't be measured." }), take({ id: 4, number: 4 }), take({ id: 5, number: 5, status: "making", file_id: null, seconds: null, made_at: null })]);
  fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, list] });
  open("/b/1/scripts/7?step=takes");
  expect(await screen.findByText("Preferred")).toBeInTheDocument();
  expect(screen.getAllByText("0:31 · a video of about 34 credits")).toHaveLength(4); // every take with a length says what its video would cost
  expect(screen.getByText(/^Making…/)).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Make this Preferred" })[0]).toBeDisabled();
  expect(screen.getByText("This take's file can't be read, so its timing can't be measured.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Try again/ })).toBeNull();
  expect(screen.getByRole("button", { name: "Make take 4 Preferred" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Use timing spread evenly/ })).toBeNull(); // the file can't be read: spreading can't help
  expect(screen.getByRole("button", { name: "Next: Cast" })).toBeEnabled();
});

test("Takes: a timing failure a retry can help offers Use timing spread evenly (free) and Try again", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs([take({ status: "timing_failed", failed_reason: "We couldn't read this song's timing. It's free to try again." })])], "POST /songs/1/spread-timing": [200, take({ timing_guessed: true })] });
  open("/b/1/scripts/7?step=takes");
  expect(await screen.findByRole("button", { name: /Try again · free/ })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Use timing spread evenly/ }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /songs/1/spread-timing")).toBe(true));
});

test("Takes: the Preferred take can't be deleted and says why; another is deleted with Undo, which puts it back", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs([take({ preferred: true }), take({ id: 2, number: 2 })])], "DELETE /songs/2": [204, null], "POST /songs/2/restore": [200, take({ id: 2, number: 2 })] });
  open("/b/1/scripts/7?step=takes");
  await userEvent.click(await screen.findByRole("button", { name: "More for Take 1" }));
  expect(screen.getByRole("menuitem", { name: "Delete take" })).toHaveAttribute("aria-disabled", "true");
  expect(screen.getByText("Make another take Preferred first.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "More for Take 2" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Delete take" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /songs/2")).toBe(true));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /songs/2/restore")).toBe(true));
});

test("a failed take says why with Try again at a request's price (both its takes are made again); songs off says so instead of a Make button", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs([take({ status: "failed", retry_credits: 1, file_id: null, seconds: null, failed_reason: "The music service wouldn't sing these lyrics. Nothing was charged." })], { songs_on: false })] });
  open("/b/1/scripts/7?step=takes");
  expect(await screen.findByText("The music service wouldn't sing these lyrics. Nothing was charged.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Try again · 1 credit/ })).toBeInTheDocument();
  expect(screen.getByText("Songs aren't switched on here.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Make 2/ })).toBeNull();
});

test("at 390: New script opens a sheet with Close and the three formats, each with its line", async () => {
  setViewport(390);
  fakeServer({ ...base, "GET /scripts": [200, []], "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs()] });
  open("/b/1/scripts");
  await userEvent.click(await screen.findByRole("button", { name: "New script" }));
  const sheet = screen.getByRole("dialog", { name: "New script" });
  expect(within(sheet).getByRole("button", { name: "Close" })).toBeInTheDocument();
  expect(within(sheet).getByRole("menuitem", { name: /Dialogue.*People speak on camera/ })).toBeInTheDocument();
  expect(within(sheet).getByRole("menuitem", { name: /Song.*Your lyrics, sung word for word/ })).toBeInTheDocument();
  expect(within(sheet).getByRole("menuitem", { name: /Narrated.*One voice reads your script over B-roll, with music/ })).toBeInTheDocument();
});

test("at 390 on a song script, the steps are one button: Step 1 of 5 · Song", async () => {
  setViewport(390);
  fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs()] });
  open("/b/1/scripts/7");
  expect(await screen.findByRole("button", { name: "Step 1 of 5 · Song" })).toBeInTheDocument();
});

test("a song script in the Library carries a Song badge", async () => {
  fakeServer({ ...base, "GET /scripts": [200, [{ ...song({ published: true, status: "published" }), versions: [{ slot: 0, status: "approved", title: "Bowl song", seconds: 31, project_id: null }] }]] });
  open("/b/1/scripts");
  const title = await screen.findByRole("heading", { name: /Bowl song/ });
  expect(within(title).getByText("Song")).toBeInTheDocument();
});

test("a press the server refuses says why on the Takes step (never silent)", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs([take({ preferred: true }), take({ id: 2, number: 2 })])], "POST /songs/2/preferred": [409, { detail: "This take sings older words. Make 2 takes of the lyrics as they are now." }] });
  open("/b/1/scripts/7?step=takes");
  await userEvent.click(await screen.findByRole("button", { name: "Make this Preferred" }));
  expect(await screen.findByText("This take sings older words. Make 2 takes of the lyrics as they are now.")).toBeInTheDocument();
});

test("after the lyrics change, a Preferred take that sings the older words doesn't open Cast", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs([take({ preferred: true, out_of_date: true }), take({ id: 2, number: 2, out_of_date: true })])] });
  open("/b/1/scripts/7?step=takes");
  expect(await screen.findByText("These takes sing older words.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Next: Cast" })).toBeDisabled();
  expect(within(screen.getByRole("list", { name: "Steps" })).getByRole("button", { name: "Cast" })).toHaveAccessibleDescription("Make takes of the new lyrics first");
});

test("a refused take offers Edit lyrics or style, which opens the Song step's boxes at once", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs([take({ status: "failed", retry_credits: 1, file_id: null, seconds: null, failed_reason: "The music service won't sing this: an artist's name in the style. Describe the sound instead." })])] });
  open("/b/1/scripts/7?step=takes");
  await userEvent.click(await screen.findByRole("link", { name: "Edit lyrics or music style" }));
  expect(await screen.findByLabelText("Lyrics")).toHaveValue(LYRICS); // the boxes open at once, no confirm
  expect(screen.queryByRole("alertdialog")).toBeNull();
});

test("a take too long for the video limit can't be Preferred yet and offers Use the first 0:55, free, with Undo", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs([take({ preferred: true }), take({ id: 2, number: 2, seconds: 72, over_cap: true, fits_until: 55 })])], "POST /songs/2/trim": [200, take({ id: 2, number: 2, seconds: 72, over_cap: false, trim_to: 55 })], "DELETE /songs/2/trim": [200, take({ id: 2, number: 2, seconds: 72, over_cap: true, fits_until: 55 })] });
  open("/b/1/scripts/7?step=takes");
  expect(await screen.findByText("This take is 1:12: a video of it would go over the limit.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Make this Preferred" })).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: /Use the first 0:55 · free/ }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /songs/2/trim")).toBe(true));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /songs/2/trim")).toBe(true));
});

test("a refusal over the style offers Use the default style instead (clears the style line, Undo) and Edit style", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs([take({ status: "failed", file_id: null, seconds: null, refused_for: "style", failed_reason: "Suno won't use an artist's name. Describe the sound instead." })])], "PUT /scripts/7/drafts/0": [200, song({}, { style_line: "" })] });
  open("/b/1/scripts/7?step=takes");
  expect(await screen.findByRole("link", { name: "Edit music style" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Use the default music style instead/ }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /scripts/7/drafts/0")?.body).toMatchObject({ text: LYRICS, style_line: "" }));
  expect(await screen.findByRole("button", { name: "Undo" })).toBeInTheDocument();
});

test("a request that came back short is asked again free, so its Try again says free, not a request's price", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs([take({ status: "failed", retry_credits: 0, file_id: null, seconds: null, failed_reason: "Only one song came back. The other is free to try again." })])] });
  open("/b/1/scripts/7?step=takes");
  expect(await screen.findByRole("button", { name: /^Try again · free$/ })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Try again · \d/ })).toBeNull();
});

test("a failed take that isn't a refusal leads with Try again; the Edit link comes after it", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs([take({ status: "failed", retry_credits: 1, file_id: null, seconds: null, failed_reason: "Suno took too long. Nothing was charged." })])] });
  open("/b/1/scripts/7?step=takes");
  const retry = await screen.findByRole("button", { name: /Try again · 1 credit/ });
  const editLink = screen.getByRole("link", { name: "Edit lyrics or music style" });
  expect(retry.compareDocumentPosition(editLink) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

test("trimming a take when nothing else is Preferred makes it the Preferred one", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs([take({ seconds: 72, over_cap: true, fits_until: 55 })])], "POST /songs/1/trim": [200, take({ seconds: 72, trim_to: 55 })], "POST /songs/1/preferred": [200, { take: take({ preferred: true, trim_to: 55 }), was_preferred_id: null }], "DELETE /songs/1/trim": [200, take({ seconds: 72, over_cap: true, fits_until: 55 })] });
  open("/b/1/scripts/7?step=takes");
  await userEvent.click(await screen.findByRole("button", { name: /Use the first 0:55/ }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /songs/1/preferred")).toBe(true));
  // One toast with one Undo for both: Undo puts the whole take back.
  expect(await screen.findByText("Take 1 now uses its first 0:55 and is Preferred. The whole take is kept.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /songs/1/trim")).toBe(true));
});

test("keepFirst counts sung lines as the server does: tags, [Lip-sync] marks and blank lines don't count", () => {
  const lyrics = "[Verse]\nOne\n\n[Chorus] [Lip-sync]\nTwo [Lip-sync]\nThree\n[Outro]\nFour";
  expect(keepFirst(lyrics, 2)).toEqual({ kept: "[Verse]\nOne\n\n[Chorus] [Lip-sync]\nTwo [Lip-sync]", dropped: 2 });
});

test("lyrics over the video limit: Make gives way to Keep the first N lines (free), which asks, saves and has Undo", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs([], { video_estimate_credits: 812, keep_lines: 1 })], "PUT /scripts/7/drafts/0": [200, song()] });
  open("/b/1/scripts/7?step=takes");
  expect(await screen.findByText(/A song this long would go over the video limit \(about 812 credits to make\)/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Make 2 takes/ })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Keep the first 1 line · free" }));
  const ask = screen.getByRole("alertdialog", { name: "Keep the first 1 line?" });
  expect(ask).toHaveTextContent("Bo would never touch his bowl");
  expect(ask).toHaveTextContent("1 sung line is dropped.");
  await userEvent.click(within(ask).getByRole("button", { name: "Keep them" }));
  await vi.waitFor(() => expect((calls.find((c) => c.key === "PUT /scripts/7/drafts/0")?.body as { text: string }).text).toBe("[Verse]\nBo would never touch his bowl"));
  expect(await screen.findByRole("button", { name: "Undo" })).toBeInTheDocument();
});

test("when not even one line fits the video limit, the press is Shorten the lyrics", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs([], { video_estimate_credits: 900, keep_lines: 0 })] });
  open("/b/1/scripts/7?step=takes");
  expect(await screen.findByRole("link", { name: "Shorten the lyrics" })).toBeInTheDocument();
});

test("a Preferred take too long for a video doesn't open Cast, whatever the server says", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs([take({ preferred: true, seconds: 800, over_cap: true, fits_until: 55 })])] });
  open("/b/1/scripts/7?step=takes");
  expect(await screen.findByRole("button", { name: "Next: Cast" })).toBeDisabled();
  expect(within(screen.getByRole("list", { name: "Steps" })).getByRole("button", { name: "Cast" })).toHaveAccessibleDescription("The Preferred take is too long for a video. Use the first part of it first");
});

test("Keep the first N lines says so when the part dropped holds the brand's end line (Advice)", async () => {
  setViewport(1440);
  const withEnd = song({}, { text: `${LYRICS}\n[Outro]\nGet Iron Paws through the link in my bio.` });
  fakeServer({ ...base, "GET /scripts/7": [200, withEnd], "GET /scripts/7/drafts/0/songs": [200, songs([], { video_estimate_credits: 812, keep_lines: 2 })] });
  open("/b/1/scripts/7?step=takes");
  await userEvent.click(await screen.findByRole("button", { name: "Keep the first 2 lines · free" }));
  expect(screen.getByRole("alertdialog")).toHaveTextContent("The brand's end line is in the part dropped.");
});
