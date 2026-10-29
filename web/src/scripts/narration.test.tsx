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

const WORDS = "Bo hated his bowl. Then he found Iron Paws.";
const narrated = (v: object = {}, o: object = {}) => song({ kind: "narrated", ...o }, { text: WORDS, style_line: "", ...v });
const narration = (o: object = {}) => take({ kind: "narration", voice: "Sarah", untrimmed_seconds: null, ...o });

test("New script → Narrated makes a narrated draft", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts": [200, []], "POST /scripts": [201, narrated({ text: "" })], "GET /scripts/7": [200, narrated({ text: "" })], "GET /scripts/7/drafts/0/songs": [200, songs()] });
  open("/b/1/scripts");
  await userEvent.click(await screen.findByRole("button", { name: "New script" }));
  await userEvent.click(screen.getByRole("menuitem", { name: /Narrated/ }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts")?.body).toMatchObject({ kind: "narrated" }));
});

test("a narrated script has five steps; Narration waits for words, and Cast for a narration in use", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, narrated({ text: "" })], "GET /scripts/7/drafts/0/songs": [200, songs()] });
  open("/b/1/scripts/7");
  const steps = await screen.findByRole("list", { name: "Steps" });
  expect(within(steps).getAllByRole("button").map((b) => b.textContent?.replace(/^\d+/, ""))).toEqual(["Script", "Narration", "Cast", "Plan", "Publish"]);
  expect(within(steps).getByRole("button", { name: "Narration" })).toHaveAccessibleDescription("Write the words first");
});

test("Narration, empty: one voice, its price, and one request; Cast stays locked until one is used", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, narrated()], "GET /scripts/7/drafts/0/songs": [200, songs([], { estimate_credits: 2 })], "POST /scripts/7/drafts/0/songs": [200, songs([narration({ status: "making", file_id: null, seconds: null })])] });
  open("/b/1/scripts/7?step=narration");
  expect(await screen.findByText("One voice reads the whole script. Voice: Sarah.")).toBeInTheDocument();
  expect(within(screen.getByRole("list", { name: "Steps" })).getByRole("button", { name: "Cast" })).toHaveAccessibleDescription("Make the narration first");
  await userEvent.click(screen.getByRole("button", { name: /Make the narration · 2 credits/ }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /scripts/7/drafts/0/songs")).toHaveLength(1));
});

test("Done: the player, pauses trimmed, Use this narration with Undo, and Make another keeps the one in use", async () => {
  setViewport(390);
  const one = narration({ seconds: 139, untrimmed_seconds: 146, advice: [] });
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, narrated()], "GET /scripts/7/drafts/0/songs": [200, songs([one, narration({ id: 2, number: 2, preferred: true, seconds: 150 })])], "POST /songs/1/preferred": [200, { take: { ...one, preferred: true }, was_preferred_id: 2 }], "POST /songs/2/preferred": [200, { take: narration({ id: 2, number: 2, preferred: true }), was_preferred_id: 1 }] });
  open("/b/1/scripts/7?step=narration");
  expect(await screen.findByText("Pauses trimmed: 2:26 → 2:19")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Play Narration 1" })).toBeInTheDocument();
  expect(screen.getByText("In use")).toBeInTheDocument();
  expect(screen.getByText("Narration 2 stays in use until you use the new one.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Use this narration" }));
  expect(await screen.findByText("Narration 1 is the one used.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /songs/2/preferred")).toBe(true));
  expect(document.documentElement.scrollWidth).toBeLessThanOrEqual(390);
});

test("words changed: Reads older words, can't be used, and the press is Make the narration again", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, narrated()], "GET /scripts/7/drafts/0/songs": [200, songs([narration({ preferred: true, out_of_date: true })])] });
  open("/b/1/scripts/7?step=narration");
  expect(await screen.findByText("Reads older words")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Use this narration" })).toBeNull();
  expect(screen.getByRole("button", { name: /^Make the narration · 1 credit/ })).toBeInTheDocument();
  expect(within(screen.getByRole("list", { name: "Steps" })).getByRole("button", { name: "Cast" })).toHaveAccessibleDescription("Make a narration of the new words first");
});

test("failed: says nothing was charged, with Try again; kept pauses show as Advice", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, narrated()], "GET /scripts/7/drafts/0/songs": [200, songs([narration({ status: "failed", file_id: null, seconds: null, failed_reason: null }), narration({ id: 2, number: 2, advice: ["Kept the pauses: trimming would have clipped a word."] })])] });
  open("/b/1/scripts/7?step=narration");
  expect(await screen.findByText("The narration didn't finish. Nothing was charged.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Try again · 1 credit/ })).toBeInTheDocument();
  expect(screen.getByText("Kept the pauses: trimming would have clipped a word.")).toBeInTheDocument();
});

test("a narrated script carries a Narrated badge in the Library", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts": [200, [{ ...narrated({}, { published: true, status: "published" }), versions: [{ slot: 0, status: "approved", title: "Bowl song", seconds: 31, project_id: null }] }]] });
  open("/b/1/scripts");
  const title = await screen.findByRole("heading", { name: /Bowl song/ });
  expect(within(title).getByText("Narrated")).toBeInTheDocument();
});

test("while one is made, the card says so in words", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, narrated()], "GET /scripts/7/drafts/0/songs": [200, songs([narration({ status: "making", file_id: null, seconds: null })])] });
  open("/b/1/scripts/7?step=narration");
  expect(await screen.findByText(/Making the narration…/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Make another/ })).toBeDisabled();
});

test("while the sentences are measured, Make another waits too, and Cast says to wait", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, narrated()], "GET /scripts/7/drafts/0/songs": [200, songs([narration({ status: "timing" })])] });
  open("/b/1/scripts/7?step=narration");
  expect(await screen.findByText(/Measuring the sentences…/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Make another/ })).toBeDisabled();
  expect(within(screen.getByRole("list", { name: "Steps" })).getByRole("button", { name: "Cast" })).toHaveAccessibleDescription("Wait for the narration to finish");
});

test("the header's format is a picker on a draft: Dialogue → Narrated asks first, saves, and Undo puts it back", async () => {
  setViewport(390);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, narrated({}, { kind: "story" })], "PATCH /scripts/7": [200, {}] });
  open("/b/1/scripts/7?step=script");
  await userEvent.click(await screen.findByRole("button", { name: "Format: Dialogue" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Narrated" }));
  const ask = screen.getByRole("alertdialog", { name: "Make this Narrated?" });
  expect(within(ask).getByText(/nobody speaks on camera/)).toBeInTheDocument();
  expect(calls.some((c) => c.key === "PATCH /scripts/7")).toBe(false);
  await userEvent.click(within(ask).getByRole("button", { name: "Change" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /scripts/7")?.body).toEqual({ kind: "narrated" }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "PATCH /scripts/7").at(-1)?.body).toEqual({ kind: "story" }));
});

test("a song, or a published script, shows its format as a plain chip", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs()] });
  open("/b/1/scripts/7");
  expect((await screen.findAllByText("Song")).length).toBeGreaterThan(0);
  expect(screen.queryByRole("button", { name: /^Format:/ })).toBeNull();
});

test("a Dialogue script that reads as narrated says so, with Make it Narrated", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, narrated({ reads_narrated: true }, { kind: "story" })], "PATCH /scripts/7": [200, {}] });
  open("/b/1/scripts/7?step=script");
  expect(await screen.findByText("This reads as narrated. Make it Narrated?")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Make it Narrated" }));
  await userEvent.click(within(screen.getByRole("alertdialog", { name: "Make this Narrated?" })).getByRole("button", { name: "Change" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /scripts/7")?.body).toEqual({ kind: "narrated" }));
});

test("on a Narrated script, a line spoken on camera is Advice: the narrator will read it", async () => {
  setViewport(390);
  fakeServer({ ...base, "GET /scripts/7": [200, narrated({ dialogue_lines: [{ line: 2, text: "BO: Then he found Iron Paws." }] })], "GET /scripts/7/drafts/0/songs": [200, songs()] });
  open("/b/1/scripts/7?step=script");
  const list = await screen.findByLabelText("Lines spoken on camera");
  expect(within(list).getByText(/Line 2, "BO: Then he found Iron Paws.": this line is spoken on camera, but a Narrated script has one voice\. The narrator will read it\./)).toBeInTheDocument();
});

test("a narration lists each sentence's start, and the voice is the server's", async () => {
  setViewport(1440);
  const sentences = [{ text: "Bo hated his bowl.", start: 0, end: 1.6 }, { text: "Then he found Iron Paws.", start: 2, end: 3.4 }];
  fakeServer({ ...base, "GET /scripts/7": [200, narrated()], "GET /scripts/7/drafts/0/songs": [200, songs([narration({ preferred: true, sentences })], { voice: "Sarah" })] });
  open("/b/1/scripts/7?step=narration");
  await userEvent.click(await screen.findByText("Each sentence's start · 2"));
  expect(screen.getByText("Then he found Iron Paws.")).toBeInTheDocument();
  expect(screen.getByText("0:02")).toBeInTheDocument();
});

test("the music under a narration: making, then with music; a failed bed keeps the narration and offers Try the music again", async () => {
  setViewport(390);
  const calls = fakeServer({
    ...base,
    "GET /scripts/7": [200, narrated()],
    "GET /scripts/7/drafts/0/songs": [200, songs([narration({ id: 1, preferred: true, music_status: "making" }), narration({ id: 2, number: 2, music_status: "failed", music_reason: "The music didn't finish. Nothing was charged for it.", music_credits: 2 }), narration({ id: 3, number: 3, music_status: "ready", music_file_id: 90 })])],
    "POST /songs/2/music-again": [200, narration({ id: 2, number: 2, music_status: "making" })],
  });
  open("/b/1/scripts/7?step=narration");
  expect(await screen.findByText(/Making the music…/)).toBeInTheDocument();
  expect(screen.getByText("The music didn't finish. Nothing was charged for it. The narration is kept.")).toBeInTheDocument();
  expect(screen.getByLabelText("The music for Narration 3")).toHaveAttribute("src", "/api/files/90");
  await userEvent.click(screen.getByRole("button", { name: /Try the music again · 2 credits/ }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /songs/2/music-again")).toBe(true));
});

test("where the music is off, a narration shows nothing about music", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, narrated()], "GET /scripts/7/drafts/0/songs": [200, songs([narration({ preferred: true, music_status: "none" })])] });
  open("/b/1/scripts/7?step=narration");
  expect(await screen.findByRole("button", { name: "Play Narration 1" })).toBeInTheDocument();
  expect(screen.queryByText(/music/i)).toBeNull();
});

test("with nothing for the narrator to read, the press is greyed with the server's reason and no price", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, narrated()], "GET /scripts/7/drafts/0/songs": [200, songs([], { estimate_credits: 0, songs_note: "Write the words first: the narrator reads them as written." })] });
  open("/b/1/scripts/7?step=narration");
  const press = await screen.findByRole("button", { name: /^Make the narration/ });
  expect(press).toBeDisabled();
  expect(press).toHaveAccessibleDescription("Write the words first: the narrator reads them as written.");
  expect(press).not.toHaveTextContent(/credit|free/);
});
