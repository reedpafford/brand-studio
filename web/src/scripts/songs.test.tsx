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
const take = (o: object = {}) => ({ id: 1, number: 1, status: "ready", failed_reason: null, retry_helps: true, file_id: 40, seconds: 31, made_at: "2026-10-28T10:42:00Z", preferred: false, out_of_date: false, peaks: [0.2, 0.8, 0.5], advice: [], timing_guessed: false, ...o });
const songs = (takes: object[] = [], o: object = {}) => ({ songs_on: true, take_credits: 1.46, estimate_credits: 2.92, takes, ...o });
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
  expect(within(steps).getAllByRole("button").map((b) => b.textContent?.replace(/^\d+/, ""))).toEqual(["Song", "Takes", "Cast", "Breakdown", "Publish"]);
  expect(within(steps).getByRole("button", { name: "Cast" })).toHaveAccessibleDescription("Write or pick the lyrics first");
  expect(screen.getByRole("button", { name: "Next: Takes" })).toBeDisabled();
  expect(screen.getByLabelText("Style")).toHaveAttribute("placeholder", "pop, female lead, 120 BPM, upbeat, modern polished");
});

test("lyrics: the sung length counts words not tags; over 3,500 characters says how many to cut and keeps the words; Save sends lyrics and style", async () => {
  setViewport(1440);
  const empty = song({}, { text: "", style_line: "" });
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, empty], "GET /scripts/7/drafts/0/songs": [200, songs()], "PUT /scripts/7/drafts/0": [200, song()] });
  open("/b/1/scripts/7");
  const box = await screen.findByLabelText("Lyrics");
  await userEvent.click(box);
  await userEvent.paste("[Verse]\n" + "la ".repeat(25));
  expect(screen.getByText(/About 10 s sung · 25 words/)).toBeInTheDocument();
  await userEvent.paste("x".repeat(3500));
  expect(screen.getAllByText(/Cut \d+ characters/).length).toBeGreaterThan(0);
  expect(screen.getByRole("button", { name: "Save lyrics" })).toBeDisabled();
  expect((box as HTMLTextAreaElement).value.length).toBeGreaterThan(3500); // the words stay
  await userEvent.clear(box);
  await userEvent.paste(LYRICS);
  await userEvent.type(screen.getByLabelText("Style"), "pop");
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

test("Takes, empty: Make 2 takes shows its price and asks for 2; Cast stays locked until a take is Preferred", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs()], "POST /scripts/7/drafts/0/songs": [201, songs([take({ status: "making", file_id: null, seconds: null, made_at: null })])] });
  open("/b/1/scripts/7?step=takes");
  const steps = await screen.findByRole("list", { name: "Steps" });
  expect(within(steps).getByRole("button", { name: "Cast" })).toHaveAccessibleDescription("Make the song first");
  await userEvent.click(screen.getByRole("button", { name: /Make 2 takes · 3 credits/ }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts/7/drafts/0/songs")?.body).toEqual({ count: 2 }));
});

test("Takes: Preferred in words; one being made, one still being timed (can't be Preferred yet); a timing failure a retry won't fix offers the even spread and the other take", async () => {
  setViewport(1440);
  const list = songs([take({ preferred: true }), take({ id: 2, number: 2, status: "timing" }), take({ id: 3, number: 3, status: "timing_failed", retry_helps: false, failed_reason: "This take's file can't be read, so its timing can't be measured." }), take({ id: 4, number: 4 }), take({ id: 5, number: 5, status: "making", file_id: null, seconds: null, made_at: null })]);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, list], "POST /songs/3/spread-timing": [200, take({ id: 3, number: 3, timing_guessed: true })] });
  open("/b/1/scripts/7?step=takes");
  expect(await screen.findByText("Preferred")).toBeInTheDocument();
  expect(screen.getByText(/Making the song…/)).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Make this Preferred" })[0]).toBeDisabled();
  expect(screen.getByText("This take's file can't be read, so its timing can't be measured.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Try again/ })).toBeNull();
  expect(screen.getByRole("button", { name: "Make take 4 Preferred" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Use timing spread evenly/ }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /songs/3/spread-timing")).toBe(true));
  expect(screen.getByRole("button", { name: "Next: Cast" })).toBeEnabled();
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

test("a failed take says why with Try again at one take's price; songs off says so instead of a Make button", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs([take({ status: "failed", file_id: null, seconds: null, failed_reason: "The music service wouldn't sing these lyrics. Nothing was charged." })], { songs_on: false })] });
  open("/b/1/scripts/7?step=takes");
  expect(await screen.findByText("The music service wouldn't sing these lyrics. Nothing was charged.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Try again · 2 credits/ })).toBeInTheDocument();
  expect(screen.getByText("Songs aren't switched on here.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Make 2/ })).toBeNull();
});

test("at 390: New script opens a sheet with Close and both choices", async () => {
  setViewport(390);
  fakeServer({ ...base, "GET /scripts": [200, []], "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs()] });
  open("/b/1/scripts");
  await userEvent.click(await screen.findByRole("button", { name: "New script" }));
  const sheet = screen.getByRole("dialog", { name: "New script" });
  expect(within(sheet).getByRole("button", { name: "Close" })).toBeInTheDocument();
  expect(within(sheet).getByRole("menuitem", { name: /Song/ })).toBeInTheDocument();
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
