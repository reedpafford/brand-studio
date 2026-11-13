import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { renderApp } from "../test/render";
import { fakeServer } from "../test/server";
import { CLIPS, FOLDERS, HOW, VOICES, alarm, dana, empty, full, officer, paige, type Routes } from "../test/studioLibrary";
import { setViewport } from "../test/viewport";

// The Library in the new look (/s/b/1/library): what each tab shows, every press it has, and exactly what each sends.
// Each request is one the current site's Library sends for the same press, through the same hook (the PR lists them
// side by side). Opening a tab sends nothing but reads; a paid press pressed twice in one tick is one request.
type Tab = "product" | "cast" | "footage" | "voices";
const OK: [number, unknown] = [200, {}];
const GONE: [number, unknown] = [204, null];
const SHEET = { model_id: "nano-banana-pro" };
async function open(tab: Tab, routes: Routes, extra: Routes = {}) {
  const calls = fakeServer({ ...routes, ...extra });
  renderApp(`/s/b/1/library${tab === "product" ? "" : `?tab=${tab}`}`);
  await screen.findByRole("heading", { name: "Library" });
  return calls;
}
/** Everything the page has sent that isn't a read: its method and path, and its body (a file upload has none here). */
const sent = (calls: ReturnType<typeof fakeServer>) => calls.filter((c) => !c.key.startsWith("GET ")).map((c) => (c.body === undefined ? [c.key] : [c.key, c.body]));
/** Each file upload's fields as they are sent (the file itself as FILE): the fake server keeps JSON bodies only. */
const FILE = "(the file)";
function uploads() {
  const answer = globalThis.fetch;
  const seen: [string, Record<string, string>][] = [];
  vi.stubGlobal("fetch", async (input: Request, init?: RequestInit) => {
    if (input.headers.get("content-type")?.includes("multipart")) {
      const fields = [...(await input.clone().formData())].map(([k, v]) => [k, typeof v === "string" ? v : FILE]);
      seen.push([`${input.method} ${new URL(input.url).pathname.replace(/^\/api/, "")}`, Object.fromEntries(fields)]);
    }
    return answer(input, init);
  });
  return seen;
}
/** Holds the server's answer to one request until the returned function is called: a press while its request is in flight. */
function hold(key: string) {
  const answer = globalThis.fetch;
  let release = () => {};
  const gate = new Promise<void>((r) => (release = r));
  vi.stubGlobal("fetch", async (input: Request, init?: RequestInit) => {
    if (`${input.method} ${new URL(input.url).pathname.replace(/^\/api/, "")}` === key) await gate;
    return answer(input, init);
  });
  return release;
}
const file = (name: string, type: string) => new File(["x"], name, { type });
const page = () => within(screen.getByRole("main"));
const dialog = (name: string | RegExp) => within(screen.getByRole("dialog", { name }));
const person = async (name: string) => (await userEvent.click(await page().findByRole("button", { name })), within(await page().findByRole("region", { name })));
const quiet = () => act(() => new Promise((r) => setTimeout(r, 40)));

beforeEach(() => {
  localStorage.clear();
  setViewport(1440);
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

test.each<[Tab, string, Routes, string]>([
  ["product", "a brand with everything", full, "Protector alarm"],
  ["cast", "a brand with everything", full, "Her mother, late forties"],
  ["footage", "a brand with everything", full, "Not in a folder"],
  ["voices", "a brand with everything", full, "Kim"],
  ["product", "an empty brand", empty, "No product saved for Palace Guard yet"],
  ["cast", "an empty brand", empty, "Nobody saved in Palace Guard yet"],
  ["footage", "an empty brand", empty, "No footage for Palace Guard yet"],
  ["voices", "an empty brand", empty, "None yet. Clone a voice from a recording to keep one for Palace Guard."],
])("opening %s on %s only reads: nothing is sent without a press", async (tab, _brand, routes, shows) => {
  const calls = await open(tab, routes);
  expect(await page().findByText(shows)).toBeInTheDocument();
  expect(page().queryByRole("alert")).toBeNull(); // an empty brand is never an error
  await quiet();
  expect(sent(calls)).toEqual([]);
});

test("Product: its photos, what the server holds about it, How it works as stored, and its clips by the folder each is in", async () => {
  await open("product", full);
  const about = within(await page().findByRole("complementary", { name: "The product" }));
  expect(about.getByRole("heading", { name: "Protector alarm" })).toBeInTheDocument();
  expect(about.getByText("A white personal alarm with a ring at the top.")).toBeInTheDocument();
  expect(about.getByText("Loud enough to stop a stranger")).toBeInTheDocument();
  expect(about.getByRole("img", { name: "Protector alarm: Protector alarm" })).toHaveAttribute("src", "/api/files/41");
  await userEvent.click(about.getByRole("button", { name: "In the hand" }));
  expect(about.getByRole("img", { name: "Protector alarm: In the hand" })).toHaveAttribute("src", "/api/files/43");
  expect(about.getByRole("region", { name: "How it works" }).querySelector(".words")!.textContent).toBe(HOW); // every space and line as stored
  expect(about.queryByRole("link", { name: "the current site" })).toBeNull(); // a physical product's photos are added and removed here
  expect(await within(page().getByRole("region", { name: "Product shots" })).findByRole("button", { name: "A hand hooks the ring and pulls it out., 0:05 long" })).toBeInTheDocument();
  expect(within(page().getByRole("region", { name: "Product shots › Close-ups" })).getAllByRole("button")).toHaveLength(1);
  expect(within(page().getByRole("region", { name: "Not in a folder" })).getByRole("button", { name: /^The alarm on a set of keys/ })).toBeInTheDocument();
  expect(page().queryByRole("button", { name: /^A path across a quad/ })).toBeNull(); // not a clip of this product
});

test("How it works: opening the editor and closing it without typing sends nothing, and the box holds the stored text untouched", async () => {
  const calls = await open("product", full, { "PATCH /library/prop/54": [200, alarm] });
  const how = within(await page().findByRole("region", { name: "How it works" }));
  await userEvent.click(how.getByRole("button", { name: "Edit" }));
  expect((how.getByRole("textbox", { name: "How it works" }) as HTMLTextAreaElement).value).toBe(HOW);
  expect(how.getByRole("button", { name: "Save" })).toBeDisabled(); // nothing typed: nothing to save
  await userEvent.click(how.getByRole("button", { name: "Save" }));
  await userEvent.click(how.getByRole("button", { name: "Cancel" }));
  expect(how.queryByRole("textbox")).toBeNull();
  await quiet();
  expect(sent(calls)).toEqual([]);
});

test("How it works: Save sends the box's text byte for byte, in the current site's own save of the product's notes", async () => {
  const typed = `${HOW}\n  Never squeezed,\ttwisted or pressed.  \n\n`;
  const calls = await open("product", full, { "PATCH /library/prop/54": [200, { ...alarm, notes: typed }] });
  const how = within(await page().findByRole("region", { name: "How it works" }));
  await userEvent.click(how.getByRole("button", { name: "Edit" }));
  fireEvent.change(how.getByRole("textbox", { name: "How it works" }), { target: { value: typed } });
  await userEvent.click(how.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(how.queryByRole("textbox")).toBeNull());
  expect(sent(calls)).toEqual([["PATCH /library/prop/54", { name: "Protector alarm", notes: typed, brand_ids: [1], short_description: "A white personal alarm with a ring at the top.", main_claim: "Loud enough to stop a stranger" }]]);
  expect(calls.find((c) => c.key.startsWith("PATCH"))!.body).toHaveProperty("notes", typed); // the very string: no trim, no tidy
});

test("Product: a photo is uploaded and added as the product's next picture", async () => {
  const calls = await open("product", full, { "POST /files": [201, { id: 80 }], "POST /brands/1/screens": [201, {}] });
  await userEvent.upload(await page().findByLabelText("Add a photo of Protector alarm"), file("side.jpg", "image/jpeg"));
  await waitFor(() => expect(sent(calls)).toEqual([["POST /files"], ["POST /brands/1/screens", { name: "Protector alarm (3)", file_id: 80, tags: ["product"], default_for: ["product"], product_id: 54, variant: "" }]]));
});

test("Product: Remove this photo removes the one shown, and Undo brings it back", async () => {
  const calls = await open("product", full, { "DELETE /brands/1/screens/40": [204, null], "POST /brands/1/screens/40/restore": [200, {}] });
  await userEvent.click(await page().findByRole("button", { name: "Remove this photo" }));
  expect(await screen.findByText("Photo removed. The director won’t be given it again; clips already made keep it.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await waitFor(() => expect(sent(calls)).toEqual([["DELETE /brands/1/screens/40"], ["POST /brands/1/screens/40/restore"]]));
});

test("Product: when the product holds its own picture list, the director's list is kept in step with a photo removed or added", async () => {
  const own = { ...full, "GET /library/prop": [200, [{ ...alarm, image_file_ids: [41] }]] } as Routes;
  const calls = await open("product", own, { "PATCH /library/prop/54": [200, alarm], "DELETE /brands/1/screens/40": [204, null], "POST /files": [201, { id: 80 }], "POST /brands/1/screens": [201, {}] });
  await userEvent.click(await page().findByRole("button", { name: "Remove this photo" }));
  await waitFor(() => expect(sent(calls)).toEqual([["PATCH /library/prop/54", { image_file_ids: [] }], ["DELETE /brands/1/screens/40"]]));
  calls.length = 0;
  await userEvent.upload(page().getByLabelText("Add a photo of Protector alarm"), file("side.jpg", "image/jpeg"));
  await waitFor(() => expect(sent(calls)).toEqual([["POST /files"], ["POST /brands/1/screens", expect.objectContaining({ file_id: 80, product_id: 54 })], ["PATCH /library/prop/54", { image_file_ids: [41, 80] }]]));
});

test("Product: its sound is uploaded and kept on the product", async () => {
  const calls = await open("product", full, { "POST /files": [201, { id: 81 }], "PATCH /library/prop/54": [200, alarm] });
  expect(await within(await page().findByRole("region", { name: "Its sound" })).findByText(/^None yet\./)).toBeInTheDocument();
  await userEvent.upload(page().getByLabelText("A sound file for Protector alarm"), file("whistle.wav", "audio/wav"));
  await waitFor(() => expect(sent(calls)).toEqual([["POST /files"], ["PATCH /library/prop/54", { voice_file_id: 81 }]]));
});

test("Product: a product with a sound plays it by name, and Remove clears it", async () => {
  const withSound = { ...full, "GET /library/prop": [200, [{ ...alarm, voice_file_id: 81, voice_file_name: "whistle.wav" }]] } as Routes;
  const calls = await open("product", withSound, { "PATCH /library/prop/54": [200, alarm] });
  const sound = within(await page().findByRole("region", { name: "Its sound" }));
  expect(sound.getByText("whistle.wav")).toBeInTheDocument();
  expect(sound.getByRole("button", { name: "Play Protector alarm’s sound" })).toBeInTheDocument();
  await userEvent.click(sound.getByRole("button", { name: "Remove" }));
  await waitFor(() => expect(sent(calls)).toEqual([["PATCH /library/prop/54", { voice_file_id: null }]]));
});

test("Product: Add clips sends the clip with its product; left without words the AI describes it, and the press says its price", async () => {
  const calls = await open("product", full, { "POST /brands/1/footage": [201, { ...CLIPS[0], id: 14, describing: true }] });
  const forms = uploads();
  await userEvent.click(await page().findByRole("button", { name: "Add clips" }));
  const box = dialog("Add a clip");
  expect(box.getByText("To All footage (the top)")).toBeInTheDocument();
  expect(await box.findByText("Leave it empty and the AI describes it from two of its frames · up to $0.02")).toBeInTheDocument();
  expect(box.getByRole("button", { name: "Add clip · up to $0.02" })).toBeDisabled(); // no clip chosen yet
  await userEvent.upload(box.getByLabelText("Choose a clip"), file("pull.mp4", "video/mp4"));
  await userEvent.click(box.getByRole("button", { name: "Add clip · up to $0.02" }));
  expect(await screen.findByText("Clip added. Describing what it shows…")).toBeInTheDocument();
  expect(forms).toEqual([["POST /brands/1/footage", { upload: FILE, description: "", folder: "", product_id: "54" }]]);
  expect(sent(calls)).toHaveLength(1);
});

test("a clip opens larger with what it shows; Delete removes it, and Undo brings it back", async () => {
  const calls = await open("product", full, { "DELETE /brands/1/footage/10": GONE, "POST /brands/1/footage/10/restore": [200, CLIPS[0]] });
  await userEvent.click(await page().findByRole("button", { name: /^A hand hooks the ring/ }));
  const box = dialog("A clip");
  expect(box.getByLabelText("A hand hooks the ring and pulls it out.")).toHaveAttribute("src", "/api/files/710");
  expect(box.getByText("0:05 long · Protector alarm · in Product shots")).toBeInTheDocument();
  await userEvent.click(box.getByRole("button", { name: "Delete this clip" }));
  expect(await screen.findByText("Clip deleted.")).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await waitFor(() => expect(sent(calls)).toEqual([["DELETE /brands/1/footage/10"], ["POST /brands/1/footage/10/restore"]]));
});

test("an empty brand's New product saves the product in this brand, then its photo (free)", async () => {
  const calls = await open("product", empty, { "POST /library/prop": [201, { ...alarm, notes: "", pictures: [] }], "POST /files": [201, { id: 80 }], "POST /brands/1/screens": [201, {}] });
  await userEvent.click(await page().findByRole("button", { name: "New product" }));
  const box = dialog("New product");
  await userEvent.type(box.getByRole("textbox", { name: "Name" }), " Protector alarm ");
  await userEvent.upload(box.getByLabelText("Upload its photo"), file("alarm.jpg", "image/jpeg"));
  await userEvent.click(box.getByRole("button", { name: "Save product" }));
  await waitFor(() =>
    expect(sent(calls)).toEqual([
      ["POST /library/prop", { name: "Protector alarm", notes: "", brand_ids: [1], image_file_ids: [], outfits: [], source_photo_file_id: null, presenter: false, product_type: "physical" }],
      ["POST /files"],
      ["POST /brands/1/screens", { name: "Protector alarm", file_id: 80, tags: ["product"], default_for: ["product"], product_id: 54, variant: "" }],
    ]),
  );
});

test("Cast: everyone saved by name; the picked one's sheet, who they are, their voice to play, their videos and their presses with the server's prices", async () => {
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  await open("cast", full);
  const people = within(await page().findByRole("group", { name: "Saved people" }));
  expect(people.getAllByRole("button").map((b) => b.querySelector("b")!.textContent)).toEqual(["Dana", "Paige", "The officer"]);
  const panel = await person("Paige");
  expect(panel.getByRole("img", { name: "Paige’s sheet" })).toHaveAttribute("src", "/api/files/301");
  expect(panel.getByRole("status")).toHaveTextContent("In use");
  expect(panel.getByText("18, tall, volleyball sweatshirt")).toBeInTheDocument();
  expect(await panel.findByText("Kim · warm")).toBeInTheDocument();
  await userEvent.click(panel.getByRole("button", { name: "Play Paige’s voice" }));
  expect(HTMLMediaElement.prototype.play).toHaveBeenCalledOnce();
  expect(await panel.findByRole("link", { name: /Three men at Target/ })).toHaveAttribute("href", "/s/b/1/videos/366");
  expect(panel.getByRole("link", { name: /Three men at Target/ })).toHaveTextContent("Done · 12 Nov");
  expect(panel.getByRole("button", { name: "Change look… up to $0.08" })).toBeInTheDocument();
  expect(panel.getByRole("link", { name: "the current site" })).toHaveAttribute("href", "/b/1/library/characters/179");
  expect(page().getByText(/Palace Guard also has 1 saved place/)).toBeInTheDocument();
  expect(within(page().getByText(/Palace Guard also has 1 saved place/)).getByRole("link", { name: "the current site" })).toHaveAttribute("href", "/b/1/library/places");
  const none = await person("The officer");
  expect(none.getByRole("status")).toHaveTextContent("No sheet yet");
  expect(none.getByRole("button", { name: "Draw the sheet up to $0.17" })).toBeInTheDocument();
  expect(none.getByText("Not in a video yet.")).toBeInTheDocument();
});

test.each<[string, (box: ReturnType<typeof within>) => Promise<void>, unknown[][]]>([
  ["a name and a line", (box) => userEvent.type(box.getByRole("textbox", { name: "Who they are, in a line" }), " A mom in her forties "), [["POST /library/character", { name: "Mia", notes: "A mom in her forties", brand_ids: [1], image_file_ids: [], outfits: [], source_photo_file_id: null, presenter: false, product_type: null }], ["POST /library/character/200/sheet", { ...SHEET, change: "" }]]],
  ["a name and a photo", (box) => userEvent.upload(box.getByLabelText("Or upload a photo"), file("mia.jpg", "image/jpeg")), [["POST /files"], ["POST /library/character", { name: "Mia", notes: "", brand_ids: [1], image_file_ids: [], outfits: [], source_photo_file_id: 80, presenter: false, product_type: null }], ["POST /library/character/200/sheet", { ...SHEET, change: "" }]]],
])("New person from %s saves them in this brand and draws their sheet, exactly as the current site's New character does", async (_from, fill, expected) => {
  const calls = await open("cast", empty, { "POST /files": [201, { id: 80 }], "POST /library/character": [201, { ...officer, id: 200, name: "Mia" }], "POST /library/character/200/sheet": [201, { id: 900 }] });
  await userEvent.click(await page().findByRole("button", { name: "New person" }));
  const box = dialog("New person");
  const draw = await box.findByRole("button", { name: "Draw their sheet · up to $0.17" });
  await userEvent.type(box.getByRole("textbox", { name: "Name" }), "Mia ");
  expect(draw).toBeDisabled(); // a name alone draws nothing
  await fill(box);
  await userEvent.click(draw);
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(sent(calls)).toEqual(expected);
});

test("Rename or describe saves the person's name and words, every other word as the server holds it", async () => {
  const calls = await open("cast", full, { "PATCH /library/character/179": [200, paige] });
  await userEvent.click((await person("Paige")).getByRole("button", { name: "Rename or describe…" }));
  const box = dialog("Rename or describe Paige");
  expect(box.getByRole("button", { name: "Save" })).toBeDisabled(); // nothing changed yet
  await userEvent.type(box.getByRole("textbox", { name: "Name" }), " M");
  await userEvent.type(box.getByRole("textbox", { name: "Who they are" }), ", hair tied back");
  await userEvent.click(box.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Saved.")).toBeInTheDocument();
  expect(sent(calls)).toEqual([["PATCH /library/character/179", { name: "Paige M", notes: "18, tall, volleyball sweatshirt, hair tied back", brand_ids: [1], outfits: [], voice_file_id: null }]]);
});

test("Change look… draws the sheet again with the note; the look check's own words can start it; a person with no sheet has Draw the sheet", async () => {
  const calls = await open("cast", full, { "POST /library/character/180/sheet": [201, { id: 901 }], "POST /library/character/181/sheet": [201, { id: 902 }] });
  const panel = await person("Dana");
  expect(panel.getByRole("note")).toHaveTextContent("This look reads as a woman in her twenties, but Dana is in her late forties. Fix it with a note");
  await userEvent.click(panel.getByRole("button", { name: "Fix it with a note" }));
  const box = dialog("Change Dana’s look");
  expect(box.getByRole("textbox", { name: "What should change?" })).toHaveValue("Dana is in her late forties");
  await userEvent.type(box.getByRole("textbox", { name: "What should change?" }), ", grey in her hair ");
  await userEvent.click(box.getByRole("button", { name: "Change it · up to $0.08" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  await userEvent.click((await person("The officer")).getByRole("button", { name: "Draw the sheet up to $0.17" }));
  await waitFor(() =>
    expect(sent(calls)).toEqual([
      ["POST /library/character/180/sheet", { ...SHEET, change: "Dana is in her late forties, grey in her hair" }],
      ["POST /library/character/181/sheet", { ...SHEET, change: "" }],
    ]),
  );
});

test("a sheet waiting for the OK is approved, and Undo takes the approval back", async () => {
  const calls = await open("cast", full, { "POST /library/character/180/sheet/approve": [200, dana], "DELETE /library/character/180/sheet/approve": [200, dana] });
  await userEvent.click((await person("Dana")).getByRole("button", { name: "Approve" }));
  expect(await screen.findByText("Dana's sheet approved.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await waitFor(() => expect(sent(calls)).toEqual([["POST /library/character/180/sheet/approve"], ["DELETE /library/character/180/sheet/approve"]]));
});

test("Remove asks first, archives the person, and Undo brings them back", async () => {
  const calls = await open("cast", full, { "DELETE /library/character/179": GONE, "POST /library/character/179/unarchive": [200, paige] });
  await userEvent.click((await person("Paige")).getByRole("button", { name: "Remove" }));
  expect(sent(calls)).toEqual([]); // not before the yes
  const box = dialog("Remove Paige?");
  expect(box.getByText("Paige leaves Palace Guard’s cast. Videos already made keep them, and Undo brings them back.")).toBeInTheDocument();
  await userEvent.click(box.getByRole("button", { name: "Remove" }));
  expect(await screen.findByText("Paige archived.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await waitFor(() => expect(sent(calls)).toEqual([["DELETE /library/character/179"], ["POST /library/character/179/unarchive"]]));
});

test("a person's voice is picked from the brand's and the app's, or taken away", async () => {
  const calls = await open("cast", full, { "PATCH /library/character/179": [200, paige] });
  const panel = await person("Paige");
  await panel.findByText("Kim · warm");
  await userEvent.click(panel.getByRole("button", { name: "Change" }));
  await userEvent.click(within(screen.getByRole("menu", { name: "Paige’s voice" })).getByRole("menuitemradio", { name: /^Roger/ }));
  await waitFor(() => expect(sent(calls)).toHaveLength(1));
  await userEvent.click(panel.getByRole("button", { name: "Change" }));
  await userEvent.click(within(screen.getByRole("menu", { name: "Paige’s voice" })).getByRole("menuitemradio", { name: "No voice" }));
  await waitFor(() =>
    expect(sent(calls)).toEqual([
      ["PATCH /library/character/179", { voice_id: null, voice_stock_key: "Roger" }],
      ["PATCH /library/character/179", { voice_id: null, voice_stock_key: null }],
    ]),
  );
});

test("Footage: folders with their clips counted at any depth; a folder opens to show the folders and clips in it", async () => {
  await open("footage", full);
  const shots = await page().findByRole("button", { name: /^Product shots\s*2 clips$/ });
  expect(page().getByRole("button", { name: /^Campus\s*1 clip$/ })).toBeInTheDocument();
  expect(within(page().getByRole("region", { name: "Not in a folder" })).getByRole("button", { name: /^The alarm on a set of keys/ })).toBeInTheDocument();
  expect(page().queryByRole("button", { name: /^A hand hooks the ring/ })).toBeNull();
  await userEvent.click(shots);
  expect(shots).toHaveAttribute("aria-expanded", "true");
  expect(page().getByRole("button", { name: /^A hand hooks the ring/ })).toBeInTheDocument();
  await userEvent.click(page().getByRole("button", { name: /^Close-ups\s*1 clip$/ }));
  expect(page().getByRole("button", { name: /^The strobe in a dark lot/ })).toBeInTheDocument();
  expect(page().getByText("Drop a clip here to add it to Close-ups.")).toBeInTheDocument();
  expect(page().getByRole("link", { name: "the current site" })).toHaveAttribute("href", "/b/1/library/footage");
});

test("a footage folder is made, renamed and deleted; the delete says where its clips go, and Undo brings it back", async () => {
  const calls = await open("footage", full, { "POST /brands/1/folders": [201, FOLDERS[2]], "PATCH /folders/1": [200, FOLDERS[0]], "DELETE /folders/1": [200, { moved: 2, ideas: 0 }], "POST /folders/1/restore": [200, FOLDERS[0]] });
  await userEvent.click(await page().findByRole("button", { name: "New folder" }));
  await userEvent.type(dialog("New folder").getByRole("textbox", { name: "Name" }), " Night ");
  await userEvent.click(dialog("New folder").getByRole("button", { name: "Make the folder" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  await userEvent.click(page().getByRole("button", { name: /^Product shots\s*2 clips$/ }));
  const more = async (item: string) => (await userEvent.click(page().getByRole("button", { name: "More for Product shots" })), userEvent.click(within(screen.getByRole("menu", { name: "More for Product shots" })).getByRole("menuitem", { name: item })));
  await more("Rename…");
  const name = dialog("Rename Product shots").getByRole("textbox", { name: "Name" });
  expect(name).toHaveValue("Product shots");
  await userEvent.clear(name);
  await userEvent.type(name, "Shots");
  await userEvent.click(dialog("Rename Product shots").getByRole("button", { name: "Rename" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  await more("Delete folder…");
  expect(dialog("Delete Product shots?").getByText("Its 2 clips move up to All footage, and the folders inside it go with it. No clip is deleted, and Undo brings it all back.")).toBeInTheDocument();
  await userEvent.click(dialog("Delete Product shots?").getByRole("button", { name: "Delete folder" }));
  expect(await screen.findByText("Deleted “Product shots”. Its 2 clips moved up to All footage.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await waitFor(() =>
    expect(sent(calls)).toEqual([
      ["POST /brands/1/folders", { name: "Night", parent_id: null, footage: true }],
      ["PATCH /folders/1", { name: "Shots" }],
      ["DELETE /folders/1"],
      ["POST /folders/1/restore"],
    ]),
  );
});

test("a clip dropped on Footage is added to the open folder with the words typed for it; with words, nothing is paid", async () => {
  await open("footage", full, { "POST /brands/1/footage": [201, { ...CLIPS[3], id: 15 }] });
  const forms = uploads();
  await userEvent.click(await page().findByRole("button", { name: /^Product shots\s*2 clips$/ }));
  await userEvent.click(page().getByRole("button", { name: /^Close-ups\s*1 clip$/ }));
  fireEvent.drop(page().getByText("Drop a clip here to add it to Close-ups."), { dataTransfer: { files: [file("quad.mp4", "video/mp4")] } });
  const box = dialog("Add a clip");
  expect(box.getByText("To Product shots/Close-ups")).toBeInTheDocument();
  expect(box.getByText("quad.mp4")).toBeInTheDocument();
  await userEvent.type(box.getByRole("textbox", { name: "What it shows" }), " A quad at dusk. ");
  expect(box.getByText("Your words, as the director reads them.")).toBeInTheDocument();
  await userEvent.click(box.getByRole("button", { name: "Add clip" })); // no price on it: his words, no AI
  expect(await screen.findByText("Clip added.")).toBeInTheDocument();
  expect(forms).toEqual([["POST /brands/1/footage", { upload: FILE, description: "A quad at dusk.", folder: "Product shots/Close-ups" }]]);
});

test("Voices: the brand's own, the looks' own and the app's, each with a sample to play, what it is and who it is the voice of", async () => {
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  await open("voices", full);
  const row = (name: string) => within(page().getByText(name, { selector: "b" }).closest("li")!);
  expect(await page().findByRole("heading", { name: "Palace Guard’s voices" })).toBeInTheDocument();
  expect(row("Kim").getByText("Warm, fifties · MiniMax clone")).toBeInTheDocument();
  expect(row("Kim").getByText("Voice of Paige")).toBeInTheDocument();
  expect(row("Kim").getByRole("button", { name: "Play Kim’s sample" }).querySelector("audio")).toHaveAttribute("src", "/api/files/60");
  await userEvent.click(row("Kim").getByRole("button", { name: "Play Kim’s sample" }));
  expect(HTMLMediaElement.prototype.play).toHaveBeenCalledOnce();
  expect(row("Dr. Pickle").getByText("The Dr. Pickle look’s voice")).toBeInTheDocument();
  expect(row("Dr. Pickle").getByText("Unused for 7 days: MiniMax may delete it soon.")).toBeInTheDocument(); // the server's words
  expect(row("Roger").getByRole("button", { name: "Play Roger’s sample" }).querySelector("audio")).toHaveAttribute("src", "/api/voices/samples/Roger.mp3");
  expect(page().queryByText("George")).toBeNull();
  await userEvent.click(page().getByRole("button", { name: "Show all 4" }));
  expect(row("George").getByText("Older man, dry · ElevenLabs")).toBeInTheDocument();
});

test("New voice uploads the recording and clones it under its name, with the server's price on the press", async () => {
  const calls = await open("voices", full, { "POST /files": [201, { id: 80 }], "POST /brands/1/voices/clone": [201, { ...VOICES.voices[0], id: 9, state: "cloning" }] });
  await userEvent.click(await page().findByRole("button", { name: "New voice" }));
  const box = dialog("New voice");
  const clone = box.getByRole("button", { name: "Clone · up to $3.00" });
  await userEvent.type(box.getByRole("textbox", { name: "Name" }), " Dana ");
  expect(clone).toBeDisabled(); // no recording yet
  await userEvent.upload(box.getByLabelText("Pick a recording"), file("dana.mp3", "audio/mpeg"));
  await userEvent.type(box.getByRole("textbox", { name: "How it sounds" }), "Warm, fifties");
  await userEvent.click(clone);
  expect(await screen.findByText("Cloning Dana…")).toBeInTheDocument();
  expect(sent(calls)).toEqual([["POST /files"], ["POST /brands/1/voices/clone", { name: "Dana", description: "Warm, fifties", sample_file_id: 80 }]]);
});

// The paid presses, pressed twice in the same tick: before the page can draw the first as in flight, so only the
// lock (./useLock) stands between two clicks and two charges.
const PAID: Routes = { "POST /files": [201, { id: 80 }], "POST /library/character": [201, { ...officer, id: 200, name: "Mia" }], "POST /library/character/200/sheet": [201, { id: 900 }], "POST /library/character/181/sheet": [201, { id: 902 }], "POST /library/character/179/sheet": [201, { id: 903 }], "POST /brands/1/footage": [201, { ...CLIPS[0], id: 14 }], "POST /brands/1/voices/clone": [201, {}] };
test.each<[string, Tab, () => Promise<HTMLElement>, string[]]>([
  ["New person's Draw their sheet", "cast", async () => {
    await userEvent.click(await page().findByRole("button", { name: "New person" }));
    await userEvent.type(dialog("New person").getByRole("textbox", { name: "Name" }), "Mia");
    await userEvent.type(dialog("New person").getByRole("textbox", { name: "Who they are, in a line" }), "A mom");
    return dialog("New person").findByRole("button", { name: /^Draw their sheet · up to/ });
  }, ["POST /library/character", "POST /library/character/200/sheet"]],
  ["Draw the sheet", "cast", async () => (await person("The officer")).getByRole("button", { name: /^Draw the sheet/ }), ["POST /library/character/181/sheet"]],
  ["Change look", "cast", async () => {
    await userEvent.click((await person("Paige")).getByRole("button", { name: /^Change look/ }));
    await userEvent.type(dialog("Change Paige’s look").getByRole("textbox", { name: "What should change?" }), "older");
    return dialog("Change Paige’s look").getByRole("button", { name: /^Change it/ });
  }, ["POST /library/character/179/sheet"]],
  ["Add clip, described by the AI", "product", async () => {
    await userEvent.click(await page().findByRole("button", { name: "Add clips" }));
    await userEvent.upload(dialog("Add a clip").getByLabelText("Choose a clip"), file("pull.mp4", "video/mp4"));
    return dialog("Add a clip").findByRole("button", { name: /^Add clip · up to/ });
  }, ["POST /brands/1/footage"]],
  ["Clone a voice", "voices", async () => {
    await userEvent.click(await page().findByRole("button", { name: "New voice" }));
    await userEvent.type(dialog("New voice").getByRole("textbox", { name: "Name" }), "Dana");
    await userEvent.upload(dialog("New voice").getByLabelText("Pick a recording"), file("dana.mp3", "audio/mpeg"));
    return dialog("New voice").getByRole("button", { name: /^Clone · up to/ });
  }, ["POST /files", "POST /brands/1/voices/clone"]],
])("%s, pressed twice before the page has drawn it as in flight, is one request", async (_press, tab, find, expected) => {
  const calls = await open(tab, full, PAID);
  const press = await find();
  fireEvent.click(press);
  fireEvent.click(press);
  await quiet();
  await waitFor(() => expect(sent(calls).map(([key]) => key)).toEqual(expected));
});

test.each<[string, Tab, string, () => Promise<HTMLElement>]>([
  ["How it works' Save", "product", "PATCH /library/prop/54", async () => {
    const how = within(await page().findByRole("region", { name: "How it works" }));
    await userEvent.click(how.getByRole("button", { name: "Edit" }));
    await userEvent.type(how.getByRole("textbox", { name: "How it works" }), "More.");
    return how.getByRole("button", { name: "Save" });
  }],
  ["Approve", "cast", "POST /library/character/180/sheet/approve", async () => (await person("Dana")).getByRole("button", { name: "Approve" })],
  ["Remove", "cast", "DELETE /library/character/179", async () => (await userEvent.click((await person("Paige")).getByRole("button", { name: "Remove" })), dialog("Remove Paige?").getByRole("button", { name: "Remove" }))],
])("a free press is off while its request is in flight: %s", async (_press, tab, key, find) => {
  const calls = await open(tab, full, { [key]: key.startsWith("DELETE") ? GONE : OK });
  const release = hold(key);
  const press = await find();
  await userEvent.click(press);
  await waitFor(() => expect(press).toBeDisabled());
  await userEvent.click(press);
  release();
  await quiet();
  expect(sent(calls).map(([sentKey]) => sentKey)).toEqual([key]);
});

test("a press the server refuses says why in the server's words, and nothing is sent again", async () => {
  const why = "This would pass this week's limit. Nothing was charged.";
  const calls = await open("cast", full, { "POST /library/character/181/sheet": [402, { detail: why }] });
  const panel = await person("The officer");
  await userEvent.click(panel.getByRole("button", { name: /^Draw the sheet/ }));
  expect(await panel.findByRole("alert")).toHaveTextContent(why);
  await quiet();
  expect(sent(calls)).toHaveLength(1);
});

test("a tab that can't be read says so in the server's words, with a way to try again", async () => {
  const calls = await open("voices", full, { "GET /brands/1/voices": [503, { detail: "The voices can't be read right now." }] });
  const alert = within(await page().findByRole("alert", {}, { timeout: 12_000 }));
  expect(alert.getByText("Couldn’t load the voices")).toBeInTheDocument();
  expect(alert.getByText("The voices can't be read right now.")).toBeInTheDocument();
  const before = calls.length;
  await userEvent.click(alert.getByRole("button", { name: "Try again" }));
  await waitFor(() => expect(calls.length).toBeGreaterThan(before));
  expect(sent(calls)).toEqual([]);
});
