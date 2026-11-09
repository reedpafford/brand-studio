import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { editor, owner } from "../test/people";
import { renderApp } from "../test/render";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { lookMedia } from "./Cards";
import { counts } from "../scripts/ScriptFrame";

const SCRIPT = "DR. PICKLE: Your gut after the weekend? A brewery with a pulse.";
const at = new Date().toISOString();
const look = (id: string, name: string, o: object = {}) => ({ id, name, blurb: `${name}'s long guide blurb.`, card: "", broll: "", on: true, own_sample: false, lanes: [], video_model: "seedance-2.0", test_clip: true, test_still: true, test_tag: true, ...o });
const LOOKS = [look("house", "House", { test_tag: false, card: "Our caricatured 3D", broll: "Near-real inserts" }), look("skeleton", "Skeleton", { broll: "Inside the body" }), look("dr-pickle", "Dr. Pickle", { broll: "Glossy 3D anatomy" }), look("ugc", "UGC", { on: false })];
const format = (id: string, name: string, o: object = {}) => ({ id, name, engine: "story", on: true, blurb: `${name} blurb.`, card: "", host: false, off: null, test_still: true, ...o });
const FORMATS = [format("dialogue", "Dialogue", { card: "People talk on camera" }), format("song", "Song", { engine: "song", off: "its music provider isn't switched on for this site yet" }), format("presenter", "Presenter", { engine: "narrated", host: true }), format("zack-d", "Zack D", { on: false, off: "off" })];
const fs = (o: object = {}) => ({ id: 9, title: "Beer gut", type: "dialogue", look: "house", shape: "9:16", brand_id: 1, status: "working", created_by_name: "Reed", created_at: at, credits: 0, file_id: null, project_id: 50, thread: [], ...o });
const version = (slot: number, o: object = {}) => ({ slot, status: "approved", title: "", seconds: 58, project_id: null, lines: 13, ...o });
const scriptRow = (id: number, title: string, o: object = {}) => ({ id, brand_id: 1, title, kind: "story", format: "dialogue", look: "dr-pickle", folder_id: null, published: true, versions: [version(0), version(1)], created_at: at, ...o });
const brand = { id: 1, name: "Resilia", colours: [], tone_notes: "" };

function server(me: object, routes: Record<string, [number, unknown]> = {}) {
  return fakeServer({
    "GET /auth/me": [200, me],
    "GET /brands": [200, [brand]],
    "GET /looks": [200, LOOKS],
    "GET /formats": [200, FORMATS],
    "GET /brands/1/folders": [200, [{ id: 4, name: "Week of 3 Nov", items: { scripts: 0, videos: 0, clips: 0 }, can_manage: true }]],
    "GET /library/character": [200, [{ id: 3, name: "Dr. Pickle", owner_project_id: null, owner_script_id: null }, { id: 5, name: "Nurse Kim", owner_project_id: null, owner_script_id: null }]],
    "GET /jobs": [200, []],
    "GET /freestyles": [200, []],
    "GET /projects/50": [200, { id: 50, brand_id: 1, name: "Beer gut", freestyle_id: 9 }],
    "GET /freestyles/9": [200, fs()],
    ...routes,
  });
}
afterEach(() => vi.unstubAllGlobals());
const words = async () => {
  await screen.findByRole("radio", { name: /^Dr\. Pickle/ }); // the guides' cards are in
  await screen.findByRole("radio", { name: /Dialogue/ });
  return screen.findByLabelText("Paste a script, or describe the video");
};
const loaded = () => screen.findByRole("radio", { name: /Dialogue/ });
const posted = (calls: { key: string; body: unknown }[], key = "POST /freestyles") => calls.filter((c) => c.key === key).at(-1)?.body;

test("S2-01/02: the owner's cards come from the guides; the press says the most in dollars, and Make it lands on the video in the open folder", async () => {
  setViewport(1440);
  const calls = server(owner, { "GET /freestyles/estimate": [200, { credits: 164, usd: 16.86, held: "", budget: null }], "POST /freestyles": [201, fs()] });
  renderApp("/b/1/videos/new?folder=4");
  expect(await screen.findByRole("heading", { name: "What should the director make?" })).toBeInTheDocument();
  await loaded();
  await screen.findByRole("radio", { name: /^Dr\. Pickle/ });
  expect(screen.getByRole("button", { name: /^Make it/ })).toBeDisabled();
  const formats = screen.getByRole("radiogroup", { name: "Format" });
  expect(within(formats).getByRole("radio", { name: /Dialogue.*People talk on camera/ })).toHaveAttribute("aria-checked", "true");
  const styles = screen.getByRole("radiogroup", { name: "Style" });
  expect(within(styles).getByRole("radio", { name: /^House/ })).toHaveAttribute("aria-checked", "true"); // the first style: brands keep no default
  await userEvent.click(within(styles).getByRole("radio", { name: /^Dr\. Pickle/ }));
  expect(within(styles).getByText("B-roll: near-real inserts")).toBeInTheDocument();
  expect(within(styles).getByText("Our caricatured 3D")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Cast: Nobody" })).toBeInTheDocument(); // nobody until picked: no default cast
  expect(screen.getByRole("button", { name: "Folder: Week of 3 Nov" })).toBeInTheDocument();
  await userEvent.type(await words(), SCRIPT);
  expect(await screen.findByRole("button", { name: "Make it · up to $16.86" }, { timeout: 3000 })).toBeInTheDocument();
  expect(screen.getByText("Most it can charge, including redos and the director’s time. Usually less.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Make it · up to $16.86" }));
  await vi.waitFor(() => expect(posted(calls)).toEqual({ type: "dialogue", look: "dr-pickle", shape: "9:16", brand_id: 1, folder_id: 4, broll_look: null, text: SCRIPT, cast_ids: [], attachments: [] }));
  expect(await screen.findByRole("list", { name: "Conversation with the director" })).toBeInTheDocument(); // the video's chat (S3)
});

test("a style plays its test sample, one at a time; House shows its site still with no tag", async () => {
  setViewport(1440);
  server(owner);
  renderApp("/b/1/videos/new");
  const styles = await screen.findByRole("radiogroup", { name: "Style" });
  await within(styles).findByRole("radio", { name: /^Skeleton/ });
  expect(within(styles).getByLabelText("Skeleton sample")).toHaveAttribute("src", "/api/looks/skeleton/test-sample.mp4");
  expect(within(styles).getByLabelText("House sample")).toHaveAttribute("src", "/api/looks/house/test-sample.mp4"); // the site's own clip
  expect(within(styles).getByRole("button", { name: "Play the House sample" })).toBeInTheDocument();
  await userEvent.click(within(styles).getByRole("button", { name: "Play the Skeleton sample" }));
  expect(within(styles).getByRole("button", { name: "Pause the Skeleton sample" })).toBeInTheDocument();
  await userEvent.click(within(styles).getByRole("button", { name: "Play the Dr. Pickle sample" }));
  expect(within(styles).getByRole("button", { name: "Play the Skeleton sample" })).toBeInTheDocument();
  expect(within(within(styles).getByRole("radio", { name: /^House/ })).queryByText("Test sample")).toBeNull();
});

test("S2-03: Song is coming next, Zack D and UGC are off on this site, with the reasons", async () => {
  setViewport(1440);
  server(owner);
  renderApp("/b/1/videos/new");
  const formats = await screen.findByRole("radiogroup", { name: "Format" });
  await loaded();
  await screen.findByRole("radio", { name: /^UGC/ });
  expect(within(formats).getByRole("radio", { name: /Song.*coming next/ })).toHaveAttribute("aria-disabled", "true");
  expect(within(formats).getByRole("radio", { name: /Zack D.*Off on this site/ })).toHaveAttribute("aria-disabled", "true");
  expect(screen.getByRole("radio", { name: /^UGC/ })).toHaveAttribute("aria-disabled", "true");
  const note = screen.getByText(/format is coming next/).closest("div")!;
  expect(note).toHaveTextContent("The Song format is coming next: its music provider isn't switched on for this site yet. The Zack D format is off on this site. The UGC style is off on this site; the owner turns it on in Settings → Looks.");
  expect(screen.getByRole("link", { name: "Settings → Looks" })).toHaveAttribute("href", "/settings?tab=looks");
});

test("S-gaps-01 (1): a format with a host offers Change B-roll look…; the picked look is sent", async () => {
  setViewport(1440);
  const calls = server(owner, { "GET /freestyles/estimate": [200, { credits: 170, usd: 17.48, held: "", budget: null }], "POST /freestyles": [201, fs()] });
  renderApp("/b/1/videos/new");
  await userEvent.click(await screen.findByRole("radio", { name: /^Dr\. Pickle/ }));
  await loaded();
  expect(screen.queryByRole("button", { name: "Change B-roll look…" })).toBeNull(); // Dialogue has no host
  await userEvent.click(screen.getByRole("radio", { name: /Presenter/ }));
  await userEvent.click(screen.getByRole("button", { name: "Change B-roll look…" }));
  const picker = screen.getByRole("dialog", { name: "B-roll look for this video" });
  expect(within(picker).getByRole("radio", { name: /Glossy 3D anatomy.*Dr. Pickle’s own · default/ })).toHaveAttribute("aria-checked", "true");
  expect(within(picker).queryByRole("radio", { name: /UGC/ })).toBeNull(); // off on this site
  await userEvent.click(within(picker).getByRole("radio", { name: /Inside the body.*from Skeleton/ }));
  await userEvent.click(within(picker).getByRole("button", { name: "Use this look" }));
  await userEvent.type(await words(), SCRIPT);
  await userEvent.click(await screen.findByRole("button", { name: "Make it · up to $17.48" }, { timeout: 3000 }));
  await vi.waitFor(() => expect(posted(calls)).toMatchObject({ type: "presenter", look: "dr-pickle", broll_look: "skeleton" }));
});

test("S-gaps-01 (3): Upload attaches pictures for this video only, and Adapt a reel instead opens Use a reel", async () => {
  setViewport(1440);
  const calls = server(owner, { "POST /files": [201, { id: 61, filename: "capsule-pack.jpg", content_type: "image/jpeg", size: 9, created_at: at }], "GET /freestyles/estimate": [200, { credits: 164, usd: 16.86, held: "", budget: null }], "POST /freestyles": [201, fs()] });
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:x" }));
  renderApp("/b/1/videos/new");
  await userEvent.type(await words(), SCRIPT);
  await userEvent.upload(screen.getByLabelText("Attach pictures or clips"), new File(["x"], "capsule-pack.jpg", { type: "image/jpeg" }));
  expect(await screen.findByText("capsule-pack.jpg")).toBeInTheDocument();
  expect(screen.getByText("Used for this video only. They aren’t added to the brand.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Upload" }));
  expect(screen.getByRole("menuitem", { name: /Attach pictures or clips.*for this video/ })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Upload" }));
  await userEvent.click(await screen.findByRole("button", { name: "Make it · up to $16.86" }, { timeout: 3000 }));
  await vi.waitFor(() => expect(posted(calls)).toMatchObject({ attachments: [61] }));
});

test("S2-04: an editor's pasted script goes to the owner, in credits, never dollars", async () => {
  setViewport(1440);
  server(editor, { "GET /freestyles/estimate": [200, { credits: 163.2, usd: null, held: "Waiting for the owner's OK: every freestyle send is checked first.", budget: null }] });
  renderApp("/b/1/videos/new");
  await userEvent.type(await words(), SCRIPT);
  expect(await screen.findByRole("button", { name: "Send to the owner · up to 164 credits" }, { timeout: 3000 })).toBeInTheDocument();
  expect(screen.getByText(/The owner approves before any generation starts. You’ll see it in My requests./)).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/\$|Reed/);
});

test("S2-06/S2-05: an editor's saved script starts inside its budget, or goes to the owner past it, saying by how much", async () => {
  setViewport(1440);
  const rows = [
    scriptRow(7, "Beer gut doctor rant", { versions: [version(0, { project_id: 70 }), version(1)] }),
    scriptRow(8, "Bloated after pizza", { look: "ugc", versions: [version(0, { lines: 1 })] }),
    scriptRow(6, "Why IPAs hit harder", { versions: [version(0, { project_id: 60 })] }), // every version has its video: still listed
    scriptRow(5, "My own draft", { published: false, versions: [version(0, { status: "draft" })] }), // an editor's own draft isn't
  ];
  const calls = server(editor, { "GET /scripts": [200, rows], "GET /freestyles/estimate": [200, { credits: 158, usd: null, held: "", budget: 194 }], "POST /freestyles": [201, fs()] });
  renderApp("/b/1/videos/new?from=script&folder=4");
  const list = await screen.findByRole("radiogroup", { name: "Scripts" });
  expect(await within(list).findByText("1 of 2 videos made")).toBeInTheDocument();
  expect(within(list).getByText("none made yet")).toBeInTheDocument();
  expect(within(list).getByText("1 of 1 videos made")).toBeInTheDocument();
  expect(within(list).queryByText("My own draft")).not.toBeInTheDocument();
  expect(within(list).getByText("Published · Version B · 13 lines")).toBeInTheDocument();
  expect(within(list).getByText("Published · Version A · 1 line")).toBeInTheDocument();
  const asked = new URL(calls.find((c) => c.key === "GET /scripts")!.url).searchParams;
  expect([asked.get("sends"), asked.get("status"), asked.get("limit")]).toEqual([null, null, "50"]); // every script, published made or not, a page at a time
  expect(screen.getByPlaceholderText("Search scripts")).toBeInTheDocument();
  expect(list).toHaveClass("max-h-[340px]", "overflow-y-auto");
  await userEvent.click(within(list).getByRole("radio", { name: /Beer gut doctor rant/ }));
  expect(await screen.findByText("Inside this video’s budget, so it starts straight away.", undefined, { timeout: 3000 })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Make it · up to 158 credits" }));
  await vi.waitFor(() => expect(posted(calls)).toEqual({ type: "dialogue", script_id: 7, slot: 1, shape: "9:16", folder_id: 4, broll_look: null }));
});

test("saved scripts: searching asks the server, which finds a script by its title or its words", async () => {
  setViewport(1440);
  const calls = server(owner, { "GET /scripts": [200, [scriptRow(113, "Small city apartment", { look: "pixar" })]], "GET /freestyles/estimate": [200, { credits: 164, usd: 16.86, held: "", budget: 194 }] });
  renderApp("/b/1/videos/new?from=script");
  await screen.findByRole("radio", { name: /Small city apartment/ });
  await userEvent.type(screen.getByPlaceholderText("Search scripts"), "sushi");
  await vi.waitFor(() => expect(calls.some((c) => new URL(c.url).searchParams.get("q") === "sushi")).toBe(true));
});

test("saved scripts: a full page offers Show more scripts, which asks for a longer one", async () => {
  setViewport(1440);
  const many = Array.from({ length: 50 }, (_, i) => scriptRow(200 + i, `Script ${i}`));
  const calls = server(owner, { "GET /scripts": [200, many] });
  renderApp("/b/1/videos/new?from=script");
  await userEvent.click(await screen.findByRole("button", { name: "Show more scripts" }));
  await vi.waitFor(() => expect(calls.some((c) => new URL(c.url).searchParams.get("limit") === "100")).toBe(true));
});

test("saved scripts: when the longer page brings nothing new, Show more goes away", async () => {
  setViewport(1440);
  server(owner, { "GET /scripts": [200, Array.from({ length: 50 }, (_, i) => scriptRow(200 + i, `Script ${i}`))] }); // exactly one full page, no more
  renderApp("/b/1/videos/new?from=script");
  await userEvent.click(await screen.findByRole("button", { name: "Show more scripts" }));
  await vi.waitFor(() => expect(screen.queryByRole("button", { name: "Show more scripts" })).toBeNull());
});

test("saved scripts: a short page has no Show more", async () => {
  setViewport(1440);
  server(owner, { "GET /scripts": [200, [scriptRow(7, "Beer gut doctor rant")]] });
  renderApp("/b/1/videos/new?from=script");
  await screen.findByRole("radio", { name: /Beer gut doctor rant/ });
  expect(screen.queryByRole("button", { name: "Show more scripts" })).toBeNull();
});

test("S2-05: past the video's budget the press goes to the owner and the line says the budget", async () => {
  setViewport(1440);
  server(editor, { "GET /scripts": [200, [scriptRow(7, "Beer gut doctor rant")]], "GET /freestyles/estimate": [200, { credits: 212, usd: null, held: "Waiting for the owner's OK: up to 212 credits is past this video's budget of 194.", budget: 194 }] });
  renderApp("/b/1/videos/new?from=script");
  await userEvent.click(await screen.findByRole("radio", { name: /Beer gut doctor rant/ }));
  expect(await screen.findByRole("button", { name: "Send to the owner · up to 212 credits" }, { timeout: 3000 })).toBeInTheDocument();
  expect(screen.getByText(/Up to 212 credits is past this video’s budget of 194, so it goes to the owner first. No generation starts while it waits./)).toBeInTheDocument();
});

test("S2-07: Use a reel uploads it, Copy it shot by shot reads it at its price; Just its look takes your script", async () => {
  setViewport(1440);
  const ready = { script_id: 30, status: "ready", source: "upload", seconds: 104, video_file_id: 31, transcript: [], problem: "", steps_done: [] };
  const calls = server(owner, {
    "POST /scripts/import/upload": [201, { ...ready, status: "preparing" }],
    "GET /scripts/30/import": [200, ready],
    "GET /freestyles/reel/estimate": [200, { credits: 3.9, usd: 0.4, ready: true }],
    "GET /freestyles/estimate": [200, { credits: 168, usd: 17.3, held: "", budget: null }],
    "POST /freestyles/reel": [201, fs({ reel_script_id: 30 })],
  });
  renderApp("/b/1/videos/new?from=reel");
  await loaded();
  await userEvent.click(await screen.findByRole("radio", { name: /^Dr\. Pickle/ }));
  await userEvent.upload(await screen.findByLabelText("Choose a reel"), new File(["x"], "doctor-rant-reference.mp4", { type: "video/mp4" }));
  expect(await screen.findByText("doctor-rant-reference.mp4")).toBeInTheDocument();
  expect(screen.getByRole("radio", { name: "Copy it shot by shot" })).toHaveAttribute("aria-checked", "true");
  await userEvent.click(await screen.findByRole("button", { name: "Watch it and write the script · up to $0.40" }, { timeout: 3000 }));
  await vi.waitFor(() => expect(posted(calls, "POST /freestyles/reel")).toMatchObject({ script_id: 30, mode: "copy", type: "dialogue", look: "dr-pickle" }));
});

test("S-gaps-01 (2): Just its look makes your script in the reel's look", async () => {
  setViewport(1440);
  const ready = { script_id: 30, status: "ready", source: "upload", seconds: 104, video_file_id: 31, transcript: [], problem: "", steps_done: [] };
  const calls = server(owner, { "GET /scripts/30/import": [200, ready], "GET /freestyles/estimate": [200, { credits: 168, usd: 17.3, held: "", budget: null }], "POST /freestyles/reel": [201, fs()] });
  renderApp("/b/1/videos/new?from=reel&reel=30");
  await loaded();
  await screen.findByRole("radio", { name: /^Dr\. Pickle/ });
  await userEvent.click(await screen.findByRole("radio", { name: "Just its look" }));
  expect(screen.getByText(/The director studies the reel’s look: camera, light, colour and cut pace/)).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Your script"), SCRIPT);
  expect(screen.getByText("from the reel")).toBeInTheDocument();
  const press = await screen.findByRole("button", { name: "Make it · up to $17.30" }, { timeout: 3000 });
  expect(screen.getByText("Watching the reel is free. The price includes the director’s time studying it.")).toBeInTheDocument();
  await userEvent.click(press);
  await vi.waitFor(() => expect(posted(calls, "POST /freestyles/reel")).toMatchObject({ mode: "look", text: SCRIPT }));
});

test("S-gaps-01: a silent reel can't be read, but Just its look takes it with no red warning", async () => {
  setViewport(1440);
  const NO_SOUND = "This video has no sound, so there's no dialogue to read.";
  const silent = { script_id: 30, status: "failed", failed_step: "prepare", problem_code: "no_sound", problem: NO_SOUND, source: "upload", seconds: 12, video_file_id: 31, transcript: [], steps_done: [] };
  const calls = server(owner, { "GET /scripts/30/import": [200, silent], "GET /freestyles/estimate": [200, { credits: 168, usd: 17.3, held: "", budget: null }], "POST /freestyles/reel": [201, fs()] });
  renderApp("/b/1/videos/new?from=reel&reel=30");
  await loaded();
  expect(await screen.findByText(`${NO_SOUND} Just its look can still use it.`)).toHaveClass("text-danger");
  expect(screen.getByRole("button", { name: /^Watch it and write the script/ })).toBeDisabled();
  await userEvent.click(screen.getByRole("radio", { name: "Just its look" }));
  expect(screen.queryByText(/no sound/)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^Make it/ })).toBeDisabled(); // your words first
  await userEvent.type(screen.getByLabelText("Your script"), SCRIPT);
  await userEvent.click(await screen.findByRole("button", { name: "Make it · up to $17.30" }, { timeout: 3000 }));
  await vi.waitFor(() => expect(posted(calls, "POST /freestyles/reel")).toMatchObject({ script_id: 30, mode: "look", text: SCRIPT }));
});

test("P-03: on a phone, the three ways in, cards that scroll, and Make it in the bar at the bottom", async () => {
  setViewport(390);
  server(owner, { "GET /freestyles/estimate": [200, { credits: 164, usd: 16.86, held: "", budget: null }] });
  renderApp("/b/1/videos/new?folder=4");
  expect(await screen.findByText("Resilia · Week of 3 Nov")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Close" })).toHaveAttribute("href", "/b/1/videos");
  for (const tab of ["Paste", "Saved script", "Use a reel"]) expect(screen.getByRole("tab", { name: tab })).toHaveClass("h-control", "lg:h-7"); // 44 px on a phone (S10)
  for (const chip of [/^Cast: /, /^Shape: /, /^Folder: /]) expect(screen.getByRole("button", { name: chip })).toHaveClass("h-control");
  expect(screen.getByRole("radiogroup", { name: "Format" })).toHaveClass("-mx-4", "px-4"); // its edge is the page's 16 px gutter, not past it
  await userEvent.type(await words(), SCRIPT);

  expect(await screen.findByRole("button", { name: "Make it · up to $16.86" }, { timeout: 3000 })).toBeInTheDocument();
  expect(screen.getByText("The most it can charge, redos included")).toBeInTheDocument();
});

test("From a saved script: the cards show the script's own format and style, locked; the owner's drafts show too", async () => {
  setViewport(1440);
  const rows = [scriptRow(7, "Beer gut doctor rant", { format: "presenter", kind: "narrated" }), scriptRow(9, "Gut glow-up", { published: false, look: "claymation", versions: [version(0, { status: "draft" })] }), scriptRow(10, "Untitled reel", { published: false, versions: [version(0, { status: "draft", lines: 0 })] })];
  server(owner, { "GET /scripts": [200, rows], "GET /freestyles/estimate": [200, { credits: 164, usd: 16.86, held: "", budget: 194 }] });
  renderApp("/b/1/videos/new?from=script");
  const list = await screen.findByRole("radiogroup", { name: "Scripts" });
  expect(await within(list).findByText("owner only")).toBeInTheDocument();
  expect(within(list).queryByText("Untitled reel")).not.toBeInTheDocument(); // no words yet: nothing to make
  await userEvent.click(within(list).getByRole("radio", { name: /Beer gut doctor rant/ }));
  expect(await screen.findByRole("radio", { name: /Presenter/ })).toHaveAttribute("aria-checked", "true");
  expect(screen.getByRole("radio", { name: /Dialogue/ })).toHaveAttribute("aria-disabled", "true"); // the script's own
  expect(screen.getByText("From the script")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Change B-roll look…" })).toBeInTheDocument(); // still the video's own pick
});

test("uncapped (Reed, 6 Nov): the owner's press says about what it will cost, an estimate, never up to", async () => {
  setViewport(1440);
  server(owner, { "GET /freestyles/estimate": [200, { credits: 91, usd: 9.1, held: "", budget: null, expected: true }] });
  renderApp("/b/1/videos/new");
  await userEvent.type(await words(), SCRIPT);
  expect(await screen.findByRole("button", { name: "Make it · about $9.10" }, { timeout: 3000 })).toBeInTheDocument();
  expect(screen.getByText(/^An estimate of what it will probably cost\. Nothing stops it at a limit here/)).toBeInTheDocument();
  expect(screen.queryByText(/up to|Most it can charge/)).toBeNull();
});

test("MAIN's run 276: a style with no sample says so, never a blank box, and the styles wrap at 1440 instead of running off the edge", async () => {
  setViewport(1440);
  const movie = look("movie", "Movie", { test_clip: false, test_still: false });
  server(owner, { "GET /looks": [200, [...LOOKS, movie]] });
  renderApp("/b/1/videos/new");
  const styles = await screen.findByRole("radiogroup", { name: "Style" });
  const card = (await within(styles).findByRole("radio", { name: /^Movie/ })).parentElement!;
  expect(within(card).getByText("No sample yet")).toBeInTheDocument();
  expect(styles).toHaveClass("grid"); // a grid that fills the width: the row ends where the box above it ends
  expect(styles).not.toHaveClass("overflow-x-auto");
});

test("MAIN's run (video 233): a sample the test site's stand-ins made never hides the real test sample on a style's card", () => {
  const made = look("disney-pixar", "Disney Pixar", { sample_clip_id: 9, sample_still_id: 8 });
  expect(lookMedia({ ...made, sample_stand_in: true } as never)).toEqual({ clip: "/api/looks/disney-pixar/test-sample.mp4", still: "/api/looks/disney-pixar/test-sample.jpg", tag: true });
  expect(lookMedia({ ...made, sample_stand_in: false } as never).clip).toMatch(/\/9\b/); // a real one: the owner's own
});

test("QA on #1440: a style made only as Dialogue (Movie) isn't offered for Presenter, with its reason; picked, it gives way and says so", async () => {
  setViewport(1440);
  const movie = look("movie", "Movie", { formats: ["dialogue"], formats_why: "its people say the script's lines on camera", video_model: "gemini-omni-1.2" });
  server(owner, { "GET /looks": [200, [movie, ...LOOKS]] });
  renderApp("/b/1/videos/new");
  await loaded();
  const styles = screen.getByRole("radiogroup", { name: "Style" });
  const card = await within(styles).findByRole("radio", { name: /^Movie/ });
  expect(card).toHaveAttribute("aria-checked", "true"); // Dialogue: Movie is offered (the first style)
  expect(card).not.toHaveAttribute("aria-disabled");
  await userEvent.click(card); // picked by the person: a format that can't use it says so
  await userEvent.click(within(screen.getByRole("radiogroup", { name: "Format" })).getByRole("radio", { name: /Presenter/ }));
  const off = within(styles).getByRole("radio", { name: /^Movie/ });
  expect(off).toHaveAttribute("aria-disabled", "true");
  expect(off).toHaveAttribute("aria-checked", "false"); // the next style that fits is used instead
  expect(within(styles).getByText("Movie is made only as Dialogue: its people say the script's lines on camera.")).toBeInTheDocument();
  expect(within(styles).getByRole("radio", { name: /^House/ })).toHaveAttribute("aria-checked", "true");
  expect(screen.getByText("Movie is made only as Dialogue: its people say the script's lines on camera. The style is House for now.")).toBeInTheDocument();
});

test("MAIN's Claymation run: a narrated script is read whole at a narrator's pace, not only its one NARRATOR: line", () => {
  const clay = ["NARRATOR: Most owners think an itchy dog has a skin problem.", "It usually starts in the belly.", "The good guys in there need more than plain kibble to win.", "[Camera] Close on the paws.", "When they lose, the itch shows up in the paws."].join("\n");
  expect(counts(clay, true)).toMatchObject({ words: 44, seconds: 15 }); // 38 read words at 2.6 a second; it said "about 2 s"
  expect(counts(clay).seconds).toBe(2); // as dialogue only the NAME: line is spoken, as before
});
