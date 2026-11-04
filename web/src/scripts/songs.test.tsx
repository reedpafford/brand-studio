import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";
import { editor, owner } from "../test/people";

const brands = [{ id: 1, name: "Iron Paws", colours: [], end_line: "Get Iron Paws through the link in my bio." }];
const LYRICS = "[Verse]\nBo would never touch his bowl\n[Chorus]\nNow he licks it clean";
const version = (o: object = {}) => ({ slot: 0, status: "draft", title: "Bowl song", seconds: 0, project_id: null, text: LYRICS, words: 10, target_seconds: null, premise: "", changes: [], problems: [], has_breakdown: false, approved_at: null, style_line: "pop, female lead, upbeat", singer: "", spoken_end_line: "", song_directions: [], ...o });
const song = (o: object = {}, v: object = {}) => ({
  id: 7, brand_id: 1, kind: "song", format: "song", title: "Bowl song", description: "", reference_id: null, published: false, status: "draft", created_by_id: 1, created_by_name: "Reed", created_at: "2026-10-28T10:00:00Z", versions_left: 0,
  notes: "", reference_replace: "", cast: [], versions: [version(v)], ...o,
});
const take = (o: object = {}) => ({ id: 1, number: 1, status: "ready", failed_reason: null, retry_helps: true, retry_credits: 0, file_id: 40, seconds: 31, made_at: "2026-10-28T10:42:00Z", preferred: false, out_of_date: false, peaks: [0.2, 0.8, 0.5], advice: [], timing_guessed: false, refused_for: null, video_credits: 34, ...o });
const songs = (takes: object[] = [], o: object = {}) => ({ songs_on: true, estimate_credits: 1, video_estimate_credits: 40, takes, ...o });
const base: Record<string, [number, unknown]> = { "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /references": [200, []], "GET /projects": [200, []], "GET /jobs": [200, []] };

function open(path: string) {
  renderApp(path);
}

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

test("New script → Song waits for a word or a setting, then opens on its Song step: five steps, Next waits for lyrics", async () => {
  setViewport(1440);
  const empty = song({ title: "Untitled script" }, { text: "", style_line: "" });
  const calls = fakeServer({ ...base, "GET /scripts": [200, []], "POST /scripts": [201, empty], "GET /scripts/7": [200, empty], "GET /scripts/7/drafts/0/songs": [200, songs()], "GET /brands/1/folders": [200, [{ id: 3, name: "Launch", brand_id: 1, counts: {} }]], "POST /folders/file": [200, { was_folder_id: null }] });
  open("/b/1/scripts");
  await userEvent.click(await screen.findByRole("button", { name: "New script" }));
  await userEvent.click(screen.getByRole("menuitem", { name: /Song/ }));
  expect(await screen.findByLabelText("Lyrics")).toHaveValue("");
  expect(calls.filter((c) => c.key === "POST /scripts")).toHaveLength(0);
  await userEvent.click(await screen.findByRole("button", { name: "Project: none" }));
  await userEvent.click(await screen.findByRole("menuitem", { name: "Launch" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts")?.body).toMatchObject({ kind: "song", format: "song", text: "" }));
  // The new page shows the same steps before the save, so wait for the script page's own Next first.
  expect(await screen.findByRole("button", { name: "Next: Takes" })).toBeInTheDocument();
  expect(await screen.findByRole("list", { name: "Steps" })).toBeInTheDocument();
  expect(await screen.findByLabelText("Lyrics")).toHaveValue("");
  const steps = screen.getByRole("list", { name: "Steps" });
  expect(within(steps).getAllByRole("button").map((b) => b.textContent?.replace(/^\d+/, ""))).toEqual(["Lyrics", "Takes", "Breakdown", "Cast"]); // v5 G_SongTakes; Publish is "Publish to library", not in the bar
  expect(within(steps).getByRole("button", { name: "Cast" })).toHaveAccessibleDescription("Write or pick the lyrics first");
  expect(screen.getByRole("button", { name: "Next: Takes" })).toBeDisabled();
  expect(screen.getByLabelText("Music style")).toHaveAttribute("placeholder", "pop, female lead, 120 BPM, upbeat, modern polished");
});

test("New script → Song: letters typed while its takes load all reach the Lyrics box", async () => {
  setViewport(1440);
  const empty = song({ title: "Untitled script" }, { text: "", style_line: "" });
  const calls = fakeServer({ ...base, "GET /scripts": [200, []], "POST /scripts": [201, empty], "GET /scripts/7/drafts/0/songs": [200, songs()] });
  let release = () => {};
  const held = new Promise<void>((r) => (release = r));
  const fake = globalThis.fetch;
  let loading = false;
  vi.stubGlobal("fetch", async (input: Request | string, init?: RequestInit) => {
    const req = input instanceof Request ? input : new Request(new URL(input, "http://x"), init);
    if (new URL(req.url).pathname.endsWith("/songs")) {
      loading = true;
      await held;
    }
    return fake(input, init);
  });
  open("/b/1/scripts/new?format=song");
  const box = await screen.findByLabelText("Lyrics");
  await userEvent.type(box, "[[");
  await vi.waitFor(() => expect(loading).toBe(true));
  await userEvent.type(box, "Verse]"); // the takes are still loading: this box still has them
  release();
  await screen.findByRole("list", { name: "Steps" });
  expect(screen.getByLabelText("Lyrics")).toHaveValue("[Verse]");
  expect(screen.getByLabelText("Lyrics")).toHaveFocus();
  expect(calls.filter((c) => c.key === "POST /scripts")).toHaveLength(1);
});

test("lyrics: the sung length counts words not tags; over 4,960 characters says how many to cut and keeps the words; Save sends lyrics and style", async () => {
  setViewport(1440);
  const empty = song({}, { text: "", style_line: "" });
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, empty], "GET /scripts/7/drafts/0/songs": [200, songs()], "PUT /scripts/7/drafts/0": [200, song()] });
  open("/b/1/scripts/7?step=script");
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
  open("/b/1/scripts/7?step=script");
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
  await userEvent.click(screen.getByRole("button", { name: /Make 2 takes · up to 1 credit/ }));
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
  const list = songs([take({ preferred: true }), take({ id: 2, number: 2, status: "timing" }), take({ id: 3, number: 3, status: "timing_failed", retry_helps: false, failed_reason: "This take's file can't be read, so its timing can't be measured." }), take({ id: 4, number: 4 }), take({ id: 5, number: 5, status: "making", file_id: null, seconds: null, made_at: null, started_at: new Date(Date.now() - 70_000).toISOString() })]);
  fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, list] });
  open("/b/1/scripts/7?step=takes");
  expect(await screen.findByText("Preferred")).toBeInTheDocument();
  expect(screen.getAllByText("A video of about 34 credits")).toHaveLength(4); // every take with a length says what its video would cost
  expect(screen.getByText((_, el) => el?.tagName === "P" && /^Making the song… 1:1\d$/.test(el.textContent ?? ""))).toBeInTheDocument(); // flows S4: from when its job started (#1033), so a reload keeps it
  expect(screen.getAllByRole("button", { name: "Make Preferred" })[0]).toBeDisabled();
  expect(screen.getByText("This take's file can't be read, so its timing can't be measured.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Try again/ })).toBeNull();
  expect(screen.getByRole("button", { name: "Make take 4 Preferred" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Use timing spread evenly/ })).toBeNull(); // the file can't be read: spreading can't help
  expect(screen.getByRole("button", { name: "Next: Breakdown" })).toBeEnabled();
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
  expect(within(sheet).getByRole("menuitem", { name: /Dialogue.*People speak their lines on camera/ })).toBeInTheDocument();
  expect(within(sheet).getByRole("menuitem", { name: /Song.*An animated music video/ })).toBeInTheDocument();
  expect(within(sheet).getByRole("menuitem", { name: /Narrated.*One voice will read it/ })).toBeInTheDocument();
});

test("a format added to the guides is a New script choice with its own words; one that is off is not", async () => {
  setViewport(390);
  const cooking = { id: "cooking", name: "Cooking", engine: "story", on: true, blurb: "A recipe, step by step." };
  const off = { id: "zack-d", name: "Zack D", engine: "narrated", on: false, blurb: "One camera journey." };
  fakeServer({ ...base, "GET /formats": [200, [{ id: "dialogue", name: "Dialogue", engine: "story", on: true, blurb: "Lines on camera." }, cooking, off]], "GET /scripts": [200, []] });
  open("/b/1/scripts");
  await userEvent.click(await screen.findByRole("button", { name: "New script" }));
  const sheet = screen.getByRole("dialog", { name: "New script" });
  expect(within(sheet).getByRole("menuitem", { name: /Cooking.*A recipe, step by step/ })).toBeInTheDocument();
  expect(within(sheet).queryByRole("menuitem", { name: /Zack D/ })).toBeNull();
});

test("at 390 on a song script, the steps are one button: Step 1 of 4 · Lyrics", async () => {
  setViewport(390);
  fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs()] });
  open("/b/1/scripts/7?step=script");
  expect(await screen.findByRole("button", { name: "Step 1 of 4 · Lyrics" })).toBeInTheDocument();
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
  await userEvent.click(await screen.findByRole("button", { name: "Make Preferred" }));
  expect(await screen.findByText("This take sings older words. Make 2 takes of the lyrics as they are now.")).toBeInTheDocument();
});

test("after the lyrics change, a Preferred take that sings the older words doesn't open Cast", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs([take({ preferred: true, out_of_date: true }), take({ id: 2, number: 2, out_of_date: true })])] });
  open("/b/1/scripts/7?step=takes");
  expect(await screen.findByText("These takes sing older words.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Next: Breakdown" })).toBeDisabled();
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

test("a failed take that isn't a refusal offers Try again on its row; Edit lyrics or music style stays in the header", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs([take({ status: "failed", retry_credits: 1, file_id: null, seconds: null, failed_reason: "Suno took too long. Nothing was charged." })])] });
  open("/b/1/scripts/7?step=takes");
  const row = within(await screen.findByRole("listitem", { name: "Take 1" }));
  expect(await row.findByRole("button", { name: /Try again · 1 credit/ })).toBeInTheDocument();
  expect(row.queryByRole("link", { name: /Edit/ })).toBeNull();
  expect(screen.getAllByRole("link", { name: "Edit lyrics or music style" })).toHaveLength(1);
});

test("a song take that hasn't started says Waiting to start, with a timer", async () => {
  setViewport(390);
  fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs([take({ status: "making", file_id: null, seconds: null, made_at: null, started_at: null })])] });
  open("/b/1/scripts/7?step=takes");
  expect(await screen.findByText((_, el) => el?.tagName === "P" && /^Waiting to start · 0:0\d$/.test(el.textContent ?? ""))).toBeInTheDocument();
});

test("at 390, an editor's Make 2 takes reads Send for approval, and once pressed the script shows it waiting (QA on #1088)", async () => {
  setViewport(390);
  const waiting = { id: 60, kind: "music", project_id: null, script_id: 7, credits: 1, status: "needs_owner_approval", created_at: new Date().toISOString(), finished_at: null, prompt_summary: "", step: "song_take", error: "", held: "Songs, narration and music on a script wait for the owner's OK.", declined: false, created_by_name: "Eli", waiting: "", auto: false, output: null };
  const routes = { ...base, "GET /auth/me": [200, editor] as [number, unknown], "GET /scripts/7": [200, song()] as [number, unknown], "GET /scripts/7/drafts/0/songs": [200, songs()] as [number, unknown], "POST /scripts/7/drafts/0/songs": [201, songs()] as [number, unknown] };
  fakeServer(routes);
  open("/b/1/scripts/7?step=takes");
  const ask = await screen.findByRole("button", { name: /Send for approval · up to 1 credit/ });
  expect(screen.queryByRole("button", { name: /Make 2 takes/ })).toBeNull();
  expect(screen.getByText("Songs, narration and music on a script wait for the owner's OK. Nothing is charged until they say yes.")).toBeInTheDocument();
  fakeServer({ ...routes, "GET /jobs": [200, [waiting]] });
  await userEvent.click(ask);
  expect(await screen.findByText("Sent for approval. It waits for the owner's OK; nothing is charged until then.")).toBeInTheDocument();
  expect(await screen.findByText("Waiting for approval")).toBeInTheDocument();
  expect(document.body).toHaveTextContent("Your song or music · 1 credit · Asked just now. Songs, narration and music on a script wait for the owner's OK.");
  expect(document.body.textContent).not.toMatch(/ask (Reed|the owner)/i);
});

test("Takes (v5): the takes are rows under the header's Edit and Make 2 more, and the card under them says what a video costs and the song's last line", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, song()], "GET /scripts/7/drafts/0/songs": [200, songs([take(), take({ id: 2, number: 2, preferred: true }), take({ id: 3, number: 3 })])] });
  open("/b/1/scripts/7?step=takes");
  const list = await screen.findByRole("list", { name: "Takes" });
  expect(within(list).getAllByRole("listitem").map((r) => r.getAttribute("aria-label"))).toEqual(["Take 2", "Take 1", "Take 3"]); // the Preferred one first
  expect(screen.getByText("Pick the Preferred take; the video is cut to it.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^Make 2 more/ })).toBeInTheDocument();
  expect(screen.getByText("A video this long: about 40 credits to make (planned).")).toBeInTheDocument();
  expect(screen.getByText('The song then ends on: "Now he licks it clean"')).toBeInTheDocument();
});

test("a new song script, before it is saved, shows the same four steps as a saved one: Lyrics · Takes · Breakdown · Cast (QA-3 on #1260)", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts": [200, []] });
  open("/b/1/scripts/new?kind=song");
  const steps = await screen.findByRole("list", { name: "Steps" });
  expect(within(steps).getAllByRole("button").map((b) => b.textContent?.replace(/^\d+/, ""))).toEqual(["Lyrics", "Takes", "Breakdown", "Cast"]);
});

test("at 390 a new song script reads Step 1 of 4 · Lyrics", async () => {
  setViewport(390);
  fakeServer({ ...base, "GET /scripts": [200, []] });
  open("/b/1/scripts/new?kind=song");
  expect(await screen.findByRole("button", { name: "Step 1 of 4 · Lyrics" })).toBeInTheDocument();
});
