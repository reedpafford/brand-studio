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
const card = (id: string, title: string, o: object = {}) => ({ id, title, subtitle: `${title}, the short of it.`, style: "movie", style_name: "Movie", format: "dialogue", format_name: "Dialogue", seconds: 30, shape: "9:16", on: true, ...o });
const CARDS = [card("public-failure", "Public failure"), card("family-sabotage", "Family sabotage"), card("bear-proof", "Bear proof", { style: "house", style_name: "House", format: "presenter", format_name: "Presenter", seconds: 45, shape: "1:1" }), card("last-goodbye", "Last goodbye", { on: false })];
const item = (id: number, name: string) => ({ id, name, owner_project_id: null, owner_script_id: null, pictures: [], image_file_ids: [] });
const fs = { id: 9, title: "Coffee", type: "dialogue", look: "movie", shape: "9:16", brand_id: 1, status: "working", created_by_name: "Reed", created_at: at, credits: 0, file_id: null, project_id: 50, thread: [] };
const PRICE = { credits: 164, usd: 16.86, held: "", budget: null };

function server(me: object, routes: Record<string, [number, unknown]> = {}) {
  return fakeServer({
    "GET /auth/me": [200, me],
    "GET /brands": [200, [{ id: 1, name: "Resilia", colours: [], tone_notes: "" }]],
    "GET /looks": [200, LOOKS],
    "GET /formats": [200, FORMATS],
    "GET /cards": [200, CARDS],
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

test("story cards: a grid by style with filter pills; a card off on this site is greyed and doesn't open", async () => {
  setViewport(1440);
  server(owner);
  renderApp("/b/1");
  const gallery = await screen.findByRole("region", { name: "Story cards" });
  await within(gallery).findByRole("list");
  expect(within(gallery).getByText("Proven story shapes. Pick one, add your product and idea.")).toBeInTheDocument();
  expect(within(within(gallery).getByRole("group", { name: "Show cards in" })).getAllByRole("button").map((b) => b.textContent)).toEqual(["All", "Movie", "House"]);
  expect(within(gallery).getAllByRole("listitem").map((li) => li.textContent)).toEqual(["MoviePublic failure", "MovieFamily sabotage", "HouseBear proof", "MovieLast goodbyeOff on this site"]);
  expect(gallery.querySelector("img")).toHaveAttribute("src", "/api/looks/movie/test-sample.jpg"); // a card's picture is its style's sample
  await userEvent.hover(within(gallery).getByRole("button", { name: /Bear proof/ }));
  expect(gallery.querySelectorAll("video")).toHaveLength(1); // one plays at a time, under the pointer
  expect(gallery.querySelector("video")).toHaveAttribute("src", "/api/looks/house/test-sample.mp4");
  await userEvent.click(within(gallery).getByRole("button", { name: "House" }));
  expect(within(gallery).getAllByRole("listitem")).toHaveLength(1);
  await userEvent.click(within(gallery).getByRole("button", { name: "All" }));
  const off = within(gallery).getByRole("button", { name: /Last goodbye/ });
  expect(off).toHaveAttribute("aria-disabled", "true");
  await userEvent.click(off);
  expect(screen.queryByRole("dialog")).toBeNull();
});

test("the story cards simply don't show when the server offers none, or doesn't offer them yet: no error box", async () => {
  setViewport(1440);
  for (const cards of [[404, { detail: "Not Found" }], [200, []], [500, { detail: "busy" }]] as [number, unknown][]) {
    const calls = server(owner, { "GET /cards": cards });
    const view = renderApp("/b/1");
    await words();
    await vi.waitFor(() => expect(calls.some((c) => c.key === "GET /cards")).toBe(true));
    await vi.waitFor(() => expect(screen.queryByRole("status", { name: "Loading story cards" })).toBeNull());
    expect(screen.queryByRole("region", { name: "Story cards" })).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
    view.unmount();
    vi.unstubAllGlobals();
  }
});

test("a card opens its dialog; Make this ad sends the card with its style and format, the idea, the picks and the mode, and lands on the video", async () => {
  setViewport(1440);
  const calls = server(owner);
  renderApp("/b/1");
  await loaded();
  const opener = await screen.findByRole("button", { name: /Bear proof/ });
  await userEvent.click(opener);
  const dialog = await screen.findByRole("dialog", { name: "Bear proof" });
  expect(within(dialog).getByRole("heading", { name: "Bear proof" })).toBeInTheDocument();
  expect(within(dialog).getByText("Bear proof, the short of it.")).toBeInTheDocument();
  expect(within(dialog).getByText("House · Presenter · about 45 s")).toBeInTheDocument();
  expect(within(dialog).queryByRole("navigation", { name: "House story cards" })).toBeNull(); // the only House card: nothing to switch to
  expect(within(dialog).getByRole("button", { name: /^Make this ad/ })).toBeDisabled();
  expect(within(dialog).getByRole("radio", { name: /^An idea/ })).toHaveAttribute("aria-checked", "true"); // empty: an idea
  expect(within(dialog).getByRole("button", { name: "Shape: 1:1" })).toBeInTheDocument(); // the card's own shape
  await userEvent.click(within(dialog).getByRole("button", { name: "Mode: Ask before making" }));
  await userEvent.keyboard("{Escape}"); // closes the menu alone: the card stays open
  expect(screen.queryByRole("menu")).toBeNull();
  expect(screen.getByRole("dialog", { name: "Bear proof" })).toBeInTheDocument();
  // Cast and Product open the same picker, over the card.
  await userEvent.click(within(dialog).getByRole("button", { name: /^Product/ }));
  const picker = await screen.findByRole("dialog", { name: "Cast and products" });
  await userEvent.click(within(picker).getByRole("checkbox", { name: "Capsule pack" }));
  await userEvent.click(within(picker).getByRole("button", { name: "Done" }));
  expect(within(dialog).getByRole("button", { name: /^Product\s*Capsule pack/ })).toBeInTheDocument();
  await userEvent.type(within(dialog).getByLabelText("Describe your idea or paste a script"), IDEA);
  await userEvent.click(await within(dialog).findByRole("button", { name: "Make this ad · up to $16.86" }, { timeout: 3000 }));
  expect(posted(calls, "POST /freestyles/estimate")).toMatchObject({ card: "bear-proof", type: "presenter", look: "house", shape: "1:1", text: IDEA, idea: true, product_ids: [21] });
  await vi.waitFor(() => expect(posted(calls)).toEqual({ card: "bear-proof", type: "presenter", look: "house", shape: "1:1", brand_id: 1, folder_id: null, broll_look: null, text: IDEA, cast_ids: [], product_ids: [21], attachments: [], idea: true, mode: "ask" }));
  expect(await screen.findByRole("list", { name: "Conversation with the director" })).toBeInTheDocument(); // the video's chat, as Make it
});

test("a card's dialog: the strip switches between the cards in the same style; Escape closes it and focus returns to the card", async () => {
  setViewport(1440);
  server(owner);
  renderApp("/b/1");
  const opener = await screen.findByRole("button", { name: /Public failure/ });
  await userEvent.click(opener);
  const dialog = await screen.findByRole("dialog", { name: "Public failure" });
  expect(within(dialog).getByLabelText("Describe your idea or paste a script")).toHaveFocus(); // straight to the words
  const strip = within(dialog).getByRole("navigation", { name: "Movie story cards" });
  expect(within(strip).getAllByRole("button").map((b) => b.getAttribute("aria-label"))).toEqual(["Public failure", "Family sabotage", "Last goodbye"]);
  expect(within(strip).getByRole("button", { name: "Public failure" })).toHaveAttribute("aria-current", "true");
  expect(within(strip).getByRole("button", { name: "Last goodbye" })).toHaveAttribute("aria-disabled", "true"); // off on this site
  await userEvent.click(within(strip).getByRole("button", { name: "Family sabotage" }));
  expect(await screen.findByRole("dialog", { name: "Family sabotage" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Family sabotage" })).toBeInTheDocument();
  await userEvent.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(opener).toHaveFocus();
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

test("on a phone the story cards are two across, and a card's dialog fills the screen with a full-width press", async () => {
  setViewport(390);
  server(owner);
  renderApp("/b/1");
  const gallery = await screen.findByRole("region", { name: "Story cards" });
  expect(await within(gallery).findByRole("list")).toHaveClass("grid-cols-2", "lg:grid-cols-4", "xl:grid-cols-5");
  await userEvent.click(within(gallery).getByRole("button", { name: /Public failure/ }));
  const dialog = await screen.findByRole("dialog", { name: "Public failure" });
  expect(dialog).toHaveClass("inset-0", "sm:max-w-[960px]"); // the whole screen on a phone; never wider than 960 px
  expect(within(dialog).getByRole("button", { name: /^Make this ad/ })).toHaveClass("w-full");
});
