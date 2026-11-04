import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { renderApp } from "../test/render";
import { setViewport } from "../test/viewport";
import { owner, editor } from "../test/people";

type Routes = Record<string, [number, unknown]>;
const brands = [{ id: 1, name: "Resilia", colours: ["#2F6B4F"] }, { id: 2, name: "Iron Paws", colours: [] }];
const base = { kind: "character", notes: "", brand_ids: [1], image_file_ids: [], outfits: [], version: 1, sheet_status: "approved", used_in_count: 0, presenter: false, product_type: null, created_at: "2026-10-28T10:00:00Z", created_by_id: 1, pictures: [], sheet_credits: 2, change_credits: 1, usd: null };
const mark = { ...base, id: 5, name: "Mark", notes: "late 40s, tired, warm", source_photo_file_id: 30, sheet_file_id: 31, presenter: true, used_in_count: 6, version: 3, usd: { sheet: 0.17, change: 0.08 } };
const dana = { ...base, id: 6, name: "Dana", sheet_file_id: 32, used_in_count: 2 };
const old = { ...base, id: 7, name: "Old Dr. Pickle v1", sheet_file_id: 33, archived_at: "2026-10-20T10:00:00Z" };
const bag = { ...base, id: 9, kind: "prop", name: "Peanut butter bag", notes: "Main text must read right", product_type: "physical", pictures: [{ screen_id: 40, file_id: 41, name: "Peanut butter bag", variant: "" }] };
const chicken = { ...bag, id: 10, name: "Chicken bag", notes: "", pictures: [] };
const app = { ...bag, id: 11, name: "fomo app", product_type: "app", notes: "", pictures: [1, 2, 3].map((n) => ({ screen_id: 50 + n, file_id: 60 + n, name: `Screen ${n}`, variant: "" })) };
const voice = (o: object) => ({ id: null, name: "", kind: "stock", stock_key: null, provider: "elevenlabs", description: "", look: null, brand_id: null, sample_file_id: null, sample_url: null, preview_file_id: null, cloned_at: null, last_used_at: null, expires_at: null, state: "ready", error: "", used_by: [], ...o });
const voices = { voices: [voice({ id: 1, name: "Dr. Pickle", kind: "cloned", provider: "minimax", description: "Deep, fixed", look: "dr-pickle", sample_url: "http://localhost:8000/voices/samples/dr-pickle.mp3" }), voice({ name: "Sarah", stock_key: "Sarah", description: "Warm narrator" }), voice({ name: "Roger", stock_key: "Roger", description: "Relaxed man", sample_url: "http://localhost:8000/voices/samples/Roger.mp3" })], clone_credits: 29.18, clone_usd: 3 };
const looks = [{ id: "house", name: "House", blurb: "", on: true }, { id: "pixar", name: "Disney Pixar", blurb: "", on: true }];

function server(me: object, o: Routes = {}): Routes {
  return {
    "GET /auth/me": [200, me],
    "GET /brands": [200, brands],
    "GET /team/members": [200, [{ id: 1, name: "Reed", email: "r@b.co", role: "owner" }]],
    "GET /looks": [200, looks],
    "GET /models": [200, [{ id: "nano-banana-pro", kind: "image", name: "Nano Banana Pro", default: true, credits_per_unit: { "2K": 1.5 } }]],
    "GET /library/character": [200, [mark, dana]],
    "GET /library/character?brand_id=1&archived=true": [200, [old]],
    "GET /library/place": [200, []],
    "GET /library/prop": [200, [bag, chicken]],
    "GET /library/character/price": [200, { credits: 2, usd: (me as { role: string }).role === "owner" ? 0.08 : null }],
    "GET /library/character/5": [200, { ...mark, used_in: [] }],
    "GET /library/character/5/versions": [200, []],
    "GET /library/character/5/sheet/versions": [200, []],
    "GET /jobs": [200, []],
    "GET /brands/1/voices": [200, (me as { role: string }).role === "owner" ? voices : { ...voices, clone_usd: null }],
    "GET /brands/2/voices": [200, voices],
    ...o,
  };
}
const posted = (calls: { key: string; body: unknown }[], key: string) => calls.filter((c) => c.key === key).at(-1)?.body;
beforeEach(() => setViewport(1440));
afterEach(() => vi.unstubAllGlobals());

test("S8-01: the tabs with their counts, cards saying who presents and how many videos use them, and search", async () => {
  fakeServer(server(owner));
  renderApp("/b/1/library/characters");
  const tabs = await screen.findByRole("navigation", { name: "Library" });
  expect(await within(tabs).findByRole("link", { name: /^Characters\s*2$/ })).toHaveAttribute("aria-current", "page");
  expect(within(tabs).getByRole("link", { name: /^Products\s*2$/ })).toHaveAttribute("href", "/b/1/library/products");
  expect(within(tabs).getByRole("link", { name: "Brand kit" })).toHaveAttribute("href", "/b/1/brand");
  expect(screen.getByText("Only Resilia sees these. They fill in each video’s cast.")).toBeInTheDocument();
  const card = screen.getByRole("link", { name: "Mark" }).closest("li")!;
  expect(within(card).getByText("Uploaded")).toBeInTheDocument();
  expect(within(card).getByText("Presenter · used in 6 videos")).toBeInTheDocument();
  expect(screen.getByText("Used in 2 videos")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Search the library"), "dan");
  expect(screen.queryByRole("link", { name: "Mark" })).toBeNull();
  expect(screen.getByRole("link", { name: "Dana" })).toBeInTheDocument();
});

test("S8-02: an empty brand offers Upload a photo, and Make one with the most it costs in dollars for the owner", async () => {
  fakeServer(server(owner, { "GET /library/character": [200, []] }));
  renderApp("/b/1/library/characters");
  expect(await screen.findByRole("heading", { name: "No characters in Resilia yet" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Upload a photo" })).toBeInTheDocument();
  expect(await screen.findByRole("button", { name: "Make one · up to $0.08" })).toBeInTheDocument();
});

test("S8-02: an editor sees the price in credits, never dollars", async () => {
  fakeServer(server(editor, { "GET /library/character": [200, []] }));
  renderApp("/b/1/library/characters");
  expect(await screen.findByRole("button", { name: "Make one · up to 2 credits" })).toBeInTheDocument();
  expect(document.body.textContent).not.toContain("$");
});

test("S8-07: New character takes a name and a description, makes the character in this brand and draws its sheet", async () => {
  const calls = fakeServer(server(owner, { "POST /library/character": [201, { ...dana, id: 12, name: "Kim" }], "POST /library/character/12/sheet": [201, { id: 90 }], "GET /library/character/12": [200, { ...dana, id: 12, sheet_status: "drawing" }] }));
  renderApp("/b/1/library/characters");
  await userEvent.click(await screen.findByRole("button", { name: "New character" }));
  const form = screen.getByRole("form", { name: "New character" });
  await userEvent.type(within(form).getByPlaceholderText("Name"), "Kim");
  await userEvent.type(within(form).getByLabelText("Description"), "Woman, late 30s, glasses");
  await userEvent.click(within(form).getByRole("button", { name: "Make it · up to $0.08" }));
  await vi.waitFor(() => expect(posted(calls, "POST /library/character/12/sheet")).toMatchObject({ change: "" }));
  expect(posted(calls, "POST /library/character")).toMatchObject({ name: "Kim", notes: "Woman, late 30s, glasses", brand_ids: [1], presenter: false });
  expect(await screen.findByText(/Drawing a front, side and back sheet from your description · up to \$0.08 · about 30 s/)).toBeInTheDocument();
});

test("S8-08: an editor's view says editors add too; Show archived lists the archive, and Unarchive has Undo", async () => {
  const calls = fakeServer(server(editor, { "POST /library/character/7/unarchive": [200, old], "DELETE /library/character/7": [204, null] }));
  renderApp("/b/1/library/characters");
  expect(await screen.findByText("Editors can add and edit characters here too.")).toBeInTheDocument();
  await userEvent.click(screen.getByLabelText("Show archived"));
  expect(await screen.findByText("Archived 20 Oct · kept for old videos")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Delete .* forever/ })).toBeNull(); // the owner's only
  await userEvent.click(screen.getByRole("button", { name: "Unarchive Old Dr. Pickle v1" }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /library/character/7")).toBe(true));
});

test("S8-03: one item open with its status, Change this… at its price, where it came from, its place, and the videos that use it", async () => {
  const used = [1, 2, 3, 4].map((n) => ({ project_id: 20 + n, name: `Video ${n}`, status: "done", still_file_id: null, at: `2026-11-0${n}T10:00:00Z` }));
  const calls = fakeServer(server(owner, {
    "GET /library/character/5": [200, { ...mark, used_in: used }],
    "GET /library/place": [200, [{ ...base, id: 8, kind: "place", name: "Mark’s kitchen" }]],
    "PATCH /library/character/5": [200, mark],
    "POST /library/character/5/sheet": [201, { id: 91 }],
  }));
  renderApp("/b/1/library/characters/5");
  expect(await screen.findByRole("heading", { name: "Mark", level: 1 })).toBeInTheDocument();
  expect(screen.getByText("In use")).toBeInTheDocument();
  expect(screen.getByText("Presenter · late 40s, tired, warm")).toBeInTheDocument();
  expect(await screen.findByText("Uploaded by Reed, 28 Oct")).toBeInTheDocument();
  const list = screen.getByRole("region", { name: "Used in" });
  expect(within(list).getByText("Used in 4 videos")).toBeInTheDocument();
  expect(within(list).getAllByText("Done")).toHaveLength(3);
  await userEvent.click(within(list).getByRole("button", { name: "+ 1 more" }));
  expect(within(list).getAllByText("Done")).toHaveLength(4);
  await userEvent.click(screen.getByRole("button", { name: /^None/ }));
  await userEvent.click(await screen.findByRole("menuitemradio", { name: "Mark’s kitchen" }));
  await vi.waitFor(() => expect(posted(calls, "PATCH /library/character/5")).toEqual({ place_id: 8 }));
  await userEvent.click(screen.getByRole("button", { name: "Change this… · up to $0.08" }));
  await userEvent.type(screen.getByLabelText("What should change?"), "No hat");
  await userEvent.click(screen.getByRole("button", { name: "Change it · up to $0.08" }));
  await vi.waitFor(() => expect(posted(calls, "POST /library/character/5/sheet")).toMatchObject({ change: "No hat" }));
});

test("S-gaps-05 L5: a sheet that needs an OK says so and a person approves it, with Undo", async () => {
  const calls = fakeServer(server(editor, { "GET /library/character/5": [200, { ...mark, sheet_status: "needs_approval", used_in: [] }], "POST /library/character/5/sheet/approve": [200, mark], "DELETE /library/character/5/sheet/approve": [200, mark] }));
  renderApp("/b/1/library/characters/5");
  expect(await screen.findByText("Needs your OK")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Approve" }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /library/character/5/sheet/approve")).toBe(true));
});

test("Archive on the item page goes back to the list with Undo", async () => {
  const calls = fakeServer(server(owner, { "DELETE /library/character/5": [204, null], "POST /library/character/5/unarchive": [200, mark] }));
  renderApp("/b/1/library/characters/5");
  await userEvent.click(await screen.findByRole("button", { name: "Archive" }));
  expect(await screen.findByText("Mark archived.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /library/character/5/unarchive")).toBe(true));
});

test("a sheet that reads wrong says so, and Fix it with a note opens Change this… with the problem as its note", async () => {
  fakeServer(server(owner, { "GET /library/character/5": [200, { ...mark, used_in: [], look_fit: { seen: "a man in his 20s", problem: "Mark is in his late 40s" } }] }));
  renderApp("/b/1/library/characters/5");
  expect(await screen.findByText(/This look reads as a man in his 20s, but Mark is in his late 40s\./)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Fix it with a note" }));
  expect(screen.getByLabelText("What should change?")).toHaveValue("Mark is in his late 40s");
});

test("More: words are saved, an old version is restored with Undo, and the owner can delete forever", async () => {
  const versions = [{ version: 3, snapshot: mark, saved_by_id: 1, created_at: "2026-10-28T10:00:00Z" }, { version: 2, snapshot: { ...mark, sheet_file_id: 29 }, saved_by_id: 1, created_at: "2026-10-27T10:00:00Z" }];
  const calls = fakeServer(server(owner, { "GET /library/character/5/versions": [200, versions], "PATCH /library/character/5": [200, mark], "POST /library/character/5/versions/2/restore": [200, { ...mark, version: 4 }], "POST /library/character/5/versions/3/restore": [200, mark] }));
  renderApp("/b/1/library/characters/5");
  await userEvent.click(await screen.findByRole("button", { name: "More" }));
  const name = screen.getByRole("textbox", { name: "Name" });
  await userEvent.clear(name);
  await userEvent.type(name, "Marcus");
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
  await vi.waitFor(() => expect(posted(calls, "PATCH /library/character/5")).toMatchObject({ name: "Marcus", brand_ids: [1] }));
  await userEvent.click(screen.getByRole("button", { name: "Restore v2" }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /library/character/5/versions/3/restore")).toBe(true));
  expect(screen.getByRole("button", { name: "Delete forever" })).toBeInTheDocument();
});

test("More: the owner makes a sheet in another style; an editor sees it without the press", async () => {
  const calls = fakeServer(server(owner, { "POST /library/character/5/sheet": [201, { id: 90 }] }));
  const { unmount } = renderApp("/b/1/library/characters/5");
  await userEvent.click(await screen.findByRole("button", { name: "More" }));
  const pixar = await screen.findByLabelText("Disney Pixar sheet");
  await userEvent.click(within(pixar).getByRole("button", { name: /Make a Disney Pixar sheet · up to 2 credits/ }));
  await vi.waitFor(() => expect(posted(calls, "POST /library/character/5/sheet")).toMatchObject({ look_id: "pixar" }));
  unmount();
  fakeServer(server(editor));
  renderApp("/b/1/library/characters/5");
  await userEvent.click(await screen.findByRole("button", { name: "More" }));
  expect(within(await screen.findByLabelText("Disney Pixar sheet")).getByText("Only the owner adds a sheet in another style.")).toBeInTheDocument();
});

test("S8-06 / L1: products are apps or physical things; one with no photo takes one from its card, linked to it", async () => {
  const calls = fakeServer(server(owner, { "GET /library/prop": [200, [bag, chicken, app]], "POST /files": [201, { id: 77 }], "POST /brands/2/screens": [201, {}] }));
  renderApp("/b/2/library/products");
  const pb = (await screen.findByRole("link", { name: "Peanut butter bag" })).closest("li")!;
  expect(within(pb).getByText("Physical")).toBeInTheDocument();
  expect(within(pb).getByText("Main text must read right")).toBeInTheDocument();
  const fomo = screen.getByRole("link", { name: "fomo app" }).closest("li")!;
  expect(within(fomo).getByText("App")).toBeInTheDocument();
  expect(within(fomo).getByText("3 screens · shown as given; numbers follow the story")).toBeInTheDocument();
  expect(screen.getByText("No photo yet. The director asks for it when a video needs it.")).toBeInTheDocument();
  await userEvent.upload(screen.getByLabelText("Add a photo of Chicken bag"), new File(["x"], "chicken.png", { type: "image/png" }));
  await vi.waitFor(() => expect(posted(calls, "POST /brands/2/screens")).toMatchObject({ product_id: 10, file_id: 77, name: "Chicken bag", tags: ["product"] }));
});

test("New product: an app with its screens, each named from its file and linked to the app", async () => {
  const calls = fakeServer(server(owner, { "POST /library/prop": [201, { ...app, id: 15, pictures: [] }], "POST /files": [201, { id: 78 }], "POST /brands/2/screens": [201, {}] }));
  renderApp("/b/2/library/products");
  await userEvent.click(await screen.findByRole("button", { name: "New product" }));
  const form = screen.getByRole("form", { name: "New product" });
  await userEvent.type(within(form).getByPlaceholderText("Name"), "fomo app");
  await userEvent.click(within(form).getByRole("radio", { name: "An app" }));
  await userEvent.upload(within(form).getByLabelText("Upload screens"), [new File(["a"], "home-rich.png", { type: "image/png" }), new File(["b"], "token-up.png", { type: "image/png" })]);
  await userEvent.click(within(form).getByRole("button", { name: "Save product" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /brands/2/screens")).toHaveLength(2));
  expect(posted(calls, "POST /library/prop")).toMatchObject({ name: "fomo app", product_type: "app", brand_ids: [2] });
  expect(calls.filter((c) => c.key === "POST /brands/2/screens").map((c) => (c.body as { name: string; product_id: number }).name)).toEqual(["Home rich", "Token up"]);
});

test("the old Props tab lands on Products", async () => {
  fakeServer(server(owner));
  renderApp("/b/2/library/props");
  expect(await screen.findByRole("link", { name: /^Products/, current: "page" })).toBeInTheDocument();
});

test("S8-04 / L3: presenters are listed beside the voices; a new presenter is a face and a voice, saved free", async () => {
  const calls = fakeServer(server(owner, { "POST /library/character": [201, { ...mark, id: 13 }], "GET /library/character/13": [200, { ...mark, id: 13, used_in: [] }], "GET /library/character/13/versions": [200, []], "GET /library/character/13/sheet/versions": [200, []] }));
  renderApp("/b/1/library/presenters");
  const presenters = await screen.findByRole("region", { name: "Presenters" });
  expect(await within(presenters).findByRole("link", { name: "Mark" })).toBeInTheDocument();
  expect(within(presenters).queryByRole("link", { name: "Dana" })).toBeNull();
  expect(screen.getByRole("region", { name: "Voices" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "New presenter" }));
  await userEvent.type(screen.getByPlaceholderText("Name"), "Paige");
  expect(screen.getByText("A face and a voice, nothing else.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Save presenter" }));
  await vi.waitFor(() => expect(posted(calls, "POST /library/character")).toMatchObject({ name: "Paige", presenter: true, brand_ids: [1] }));
});

test("P-13: on a phone the tabs are a strip with every tab, and cards say how many videos", async () => {
  setViewport(390);
  fakeServer(server(owner));
  renderApp("/b/1/library/characters");
  const tabs = await screen.findByRole("navigation", { name: "Library" });
  expect(within(tabs).getAllByRole("link").map((l) => l.textContent)).toEqual(["Characters", "Places", "Products", "Presenters", "Brand kit"]);
  expect(await screen.findByText("6 videos")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "New character" })).toBeInTheDocument();
});

test("S8-04 / L4: the brand's own voices, then every app voice with its free sample, and Clone a voice with its price", async () => {
  const calls = fakeServer(server(owner, { "POST /files": [201, { id: 80 }], "POST /brands/1/voices/clone": [201, voice({ id: 2, name: "Kim", kind: "cloned", state: "cloning" })] }));
  renderApp("/b/1/library/presenters");
  const list = await screen.findByRole("region", { name: "Voices" });
  expect(await within(list).findByText("Dr. Pickle (cloned)")).toBeInTheDocument();
  expect(within(list).getByText("Deep, fixed · MiniMax clone")).toBeInTheDocument();
  expect(within(list).getByText(/^The app’s voices · 2 · usable in any video/)).toBeInTheDocument();
  expect(within(list).getByRole("button", { name: "Play Roger" })).toBeEnabled();
  expect(within(list).queryByRole("button", { name: "Play Sarah" })).toBeNull(); // no free sample yet: no Play
  expect(list.querySelector("audio[src='/api/voices/samples/Roger.mp3']")).not.toBeNull();
  expect(await screen.findByRole("link", { name: /^Presenters & voices\s*2$/ })).toBeInTheDocument(); // Mark and the brand's one voice
  await userEvent.click(within(list).getByRole("button", { name: "Clone a voice · up to $3.00" }));
  await userEvent.upload(within(list).getByLabelText("Pick a sample"), new File(["a"], "kim.mp3", { type: "audio/mpeg" }));
  await userEvent.type(within(list).getByLabelText("Name"), "Kim");
  await userEvent.click(within(list).getByRole("button", { name: "Clone · up to $3.00" }));
  await vi.waitFor(() => expect(posted(calls, "POST /brands/1/voices/clone")).toEqual({ name: "Kim", description: "", sample_file_id: 80 }));
});

test("an editor's Clone says credits, never dollars", async () => {
  fakeServer(server(editor));
  renderApp("/b/1/library/presenters");
  expect(await screen.findByRole("button", { name: "Clone a voice · up to 30 credits" })).toBeInTheDocument();
});

test("S8-03: a character's voice is any app voice or a saved one, picked from every voice", async () => {
  const calls = fakeServer(server(owner, { "GET /library/character/5": [200, { ...mark, voice_stock_key: "Roger", used_in: [] }], "PATCH /library/character/5": [200, mark] }));
  renderApp("/b/1/library/characters/5");
  expect(await screen.findByText("Roger · relaxed man")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Change" }));
  await userEvent.click(await screen.findByRole("menuitemradio", { name: "Dr. Pickle" }));
  await vi.waitFor(() => expect(posted(calls, "PATCH /library/character/5")).toEqual({ voice_id: 1, voice_stock_key: null }));
});

test("a New character whose sheet is refused can be tried again without making a second character (QA)", async () => {
  const routes = server(owner, { "POST /library/character": [201, { ...dana, id: 12, name: "Kim" }], "POST /library/character/12/sheet": [409, { detail: "Generation is paused." }], "GET /library/character/12": [200, { ...dana, id: 12, sheet_status: "drawing" }] });
  const calls = fakeServer(routes);
  renderApp("/b/1/library/characters?new=1");
  const form = await screen.findByRole("form", { name: "New character" });
  await userEvent.type(within(form).getByPlaceholderText("Name"), "Kim");
  await userEvent.type(within(form).getByLabelText("Description"), "Woman, 30s");
  await userEvent.click(within(form).getByRole("button", { name: /^Make it/ }));
  expect(await within(form).findByText("Generation is paused.")).toBeInTheDocument();
  routes["POST /library/character/12/sheet"] = [201, { id: 90 }];
  await userEvent.click(within(form).getByRole("button", { name: /^Make it/ }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /library/character/12/sheet")).toHaveLength(2));
  expect(calls.filter((c) => c.key === "POST /library/character")).toHaveLength(1);
});
