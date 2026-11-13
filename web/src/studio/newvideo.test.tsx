import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { editor, owner } from "../test/people";
import { renderApp } from "../test/render";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

// A saved character shares a role's name (Mia) and another's a speaker's (Nate): neither is used unless given a role.
const SCRIPT = "[A kitchen at dawn.]\nMIA: The dip is in. I'm buying.\nNATE (V.O.): She always says that.";
const look = (id: string, name: string, o: object = {}) => ({ id, name, blurb: `${name} blurb.`, card: `${name} line`, broll: "", on: true, own_sample: false, lanes: [], video_model: "seedance-2.0", test_clip: true, test_still: true, test_tag: false, formats: [], formats_why: "", ...o });
const LOOKS = [look("movie", "Movie", { formats: ["dialogue"] }), look("house", "House"), look("clay", "Claymation", { formats: ["narrated", "song"] }), look("ugc", "UGC", { on: false })];
const format = (id: string, name: string, o: object = {}) => ({ id, name, engine: "story", on: true, blurb: `${name} blurb.`, card: `${name} line`, host: false, off: null, test_still: false, ...o });
const FORMATS = [format("dialogue", "Dialogue"), format("narrated", "Narrated", { engine: "narrated" }), format("song", "Song", { engine: "song", off: "the music provider" })];
const item = (id: number, name: string, o: object = {}) => ({ id, name, short_description: `${name}, as saved`, owner_project_id: null, owner_script_id: null, pictures: [], image_file_ids: [], ...o });
const fs = { id: 9, title: "The dip", type: "dialogue", look: "movie", shape: "9:16", brand_id: 1, status: "working", created_by_name: "Reed", created_at: "2026-11-13T08:00:00", credits: 0, file_id: null, project_id: 50, thread: [] };
/** The send with nothing picked: the contract's every field, and no other. */
// The video the send makes, as its page in the new look first reads it.
const head = { title: "The dip", status: { kind: "working", words: "Working", reason: null, at: null, made: 0, total: 0 }, spent: { credits: 0, usd: 0 }, up_to: null, budget: null, actual: true, unreported: false, folder: null, format: "Dialogue", style: "Movie", seconds: null, song: false };
const DEFAULT = { type: "dialogue", look: "movie", shape: "9:16", brand_id: 1, text: SCRIPT, folder_id: null, cast: [], attachments: [], mode: "ask", product_ids: [], idea: false };

function server(me: object = owner, routes: Record<string, [number, unknown]> = {}) {
  return fakeServer({
    "GET /auth/me": [200, me],
    "GET /brands": [200, [{ id: 1, name: "Resilia", colours: [] }]],
    "GET /looks": [200, LOOKS],
    "GET /formats": [200, FORMATS],
    "GET /brands/1/folders": [200, [{ id: 4, brand_id: 1, parent_id: null, name: "Launch" }]],
    "GET /library/character": [200, [item(3, "Mia"), item(5, "Nate"), item(8, "A video's own extra", { owner_project_id: 50 })]],
    "GET /library/prop": [200, [item(21, "Capsule pack")]],
    "POST /freestyles/estimate": [200, { credits: 49, usd: 4.87, held: "", budget: null, expected: true }],
    "POST /freestyles": [201, fs],
    "GET /freestyles/9": [200, fs],
    "GET /projects/50": [200, { id: 50, brand_id: 1, name: "The dip", freestyle_id: 9, aspect_ratio: "9:16", look: "movie", credits_used: 0 }],
    "GET /projects/50/idea": [200, head],
    "POST /files": [201, { id: 61 }],
    ...routes,
  });
}
type Calls = ReturnType<typeof server>;
const posted = (calls: Calls, key = "POST /freestyles") => calls.filter((c) => c.key === key).map((c) => c.body);
const box = () => screen.findByRole("textbox", { name: "Your script" });
/** The page with its looks loaded and the script pasted in. */
async function pasted(text = SCRIPT) {
  renderApp("/s/b/1");
  await screen.findByRole("button", { name: "Movie", pressed: true });
  await userEvent.click(await box());
  await userEvent.paste(text);
}
/** The send went, and its video's page is open in the new look. */
const opened = () => screen.findByRole("heading", { name: "The dip" });
const make = () => screen.findByRole("button", { name: "Make it about $4.87" }, { timeout: 3000 });
const pill = (name: string) => screen.getByRole("button", { name });
const choice = (name: RegExp | string) => screen.getByRole("menuitemradio", { name });
/** Holds every request to a path until released, so the screen can be seen mid-flight. */
function hold(path: string) {
  const real = globalThis.fetch;
  let release = () => {};
  const held = new Promise<void>((done) => (release = done));
  vi.stubGlobal("fetch", async (input: Request | string, init?: RequestInit) => {
    if (new URL(typeof input === "string" ? input : input.url, "http://x").pathname === `/api${path}`) await held;
    return real(input, init);
  });
  return release;
}

beforeEach(() => {
  localStorage.clear();
  setViewport(1440);
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:x" }));
});
afterEach(() => vi.unstubAllGlobals());

test("Make it posts the script as pasted, with nobody saved, no product and the plan first; the price asked for the same send; then the video opens on its page in the new look", async () => {
  const calls = server();
  await pasted(`  ${SCRIPT}\n\n`);
  expect(screen.getByRole("switch", { name: /Show me the plan and cast first/ })).toBeChecked();
  expect(await screen.findByText("About $4.87", {}, { timeout: 3000 })).toBeInTheDocument();
  expect(screen.getByText("An estimate. What it really spends shows on the video as it goes.")).toBeInTheDocument();
  await userEvent.click(await make());
  await opened();
  expect(screen.getByRole("region", { name: "The director" })).toBeInTheDocument(); // the new look's page for it
  expect(posted(calls)).toStrictEqual([DEFAULT]);
  expect(posted(calls, "POST /freestyles/estimate").at(-1)).toStrictEqual(DEFAULT);
});

const TWO_HOOKS = `Hook 1: A gate left open nearly cost a family everything.\nHook 2 (proven winner): If your pool has a gate, check it tonight.\n\nBody:\n${SCRIPT}`;
test("a script with several hooks is sent as it is, with nothing to choose: the script decides, every hook is a version", async () => {
  const calls = server();
  await pasted(TWO_HOOKS);
  expect(screen.queryByRole("button", { name: /^Hooks/ })).toBeNull();
  await userEvent.click(await make());
  await opened();
  expect(posted(calls)).toStrictEqual([{ ...DEFAULT, text: TWO_HOOKS }]);
  expect(posted(calls, "POST /freestyles/estimate").at(-1)).toStrictEqual({ ...DEFAULT, text: TWO_HOOKS });
});

test("a role given to a saved character, the product picked and the plan-first switch off are sent; the switch is remembered", async () => {
  const calls = server();
  await pasted();
  await userEvent.click(pill("Cast: New for this video"));
  const cast = within(screen.getByRole("menu", { name: "Cast" }));
  expect(cast.getAllByRole("button").map((b) => b.getAttribute("aria-label"))).toEqual(["Mia: New", "Nate: New"]); // the script's speakers, nobody matched by name
  await userEvent.click(cast.getByRole("button", { name: "Mia: New" }));
  expect(within(cast.getByRole("group", { name: "Who plays Mia" })).getAllByRole("menuitemradio")).toHaveLength(3); // New, and the brand's two: never a video's own extra
  await userEvent.click(choice(/^Nate/));
  expect(cast.getByRole("button", { name: "Mia: Nate" })).toHaveFocus();
  await userEvent.keyboard("{Escape}");
  await userEvent.click(pill("Product: The director decides"));
  await userEvent.click(choice(/^Capsule pack/));
  await userEvent.click(screen.getByRole("switch", { name: /Show me the plan and cast first/ }));
  expect(localStorage.getItem("bs.newvideo.mode")).toBe("auto");
  expect(pill("Cast: Nate as Mia")).toBeInTheDocument();
  expect(pill("Product: Capsule pack")).toBeInTheDocument();
  await userEvent.click(await make());
  await opened();
  expect(posted(calls)).toStrictEqual([{ ...DEFAULT, cast: [{ role: "MIA", item_id: 5 }], product_ids: [21], mode: "auto" }]);
});

test("Cast says so when the script names no speakers", async () => {
  server();
  await pasted("It was the first hot Saturday of the year.");
  await userEvent.click(pill("Cast: New for this video"));
  expect(screen.getByRole("menu", { name: "Cast" })).toHaveTextContent("No named speakers in this script. The director draws whoever it needs.");
});

test("a brand with nobody and no product saved says so, with the way to add a product", async () => {
  server(owner, { "GET /library/character": [200, []], "GET /library/prop": [200, []] });
  await pasted();
  await userEvent.click(pill("Cast: New for this video"));
  expect(screen.getByRole("menu", { name: "Cast" })).toHaveTextContent("Nobody is saved in Resilia yet. The director draws everyone for this video.");
  await userEvent.keyboard("{Escape}");
  await userEvent.click(pill("Product: None yet"));
  expect(screen.getByRole("menu", { name: "Product" })).toHaveTextContent("Resilia has no product saved yet.");
  expect(choice(/^The director decides/)).toBeChecked();
  expect(screen.getByRole("link", { name: "Add a product" })).toHaveAttribute("href", "/b/1/library/products?new=1");
});

test("an editor has no plan-first switch and always sends the plan first", async () => {
  localStorage.setItem("bs.newvideo.mode", "auto");
  const calls = server(editor, { "POST /freestyles": [201, { ...fs, status: "waiting", project_id: null }] });
  await pasted();
  expect(screen.queryByRole("switch")).toBeNull();
  await userEvent.click(await screen.findByRole("button", { name: "Make it about $4.87" }, { timeout: 3000 }));
  await vi.waitFor(() => expect(posted(calls)).toStrictEqual([DEFAULT]));
  await screen.findByRole("button", { name: "Account menu" }); // held for the owner, with no video to open yet: its page on the current site
  expect(document.querySelector(".studio")).toBeNull();
});

test("a look not made in the format moves the format and says so; the Format menu offers only what the look is made in", async () => {
  server();
  await pasted();
  await userEvent.click(screen.getByRole("button", { name: "Claymation" }));
  expect(await screen.findByText("Claymation is made only as Narrated or Song. The format is Narrated now.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Claymation", pressed: true })).toBeInTheDocument();
  await userEvent.click(pill("Format: Narrated"));
  expect(choice(/^Narrated/)).toBeChecked();
  expect(choice(/^Dialogue/)).toBeDisabled();
  expect(choice(/^Dialogue/)).toHaveTextContent("Not made in Claymation");
  expect(choice(/^Song/)).toBeDisabled();
  expect(choice(/^Song/)).toHaveTextContent("Coming next: the music provider");
  await userEvent.keyboard("{Escape}");
  await userEvent.click(screen.getByRole("button", { name: "House" })); // made in every format: the format stays
  expect(pill("Format: Narrated")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "UGC" })).toBeNull(); // a look that is off isn't offered
});

test("hovering a look plays it in the large preview; leaving puts the chosen one back", async () => {
  server();
  renderApp("/s/b/1");
  expect(await screen.findByLabelText("Movie sample")).toHaveAttribute("src", "/api/looks/movie/test-sample.mp4");
  await userEvent.hover(screen.getByRole("button", { name: "House" }));
  expect(screen.getByLabelText("House sample").closest(".monitor")).toHaveClass("peek");
  await userEvent.unhover(screen.getByRole("button", { name: "House" }));
  expect(screen.getByLabelText("Movie sample").closest(".monitor")).not.toHaveClass("peek");
  expect(screen.getByRole("button", { name: "Movie", pressed: true })).toBeInTheDocument();
});

test("the tint lies under the typed text with the same words: names a step dimmer, notes dimmest", async () => {
  server();
  await pasted(`${SCRIPT}\n`);
  const ink = document.querySelector(".ink")!;
  expect(ink.textContent).toBe(`${SCRIPT}\n\u200b`);
  expect([...ink.querySelectorAll(".nm")].map((n) => n.textContent)).toEqual(["MIA:", "NATE (V.O.):"]);
  expect([...ink.querySelectorAll(".ctx")].map((n) => n.textContent)).toEqual(["[A kitchen at dawn.]"]);
  expect(screen.getByText("2 voices · 2 spoken lines · about 10 s. Your words are never changed.")).toHaveAttribute("id", (await box()).getAttribute("aria-describedby")!);
});

test("Make it is off with no script and past 50,000 characters, which the box says plainly; nothing is priced", async () => {
  const calls = server();
  renderApp("/s/b/1");
  await screen.findByRole("button", { name: "Movie", pressed: true });
  expect(screen.getByRole("button", { name: "Make it" })).toBeDisabled();
  expect(screen.getByText("No script yet")).toBeInTheDocument();
  expect(screen.getByText("Put what’s going on in [brackets]. Lines that start with a name are spoken.")).toBeInTheDocument();
  fireEvent.change(await box(), { target: { value: "x".repeat(50_001) } });
  expect(screen.getByRole("alert")).toHaveTextContent("This script is 50,001 characters; the most is 50,000. Trim it or split it.");
  expect(screen.getByRole("button", { name: "Make it" })).toBeDisabled();
  await new Promise((r) => setTimeout(r, 500)); // past the estimate's settle
  expect(posted(calls, "POST /freestyles/estimate")).toEqual([]);
});

test("Make it takes one press: it says Starting… and a second press sends nothing", async () => {
  const calls = server();
  await pasted();
  const button = await make();
  const release = hold("/freestyles");
  fireEvent.click(button);
  fireEvent.click(button);
  expect(await screen.findByRole("button", { name: "Starting…" })).toBeDisabled();
  release();
  await opened();
  expect(posted(calls)).toHaveLength(1);
});

test("a price that can't be had says why", async () => {
  server(owner, { "POST /freestyles/estimate": [400, { detail: "That look is off on this site." }] });
  await pasted();
  expect(await screen.findByText("Price unavailable", {}, { timeout: 3000 })).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent("That look is off on this site.");
});

test("the paperclip uploads pictures for this video: Make it waits for an upload, a file can be removed, and six is the most", async () => {
  const calls = server();
  await pasted();
  await make();
  const release = hold("/files");
  await userEvent.click(screen.getByRole("button", { name: "Add to this video" }));
  expect(screen.getByRole("menuitem", { name: /Upload pictures or clips/ })).toHaveTextContent("Used for this video only. Up to 6.");
  await userEvent.keyboard("{Escape}");
  const input = screen.getByLabelText("Upload pictures or clips");
  await userEvent.upload(input, new File(["x"], "pack.jpg", { type: "image/jpeg" }));
  const files = within(screen.getByRole("list", { name: "For this video only" }));
  expect(files.getByRole("listitem")).toHaveTextContent("pack.jpgUploading…");
  expect(screen.getByRole("button", { name: /^Make it/ })).toBeDisabled();
  release();
  expect(await files.findByText("For this video only")).toBeInTheDocument();
  await vi.waitFor(() => expect(posted(calls, "POST /freestyles/estimate").at(-1)).toStrictEqual({ ...DEFAULT, attachments: [61] }), { timeout: 3000 });
  expect(screen.getByRole("button", { name: /^Make it/ })).toBeEnabled();
  await userEvent.click(files.getByRole("button", { name: "Remove pack.jpg" }));
  expect(screen.queryByRole("list", { name: "For this video only" })).toBeNull();
  await userEvent.upload(input, Array.from({ length: 7 }, (_, n) => new File(["x"], `shot-${n}.jpg`, { type: "image/jpeg" })));
  expect(await screen.findByText("That’s six, the most a video takes.")).toBeInTheDocument();
  expect(within(screen.getByRole("list", { name: "For this video only" })).getAllByRole("listitem")).toHaveLength(6);
});

test("Save in and Shape go with the send, and ⌘↵ in the script box presses Make it", async () => {
  const calls = server();
  await pasted();
  await userEvent.click(pill("Save in: Unsorted"));
  await userEvent.click(choice("Launch"));
  await userEvent.click(pill("Shape: 9:16"));
  await userEvent.click(choice(/^Square · 1:1/));
  await make();
  await userEvent.click(await box());
  await userEvent.keyboard("{Meta>}{Enter}{/Meta}");
  await opened();
  expect(posted(calls)).toStrictEqual([{ ...DEFAULT, folder_id: 4, shape: "1:1" }]);
});

test("an address for a brand that isn't there says so", async () => {
  server();
  renderApp("/s/b/7");
  expect(await screen.findByText("That brand doesn’t exist.")).toBeInTheDocument();
});
