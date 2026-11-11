import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { editor, owner } from "../test/people";
import { renderApp } from "../test/render";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { readsAsScript } from "./Words";

const IDEA = "A tired mom finds our coffee and her morning turns around.";
const SCRIPT = "MIA: The dip is in. I'm buying.";
const at = new Date().toISOString();
const look = (id: string, name: string, o: object = {}) => ({ id, name, blurb: `${name} blurb.`, card: "", broll: "", on: true, own_sample: false, lanes: [], video_model: "seedance-2.0", test_clip: true, test_still: true, test_tag: false, ...o });
const LOOKS = [look("movie", "Movie"), look("house", "House"), look("ugc", "UGC", { on: false })];
const format = (id: string, name: string, o: object = {}) => ({ id, name, engine: "story", on: true, blurb: `${name} blurb.`, card: `${name} line`, host: false, off: null, test_still: false, ...o });
const FORMATS = [format("dialogue", "Dialogue"), format("presenter", "Presenter", { engine: "narrated", host: true })];
const item = (id: number, name: string) => ({ id, name, owner_project_id: null, owner_script_id: null, pictures: [], image_file_ids: [] });
const fs = { id: 9, title: "Coffee", type: "dialogue", look: "movie", shape: "9:16", brand_id: 1, status: "working", created_by_name: "Reed", created_at: at, credits: 0, file_id: null, project_id: 50, thread: [] };
const PRICE = { credits: 164, usd: 16.86, held: "", budget: null };

function server(me: object, routes: Record<string, [number, unknown]> = {}) {
  return fakeServer({
    "GET /auth/me": [200, me],
    "GET /brands": [200, [{ id: 1, name: "Resilia", colours: [], tone_notes: "" }]],
    "GET /looks": [200, LOOKS],
    "GET /formats": [200, FORMATS],
    "GET /brands/1/folders": [200, []],
    "GET /library/character": [200, [item(3, "Dr. Pickle"), item(5, "Nurse Kim"), { ...item(8, "A video's own extra"), owner_project_id: 50 }]],
    "GET /library/prop": [200, [item(21, "Capsule pack"), item(22, "Gut tea")]],
    "GET /jobs": [200, []],
    "GET /freestyles": [200, []],
    "GET /projects/50": [200, { id: 50, brand_id: 1, name: "Coffee", freestyle_id: 9 }],
    "GET /freestyles/9": [200, fs],
    "POST /freestyles/estimate": [200, PRICE],
    "POST /freestyles": [201, fs],
    ...routes,
  });
}
beforeEach(() => localStorage.clear());
afterEach(() => vi.unstubAllGlobals());
const loaded = () => screen.findByRole("button", { name: /^Style: .+ · / });
const words = async () => {
  await loaded();
  return screen.findByLabelText("Paste a script, or describe the video");
};
const posted = (calls: { key: string; body: unknown }[], key = "POST /freestyles") => calls.filter((c) => c.key === key).at(-1)?.body;
const press = (name = "Make it · up to $16.86") => screen.findByRole("button", { name }, { timeout: 3000 });
const kind = (name: RegExp) => screen.getByRole("radio", { name });

test("the words read as a script at 40 words, with a speaker line or a scene heading; anything else is an idea", () => {
  expect(readsAsScript("")).toBe(false);
  expect(readsAsScript(IDEA)).toBe(false);
  expect(readsAsScript("A Dr. Pickle rant about beer bellies: under a minute, ending on the capsule.")).toBe(false); // a colon in a sentence is no speaker
  expect(readsAsScript(SCRIPT)).toBe(true);
  expect(readsAsScript("Open on the kitchen.\nDr. Pickle: Your gut after the weekend?")).toBe(true);
  expect(readsAsScript("SCENE 1 — INT. KITCHEN — DAY\nShe pours the coffee.")).toBe(true);
  expect(readsAsScript("INT. KITCHEN — DAY")).toBe(true);
  expect(readsAsScript("a scene in a kitchen where she pours the coffee")).toBe(false);
  expect(readsAsScript(Array(39).fill("word").join(" "))).toBe(false);
  expect(readsAsScript(Array(40).fill("word").join(" "))).toBe(true);
});

test("My words are: a short description is an idea and is sent as one; a script is kept word for word; the person's own flip wins", async () => {
  setViewport(1440);
  const calls = server(owner);
  renderApp("/b/1");
  const box = await words();
  expect(within(screen.getByRole("radiogroup", { name: "My words are" })).getAllByRole("radio").map((r) => r.textContent)).toEqual(["A script (kept word for word)", "An idea (write the script for me)"]);
  await userEvent.type(box, IDEA);
  expect(kind(/^An idea/)).toHaveAttribute("aria-checked", "true");
  await press();
  expect(posted(calls, "POST /freestyles/estimate")).toMatchObject({ text: IDEA, idea: true });
  await userEvent.clear(box);
  await userEvent.type(box, SCRIPT);
  expect(kind(/^A script/)).toHaveAttribute("aria-checked", "true"); // a speaker line: the guess follows the words
  await userEvent.click(kind(/^An idea/));
  await userEvent.type(box, " NATE: Same.");
  expect(kind(/^An idea/)).toHaveAttribute("aria-checked", "true"); // flipped by the person: the guess no longer moves it
  await vi.waitFor(() => expect(posted(calls, "POST /freestyles/estimate")).toMatchObject({ idea: true, text: `${SCRIPT} NATE: Same.` }), { timeout: 3000 });
  await userEvent.click(await press());
  await vi.waitFor(() => expect(posted(calls)).toMatchObject({ text: `${SCRIPT} NATE: Same.`, idea: true, type: "dialogue", look: "movie" }));
});

test("the styles gallery under the box: the styles that are on first, then the off ones greyed; a tile plays its sample under the pointer, one at a time", async () => {
  setViewport(1440);
  server(owner, { "GET /looks": [200, [look("ugc", "UGC", { on: false }), look("movie", "Movie", { card: "Filmed like a drama" }), look("house", "House")]] });
  renderApp("/b/1");
  const gallery = await screen.findByRole("region", { name: "Styles" });
  expect(within(gallery).getByRole("heading", { name: "Styles" }).parentElement).toHaveClass("lg:text-center");
  expect(within(gallery).getByText("Pick a look. Each one comes with its own way of shooting.")).toBeInTheDocument();
  expect(within(gallery).getAllByRole("listitem").map((li) => li.textContent)).toEqual(["MovieFilmed like a drama", "HouseHouse blurb.", "UGCUGC blurb.Off on this site"]);
  const movie = within(gallery).getByRole("button", { name: /^Movie/ });
  expect(movie).toHaveClass("rounded-xl", "aspect-[9/16]");
  expect(movie.querySelector("img")).toHaveAttribute("src", "/api/looks/movie/test-sample.jpg");
  expect(movie).toHaveAttribute("aria-pressed", "true"); // the style the box starts on
  await userEvent.hover(within(gallery).getByRole("button", { name: /^House/ }));
  expect(gallery.querySelectorAll("video")).toHaveLength(1);
  expect(gallery.querySelector("video")).toHaveAttribute("src", "/api/looks/house/test-sample.mp4");
  await userEvent.hover(movie);
  expect(gallery.querySelectorAll("video")).toHaveLength(1);
  expect(gallery.querySelector("video")).toHaveAttribute("src", "/api/looks/movie/test-sample.mp4");
  const off = within(gallery).getByRole("button", { name: /^UGC/ });
  await userEvent.hover(off);
  expect(gallery.querySelector("video")).toBeNull(); // an off style doesn't play
  expect(off).toHaveAttribute("aria-disabled", "true");
  await userEvent.click(off);
  expect(off).toHaveAttribute("aria-pressed", "false"); // and can't be picked
  expect(screen.getByRole("button", { name: "Style: Movie · Dialogue" })).toBeInTheDocument();
});

test("pressing a style in the gallery picks it for the box: the Style pill and the send follow, the tile is marked, and focus goes to the words", async () => {
  setViewport(1440);
  const calls = server(owner);
  renderApp("/b/1");
  const box = await words();
  const gallery = await screen.findByRole("region", { name: "Styles" });
  const house = within(gallery).getByRole("button", { name: /^House/ });
  expect(house.querySelector("svg")).toBeNull();
  await userEvent.click(house);
  expect(house).toHaveAttribute("aria-pressed", "true");
  expect(house).toHaveClass("border-accent", "ring-accent");
  expect(house.querySelector("svg")).not.toBeNull(); // its check
  expect(within(gallery).getByRole("button", { name: /^Movie/ })).toHaveAttribute("aria-pressed", "false");
  expect(screen.getByRole("button", { name: "Style: House · Dialogue" })).toBeInTheDocument();
  expect(box).toHaveFocus();
  expect(screen.queryByText(/The format is/)).toBeNull(); // House is made as Dialogue: nothing to say
  await userEvent.type(box, SCRIPT);
  await userEvent.click(await press());
  await vi.waitFor(() => expect(posted(calls)).toMatchObject({ look: "house", type: "dialogue" }));
});

test("a style in the gallery that isn't made in the picked format switches the format to one it is made in, and says so", async () => {
  setViewport(1440);
  const movie = look("movie", "Movie", { formats: ["dialogue"], formats_why: "its scenes are filmed whole" });
  server(owner, { "GET /looks": [200, [look("house", "House"), movie]], "GET /formats": [200, [FORMATS[1], FORMATS[0]]] });
  renderApp("/b/1");
  const chip = await loaded();
  expect(chip).toHaveAccessibleName("Style: House · Presenter");
  await userEvent.click(await screen.findByRole("button", { name: /^Movie/ }));
  expect(chip).toHaveAccessibleName("Style: Movie · Dialogue");
  expect(screen.getByText("Movie is made only as Dialogue: its scenes are filmed whole. The format is Dialogue now.")).toHaveAttribute("role", "status");
  expect(await words()).toHaveFocus();
  await userEvent.click(screen.getByRole("button", { name: /^House/ }));
  expect(chip).toHaveAccessibleName("Style: House · Dialogue"); // the format stays where it was put
  expect(screen.queryByText(/The format is/)).toBeNull();
});

test("a style with no sample picture is a text poster in the gallery: its line on a tint, grey when it is off", async () => {
  setViewport(1440);
  server(owner, { "GET /looks": [200, [look("movie", "Movie", { test_still: false, test_clip: false }), look("house", "House"), look("ugc", "UGC", { on: false, test_still: false, test_clip: false })]] });
  renderApp("/b/1");
  const tile = await screen.findByRole("button", { name: /^Movie/ });
  expect(tile).toHaveClass("bg-accent-soft", "text-accent-text");
  expect(tile.querySelector("img")).toBeNull();
  expect(within(tile).getAllByText("Movie blurb.")).toHaveLength(1); // the poster, not said twice
  expect(within(tile).getByText("Movie blurb.")).toHaveClass("sm:text-base", "font-medium", "line-clamp-5");
  expect(screen.getByRole("button", { name: /^UGC/ })).toHaveClass("bg-surface-2", "text-muted");
  expect(screen.getByRole("button", { name: /^House/ }).querySelector("img")).not.toBeNull();
});

test("Mode: the owner picks Make without asking, it is sent and remembered; the menu says what each does", async () => {
  setViewport(1440);
  const calls = server(owner);
  const view = renderApp("/b/1");
  await userEvent.type(await words(), SCRIPT);
  await userEvent.click(screen.getByRole("button", { name: "Mode: Ask before making" }));
  expect(screen.getAllByRole("menuitemradio").map((m) => m.textContent)).toEqual(["Ask before makingYou OK the plan and price first", "Make without askingIt starts as soon as the plan is ready, inside the price shown"]);
  expect(screen.getByRole("menuitemradio", { name: /^Ask before making/ })).toHaveAttribute("aria-checked", "true");
  await userEvent.click(screen.getByRole("menuitemradio", { name: /^Make without asking/ }));
  expect(screen.getByRole("button", { name: "Mode: Make without asking" })).toHaveTextContent("ModeAuto");
  await userEvent.click(await press());
  await vi.waitFor(() => expect(posted(calls)).toMatchObject({ mode: "auto", text: SCRIPT, idea: false }));
  view.unmount();
  renderApp("/b/1");
  expect(await screen.findByRole("button", { name: "Mode: Make without asking" })).toBeInTheDocument(); // remembered on this computer
});

test("Mode: an editor is only offered Ask before making, even on a computer the owner left on Auto, and it is what is sent", async () => {
  setViewport(1440);
  localStorage.setItem("bs.newvideo.mode", "auto");
  const calls = server(editor, { "POST /freestyles/estimate": [200, { credits: 164, usd: null, held: "", budget: 194 }] });
  renderApp("/b/1");
  await userEvent.type(await words(), SCRIPT);
  await userEvent.click(screen.getByRole("button", { name: "Mode: Ask before making" }));
  expect(screen.getAllByRole("menuitemradio").map((m) => m.textContent)).toEqual(["Ask before makingYou OK the plan and price first"]);
  await userEvent.keyboard("{Escape}");
  await userEvent.click(await press("Make it · up to 164 credits"));
  await vi.waitFor(() => expect(posted(calls)).toMatchObject({ mode: "ask" }));
  expect(document.body.textContent).not.toMatch(/\$|Reed/);
});

test("the Styles dialog picks the format and the style; both are on the chip and in the send; Escape closes it and focus returns", async () => {
  setViewport(1440);
  const calls = server(owner);
  renderApp("/b/1");
  const chip = await loaded();
  expect(chip).toHaveAccessibleName("Style: Movie · Dialogue");
  await userEvent.click(chip);
  const dialog = await screen.findByRole("dialog", { name: "Styles" });
  expect(within(dialog).getByText("How the words are delivered")).toBeInTheDocument();
  expect(within(dialog).getByRole("radio", { name: /^Dialogue.*Dialogue line/ })).toHaveAttribute("aria-checked", "true");
  await userEvent.click(within(dialog).getByRole("radio", { name: /^Presenter/ }));
  await userEvent.click(within(dialog).getByRole("radio", { name: /^House/ }));
  expect(within(dialog).getByRole("radio", { name: /^UGC.*Off on this site/ })).toHaveAttribute("aria-disabled", "true");
  expect(within(dialog).getByText("House · Presenter")).toBeInTheDocument(); // what is picked, at the foot
  await userEvent.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(chip).toHaveFocus();
  expect(chip).toHaveAccessibleName("Style: House · Presenter");
  await userEvent.type(await words(), SCRIPT);
  await userEvent.click(await press());
  await vi.waitFor(() => expect(posted(calls)).toMatchObject({ type: "presenter", look: "house" }));
});

test("Product and Cast open one picker on their own tab; the picks show on the chips and are sent", async () => {
  setViewport(1440);
  const calls = server(owner);
  renderApp("/b/1");
  await userEvent.type(await words(), SCRIPT);
  await userEvent.click(screen.getByRole("button", { name: "Product: None" }));
  const picker = await screen.findByRole("dialog", { name: "Cast and products" });
  expect(within(picker).getByRole("tab", { name: "Products" })).toHaveAttribute("aria-selected", "true");
  expect(within(picker).getByRole("link", { name: /^Add product/ })).toHaveAttribute("href", "/b/1/library/products?new=1");
  await userEvent.click(within(picker).getByRole("checkbox", { name: "Capsule pack" }));
  await userEvent.click(within(picker).getByRole("checkbox", { name: "Gut tea" }));
  await userEvent.click(within(picker).getByRole("tab", { name: /^Cast/ }));
  expect(within(picker).getByText("The same person in every ad you make")).toBeInTheDocument();
  expect(within(picker).getByRole("link", { name: /^New character/ })).toHaveAttribute("href", "/b/1/library/characters?new=1");
  expect(within(picker).queryByRole("checkbox", { name: "A video's own extra" })).toBeNull(); // only the brand's saved characters
  await userEvent.click(within(picker).getByRole("checkbox", { name: "Nurse Kim" }));
  expect(within(picker).getByRole("checkbox", { name: "Nurse Kim" })).toHaveAttribute("aria-checked", "true");
  expect(within(picker).getByText("Picked: 1 person · 2 products")).toBeInTheDocument();
  await userEvent.click(within(picker).getByRole("button", { name: "Done" }));
  expect(screen.getByRole("button", { name: "Product: 2 products" })).toHaveFocus();
  expect(screen.getByRole("button", { name: "Cast: Nurse Kim" })).toBeInTheDocument();
  await userEvent.click(await press());
  expect(posted(calls, "POST /freestyles/estimate")).toMatchObject({ cast_ids: [5], product_ids: [21, 22] });
  await vi.waitFor(() => expect(posted(calls)).toMatchObject({ cast_ids: [5], product_ids: [21, 22] }));
});

test("a picked Product or Cast has a small × in its pill that clears it, and focus stays on the pill; Style has none", async () => {
  setViewport(1440);
  const calls = server(owner);
  renderApp("/b/1");
  await userEvent.type(await words(), SCRIPT);
  expect(screen.queryByRole("button", { name: /^Clear/ })).toBeNull(); // nothing picked: nothing to clear
  await userEvent.click(screen.getByRole("button", { name: "Product: None" }));
  const picker = await screen.findByRole("dialog", { name: "Cast and products" });
  await userEvent.click(within(picker).getByRole("checkbox", { name: "Capsule pack" }));
  await userEvent.click(within(picker).getByRole("tab", { name: /^Cast/ }));
  await userEvent.click(within(picker).getByRole("checkbox", { name: "Nurse Kim" }));
  await userEvent.click(within(picker).getByRole("button", { name: "Done" }));
  expect(screen.getByRole("button", { name: "Product: Capsule pack" })).toHaveTextContent("ProductCapsule pack");
  expect(screen.getAllByRole("button", { name: /^Clear/ }).map((b) => b.getAttribute("aria-label"))).toEqual(["Clear product", "Clear cast"]);
  await userEvent.click(screen.getByRole("button", { name: "Clear product" }));
  expect(screen.getByRole("button", { name: "Product: None" })).toHaveFocus();
  expect(screen.queryByRole("button", { name: "Clear product" })).toBeNull();
  expect(screen.queryByRole("dialog")).toBeNull(); // the × clears; it doesn't open the picker
  screen.getByRole("button", { name: "Clear cast" }).focus();
  await userEvent.keyboard("{Enter}");
  expect(screen.getByRole("button", { name: "Cast: Nobody" })).toHaveFocus();
  await userEvent.click(await press());
  await vi.waitFor(() => expect(posted(calls)).toMatchObject({ cast_ids: [], product_ids: [] }));
});

test("the + menu's saved scripts have Manage scripts, to the brand's Scripts page", async () => {
  for (const width of [1440, 390]) {
    setViewport(width);
    server(owner, { "GET /scripts": [200, []] });
    const view = renderApp("/b/1?from=script");
    expect(await screen.findByRole("heading", { name: "Use a saved script" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Manage scripts" })).toHaveAttribute("href", "/b/1/scripts");
    expect(screen.queryByRole("region", { name: "Styles" })).toBeNull(); // a saved script has its own style
    view.unmount();
    vi.unstubAllGlobals();
  }
});

test("Home's composition: a two-line headline, the second muted, over a box no wider than 720 px; the pills wrap beside room held for the price, so nothing moves when it arrives", async () => {
  setViewport(1440);
  server(owner);
  renderApp("/b/1");
  const box = await words();
  const head = screen.getByRole("heading", { level: 1 });
  expect(head).toHaveClass("type-hero");
  expect([...head.children].map((l) => [l.textContent, l.className])).toEqual([["Paste your script, pick a style.", "block"], ["We handle the rest.", "block text-muted"]]);
  expect(head.closest(".max-w-\\[720px\\]")).toContainElement(box);
  const right = screen.getByRole("button", { name: "Make it" }).parentElement!;
  expect(right).toHaveClass("min-w-[19rem]", "shrink-0"); // Mode and the press, at the right
  expect(right).toContainElement(screen.getByRole("button", { name: "Mode: Ask before making" }));
  const pills = right.previousElementSibling!;
  expect(pills).toHaveClass("flex-wrap", "min-w-0", "flex-1");
  expect(pills).toContainElement(screen.getByRole("button", { name: "Shape: 9:16" }));
  for (const pill of [/^Style: /, "Product: None", "Cast: Nobody", "Shape: 9:16", "Folder: Unsorted"]) expect(screen.getByRole("button", { name: pill }).querySelector("svg, img")).not.toBeNull(); // an icon and a label each (Style: its sample's picture)
  await userEvent.type(box, SCRIPT);
  expect((await press()).parentElement).toBe(right);
  expect(screen.getByText(/^Most it can charge/).parentElement).toHaveClass("min-h-10"); // its line has its room before the price
});

test("the picker's Uploads tab attaches pictures for this video; a brand with no products says what to do", async () => {
  setViewport(1440);
  const calls = server(owner, { "GET /library/prop": [200, []], "POST /files": [201, { id: 61, filename: "pack.jpg", content_type: "image/jpeg", size: 9, created_at: at }] });
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:x" }));
  renderApp("/b/1");
  await userEvent.type(await words(), SCRIPT);
  await userEvent.click(screen.getByRole("button", { name: "Product: None" }));
  const picker = await screen.findByRole("dialog", { name: "Cast and products" });
  expect((await within(picker).findByRole("link", { name: "Add your product" })).closest("p")).toHaveTextContent("No products yet. Add your product so every ad shows the real one.");
  expect(within(picker).getByRole("link", { name: "Add your product" })).toHaveAttribute("href", "/b/1/library/products?new=1");
  await userEvent.click(within(picker).getByRole("tab", { name: "Uploads" }));
  await userEvent.upload(within(picker).getByLabelText("Upload pictures or clips for this video"), new File(["x"], "pack.jpg", { type: "image/jpeg" }));
  expect(await within(picker).findByText("pack.jpg")).toBeInTheDocument();
  await userEvent.click(within(picker).getByRole("button", { name: "Done" }));
  expect(screen.getByText("pack.jpg")).toBeInTheDocument(); // under the words too
  await userEvent.click(await press());
  await vi.waitFor(() => expect(posted(calls)).toMatchObject({ attachments: [61] }));
});

test("on a phone the styles gallery is two across, then three, and four on a desktop", async () => {
  setViewport(390);
  server(owner);
  renderApp("/b/1");
  const gallery = await screen.findByRole("region", { name: "Styles" });
  expect(within(gallery).getByRole("list")).toHaveClass("grid-cols-2", "gap-3", "sm:grid-cols-3", "lg:grid-cols-4"); // four big posters across, never five small ones
  await userEvent.click(within(gallery).getByRole("button", { name: /^House/ }));
  expect(screen.getByRole("button", { name: "Style: House · Dialogue" })).toBeInTheDocument();
});
