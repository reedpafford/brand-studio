import { act, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { editor, owner } from "../test/people";
import { cutOut } from "../test/cut";
import { renderApp } from "../test/render";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { NOT_PLAIN } from "./director";

// The video page (v6 S3): the director's chat with the preview panel beside it. Boards S3-01, S3-09, S3-15, S3-16, P-04,
// P-05, and S-gaps-03 (the Locks menu, the ⋯ menu, the phone's tab row).
const at = "2026-11-04T10:02:00Z";
const later = "2026-11-04T10:25:00Z";
const item = (id: string, kind: string, who: string, text: string, status: string | null = null, when = at, o: object = {}) => ({ id, kind, at: when, who, text, status, why: "", ...o });
const SCRIPT = "DR. PICKLE: Your gut after the weekend? A brewery with a pulse.\nDR. PICKLE: Every pint sits there and ferments.\nDR. PICKLE: That's not a belly.\nDR. PICKLE: It's a science project.";
const fs = (o: object = {}) => ({ id: 9, title: "Beer gut doctor rant", type: "dialogue", look: "house", shape: "9:16", brand_id: 1, status: "working", created_by_name: "Reed", created_at: at, credits: 61.2, file_id: null, up_to: 164, project_id: 50, script_id: 3, thread: [item("m1", "message", "Reed", SCRIPT), item("t1", "move", "Director", "Made the plan.", "done")], ...o });
const run = (o: object = {}) => ({ status: "running", ended: "", turns: [{ turn: 0, tool: "make_take", why: "", result: "", status: "succeeded", created_at: at }], credits: 61, spent_usd: null, start_blocked: "", thread: [], unread: 0, run_price: 40, ...o });
const project = { id: 50, brand_id: 1, name: "Beer gut doctor rant · freestyle 9", freestyle_id: 9, aspect_ratio: "9:16", look: "house", credits_used: 60, budget_credits: 164, created_by_id: 1, created_by_name: "Reed", folder_id: 4, script_draft_id: 7, product_variants: {}, plan_status: "none", kind: "story" };
const status = (kind: string, words: string, reason: string | null = null) => ({ kind, words, reason, at: null, made: 0, total: 0 });
const money = (credits: number, usd: number | null) => ({ credits, usd });
const head = (o: object = {}) => ({ title: "Beer gut doctor rant", status: status("working", "Working", "14 of 24"), spent: money(60, 6.12), up_to: money(164, 16.86), budget: money(164, 16.86), folder: { id: 4, name: "Week of 3 Nov" }, format: "Presenter", style: "Dr. Pickle", seconds: 58, song: false, ...o });
const locks = { locks: { cast: true, look: true, length: false, song: false, end_line: false, screens: [7] }, outfits: {} };
function server(me: object, f: object | null, r: object, routes: Record<string, [number, unknown]> = {}) {
  return fakeServer({
    "GET /auth/me": [200, me],
    "GET /brands": [200, [{ id: 1, name: "Resilia", colours: [] }]],
    "GET /looks": [200, [{ id: "house", name: "House", blurb: "", on: true, own_sample: false, lanes: [] }]],
    "GET /jobs": [200, []],
    "GET /projects/50": [200, f ? project : { ...project, freestyle_id: null }],
    ...(f ? { "GET /freestyles/9": [200, f] as [number, unknown] } : {}),
    "GET /projects/50/director": [200, r],
    "GET /projects/50/idea": [200, head(me === editor ? { spent: money(60, null), up_to: money(164, null), budget: money(164, null) } : {})],
    "GET /projects/50/clips": [200, []],
    "GET /projects/50/storyboard": [200, []],
    "GET /projects/50/assets": [200, [{ kind: "character", ref: "char:5", role: "Dr. Pickle", library_item_id: 5, name: "Dr. Pickle", locked: true, sheet_status: "approved", ready: true, slot_id: null, shots: 3 }]],
    "GET /projects/50/video": [404, { detail: "none" }],
    "GET /projects/50/locks": [200, locks],
    ...routes,
  });
}
afterEach(() => vi.unstubAllGlobals());

/** The message box once the page has loaded (the loading skeleton has a box too, S3-15). */
async function ready() {
  await screen.findByRole("list", { name: "Conversation with the director" });
  return screen.getByLabelText("Tell the director what to change");
}

test("S3-01: the header says where it is, its status and reason, the money, and the chips; the panel opens on the plan", async () => {
  setViewport(1440);
  server(owner, fs({ thread: [item("m1", "message", "Reed", SCRIPT), item("t1", "move", "Director", "Reading the script.", "running")] }), run({ turns: [{ turn: 0, tool: null, why: "", result: "", status: "running", created_at: at }] }));
  renderApp("/b/1/videos/50");
  const top = await screen.findByRole("banner");
  expect(within(top).getByRole("heading", { name: "Beer gut doctor rant" })).toBeInTheDocument();
  expect(within(top).getByRole("link", { name: "Resilia" })).toHaveAttribute("href", "/b/1/videos");
  expect(within(top).getByRole("link", { name: "Week of 3 Nov" })).toHaveAttribute("href", "/b/1/videos?folder=4");
  expect(within(top).getByText("Working · starting")).toBeInTheDocument(); // the run's place, not the clip count
  expect(within(top).getByText("$6.12 spent ·", { exact: false })).toBeInTheDocument();
  expect(within(top).getByText("up to $16.86")).toBeInTheDocument();
  const chips = within(top).getByLabelText("What it builds around");
  expect(within(chips).getByText("Presenter · Dr. Pickle")).toBeInTheDocument();
  expect(within(chips).getByText("about 58 s")).toBeInTheDocument();
  expect(await within(chips).findByRole("button", { name: "Locks +1" })).toBeInTheDocument(); // Screens: on, and not a chip
  expect(within(top).getByRole("button", { name: "Stop" })).toBeInTheDocument();
  // The first message is a bubble with the script's first lines; the director's move under way shows its dots.
  const thread = screen.getByRole("list", { name: "Conversation with the director" });
  expect(within(thread).getByText("+ 2 more lines")).toBeInTheDocument();
  expect(within(thread).getByText("Reading the script.")).toBeInTheDocument();
  expect(within(screen.getByRole("tablist", { name: "Preview" })).getByRole("tab", { name: "Plan", selected: true })).toBeInTheDocument();
  expect(await screen.findByText("The plan shows here first")).toBeInTheDocument();
  expect(screen.getByPlaceholderText("Add anything the director should know")).toBeInTheDocument();
});

test("before Make it the header says No generation started, even after the treatment's small planning spend (Reed, 4 Nov)", async () => {
  setViewport(1440);
  server(owner, fs(), run({ started: false }));
  renderApp("/b/1/videos/50");
  const top = await screen.findByRole("banner");
  expect(await within(top).findByText("No generation started ·", { exact: false })).toBeInTheDocument();
  expect(within(top).getByText("up to $16.86")).toBeInTheDocument();
  expect(top.textContent).not.toMatch(/Nothing spent/);
});

test("an editor sees credits and the budget, never dollars (rule 4)", async () => {
  setViewport(1440);
  server(editor, fs({ created_by_name: "Eli" }), run(), { "GET /projects/50": [200, { ...project, created_by_id: 2 }] });
  renderApp("/b/1/videos/50");
  expect(await screen.findByText("60 credits used ·", { exact: false })).toBeInTheDocument();
  expect(screen.getByText("up to 164 credits")).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/\$\d|ask (Reed|the owner)/i);
});

test("Locks +N opens the locks, one press each; Song is off in a video with no song, Screens only shows (S-gaps-03 1)", async () => {
  setViewport(1440);
  const calls = server(owner, fs(), run(), { "PUT /projects/50/locks": [200, { ...locks, locks: { ...locks.locks, length: true } }] });
  renderApp("/b/1/videos/50");
  await userEvent.click(await screen.findByRole("button", { name: "Locks +1" }));
  const menu = screen.getByRole("menu", { name: "Locks" });
  expect(within(menu).getByRole("switch", { name: "Lock the cast" })).toBeChecked();
  expect(within(menu).getByRole("switch", { name: "Lock the song" })).toBeDisabled();
  expect(within(menu).getByText("Not in a Presenter video")).toBeInTheDocument();
  expect(within(menu).queryByText("End line")).toBeNull(); // held back for Reed's answer (#1315)
  expect(within(menu).getByText("1 · picked in the plan")).toBeInTheDocument();
  await userEvent.click(within(menu).getByRole("switch", { name: "Lock the length" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /projects/50/locks")?.body).toEqual({ ...locks, locks: { ...locks.locks, length: true } }));
});

test("the ⋯ menu: Move to folder…, and once it's done Download MP4 and Archive (S-gaps-03 2); Move files it", async () => {
  setViewport(1440);
  const done = fs({ status: "delivered", file_id: 8, thread: [item("m1", "message", "Reed", SCRIPT), item("t2", "move", "Director", "Here's the cut.", "done", later)] });
  const delivered = run({ status: "delivered", turns: [{ turn: 3, tool: "deliver", why: "", result: "Delivered.", status: "succeeded", created_at: later }] });
  const tree = { folders: [{ id: 4, parent_id: null, name: "Week of 3 Nov", ideas: [], count: 1, more: 0, folders: [], can_manage: true }, { id: 6, parent_id: null, name: "UGC testimonials", ideas: [], count: 0, more: 0, folders: [], can_manage: true }], unsorted: { id: null, name: "Unsorted", count: 0, ideas: [], more: 0 } };
  const calls = server(owner, done, delivered, { "GET /projects/50": [200, { ...project, finished_at: later }], "GET /projects/50/video": [200, { file_id: 8, take_ids: [], out_of_date: false }], "GET /brands/1/tree": [200, tree], "POST /folders/file": [200, { moved: 1 }] });
  renderApp("/b/1/videos/50");
  await userEvent.click(await screen.findByRole("button", { name: "More for Beer gut doctor rant" }));
  const menu = screen.getByRole("menu", { name: "More for Beer gut doctor rant" });
  expect(within(menu).getByRole("menuitem", { name: "Download MP4" })).toHaveAttribute("href", "/api/files/8");
  expect(within(menu).getByRole("menuitem", { name: "Archive" })).toBeInTheDocument();
  expect(within(menu).queryByRole("menuitem", { name: /Release/ })).toBeNull();
  await userEvent.click(within(menu).getByRole("menuitem", { name: "Move to folder…" }));
  const dialog = await screen.findByRole("alertdialog", { name: /Move Beer gut doctor rant to/ });
  await userEvent.click(await within(dialog).findByRole("radio", { name: "UGC testimonials" }));
  await userEvent.click(within(dialog).getByRole("button", { name: "Move" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /folders/file")?.body).toEqual({ kind: "video", ids: [50], folder_id: 6 }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" })); // back where it was
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /folders/file").map((c) => c.body)).toContainEqual({ kind: "video", ids: [50], folder_id: 4 }));
});

test("S3-09: delivered, the cut plays in the Cut tab with its downloads and what it's made of; the box asks what to change", async () => {
  setViewport(1440);
  const done = fs({ status: "delivered", file_id: 8, thread: [item("m1", "message", "Reed", SCRIPT), item("t2", "move", "Director", "Here's the cut.", "done", later)] });
  const delivered = run({ status: "delivered", turns: [{ turn: 3, tool: "deliver", why: "", result: "Delivered.", status: "succeeded", created_at: later }] });
  server(owner, done, delivered, { "GET /projects/50/idea": [200, head({ status: status("delivered", "Delivered"), spent: money(96, 9.84) })], "GET /projects/50/video": [200, { file_id: 8, take_ids: [], out_of_date: false }] });
  renderApp("/b/1/videos/50");
  expect(await screen.findByText("$9.84 of", { exact: false })).toBeInTheDocument();
  const panel = await screen.findByRole("tabpanel", { name: "Cut" });
  expect(await within(panel).findByLabelText("The cut")).toHaveAttribute("src", "/api/files/8");
  expect(within(panel).getByRole("link", { name: "Download MP4" })).toHaveAttribute("download", "beer-gut-doctor-rant.mp4");
  expect(within(panel).getByRole("link", { name: "Download every clip (.zip)" })).toHaveAttribute("href", "/api/projects/50/clips.zip");
  expect(within(panel).getByText("$9.84")).toBeInTheDocument();
  expect(screen.getByPlaceholderText(/^Say what to change: “warmer light in scene 2”/)).toBeInTheDocument(); // never a promise that a change is free (Reed, 5 Nov)
  expect(screen.queryByRole("button", { name: "Stop" })).toBeNull();
});

test("the owner's note after a delivery starts the next run by talking; there's no Make it again press under the note (S3-12)", async () => {
  setViewport(1440);
  const done = fs({ status: "delivered", file_id: 8, thread: [item("m1", "message", "Reed", SCRIPT), item("t2", "move", "Director", "Every take checked clean.", "done", later)] });
  const delivered = run({ status: "delivered", turns: [{ turn: 3, tool: "deliver", why: "", result: "Delivered.", status: "succeeded", created_at: later }] });
  const going = { ...run(), thread: [item("m0", "message", "Reed", "Cut 2 seconds.", null, "2026-11-04T10:30:00Z")] };
  const calls = server(owner, done, delivered, { "POST /projects/50/director/messages": [201, going] });
  renderApp("/b/1/videos/50");
  const box = await ready();
  expect(screen.queryByRole("button", { name: /^Make it again/ })).toBeNull(); // no leftover press on a delivered video
  expect(screen.getByRole("button", { name: "Send to the director" })).toBeDisabled(); // nothing to send yet
  await userEvent.type(box, "Cut 2 seconds.{Enter}");
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/50/director/messages")?.body).toEqual({ text: "Cut 2 seconds." }));
  expect(await within(screen.getByRole("list", { name: "Conversation with the director" })).findByText("Cut 2 seconds.")).toBeInTheDocument();
  expect(screen.queryByText("Saved. Press Make it again to make this change.")).toBeNull();
  expect(calls.some((c) => c.key === "POST /projects/50/director")).toBe(false); // the note itself starts it
});

test("M1: the owner is never shown the held-send card or 'once the owner approves' for his own run", async () => {
  setViewport(1440);
  const waiting = fs({ status: "waiting", thread: [item("m1", "message", "Reed", SCRIPT), item("t1", "move", "Director", "Ready.", "held")] });
  server(owner, waiting, run({ status: "running", thread: [] }));
  renderApp("/b/1/videos/50");
  await ready();
  expect(screen.queryByText(/The owner has been asked/)).toBeNull();
  expect(screen.queryByText(/once the owner approves/)).toBeNull();
});


test("pictures or clips go with a note, for this video only (rule 12)", async () => {
  setViewport(1440);
  const calls = server(owner, null, run({ thread: [item("t1", "move", "Director", "Made the plan.", "done")] }), {
    "POST /files": [201, { id: 77, kind: "image", content_type: "image/png" }],
    "POST /projects/50/director/messages": [201, run()],
  });
  renderApp("/b/1/videos/50");
  await ready();
  const pick = screen.getByRole("button", { name: "Add pictures or clips for this video" });
  const input = pick.parentElement!.querySelector<HTMLInputElement>('input[type="file"]')!;
  await userEvent.upload(input, new File(["x"], "capsule-pack.png", { type: "image/png" }));
  expect(await screen.findByRole("link", { name: "capsule-pack.png" })).toHaveAttribute("href", "/api/files/77");
  await userEvent.type(screen.getByLabelText("Tell the director what to change"), "Use this bag at the end.{Enter}");
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/50/director/messages")?.body).toEqual({ text: "Use this bag at the end.", files: [77] }));
});

test("during a run a note is read on the next move; a double press sends one note; Stop asks first", async () => {
  setViewport(1440);
  const going = run({ thread: [item("t1", "move", "Director", "Made the plan.", "done")] });
  const sent = run({ thread: [item("t1", "move", "Director", "Made the plan.", "done"), item("m0", "message", "Reed", "Warmer light.", null, later)] });
  const calls = server(owner, null, going, { "POST /projects/50/director/messages": [201, sent], "POST /projects/50/director/stop": [200, run({ status: "ended", ended: "Stopped." })] });
  renderApp("/b/1/videos/50");
  await userEvent.type(await ready(), "Warmer light.");
  await userEvent.dblClick(screen.getByRole("button", { name: "Send to the director" }));
  expect(await screen.findByText("The director will read this on its next move.")).toBeInTheDocument();
  expect(calls.filter((c) => c.key === "POST /projects/50/director/messages")).toHaveLength(1);
  await userEvent.click(screen.getByRole("button", { name: "Stop" }));
  await userEvent.click(within(screen.getByRole("alertdialog", { name: "Stop the director?" })).getByRole("button", { name: "Stop" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/50/director/stop")).toBe(true));
});

test("move lines are plain words: no tool names, codes, ids or JSON; a refusal drops the server's prefix; notes say Answered or Open", async () => {
  setViewport(1440);
  const thread = [
    item("m0", "message", "Reed", "Warmer light.", null, at, { answered: true }),
    item("t1", "move", "Director", "Picked take 12 for c2.", "done", at, { why: "c2 is flagged: the boss looks calm." }),
    item("t2", "move", "Director", "Refused: the cast is locked, so it stays.", "refused"),
    item("t3", "move", "Director", "Made the cut.", "done", at, { why: '{"tool": "make_take", "clip_id": "c9"}' }),
    item("m1", "message", "Reed", "Shorter.", null, at, { answered: false }),
  ];
  server(owner, null, run({ thread }), { "GET /projects/50/clips": [200, [{ id: 2, clip_id: "c2", seconds: 5, takes: [{ id: 12, number: 3, file_id: 1, created_at: at }], picked_take_id: 12 }]] });
  renderApp("/b/1/videos/50");
  const list = await screen.findByRole("list", { name: "Conversation with the director" });
  expect(await within(list).findByText("Picked take 3 for clip 2.")).toBeInTheDocument();
  expect(within(list).getByText("clip 2 is flagged: the boss looks calm.")).toBeInTheDocument();
  expect(within(list).getByText("The cast is locked, so it stays.")).toBeInTheDocument();
  expect(list.textContent).not.toMatch(NOT_PLAIN);
  expect(within(list).getAllByText(/· Answered$/)).toHaveLength(1);
  expect(within(list).getAllByText(/· Open$/)).toHaveLength(1);
});

test("before the owner's OK an editor's send opens by its freestyle: the script it came from, and the box opens once approved", async () => {
  setViewport(1440);
  const script = { id: 3, title: "Beer gut doctor rant", created_at: "2026-10-30T10:00:00Z", versions: [{ slot: 1, project_id: null, text: SCRIPT, seconds: 35 }] };
  server(editor, fs({ status: "waiting", created_by_name: "Eli", thread: [item("m1", "message", "Eli", SCRIPT), item("t1", "move", "Director", "Waiting for the owner's OK.", "held")] }), run({ status: "none", turns: [] }), { "GET /scripts/3": [200, script], "GET /projects/50": [404, { detail: "No such project." }] });
  renderApp("/b/1/freestyle/9");
  expect(await screen.findByText("From script Beer gut doctor rant · version B")).toBeInTheDocument();
  expect(screen.getByText("Waiting for the owner")).toBeInTheDocument();
  expect(screen.getByLabelText("Tell the director what to change")).toBeDisabled();
  expect(screen.getByPlaceholderText("Opens once the owner approves")).toBeInTheDocument();
});

test("the director's treatment is a card in the thread; a new one says Changed", async () => {
  setViewport(1440);
  const treatment = (hook: string) => ({ hook, logline: "Dr. Pickle rants.", why_it_holds: "The spine glows first.", beats: [{ id: "b1", purpose: "Hook", picture: "Glowing spine" }], ending: "Capsule hold." });
  const told = (id: string, text: string, hook: string, when: string) => ({ ...item(id, "move", "Director", text, "done", when), treatment: treatment(hook) });
  server(owner, fs({ thread: [item("m1", "message", "Reed", SCRIPT), told("s1", "The treatment: …", "Your gut after the weekend", at), told("s2", "Changed the treatment: …", "A brewery with a pulse", later)] }), run());
  renderApp("/b/1/videos/50");
  const [first, second] = await screen.findAllByRole("region", { name: "Treatment" });
  expect(within(first).queryByText("Changed")).toBeNull();
  expect(within(second).getByText("Changed")).toBeInTheDocument();
  expect(screen.queryByText("The treatment: …")).toBeNull();
});

test("S3-16: offline, the page says the director keeps working; what's typed sends once it's back", async () => {
  setViewport(1440);
  const calls = server(owner, null, run({ thread: [item("t1", "move", "Director", "Made the plan.", "done")] }), { "POST /projects/50/director/messages": [201, run()] });
  renderApp("/b/1/videos/50");
  const box = await ready();
  vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
  act(() => void window.dispatchEvent(new Event("offline")));
  expect(await screen.findByText(/^You’re offline\. The director keeps working on the server/)).toBeInTheDocument();
  expect(screen.getByPlaceholderText("You can type; it sends when you’re back")).toBeInTheDocument();
  await userEvent.type(box, "Brighter.{Enter}");
  expect(await screen.findByText("Sends when you’re back.")).toBeInTheDocument();
  expect(calls.some((c) => c.key === "POST /projects/50/director/messages")).toBe(false);
  vi.spyOn(navigator, "onLine", "get").mockReturnValue(true);
  act(() => void window.dispatchEvent(new Event("online")));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/50/director/messages")?.body).toEqual({ text: "Brighter." }));
});

test("S3-15: while it loads, grey shapes where the header, the thread and the cut go; the box is already there", async () => {
  setViewport(1440);
  server(owner, null, run());
  const answer = globalThis.fetch;
  vi.stubGlobal("fetch", vi.fn((input: Request | string, init?: RequestInit) => (String(input instanceof Request ? input.url : input).includes("/projects/50") ? new Promise(() => {}) : answer(input, init)))); // the video doesn't answer yet
  renderApp("/b/1/videos/50");
  expect(await screen.findByText("Script")).toBeInTheDocument(); // the panel's tabs
  expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
  expect(screen.getByLabelText("Tell the director what to change")).toBeDisabled();
});

test("old addresses open their tab: ?step=clips opens Clips, ?step=downloads the Cut", async () => {
  setViewport(1440);
  server(owner, null, run());
  renderApp("/b/1/videos/50?step=downloads");
  expect(await screen.findByRole("tab", { name: "Cut", selected: true })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("tab", { name: "Script" }));
  expect(screen.getByRole("tab", { name: "Script", selected: true })).toBeInTheDocument();
});

test("P-04, P-05: at 390 a Chat | Preview switch; Preview always shows its tab row (S-gaps-03 3); Stop is in the ⋯ menu", async () => {
  setViewport(390);
  server(owner, fs(), run());
  renderApp("/b/1/videos/50");
  const sides = await screen.findByRole("tablist", { name: "Chat or preview" });
  expect(within(sides).getByRole("tab", { name: "Chat", selected: true })).toBeInTheDocument();
  expect(screen.getByText(/· up to \$16\.86$/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Stop" })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "More for Beer gut doctor rant" }));
  expect(await screen.findByRole("menuitem", { name: "Stop the director" })).toBeInTheDocument();
  await userEvent.keyboard("{Escape}");
  await userEvent.click(within(sides).getByRole("tab", { name: "Preview" }));
  const tabs = screen.getByRole("tablist", { name: "Preview" });
  expect(within(tabs).getAllByRole("tab").map((t) => t.textContent)).toEqual(["Cut", "Clips", "Cast", "Plan", "Script"]);
  await userEvent.click(within(sides).getByRole("tab", { name: "Chat" }));
  await userEvent.type(screen.getByLabelText("Tell the director what to change"), "Warmer light");
  await userEvent.click(within(sides).getByRole("tab", { name: "Preview" }));
  await userEvent.click(within(sides).getByRole("tab", { name: "Chat" }));
  expect(screen.getByLabelText("Tell the director what to change")).toHaveValue("Warmer light"); // a draft survives the switch
});

test("the first message's script shows its first lines and opens in full; a later note of many lines reads whole", async () => {
  setViewport(1440);
  const note = "Shorter.\nWarmer light.\nEnd on the capsule.";
  server(owner, fs({ thread: [item("m1", "message", "Reed", SCRIPT), item("m2", "message", "Reed", note, null, later)] }), run());
  renderApp("/b/1/videos/50");
  const thread = await screen.findByRole("list", { name: "Conversation with the director" });
  await userEvent.click(within(thread).getByRole("button", { name: "+ 2 more lines" }));
  expect(within(thread).getByText("DR. PICKLE: It's a science project.")).toBeInTheDocument();
  expect(within(thread).getByText(/End on the capsule\./)).toBeInTheDocument();
});

// Screen 4: the run's one live card, the stopped and failed ends, and the delivery note (pieces C and D).
const cell = (n: number, scene: number, o: object = {}) => ({ clip_id: `c${n}`, number: n, scene, label: "", seconds: 2, model: "Seedance 2.0", state: "done", frame_file_id: 100 + n, take_id: 200 + n, note: "", percent: null, minutes_left: null, credits: null, changed: false, watched: false, found: false, ...o });
const scenes = [
  { id: 1, name: "Hook", total: 2, done: 2, clips: [cell(1, 1), cell(2, 1, { state: "redone", changed: true })] },
  { id: 2, name: "The fix", total: 2, done: 1, clips: [cell(3, 2, { state: "making", frame_file_id: null }), cell(4, 2, { state: "todo", frame_file_id: null, take_id: null })] },
];
const record = (o: object = {}) => ({ run: "r9", status: "working", title: "Making the clips", sub: "3 of 4 · scene 2 of 2", tone: "now", started_at: at, ended_at: null, clips: 4, made: 3, redone: 1, scene_at: 2, scenes, counts: { all: 4, needs_you: 0, flagged: 0, redone: 1 }, minutes_left: 3, steps: [{ key: "read", state: "done", text: "Read the script", sub: "" }, { key: "takes", state: "now", text: "Making takes: 3 of 4", sub: "Clip 4 · scene 2 · 2 s · about 3 min" }, { key: "cut", state: "todo", text: "Watch and listen to the whole cut, then deliver", sub: "" }], spent: 40, up_to: 164, spent_usd: 4.1, changed: [{ clip_id: "c2", number: 2, take_id: 202, frame_file_id: 102, watched: false }], stopped: null, failed: null, ...o });
const card = item("r9", "move", "Director", "Making the clips · 3 of 4 · scene 2 of 2", "running", later, { run: "r9" });
const note = { made: "A 0:08 rant in 2 scenes.", redid: [{ at: 14, clip: "c2", text: "Clip 2: cartoon eyes landed on the stomach. Remade on Seedance 2.0." }], unsure: "The capsule holds for 1.5 s.", open: [] as string[], needs: "Nothing. It’s ready to post.", cost: "$9.84 spent of up to $16.86", spent: 96, up_to: 164, spent_usd: 9.84, cut: 2, seconds: 58, clips: 24 };

test("S3-03/04: the run is one card: its frames scene by scene, the scene being made named; Every step opens the steps", async () => {
  setViewport(1440);
  server(owner, null, run({ thread: [card] }), { "GET /projects/50/director/progress": [200, record()] });
  renderApp("/b/1/videos/50");
  const live = await screen.findByRole("region", { name: "Making the clips" });
  expect(within(live).getByText("· 3 of 4 · scene 2 of 2")).toBeInTheDocument();
  const strip = within(live).getByRole("list", { name: "The video, scene by scene" });
  expect(within(strip).getByText("The fix")).toHaveClass("text-accent-text"); // the scene being made
  expect(within(strip).getByTitle("Clip 2")).toBeInTheDocument();
  expect(within(live).queryByRole("list", { name: "Every step" })).toBeNull();
  await userEvent.click(within(live).getByRole("button", { name: "Every step" }));
  const steps = within(live).getByRole("list", { name: "Every step" });
  expect(within(steps).getByText("Clip 4 · scene 2 · 2 s · about 3 min")).toBeInTheDocument();
  expect(within(live).getByRole("button", { name: "Hide steps" })).toBeInTheDocument();
  expect(screen.queryByText("Making the clips · 3 of 4 · scene 2 of 2")).toBeNull(); // the card, not its line
});

test("S3-08: stopped by a person: who and when, what's kept, and Carry on at its price starts it again", async () => {
  setViewport(1440);
  const stopped = record({ status: "stopped", title: "Stopped", sub: "3 of 4 clips made", tone: "stop", stopped: { by: "Reed", at: "2026-11-04T10:14:00Z", made: 3, total: 4, carry_on: "$10.74" } });
  const calls = server(owner, null, run({ status: "ended", thread: [card] }), { "GET /projects/50/director/progress": [200, stopped], "POST /projects/50/director/carry-on": [201, run()] });
  renderApp("/b/1/videos/50");
  expect(await screen.findByText(/^Reed stopped the director at \d\d:\d\d\. Nothing more is being spent\.$/)).toBeInTheDocument();
  expect(screen.getByText("Stopped. The 3 finished clips are kept. Tell me what to change, or carry on where I left off.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^Make it again/ })).toBeNull(); // Carry on is the press here
  await userEvent.click(screen.getByRole("button", { name: "Carry on · up to $10.74 more" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/50/director/carry-on")).toBe(true)); // the same run, under the owner's OK
  expect(calls.some((c) => c.key === "POST /projects/50/director")).toBe(false); // not a new run
});

test("S3-08: Start the plan again starts a new run that plans the whole video again; it says why when it can't", async () => {
  setViewport(1440);
  const stopped = record({ status: "stopped", title: "Stopped", sub: "3 of 4 clips made", tone: "stop", stopped: { by: "Reed", at: "2026-11-04T10:14:00Z", made: 3, total: 4, carry_on: "$10.74" } });
  const calls = server(owner, null, run({ status: "ended", thread: [card] }), { "GET /projects/50/director/progress": [200, stopped], "POST /projects/50/director/plan-again": [201, run()] });
  const first = renderApp("/b/1/videos/50");
  await userEvent.click(await screen.findByRole("button", { name: "Start the plan again" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/50/director/plan-again")).toBe(true));
  expect(calls.some((c) => c.key === "POST /projects/50/director")).toBe(false); // not Carry on
  first.unmount();
  server(owner, null, run({ status: "ended", thread: [card] }), { "GET /projects/50/director/progress": [200, stopped], "POST /projects/50/director/plan-again": [409, { detail: "The director is already building this video." }] });
  renderApp("/b/1/videos/50");
  await userEvent.click(await screen.findByRole("button", { name: "Start the plan again" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("The director is already building this video.");
});

test("S3-11: a step that failed says why in plain words, with its one-click fixes", async () => {
  setViewport(1440);
  const failed = record({ status: "needs_fix", title: "Stopped at clip 4", sub: "3 of 4 clips made", tone: "bad", scenes: scenes.slice(0, 1), failed: { title: "Clip 4 couldn’t be made", why: "The service was busy. Nothing was charged.", clip: 44, fixes: [{ kind: "again", label: "Try again", price: "$0.32" }, { kind: "carry_on", label: "Carry on", price: "$10.74" }] } });
  const calls = server(owner, null, run({ status: "ended", thread: [card] }), { "GET /projects/50/director/progress": [200, failed], "POST /projects/50/clips/44/generate": [201, { id: 1 }], "POST /projects/50/director": [201, run()] });
  renderApp("/b/1/videos/50");
  const box = await screen.findByRole("region", { name: "Clip 4 couldn’t be made" });
  expect(within(box).getByText("The service was busy. Nothing was charged.")).toBeInTheDocument();
  await userEvent.click(within(box).getByRole("button", { name: "Try again · up to $0.32" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/50/clips/44/generate")).toBe(true));
  await userEvent.click(within(box).getByRole("button", { name: "Carry on · up to $10.74" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/50/director")).toBe(true));
});

test("S3-11: a clip too long for its model offers Split it into N clips · free, with what its new clips then cost, and the settings to pick a longer model", async () => {
  setViewport(1440);
  const problem = "clip c4: 115 s is outside 4–12 s";
  const long = record({ status: "needs_fix", title: "Stopped at clip 4", sub: "3 of 18 clips made", tone: "bad", scenes: scenes.slice(0, 1), failed: { title: "Clip 4 couldn’t be made", why: "Clip 4 runs 115 s, but Seedance 1 Lite makes at most 12 s a clip. Nothing was charged.", offer: "I can split it into 10 clips at the sentence breaks. The words don’t change, and the split itself is free.", clip: 44, fixes: [{ kind: "split", label: "Split it into 10 clips", price: "free", problem, then: "$9.80" }, { kind: "model", label: "Use a model that makes longer clips…", price: null, problem: "", then: null }] } });
  const calls = server(owner, null, run({ status: "ended", thread: [card] }), { "GET /projects/50/director/progress": [200, long], "POST /projects/50/breakdown/fix": [200, { fixed: ["Split clip 4 so the video model can make it."] }] });
  renderApp("/b/1/videos/50");
  const box = await screen.findByRole("region", { name: "Clip 4 couldn’t be made" });
  expect(within(box).getByText("I can split it into 10 clips at the sentence breaks. The words don’t change, and the split itself is free.")).toBeInTheDocument();
  expect(within(box).getByText("Its new clips are then made at their own price: up to $9.80.")).toBeInTheDocument();
  await userEvent.click(within(box).getByRole("button", { name: "Split it into 10 clips · free" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/50/breakdown/fix")?.body).toEqual({ problems: [problem] }));
  expect(calls.some((c) => c.key === "POST /projects/50/director")).toBe(false); // a split never carries on by itself
  await userEvent.click(within(box).getByRole("button", { name: "Use a model that makes longer clips…" }));
  await vi.waitFor(() => expect(screen.getByRole("tabpanel", { name: "Plan" })).toBeInTheDocument());
});

test("S3-11 on a phone: Use a model that makes longer clips opens the preview on the Plan tab, where the settings are", async () => {
  setViewport(390);
  const long = record({ status: "needs_fix", title: "Stopped at clip 4", sub: "3 of 18 clips made", tone: "bad", scenes: scenes.slice(0, 1), failed: { title: "Clip 4 couldn’t be made", why: "Clip 4 runs 115 s, but Seedance 1 Lite makes at most 12 s a clip. Nothing was charged.", offer: "One of its sentences is too long to split. Make its shot shorter, or use a model that makes longer clips.", clip: 44, fixes: [{ kind: "model", label: "Use a model that makes longer clips…", price: null, problem: "", then: null }, { kind: "carry_on", label: "Carry on", price: "$10.74", problem: "", then: null }] } });
  server(owner, null, run({ status: "ended", thread: [card] }), { "GET /projects/50/director/progress": [200, long] });
  renderApp("/b/1/videos/50");
  const box = await screen.findByRole("region", { name: "Clip 4 couldn’t be made" });
  await userEvent.click(within(box).getByRole("button", { name: "Use a model that makes longer clips…" }));
  const sides = screen.getByRole("tablist", { name: "Chat or preview" });
  expect(within(sides).getByRole("tab", { name: "Preview", selected: true })).toBeInTheDocument();
  expect(within(screen.getByRole("tablist", { name: "Preview" })).getByRole("tab", { name: "Plan", selected: true })).toBeInTheDocument();
});

test("S3-09: delivered: the note in parts with the times it redid, the real cost; Watch the changes marks them seen and opens the cut; an earlier cut's note folds to a line", async () => {
  setViewport(1440);
  const done = record({ status: "delivered", title: "Made in 22 min", sub: "4 clips · 1 redone after watching", tone: "done" });
  const old = { ...note, cut: 1, spent_usd: 9.1 };
  const thread = [item("t1", "move", "Director", "…", "done", at, { note: old }), card, item("t2", "move", "Director", "…", "done", later, { note })];
  const calls = server(owner, null, run({ status: "delivered", thread }), { "GET /projects/50/director/progress": [200, done], "POST /projects/50/director/seen": [204, null], "GET /projects/50/video": [200, { file_id: 8, take_ids: [], out_of_date: false }] });
  renderApp("/b/1/videos/50?tab=plan");
  const n = await screen.findByRole("region", { name: "Delivery note" });
  expect(within(n).getByText("A 0:08 rant in 2 scenes.")).toBeInTheDocument();
  expect(within(n).getByText("0:14")).toBeInTheDocument();
  expect(within(n).getByText("Clip 2: cartoon eyes landed on the stomach. Remade on Seedance 2.0.")).toBeInTheDocument();
  expect(within(n).getByText("The capsule holds for 1.5 s.")).toBeInTheDocument();
  expect(within(n).getByRole("heading", { name: "What remains uncertain" })).toBeInTheDocument(); // Reed's three parts (5 Nov)
  expect(within(n).getAllByRole("heading", { level: 4 }).map((h) => h.textContent)).toEqual(["What I made", "What I watched and redid", "What remains uncertain", "What I need from you"]); // its rows their own part (board S3-09, S5)
  expect(within(within(n).getByRole("list", { name: "What I watched and redid" })).getByText("0:14")).toBeInTheDocument();
  expect(within(n).getByText("Nothing. It’s ready to post.")).toBeInTheDocument(); // the server's words: ready only when nothing is open
  expect(within(n).getByText("$9.84 spent of up to $16.86")).toBeInTheDocument();
  expect(screen.getByText("Delivery note · Cut 1 · 0:58 · $9.10")).toBeInTheDocument(); // S3-12: the earlier cut, folded
  expect(screen.getByText("Here’s the cut.")).toBeInTheDocument();
  await userEvent.click(within(n).getByRole("button", { name: "Watch the changes" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/50/director/seen")?.body).toEqual({ take_ids: [202] }));
  expect(screen.getByRole("tab", { name: "Cut", selected: true })).toBeInTheDocument();
  const cut = screen.getByRole("tabpanel", { name: "Cut" });
  expect(await within(cut).findByRole("button", { name: "Clip 2, not watched yet" })).toBeInTheDocument(); // Changed after watching, outlined until watched
  await userEvent.click(within(within(cut).getByRole("list", { name: "The video, scene by scene" })).getByRole("button", { name: "Clip 1" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /projects/50/director/seen").map((c) => c.body)).toContainEqual({ take_ids: [201] })); // a frame played is watched
});

test("S3-09: what the server knows is still open goes under What remains uncertain, and the note isn't ready to post", async () => {
  setViewport(390);
  const open = { ...note, unsure: "", open: ["The cut wasn't watched.", "Clip 3's take wasn't checked."], needs: "Nothing yet, but look at what remains uncertain before you post it." };
  const thread = [item("t2", "move", "Director", "…", "done", later, { note: open })];
  server(owner, null, run({ status: "delivered", thread }), { "GET /projects/50/director/progress": [200, record({ status: "delivered", title: "Made in 22 min", sub: "4 clips", tone: "done" })], "GET /projects/50/video": [200, { file_id: 8, take_ids: [], out_of_date: false }] });
  renderApp("/b/1/videos/50");
  const n = await screen.findByRole("region", { name: "Delivery note" });
  expect(within(n).getByRole("heading", { name: "What remains uncertain" })).toBeInTheDocument();
  expect(within(n).getByText("The cut wasn't watched.")).toBeInTheDocument();
  expect(within(n).getByText("Clip 3's take wasn't checked.")).toBeInTheDocument();
  expect(within(n).getByText("Nothing yet, but look at what remains uncertain before you post it.")).toBeInTheDocument();
  expect(n.textContent).not.toMatch(/ready to post/);
});

test("S3-13: a long video reads a row a scene with its count, eight at most, and how long is left", async () => {
  setViewport(1440);
  const many = Array.from({ length: 10 }, (_, i) => ({ id: i + 1, name: `Scene ${i + 1}`, total: 12, done: i < 4 ? 12 : 0, clips: Array.from({ length: 12 }, (_, j) => cell(i * 12 + j + 1, i + 1)) }));
  server(owner, null, run({ thread: [card] }), { "GET /projects/50/director/progress": [200, record({ clips: 120, made: 48, scenes: many, sub: "48 of 120 · scene 5 of 10", minutes_left: 130 })] });
  renderApp("/b/1/videos/50");
  const live = await screen.findByRole("region", { name: "Making the clips" });
  const rows = within(live).getByRole("list", { name: "Scenes" });
  expect(within(rows).getAllByRole("listitem")).toHaveLength(8);
  expect(within(rows).getAllByText("12/12")).toHaveLength(4);
  expect(within(live).getByText("+ 2 more scenes · about 2 h 10 min left")).toBeInTheDocument();
  expect(within(live).queryByRole("list", { name: "The video, scene by scene" })).toBeNull();
});

test("P-04: on a phone the card shows one frame a scene with its count, and the steps fold under a chevron", async () => {
  setViewport(390);
  server(owner, null, run({ thread: [card] }), { "GET /projects/50/director/progress": [200, record()] });
  renderApp("/b/1/videos/50");
  const live = await screen.findByRole("region", { name: "Making the clips" });
  expect(within(live).getByText("3 of 4 · scene 2 of 2 · 1 redone after watching")).toBeInTheDocument();
  expect(within(live).getByText("2/2")).toBeInTheDocument();
  expect(within(live).getByText("1/2")).toBeInTheDocument();
  await userEvent.click(within(live).getByRole("button", { name: "Every step" }));
  expect(within(live).getByRole("list", { name: "Every step" })).toBeInTheDocument();
});

test("Try again can't be pressed twice: while its clip is made the press waits, and a stop with nothing made says so", async () => {
  setViewport(1440);
  const failed = { title: "Clip 4 couldn’t be made", why: "Busy.", clip: 44, fixes: [{ kind: "again", label: "Try again", price: "$0.32" }] };
  server(owner, null, run({ status: "ended", thread: [card] }), { "GET /projects/50/director/progress": [200, record({ status: "needs_fix", title: "Stopped at clip 4", tone: "bad", failed })] });
  const first = renderApp("/b/1/videos/50");
  expect(await screen.findByRole("button", { name: "Try again · up to $0.32" })).toHaveAttribute("aria-busy", "true"); // clip 3 of the record is still being made: a press does nothing
  first.unmount();
  server(owner, null, run({ status: "ended", thread: [card] }), { "GET /projects/50/director/progress": [200, record({ status: "stopped", title: "Stopped", tone: "stop", stopped: { by: "Reed", at, made: 0, total: 4, carry_on: "$10.74" } })] });
  renderApp("/b/1/videos/50");
  expect(await screen.findByText("Stopped. Nothing was finished yet. Tell me what to change, or carry on where I left off.")).toBeInTheDocument();
});

test("rule 22: with no stills or clips yet, the Clips tab points to the chat; on a phone it goes there", async () => {
  setViewport(390);
  server(owner, null, run({ status: "none", turns: [] }), { "GET /projects/50/assets": [200, []], "GET /projects/50/script": [200, { version: 1, source: "paste", words: 2, created_by_id: 1, created_at: at, text: "Bo." }], "GET /projects/50/breakdown": [200, { id: 1, script_version: 1, source: "claude", stale: false, problems: [], breakdown: { hook: "", scenes: [{ id: 1, heading: "K", look: "", shots: [] }], clips: [] } }] });
  renderApp("/b/1/videos/50?tab=clips");
  await userEvent.click(await screen.findByRole("button", { name: "Start it or tell it what to do in the chat." }));
  expect(screen.getByRole("tab", { name: "Chat", selected: true })).toBeInTheDocument();
});

// Screen 5: the director's cards (piece B, #1313): questions, story choices, the start-of-run and budget OKs, the pinned bar.
const price = (credits: number, usd: number | null = null) => ({ credits, usd });
const ask = (o: object = {}) => ({ id: 7, project_id: 50, kind: "presenter", topic: "The presenter", question: "Who should be the presenter?", why: "He talks to camera the whole time.", state: "open", by_owner: false, saved_in: "Saved in Resilia", saved: [{ id: "item:1", name: "Mark", note: "UGC", file_id: 31, used_in: 6 }, { id: "item:2", name: "Dana", note: "UGC", file_id: 32, used_in: 2 }], pick: "item:1", choices: [], decide_at: null, generate: price(3, 0.24), clone: null, options: [], options_spent: null, answer: null, answered_by: "", answered_at: null, closed: "", money: null, can: ["reply", "saved", "upload", "generate"], created_at: at, ...o });
const asked = (id = 7) => item(`a${id}`, "move", "Director", "Who should be the presenter?", null, later, { kind: "ask", ask_id: id });
const cards = (...a: object[]) => ({ "GET /projects/50/asks": [200, a] as [number, unknown] });
const held$ = (o: object = {}) => ({ up_to: price(140, 14.4), spent: null, budget: null, past: null, usual: price(97, 10), clips: [], sent_at: later, held: "", ...o });

test("S4-01/S3-05: a question shows the brand's saved items first, its pick outlined; Use sends that pick; the pinned bar shows it", async () => {
  setViewport(1440);
  const calls = server(owner, null, run({ thread: [asked()], waiting: [{ id: 7, topic: "The presenter", question: "Who should be the presenter?" }] }), { ...cards(ask()), "POST /asks/7/answer": [200, ask({ state: "answered" })] });
  renderApp("/b/1/videos/50");
  const card = await screen.findByRole("region", { name: "Who should be the presenter?" });
  expect(within(card).getByText("The director needs you")).toBeInTheDocument();
  expect(within(card).getByRole("button", { name: /^Mark/ })).toHaveAttribute("aria-pressed", "true");
  expect(within(card).getByText("3 avatars · up to $0.24 · this video only")).toBeInTheDocument();
  expect(screen.getByText("1 question waiting · The presenter")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Show" })).toBeInTheDocument();
  await userEvent.click(within(card).getByRole("button", { name: /^Dana/ }));
  await userEvent.click(within(card).getByRole("button", { name: "Use Dana" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /asks/7/answer")?.body).toEqual({ how: "saved", option: "item:2" }));
});

test("S3-05: once a question is answered, the pinned bar goes at once, with no reload", async () => {
  setViewport(1440);
  const r = run({ status: "ended", thread: [asked()], waiting: [{ id: 7, topic: "The presenter", question: "Who should be the presenter?" }] });
  const open = ask();
  server(owner, null, r, { ...cards(open), "POST /asks/7/answer": [200, ask({ state: "answered" })] });
  renderApp("/b/1/videos/50");
  const card = await screen.findByRole("region", { name: "Who should be the presenter?" });
  expect(screen.getByText("1 question waiting · The presenter")).toBeInTheDocument();
  Object.assign(r, { waiting: [] }); // the server's answer: nothing waits now
  Object.assign(open, { state: "answered" });
  await userEvent.click(within(card).getByRole("button", { name: "Use Mark" }));
  await vi.waitFor(() => expect(screen.queryByText(/question waiting/)).toBeNull(), { timeout: 2_000 });
});

test("S3-05: a question answered somewhere else (Needs you, the director's own pick) leaves the pinned bar once the cards are read again", async () => {
  setViewport(1440);
  const r = run({ status: "ended", thread: [asked()], waiting: [{ id: 7, topic: "The presenter", question: "Who should be the presenter?" }] });
  const open = ask();
  const calls = server(owner, null, r, cards(open));
  renderApp("/b/1/videos/50");
  await screen.findByRole("region", { name: "Who should be the presenter?" });
  expect(screen.getByText("1 question waiting · The presenter")).toBeInTheDocument();
  Object.assign(open, { state: "answered" }); // answered in Needs you; the run's own list is read again after
  await vi.waitFor(() => expect(screen.queryByText(/question waiting/)).toBeNull(), { timeout: 6_000 });
  expect(calls.filter((c) => c.key === "GET /projects/50/director").length).toBeGreaterThan(1); // the run, read again
}, 10_000);

test("S4-01: Reply answers in words; Generate options starts a priced round", async () => {
  setViewport(1440);
  const calls = server(owner, null, run({ thread: [asked()] }), { ...cards(ask()), "POST /asks/7/answer": [200, ask()], "POST /asks/7/generate": [200, ask({ state: "generating" })] });
  renderApp("/b/1/videos/50");
  const card = await screen.findByRole("region", { name: "Who should be the presenter?" });
  await userEvent.click(within(card).getByRole("button", { name: /^Reply/ }));
  await userEvent.type(within(card).getByLabelText("Your answer"), "Someone older, tired");
  await userEvent.click(within(card).getByRole("button", { name: "Send the answer" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /asks/7/answer")?.body).toEqual({ how: "reply", text: "Someone older, tired" }));
  await userEvent.click(within(card).getByRole("button", { name: /^Generate options/ }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /asks/7/generate")).toBe(true));
});

test("S4-03: generating shows its price and Cancel; options ready: Use option, More like it, Change something…, what's spent", async () => {
  setViewport(1440);
  const drawing = ask({ state: "generating", options: [0, 1, 2].map((index) => ({ index, state: "running", file_id: null })), can: ["reply", "saved", "upload", "cancel"] });
  const first = server(owner, null, run({ thread: [asked()] }), { ...cards(drawing), "POST /asks/7/cancel": [200, ask()] });
  const a = renderApp("/b/1/videos/50");
  const card = await screen.findByRole("region", { name: "Who should be the presenter?" });
  expect(within(card).getByText("Drawing 3 avatars · up to $0.24")).toBeInTheDocument();
  expect(within(card).getAllByText("drawing…")).toHaveLength(3);
  await userEvent.click(within(card).getByRole("button", { name: "Cancel" }));
  await vi.waitFor(() => expect(first.some((c) => c.key === "POST /asks/7/cancel")).toBe(true));
  a.unmount();
  const ready = ask({ state: "ready", options: [0, 1, 2].map((index) => ({ index, state: "succeeded", file_id: 40 + index })), options_spent: price(3, 0.18), can: ["reply", "saved", "upload", "generate", "option"] });
  const calls = server(owner, null, run({ thread: [asked()] }), { ...cards(ready), "POST /asks/7/answer": [200, ask({ state: "answered" })], "POST /asks/7/generate": [200, ready] });
  renderApp("/b/1/videos/50");
  const r = await screen.findByRole("region", { name: "Who should be the presenter?" });
  expect(within(r).getByText("Made for this video · not saved to the brand")).toBeInTheDocument();
  expect(within(r).getByText("$0.18 spent")).toBeInTheDocument();
  expect(within(r).getByRole("button", { name: /^Option 1/ })).toHaveAttribute("aria-pressed", "true"); // the first, as drawn
  await userEvent.click(within(r).getByRole("button", { name: /^Option 2/ }));
  await userEvent.click(within(r).getByRole("button", { name: "More like 2 · up to $0.24" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /asks/7/generate")?.body).toEqual({ like: 1 }));
  await userEvent.click(within(r).getByRole("button", { name: "Use option 2" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /asks/7/answer")?.body).toEqual({ how: "option", option: 1 }));
});

test("S4-03: a failed round says nothing was charged, with Try again and Upload instead; answered folds and can change; not needed says why", async () => {
  setViewport(1440);
  server(owner, null, run({ thread: [asked(), asked(8), asked(9)] }), cards(
    ask({ state: "failed", options: [{ index: 0, state: "failed", file_id: null }] }),
    ask({ id: 8, state: "answered", topic: "Husband", question: "Who plays the husband?", answer: { how: "saved", name: "Mark", file_id: 31 }, answered_by: "Reed", answered_at: later }),
    ask({ id: 9, state: "not_needed", question: "Which kitchen?", closed: "You locked the cast to Mark, who comes with his kitchen, so I used that.", can: [] }),
  ));
  renderApp("/b/1/videos/50");
  const failed = await screen.findByRole("region", { name: "Who should be the presenter?" });
  expect(within(failed).getByText("The picture service made nothing. Nothing was charged.")).toBeInTheDocument();
  expect(within(failed).getByRole("button", { name: "Try again · up to $0.24" })).toBeInTheDocument();
  expect(within(failed).getByRole("button", { name: "Upload instead" })).toBeInTheDocument();
  const done = screen.getByRole("region", { name: "Who plays the husband?" });
  expect(within(done).getByText("Husband: Mark")).toBeInTheDocument();
  expect(within(done).getByText(/picked by Reed, \d\d:\d\d/)).toBeInTheDocument();
  await userEvent.click(within(done).getByRole("button", { name: "Change" }));
  expect(within(screen.getByRole("region", { name: "Who plays the husband?" })).getByText("Saved in Resilia")).toBeInTheDocument();
  expect(within(screen.getByRole("region", { name: "Which kitchen?" })).getByText(/You locked the cast to Mark/)).toBeInTheDocument();
});

test("S4-02: a story choice shows its pick and why, Go with A or B, and when it goes with its pick", async () => {
  setViewport(1440);
  const story = ask({ kind: "story", topic: "How it ends", question: "How should it end?", saved: [], saved_in: "", generate: null, pick: "A", decide_at: "2026-11-04T11:00:00Z", choices: [{ key: "A", title: "He bins the pint", why: "Clear before and after." }, { key: "B", title: "He toasts the camera", why: "Funnier." }], can: ["reply", "choice"] });
  const calls = server(owner, null, run({ thread: [asked()] }), { ...cards(story), "POST /asks/7/answer": [200, story] });
  renderApp("/b/1/videos/50");
  const card = await screen.findByRole("region", { name: "How should it end?" });
  expect(within(card).getByText("A · my pick")).toBeInTheDocument();
  expect(within(card).getByText(/^I’ll go with A at \d\d:\d\d if I don’t hear back$/)).toBeInTheDocument();
  await userEvent.click(within(card).getByRole("button", { name: "Go with B" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /asks/7/answer")?.body).toEqual({ how: "choice", choice: "B" }));
});

test("S3-02: the start-of-run card: Make it · up to its price, Change the plan first opens the box; the general Make it stands aside", async () => {
  setViewport(1440);
  const start = ask({ kind: "start", topic: "", question: "Make it for up to $14.40?", why: "That's the most this run can charge.", saved: [], money: held$(), can: ["make_it"] });
  const calls = server(owner, null, run({ status: "ended", turns: [], make_it: 7, run_price: 140, thread: [asked()] }), { ...cards(start), "POST /asks/7/answer": [200, start] });
  renderApp("/b/1/videos/50");
  const card = await screen.findByRole("region", { name: "Make it for up to $14.40?" });
  expect(within(card).getByText("Ready to start")).toBeInTheDocument();
  expect(within(card).getByText("No generation starts until you press.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^Make it again/ })).toBeNull();
  await userEvent.click(within(card).getByRole("button", { name: "Change the plan first" }));
  expect(screen.getByLabelText("Tell the director what to change")).toHaveFocus();
  await userEvent.click(within(card).getByRole("button", { name: "Make it · up to $14.40" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /asks/7/answer")?.body).toEqual({ how: "make_it" }));
});

test("rule 34: past a later run's own price, the owner's card says so in its header; the editor's waits for the owner", async () => {
  setViewport(1440);
  const later = (o: object) => ask({ kind: "budget", question: "Redo clip 2? That goes $0.60 past the $2.50 approved for this run.", why: "Redoing it takes this run to up to $3.10 ($2.20 spent in this run plus up to $0.90); this run's approved price is $2.50.", saved: [], money: held$({ up_to: price(9, 0.9), over: "the $2.50 approved for this run", clips: [{ clip: "2", still_file_id: 51 }] }), ...o });
  const r = (server(owner, null, run({ thread: [asked()] }), cards(later({ can: ["approve", "keep"] }))), renderApp("/b/1/videos/50"));
  const mine = await screen.findByRole("region", { name: "Redo clip 2? That goes $0.60 past the $2.50 approved for this run." });
  expect(within(mine).getByText("Past this run’s price · needs your OK")).toBeInTheDocument();
  r.unmount();
  server(editor, null, run({ thread: [asked()] }), cards(later({ state: "held", question: "Redo clip 2? That goes 6 credits past the 25 credits approved for this run.", why: "The owner has been asked; nothing is charged while it waits.", can: ["withdraw"] })));
  renderApp("/b/1/videos/50");
  const theirs = await screen.findByRole("region", { name: "Redo clip 2? That goes 6 credits past the 25 credits approved for this run." });
  expect(within(theirs).getByText("Waiting for the owner’s OK")).toBeInTheDocument();
});

test("S3-06: past the budget, the owner approves the most it adds, or keeps the cut", async () => {
  setViewport(1440);
  const budget = ask({ kind: "budget", question: "Redo clips 9 and 12? That goes $1.54 past the budget.", why: "$16.30 spent plus up to $2.10 makes up to $18.40; the budget is $16.86.", saved: [], money: held$({ up_to: price(21, 2.1), clips: [{ clip: "9", still_file_id: 51 }, { clip: "12", still_file_id: 52 }] }), can: ["approve", "keep"] });
  const calls = server(owner, null, run({ thread: [asked()] }), { ...cards(budget), "POST /asks/7/answer": [200, budget] });
  renderApp("/b/1/videos/50");
  const card = await screen.findByRole("region", { name: "Redo clips 9 and 12? That goes $1.54 past the budget." });
  expect(within(card).getByText("Past the budget · needs your OK")).toBeInTheDocument();
  expect(within(card).getByText("Clip 9 · Clip 12")).toBeInTheDocument();
  await userEvent.click(within(card).getByRole("button", { name: "Keep the cut as it is" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /asks/7/answer")?.body).toEqual({ how: "keep" }));
  await userEvent.click(within(card).getByRole("button", { name: "Approve · up to $2.10 more" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /asks/7/answer").map((c) => c.body)).toContainEqual({ how: "approve" }));
});

test("S3-07/P-07: an editor's held request waits for the owner in credits, never names them, and can be withdrawn", async () => {
  setViewport(390);
  const held = ask({ kind: "budget", question: "Redo clips 9 and 12? That goes 15 credits past the budget.", why: "The owner has been asked; nothing is charged while it waits.", saved: [], money: held$({ up_to: price(21) }), can: ["withdraw"] });
  const calls = server(editor, null, run({ thread: [asked()] }), { ...cards(held), "GET /projects/50": [200, { ...project, freestyle_id: null, created_by_id: 2 }], "POST /asks/7/answer": [200, held] });
  renderApp("/b/1/videos/50");
  const card = await screen.findByRole("region", { name: "Redo clips 9 and 12? That goes 15 credits past the budget." });
  expect(within(card).getByText("Waiting for the owner’s OK")).toBeInTheDocument();
  expect(within(card).getByText(/^Sent \d\d:\d\d · you’ll see the answer here$/)).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/\$\d|ask (Reed|the owner)|Reed/);
  await userEvent.click(within(card).getByRole("button", { name: "Withdraw the request" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /asks/7/answer")?.body).toEqual({ how: "withdraw" }));
});

test("an editor's send on a freestyle withdraws through the freestyle (so its send is let go too)", async () => {
  setViewport(1440);
  const held = ask({ kind: "start", question: "Make it for up to 140 credits?", saved: [], money: held$({ up_to: price(140) }), can: ["withdraw"] });
  const sent = fs({ status: "waiting", created_by_name: "Eli", thread: [item("m1", "message", "Eli", SCRIPT)] });
  const calls = server(editor, sent, run({ thread: [asked()] }), { ...cards(held), "GET /projects/50": [200, { ...project, created_by_id: 2 }], "POST /freestyles/9/withdraw": [200, { ...sent, status: "withdrawn" }] });
  renderApp("/b/1/videos/50");
  const card = await screen.findByRole("region", { name: "Make it for up to 140 credits?" });
  const before = calls.filter((c) => c.key === "GET /projects/50/asks").length;
  await userEvent.click(within(card).getByRole("button", { name: "Withdraw the request" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /freestyles/9/withdraw")).toBe(true));
  expect(calls.some((c) => c.key === "POST /asks/7/answer")).toBe(false);
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "GET /projects/50/asks").length).toBeGreaterThan(before)); // the card reads again
});

test("on a freestyle, a held budget card withdraws itself, not the freestyle's send", async () => {
  setViewport(1440);
  const held = ask({ kind: "budget", question: "Redo clip 2? That goes 12 credits past the budget.", saved: [], money: held$({ up_to: price(21) }), can: ["withdraw"] });
  const calls = server(editor, fs({ created_by_name: "Eli" }), run({ thread: [asked()] }), { ...cards(held), "GET /projects/50": [200, { ...project, created_by_id: 2 }], "POST /asks/7/answer": [200, held] });
  renderApp("/b/1/videos/50");
  const card = await screen.findByRole("region", { name: "Redo clip 2? That goes 12 credits past the budget." });
  await userEvent.click(within(card).getByRole("button", { name: "Withdraw the request" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /asks/7/answer")?.body).toEqual({ how: "withdraw" }));
  expect(calls.some((c) => c.key === "POST /freestyles/9/withdraw")).toBe(false);
});

test("a voice card's clone: cloning and held say the clone's price and where it goes; held has Withdraw; a failed clone keeps the voices", async () => {
  setViewport(1440);
  const voice = (o: object) => ask({ kind: "voice", question: "Which voice should Mark have?", saved: [{ id: "stock:roger", name: "Roger", note: "", file_id: null, used_in: 0 }], pick: null, generate: null, clone: price(30, 3), ...o });
  const a = server(editor, null, run({ thread: [asked()] }), cards(voice({ state: "generating", clone: price(30), can: ["reply", "saved", "clone", "cancel"] })));
  const r1 = renderApp("/b/1/videos/50");
  const cloning = await screen.findByRole("region", { name: "Which voice should Mark have?" });
  expect(within(cloning).getByText("Cloning the voice · up to 30 credits")).toBeInTheDocument();
  expect(within(cloning).queryByRole("button", { name: "Cancel" })).toBeNull();
  expect(a.length).toBeGreaterThan(0);
  r1.unmount();
  const opened = voice({ state: "open", can: ["reply", "saved", "clone"] });
  const b = server(editor, null, run({ thread: [asked()] }), { ...cards(voice({ state: "held", clone: price(30), can: ["reply", "saved", "upload", "clone", "cancel"] })), "POST /asks/7/cancel": [200, opened] });
  const r2 = renderApp("/b/1/videos/50");
  const held = await screen.findByRole("region", { name: "Which voice should Mark have?" });
  expect(within(held).getByText("You asked to clone this voice (up to 30 credits, saved to Resilia’s voices). The owner has been asked; nothing is charged while it waits.")).toBeInTheDocument();
  expect(within(held).queryByRole("button", { name: "Upload instead" })).toBeNull(); // an upload wouldn't stop the clone waiting
  await userEvent.click(within(held).getByRole("button", { name: "Withdraw" })); // flow.md: the editor withdraws it on the card
  await vi.waitFor(() => expect(b.some((c) => c.key === "POST /asks/7/cancel")).toBe(true));
  r2.unmount();
  const r3 = (server(editor, null, run({ thread: [asked()] }), cards(voice({ state: "failed", answer: { how: "clone", option: "voice:4", name: "Nate", withdrawn: true }, can: ["reply", "saved", "clone"] }))), renderApp("/b/1/videos/50"));
  const reused = await screen.findByRole("region", { name: "Which voice should Mark have?" }); // it reused a clone its asker withdrew
  expect(within(reused).getByText("The clone this card used was withdrawn before it was made. Nothing was charged.")).toBeInTheDocument();
  expect(within(reused).getByRole("button", { name: /Clone it once/ })).toBeInTheDocument();
  r3.unmount();
  server(owner, null, run({ thread: [asked()] }), cards(voice({ state: "failed", clone_to: "Saved to Resilia's voices", can: ["reply", "saved", "clone"] })));
  renderApp("/b/1/videos/50");
  const failed = await screen.findByRole("region", { name: "Which voice should Mark have?" });
  expect(within(failed).getByText("The voice didn’t clone. Nothing was charged.")).toBeInTheDocument();
  expect(within(failed).getByRole("button", { name: /^Roger/ })).toBeInTheDocument();
  expect(within(failed).getByRole("button", { name: /Clone it once · saved to Resilia's voices · up to \$3\.00/ })).toBeInTheDocument();
});

test("a voice answered with a clone that was already in the brand says so, and that nothing was charged", async () => {
  setViewport(1440);
  const done = ask({ kind: "voice", topic: "Mark's voice", question: "Which voice should Mark have?", state: "answered", answer: { how: "clone", option: "voice:4", name: "Dr. Pickle", reused: true }, answered_by: "Reed", answered_at: later, can: [] });
  server(owner, null, run({ thread: [asked()] }), cards(done));
  renderApp("/b/1/videos/50");
  const card = await screen.findByRole("region", { name: "Which voice should Mark have?" });
  expect(within(card).getByText("Using Dr. Pickle, already in Resilia’s voices. Nothing was charged.")).toBeInTheDocument();
});

test("a failed picture round shows only what went wrong and the two ways on (S4-03)", async () => {
  setViewport(1440);
  server(owner, null, run({ thread: [asked()] }), cards(ask({ state: "failed", options: [{ index: 0, state: "failed", file_id: null }] })));
  renderApp("/b/1/videos/50");
  const card = await screen.findByRole("region", { name: "Who should be the presenter?" });
  expect(within(card).queryByRole("button", { name: /^Mark/ })).toBeNull();
  expect(within(card).queryByText(/didn’t draw/)).toBeNull();
});

test("while the first move runs the header reads Working, not the server's lagging Needs you · Start it", async () => {
  setViewport(1440);
  server(owner, null, run({ turns: [{ turn: 0, tool: null, why: "", result: "", status: "running", created_at: at }] }), { "GET /projects/50/idea": [200, head({ status: status("needs_you", "Needs you", "Start it") })] });
  renderApp("/b/1/videos/50");
  expect(await within(await screen.findByRole("banner")).findByText("Working · starting")).toBeInTheDocument();
});

test("P-06: on a phone the card fits, and two questions read Next on the pinned bar", async () => {
  setViewport(390);
  const second = ask({ id: 8, topic: "How it ends", question: "How should it end?" });
  server(owner, null, run({ thread: [asked(), asked(8)], waiting: [{ id: 7, topic: "The presenter", question: "" }, { id: 8, topic: "How it ends", question: "" }] }), cards(ask(), second));
  renderApp("/b/1/videos/50");
  expect(await screen.findByText("2 questions waiting")).toBeInTheDocument(); // the count only on a phone
  expect(screen.getByRole("button", { name: "Next" })).toBeInTheDocument();
});

test("S4-03: an editor's Generate options past their allowance waits for the owner, with Withdraw and Upload instead", async () => {
  setViewport(1440);
  const held = ask({ state: "held", generate: price(3), can: ["reply", "saved", "upload", "generate", "cancel"] });
  const calls = server(editor, null, run({ thread: [asked()] }), { ...cards(held), "POST /asks/7/cancel": [200, ask()] });
  renderApp("/b/1/videos/50");
  const card = await screen.findByRole("region", { name: "Who should be the presenter?" });
  expect(within(card).getByText("Waiting for the owner’s OK")).toBeInTheDocument();
  expect(within(card).getByText("You asked for 3 generated avatars (up to 3 credits). The owner has been asked; nothing is charged while it waits.")).toBeInTheDocument();
  expect(within(card).getByRole("button", { name: "Upload instead" })).toBeInTheDocument();
  expect(within(card).queryByRole("button", { name: /^Mark/ })).toBeNull();
  await userEvent.click(within(card).getByRole("button", { name: "Withdraw" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /asks/7/cancel")).toBe(true));
});

test("S3-07: an editor's send, held before its video has cards, is the same held card in credits, with Withdraw the request", async () => {
  setViewport(390);
  const sent = fs({ status: "waiting", created_by_name: "Eli", thread: [item("m1", "message", "Eli", SCRIPT), item("h1", "move", "Director", "Waiting for the owner's OK", "held")] });
  const calls = server(editor, sent, run({ status: "ended", turns: [] }), { "GET /projects/50": [200, { ...project, created_by_id: 2 }], "POST /freestyles/9/withdraw": [200, { ...sent, status: "withdrawn" }] });
  renderApp("/b/1/videos/50");
  const card = await screen.findByRole("region", { name: "Make it for up to 164 credits?" });
  expect(within(card).getByText("Waiting for the owner’s OK")).toBeInTheDocument();
  expect(within(card).getByText("The owner has been asked. No generation starts until they say yes.")).toBeInTheDocument();
  await userEvent.click(within(card).getByRole("button", { name: "Withdraw the request" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /freestyles/9/withdraw")).toBe(true));
});

test("S3-07: an editor's change after a delivery waits with its own price from its held job, never up to free", async () => {
  setViewport(1440);
  const sent = fs({ status: "waiting", file_id: 88, created_by_name: "Eli", thread: [item("m1", "message", "Eli", SCRIPT), item("h1", "move", "Director", "Punchier ending.", "held", later)] });
  const job = { id: 31, status: "needs_owner_approval", project_id: 50, credits: 4, kind: "director", created_at: later, freestyle: { id: 9, change: true, up_to: 23 } };
  server(editor, sent, run({ status: "delivered", turns: [], run_price: 0 }), { "GET /projects/50": [200, { ...project, created_by_id: 2 }], "GET /jobs": [200, [job]] });
  renderApp("/b/1/videos/50");
  const card = await screen.findByRole("region", { name: "Make this change for up to 23 credits?" });
  expect(within(card).getByText("The owner has been asked. The cut stays as it is; no generation starts until they say yes.")).toBeInTheDocument();
  expect(within(card).getByRole("button", { name: "Withdraw the request" })).toBeInTheDocument();
});

test("S4-01: a voice card plays its samples free; Clone it once says it's saved to the brand's voices before its price", async () => {
  setViewport(1440);
  const voice = ask({ kind: "voice", topic: "Mark's voice", question: "Which voice should Mark have?", saved: [{ id: "stock:roger", name: "Roger", note: "Relaxed, mid", file_id: null, used_in: 3, sample_url: "/voices/sample/roger.mp3" }], pick: "stock:roger", generate: null, clone: price(30, 3), can: ["describe", "saved", "clone"] });
  server(owner, null, run({ thread: [asked()] }), cards(voice));
  renderApp("/b/1/videos/50");
  const card = await screen.findByRole("region", { name: "Which voice should Mark have?" });
  expect(within(card).getByRole("button", { name: "Play Roger's sample" })).toBeInTheDocument();
  expect(within(card).getByRole("button", { name: /Clone it once · saved to Resilia’s voices · up to \$3\.00/ })).toBeInTheDocument();
  expect(within(card).getByRole("button", { name: /^Describe it/ })).toBeInTheDocument();
  expect(within(card).getByRole("button", { name: "Use Roger" })).toBeInTheDocument();
});

test("S4-01: Describe it saves a voice to the brand from words, read free in the nearest app voice", async () => {
  setViewport(1440);
  const voice = ask({ kind: "voice", topic: "Mark's voice", question: "Which voice should Mark have?", saved: [], pick: null, generate: null, clone: price(30, 3), can: ["describe", "clone"] });
  const done = { ...voice, state: "answered", answer: { how: "describe", option: "voice:9", name: "Dana", text: "late 40s, tired, warm", uses: "Graceful Lady" }, answered_by: "Reed", answered_at: later, can: ["describe", "clone"] };
  const calls = server(owner, null, run({ thread: [asked()] }), { ...cards(voice), "POST /asks/7/answer": [200, done] });
  renderApp("/b/1/videos/50");
  const card = await screen.findByRole("region", { name: "Which voice should Mark have?" });
  await userEvent.click(within(card).getByRole("button", { name: /^Describe it/ }));
  await userEvent.type(within(card).getByRole("textbox", { name: "What the voice sounds like" }), "late 40s, tired, warm");
  await userEvent.type(within(card).getByRole("textbox", { name: "Its name (optional)" }), "Dana");
  expect(within(card).getByText("The nearest app voice reads it, free. It’s saved to Resilia’s voices to use again.")).toBeInTheDocument();
  await userEvent.click(within(card).getByRole("button", { name: "Save and use it" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /asks/7/answer")?.body).toEqual({ how: "describe", text: "late 40s, tired, warm", name: "Dana" }));
});

test("S4-01: a card answered by a description says what was saved and which app voice reads it", async () => {
  setViewport(1440);
  const done = ask({ kind: "voice", topic: "Mark's voice", question: "Which voice should Mark have?", saved: [], pick: null, generate: null, state: "answered", answer: { how: "describe", option: "voice:9", name: "Dana", text: "late 40s, tired, warm", uses: "Graceful Lady" }, answered_by: "Reed", answered_at: later, can: ["describe"] });
  server(owner, null, run({ thread: [asked()] }), cards(done));
  renderApp("/b/1/videos/50");
  const card = await screen.findByRole("region", { name: "Which voice should Mark have?" });
  expect(within(card).getByText("Mark's voice: Dana")).toBeInTheDocument();
  expect(within(card).getByText(/^Described: “late 40s, tired, warm” · Graceful Lady’s voice · saved to Resilia’s voices\. Nothing was charged\. · picked by Reed, \d\d:\d\d$/)).toBeInTheDocument();
});

test("S4-01: a voice card lists its first three voices, the rest a press away; with nothing picked it has no empty foot", async () => {
  setViewport(1440);
  const v = (n: number) => ({ id: `stock:v${n}`, name: `Voice ${n}`, note: "", file_id: null, used_in: 0 });
  const voice = ask({ kind: "voice", question: "Which voice should Mark have?", saved: [1, 2, 3, 4, 5].map(v), pick: null, generate: null, clone: price(30, 3), can: ["describe", "saved", "clone"] });
  server(owner, null, run({ thread: [asked()] }), cards(voice));
  renderApp("/b/1/videos/50");
  const card = await screen.findByRole("region", { name: "Which voice should Mark have?" });
  expect(within(card).queryByText("Voice 4")).toBeNull();
  expect(within(card).queryByRole("button", { name: /^Use / })).toBeNull();
  await userEvent.click(within(card).getByRole("button", { name: "2 more voices" }));
  await userEvent.click(within(card).getByRole("button", { name: /^Voice 5/ }));
  expect(within(card).getByRole("button", { name: "Use Voice 5" })).toBeInTheDocument();
});

test("S3-07: before the owner's OK its video's thread is closed, so the send's own card shows under its held move", async () => {
  setViewport(1440);
  const held = ask({ kind: "start", question: "Make it for up to 140 credits?", saved: [], money: held$({ up_to: price(140) }), can: ["withdraw"] });
  const sent = fs({ status: "waiting", created_by_name: "Eli", thread: [item("m1", "message", "Eli", SCRIPT), item("r1", "move", "Director", "Waiting for the owner's OK · up to 140 credits is past this video's budget of 52", "held")] });
  const calls = server(editor, sent, run({ status: "ended", turns: [] }), { ...cards(held), "GET /projects/50": [200, { ...project, created_by_id: 2 }], "POST /freestyles/9/withdraw": [200, { ...sent, status: "withdrawn" }] });
  renderApp("/b/1/videos/50");
  const card = await screen.findByRole("region", { name: "Make it for up to 140 credits?" });
  expect(screen.getAllByRole("region", { name: /^Make it/ })).toHaveLength(1);
  await userEvent.click(within(card).getByRole("button", { name: "Withdraw the request" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /freestyles/9/withdraw")).toBe(true));
});

test("S3-12: while Cut 2 is made, Cut 1 stays watchable; the switch plays and downloads any cut made; what it replaces is going out of date", async () => {
  setViewport(1440);
  const making = cutOut({ number: 1, file_id: 80, versions: [{ number: 1, file_id: 80, made_at: at }], making: { number: 2, percent: 40, doing: "laying the B-roll", about_seconds: 240, changes: 2 }, going: [{ piece: "c7", label: "Clip 7", file_id: 207 }, { piece: "c9", label: "the ending", file_id: 209 }] });
  server(owner, null, run({ status: "running" }), { "GET /projects/50/cut": [200, making], "GET /projects/50/video": [200, { file_id: 80, take_ids: [], out_of_date: false }] });
  const r = renderApp("/b/1/videos/50?tab=cut");
  const panel = await screen.findByRole("tabpanel", { name: "Cut" });
  const which = await within(panel).findByRole("radiogroup", { name: "Which cut" });
  expect(within(which).getByRole("radio", { name: "Cut 1" })).toHaveAttribute("aria-checked", "true");
  expect(within(which).getByRole("radio", { name: "Cut 2 · making" })).toHaveAttribute("aria-disabled", "true");
  expect(within(panel).getByText("Cut 1 stays watchable until Cut 2 is ready.")).toBeInTheDocument();
  expect(within(panel).getByRole("heading", { name: "Going out of date" })).toBeInTheDocument();
  expect(within(panel).getByText("Clip 7 and the ending")).toBeInTheDocument();
  expect(within(panel).getByLabelText("The cut")).toHaveAttribute("src", "/api/files/80");
  r.unmount();
  server(owner, null, run({ status: "delivered" }), { "GET /projects/50/cut": [200, cutOut()], "GET /projects/50/video": [200, { file_id: 90, take_ids: [], out_of_date: false }] });
  renderApp("/b/1/videos/50?tab=cut");
  const done = await screen.findByRole("tabpanel", { name: "Cut" });
  const cuts = await within(done).findByRole("radiogroup", { name: "Which cut" });
  expect(within(cuts).getByRole("radio", { name: "Cut 2" })).toHaveAttribute("aria-checked", "true");
  expect(within(done).getByLabelText("The cut")).toHaveAttribute("src", "/api/files/90");
  await userEvent.click(within(cuts).getByRole("radio", { name: "Cut 1" }));
  expect(within(done).getByLabelText("The cut")).toHaveAttribute("src", "/api/files/80");
  expect(within(done).getByRole("link", { name: "Download MP4" })).toHaveAttribute("download", "beer-gut-doctor-rant-cut-1.mp4");
  expect(within(done).queryByText(/stays watchable/)).toBeNull();
});

test("S3-09: one cut and nothing being made: no switch, the heading reads Final cut", async () => {
  setViewport(1440);
  server(owner, null, run({ status: "delivered" }), { "GET /projects/50/cut": [200, cutOut({ number: 1, file_id: 80, versions: [{ number: 1, file_id: 80, made_at: at }] })], "GET /projects/50/video": [200, { file_id: 80, take_ids: [], out_of_date: false }] });
  renderApp("/b/1/videos/50?tab=cut");
  const panel = await screen.findByRole("tabpanel", { name: "Cut" });
  expect(await within(panel).findByRole("heading", { name: "Final cut" })).toBeInTheDocument();
  expect(within(panel).queryByRole("radiogroup", { name: "Which cut" })).toBeNull();
});

test("S3-12: a new cut finishing while an older one is picked keeps that pick; the cut that plays isn't pinned, so the new one replaces it", async () => {
  setViewport(1440);
  const v = (n: number) => ({ number: n, file_id: 70 + 10 * n, made_at: at });
  const making = () => cutOut({ number: 2, file_id: 90, versions: [v(1), v(2)], making: { number: 3, percent: 40, doing: "", about_seconds: 20, changes: 1 } });
  const done = cutOut({ number: 3, file_id: 100, versions: [v(1), v(2), v(3)] });
  for (const choice of ["Cut 1", "Cut 2"]) {
    const route: [number, unknown] = [200, making()];
    server(owner, null, run({ status: "delivered" }), { "GET /projects/50/cut": route, "GET /projects/50/video": [200, { file_id: 90, take_ids: [], out_of_date: false }] });
    const r = renderApp("/b/1/videos/50?tab=cut");
    const panel = await screen.findByRole("tabpanel", { name: "Cut" });
    await userEvent.click(await within(panel).findByRole("radio", { name: choice }));
    route[1] = done; // Cut 3 is made
    await vi.waitFor(() => expect(within(panel).getByRole("radio", { name: "Cut 3" })).toBeInTheDocument(), { timeout: 5000 });
    if (choice === "Cut 1") {
      expect(within(panel).getByRole("radio", { name: "Cut 1" })).toHaveAttribute("aria-checked", "true"); // what you picked stays
      expect(within(panel).getByLabelText("The cut")).toHaveAttribute("src", "/api/files/80");
      expect(within(panel).getByText(/^Cut 1 · made /)).toBeInTheDocument(); // not the newest cut's length and clips
      expect(within(panel).getByRole("link", { name: "Download every clip (.zip)" })).toHaveAttribute("download", "beer-gut-doctor-rant-clips.zip");
    } else {
      expect(within(panel).getByRole("radio", { name: "Cut 3" })).toHaveAttribute("aria-checked", "true"); // the new one plays
      expect(within(panel).getByLabelText("The cut")).toHaveAttribute("src", "/api/files/100");
    }
    r.unmount();
  }
}, 20_000);

test("S3-12: a failed cut says why in Watch with its way forward, and the cut before keeps playing", async () => {
  setViewport(1440);
  const why = "Cut 3 couldn’t be made: the music is shorter than the cut. Nothing was charged.";
  const failed = cutOut({ failed: { number: 3, why, fixes: ["loop_music", "again"] } });
  const calls = server(owner, null, run({ status: "delivered" }), { "GET /projects/50/cut": [200, failed], "GET /projects/50/video": [200, { file_id: 90, take_ids: [], out_of_date: false }], "POST /projects/50/cut/fix": [202, cutOut()] });
  renderApp("/b/1/videos/50?tab=cut");
  const panel = await screen.findByRole("tabpanel", { name: "Cut" });
  expect(await within(panel).findByText(why)).toBeInTheDocument(); // said once, as the server says it
  expect(within(panel).queryAllByText(/couldn’t be made/)).toHaveLength(1);
  expect(within(panel).getByLabelText("The cut")).toHaveAttribute("src", "/api/files/90");
  await userEvent.click(within(panel).getByRole("button", { name: "Loop the music to fit · free" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/50/cut/fix")?.body).toEqual({ fix: "loop_music" }));
});

test("S3-12: while a failed cut's fixes show, Out of date has no Make it again and doesn't promise one", async () => {
  setViewport(1440);
  const failed = cutOut({ failed: { number: 3, why: "Cut 3 couldn’t be made: the music is shorter than the cut. Nothing was charged.", fixes: ["loop_music", "again"] } });
  server(owner, null, run({ status: "delivered" }), { "GET /projects/50/cut": [200, failed], "GET /projects/50/video": [200, { file_id: 90, take_ids: [], out_of_date: true }] });
  renderApp("/b/1/videos/50?tab=cut");
  const panel = await screen.findByRole("tabpanel", { name: "Cut" });
  expect(await within(panel).findByText("Out of date.")).toBeInTheDocument();
  expect(within(panel).getByRole("button", { name: "Loop the music to fit · free" })).toBeInTheDocument();
  expect(within(panel).queryByRole("button", { name: "Make it again" })).toBeNull();
  expect(panel.textContent).not.toMatch(/Making it again is free/);
});

test("S3-12: the director making Cut 1 again before it delivers adds no second Cut 1 to the switch", async () => {
  setViewport(1440);
  const again = cutOut({ number: 1, file_id: 80, versions: [{ number: 1, file_id: 80, made_at: at }], making: { number: 1, percent: 40, doing: "", about_seconds: 20, changes: 0 } });
  server(owner, null, run({ status: "running" }), { "GET /projects/50/cut": [200, again], "GET /projects/50/video": [200, { file_id: 80, take_ids: [], out_of_date: false }] });
  renderApp("/b/1/videos/50?tab=cut");
  const panel = await screen.findByRole("tabpanel", { name: "Cut" });
  expect(await within(panel).findByRole("heading", { name: "Final cut" })).toBeInTheDocument();
  expect(within(panel).queryByRole("radiogroup", { name: "Which cut" })).toBeNull();
  expect(within(panel).queryByText(/stays watchable/)).toBeNull();
});

test("an answered money card says who approved it and when, never picked by", async () => {
  setViewport(1440);
  const start = ask({ kind: "start", question: "Make it for up to $14.73?", saved: [], money: held$(), state: "answered", answer: { how: "make_it" }, answered_by: "Reed", answered_at: later, can: [] });
  server(owner, null, run({ thread: [asked()] }), cards(start));
  renderApp("/b/1/videos/50");
  const card = await screen.findByRole("region", { name: "Make it for up to $14.73?" });
  expect(within(card).getByText("Make it for up to $14.73? Approved")).toBeInTheDocument();
  expect(within(card).getByText(/^by Reed, \d\d:\d\d$/)).toBeInTheDocument();
  expect(card.textContent).not.toMatch(/picked by/);
});

test("S3-09: a note with nothing redone, nothing uncertain and nothing open has only its two parts", async () => {
  setViewport(1440);
  const clear = { ...note, unsure: "", open: [], redid: [] };
  server(owner, null, run({ status: "delivered", thread: [item("t2", "move", "Director", "…", "done", later, { note: clear })] }), { "GET /projects/50/director/progress": [200, record({ status: "delivered", title: "Made in 22 min", sub: "4 clips", tone: "done" })], "GET /projects/50/video": [200, { file_id: 8, take_ids: [], out_of_date: false }] });
  renderApp("/b/1/videos/50");
  const n = await screen.findByRole("region", { name: "Delivery note" });
  expect(within(n).getAllByRole("heading", { level: 4 }).map((h) => h.textContent)).toEqual(["What I made", "What I need from you"]);
});

// S3-14: an editor asks to change a locked line; the reply offers what can change instead, priced, and the Script tab
// says the words are set, with the asked words marked.
const instead = (o: object = {}) => ask({ id: 12, kind: "instead", topic: "", subject: "beer gut", question: "The script’s words are set for this script, so I can’t change “beer gut”. Here’s what I can change instead:", why: "", state: "offered", saved_in: "", saved: [], pick: null, generate: null, choices: [{ key: "A", title: "Say it softer", why: "Dr. Pickle says it more softly. Redo the voice line and clip 2", do: "softer", price: price(4), made: "" }], can: ["instead"], ...o });

test("S3-14: the reply to a locked line offers what can change instead at its price; a press makes it; the Script tab is set", async () => {
  setViewport(1440);
  const thread = [item("m1", "message", "Kel", "Can we change “beer gut” to “belly”? It feels a bit harsh.", null, later, { answered: true }), item("a12", "move", "Director", "The script’s words are set…", null, later, { kind: "ask", ask_id: 12 })];
  const calls = server(editor, null, run({ status: "delivered", thread }), { ...cards(instead()), "POST /asks/12/answer": [200, instead({ choices: [{ key: "A", title: "Say it softer", why: "", do: "softer", price: price(4), made: "making" }], can: [] })], "GET /projects/50/script": [200, { version: 1, source: "paste", words: 9, created_by_id: 1, created_at: at, text: "DR. PICKLE: Your beer gut after the weekend?\nDR. PICKLE: Every pint sits there." }] });
  renderApp("/b/1/videos/50");
  expect(await screen.findByText("The script’s words are set for this script, so I can’t change “beer gut”. Here’s what I can change instead:")).toBeInTheDocument();
  const softer = screen.getByRole("button", { name: /^Say it softer/ });
  expect(softer).toHaveTextContent("Dr. Pickle says it more softly. Redo the voice line and clip 2 · up to 4 credits"); // credits only (rule 4)
  await userEvent.click(softer);
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /asks/12/answer")?.body).toEqual({ how: "instead", choice: "A" }));
  await userEvent.click(screen.getByRole("tab", { name: "Script" }));
  expect(await screen.findByText("Published script · the words are set")).toBeInTheDocument();
  expect(screen.getByText("beer gut", { selector: "mark" })).toBeInTheDocument();
});

test("S3-14: an editor's note on a delivered video from New video goes through its freestyle, and the reply shows at once", async () => {
  setViewport(1440);
  const mine = fs({ status: "delivered", created_by_name: "Kel", thread: [item("m1", "message", "Kel", SCRIPT)] });
  const calls = server(editor, mine, run({ status: "delivered", thread: [] }), { ...cards(), "GET /projects/50": [200, { ...project, created_by_id: 2 }], "POST /freestyles/9/messages": [201, mine] });
  renderApp("/b/1/videos/50");
  const box = await ready();
  const read = (key: string) => calls.filter((c) => c.key === key).length;
  const before = { asks: read("GET /projects/50/asks"), chat: read("GET /projects/50/director") };
  await userEvent.type(box, "Change “beer gut” to “belly”.{Enter}");
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /freestyles/9/messages")?.body).toEqual({ text: "Change “beer gut” to “belly”." }));
  await vi.waitFor(() => expect(read("GET /projects/50/asks")).toBeGreaterThan(before.asks)); // its reply card is read at once
  expect(read("GET /projects/50/director")).toBeGreaterThan(before.chat); // and the thread it's in
});

test("S3-14: once chosen, the card says so and how it's going; the other choices stay pressable; a free one says free", async () => {
  setViewport(1440);
  const choices = [{ key: "A", title: "Say it softer", why: "Dr. Pickle says it more softly. Redo the voice line and clip 2", do: "softer", price: price(4), made: "held", said: "Waiting for the owner’s OK.", cannot: "" }, { key: "B", title: "Shorter pause after it", why: "Tighten 0.4 s", do: "pause", price: null, made: "", said: "", cannot: "" }];
  server(editor, null, run({ status: "delivered", thread: [item("a12", "move", "Director", "…", null, later, { kind: "ask", ask_id: 12 })] }), cards(instead({ choices })));
  renderApp("/b/1/videos/50");
  expect(await screen.findByText("You chose: Say it softer")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^Say it softer/ })).toBeDisabled();
  expect(screen.getByRole("button", { name: /^Say it softer/ })).toHaveTextContent("Waiting for the owner’s OK.");
  const pause = screen.getByRole("button", { name: /^Shorter pause after it/ });
  expect(pause).toBeEnabled();
  expect(pause).toHaveTextContent("Tighten 0.4 s · free");
});

test("S3-14: a choice that can't be made now says why and can't be pressed; the cut's outcome is the server's words", async () => {
  setViewport(1440);
  const choices = [{ key: "A", title: "Say it softer", why: "Dr. Pickle says it more softly. Redo the voice line and clip 2", do: "softer", price: null, made: "", said: "", cannot: "Clip 2 isn't in this video any more." }];
  server(editor, null, run({ status: "delivered", thread: [item("a12", "move", "Director", "…", null, later, { kind: "ask", ask_id: 12 })] }), cards(instead({ choices, can: [] })));
  const view = renderApp("/b/1/videos/50");
  const gone = await screen.findByRole("button", { name: /^Say it softer/ });
  expect(gone).toBeDisabled();
  expect(gone).toHaveTextContent("Clip 2 isn't in this video any more.");
  expect(gone).not.toHaveTextContent("free");
  view.unmount();
  const done = [{ ...choices[0], price: price(4), made: "kept", said: "Made and watched, but the cut wasn’t made again: The music file stops at 0:41. Make the cut from the Cut tab once that’s done.", cannot: "" }];
  server(editor, null, run({ status: "delivered", thread: [item("a12", "move", "Director", "…", null, later, { kind: "ask", ask_id: 12 })] }), cards(instead({ choices: done, can: [] })));
  renderApp("/b/1/videos/50");
  expect(await screen.findByRole("button", { name: /^Say it softer/ })).toHaveTextContent("the cut wasn’t made again: The music file stops at 0:41.");
});

test("S3-14: a take nobody watched offers its free one-click press: use it and make the cut", async () => {
  setViewport(1440);
  const choices = [{ key: "A", title: "Say it softer", why: "", do: "softer", price: price(4), made: "kept", said: "Made. Not watched: the video is at its budget, so the cut stays as it was. Use take 3 and make the cut, or look at it in Clips first.", cannot: "", then: "Use take 3 and make the cut" }];
  const calls = server(editor, null, run({ status: "delivered", thread: [item("a12", "move", "Director", "…", null, later, { kind: "ask", ask_id: 12 })] }), { ...cards(instead({ choices })), "POST /asks/12/answer": [200, instead({ choices: [{ ...choices[0], made: "done", said: "Take 3 is used. The cut is made again with it.", then: "" }], can: [] })] });
  renderApp("/b/1/videos/50");
  await userEvent.click(await screen.findByRole("button", { name: "Use take 3 and make the cut · free" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /asks/12/answer")?.body).toEqual({ how: "instead", choice: "A", option: "use" }));
});

test("S3-14 on a Presenter video: Cut away while it's said is free, and its press makes it", async () => {
  setViewport(1440);
  const away = { key: "A", title: "Cut away while it’s said", why: "Show the B-roll instead of Dr. Pickle’s face on that line", do: "cut_away", price: null, made: "", said: "", cannot: "", then: "" };
  const calls = server(editor, null, run({ status: "delivered", thread: [item("a12", "move", "Director", "…", null, later, { kind: "ask", ask_id: 12 })] }), { ...cards(instead({ choices: [away] })), "POST /asks/12/answer": [200, instead({ choices: [{ ...away, made: "done", said: "Done. Making Cut 2 with it." }], can: [] })] });
  renderApp("/b/1/videos/50");
  const button = await screen.findByRole("button", { name: /^Cut away while it’s said/ });
  expect(button).toHaveTextContent("Show the B-roll instead of Dr. Pickle’s face on that line · free");
  await userEvent.click(button);
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /asks/12/answer")?.body).toEqual({ how: "instead", choice: "A" }));
});

test("S3-08: a run carried on shows the Stop it carried on from; an editor's Carry on waiting for the owner has no press of its own", async () => {
  setViewport(1440);
  const going = record({ stops: [{ by: "Reed", at: "2026-11-04T10:14:00Z", carried_at: "2026-11-04T10:20:00Z" }] });
  server(owner, null, run({ thread: [card] }), { "GET /projects/50/director/progress": [200, going] });
  const view = renderApp("/b/1/videos/50");
  expect(await screen.findByText(/^Reed stopped the director at \d\d:\d\d · carried on at \d\d:\d\d\.$/)).toBeInTheDocument();
  view.unmount();
  const waiting = record({ status: "stopped", title: "Stopped", sub: "3 of 4 clips made", tone: "stop", stopped: { by: "Reed", at: "2026-11-04T10:14:00Z", made: 3, total: 4, carry_on: "" } });
  server(editor, null, run({ status: "ended", thread: [card] }), { "GET /projects/50/director/progress": [200, waiting] });
  renderApp("/b/1/videos/50");
  expect(await screen.findByRole("button", { name: "Start the plan again" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^Carry on/ })).toBeNull();
});

test("Flow-QA S7: while a step waits, the header never shows a budget below what's spent: the video's spent against its up to", async () => {
  setViewport(1440);
  const waits = { status: status("waiting", "Waiting for your OK"), spent: money(124, 12.73), up_to: money(250, 25.71), budget: money(54, 5.56) };
  server(owner, null, run({ status: "running" }), { "GET /projects/50/idea": [200, head(waits)] });
  renderApp("/b/1/videos/50");
  const top = await screen.findByRole("banner");
  expect(await within(top).findByText("$12.73 spent ·", { exact: false })).toBeInTheDocument();
  expect(within(top).getByText("up to $25.71")).toBeInTheDocument();
  expect(within(top).queryByText(/budget \$5\.56/)).toBeNull();
});

test("Flow-QA M6: a run that ended by itself is read again at once: no Stop or 'already building' left behind", async () => {
  setViewport(1440);
  const failed = record({ status: "needs_fix", title: "Stopped at clip 4", tone: "bad", failed: { title: "The director stopped", why: "It stopped.", offer: "", clip: null, fixes: [{ kind: "carry_on", label: "Carry on", price: "$10.74", problem: "", then: null }] } });
  const calls = server(owner, null, run({ status: "running", start_blocked: "The director is already building this video.", thread: [card] }), { "GET /projects/50/director/progress": [200, failed] });
  renderApp("/b/1/videos/50");
  await screen.findByText("The director stopped");
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "GET /projects/50/director").length).toBeGreaterThan(1)); // read again, not left
});

test("S3-02 (QA on #1383): before Make it the Plan tab shows the director's treatment as the plan's scenes, nothing spent", async () => {
  setViewport(1440);
  const story = { hook: "The glowing spine.", logline: "A doctor shows the weekend's damage.", why_it_holds: "A gross picture first.", beats: [{ id: "b1", lines: [1], purpose: "hook", picture: "The glowing spine, slow push in." }, { id: "b2", lines: [2, 3], purpose: "what beer does", picture: "Beer pours through the see-through body." }], ending: "The capsule." };
  const r = run({ status: "running", make_it: null, thread: [item("t1", "move", "Director", "Here's how I'll make it.", "done", at, { treatment: story })] });
  server(owner, null, r, { "GET /projects/50": [200, { ...project, freestyle_id: null, plan_status: "none", planned_seconds: 60 }], "GET /projects/50/idea": [200, head({ status: status("waiting", "Waiting for your OK") })] });
  renderApp("/b/1/videos/50?tab=plan");
  const plan = await screen.findByRole("region", { name: "Plan" });
  expect(within(plan).getByText("2 scenes · about 60 s")).toBeInTheDocument();
  expect(within(within(plan).getByLabelText("Scene 2")).getByText("2. What beer does")).toBeInTheDocument();
  expect(within(within(plan).getByLabelText("Scene 2")).getByText("Lines 2–3")).toBeInTheDocument();
  expect(within(plan).getByText("The director plans each scene's shots and clips after Make it.")).toBeInTheDocument();
  expect(screen.queryByText(/No plan yet/)).toBeNull();
});

test("QA on #1383: the owner's Make it says dollars, as every owner press does (rule 4)", async () => {
  setViewport(1440);
  server(owner, null, run({ status: "none", turns: [], thread: [], run_price: 40 }), { "GET /projects/50/idea": [200, head({ usd_per_credit: 0.1028 })] });
  renderApp("/b/1/videos/50");
  expect(await screen.findByRole("button", { name: "Make it · up to $4.12" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /credits/ })).toBeNull();
});

// Reed, 6 Nov (BS_OWNER_UNCAPPED, his test site): no limit, so the owner reads what it will probably cost and what the
// providers really charged; never "up to", never a budget below what's spent.
test("uncapped: the start card is an estimate, the header and the run card read the providers' spend, never a budget", async () => {
  setViewport(1440);
  const start = ask({ kind: "start", topic: "", question: "Make it? About $9.10 (estimate).", why: "That's what this run will probably cost.", saved: [], money: held$({ up_to: price(91, 9.1), expected: true }), can: ["make_it"] });
  const going = record({ actual_usd: 3.2, listed_usd: 0, unreported: true, expected_usd: 9.1, cost: "$3.20 spent on this run, more not reported yet" });
  const top = head({ spent: money(60, 16.77), up_to: null, budget: null, expected: money(91, 9.1), actual: true, listed_usd: 4, unreported: false });
  server(owner, null, run({ status: "running", thread: [card, asked()] }), { ...cards(start), "GET /projects/50/idea": [200, top], "GET /projects/50/director/progress": [200, going] });
  renderApp("/b/1/videos/50");
  const startCard = await screen.findByRole("region", { name: "Make it? About $9.10 (estimate)." });
  expect(within(startCard).getByRole("button", { name: "Make it · about $9.10" })).toBeInTheDocument();
  const banner = await screen.findByRole("banner");
  expect(await within(banner).findByText("This video so far $16.77 ($4.00 of it at list price) ·", { exact: false })).toBeInTheDocument();
  expect(within(banner).getByText("this run about $9.10 (estimate)")).toBeInTheDocument();
  expect(within(banner).queryByText(/budget|up to/)).toBeNull();
  expect(await screen.findByText("$3.20 spent on this run, more not reported yet · about $9.10 (estimate)")).toBeInTheDocument();
});

test("uncapped: Carry on is just Carry on, the same run; Make it again says about its estimate", async () => {
  setViewport(1440);
  const stopped = record({ status: "stopped", title: "Stopped", tone: "stop", stopped: { by: "Reed", at, made: 1, total: 4, carry_on: "", free: true } });
  server(owner, null, run({ status: "ended", thread: [card], run_expected_usd: 8.01 }), { "GET /projects/50/director/progress": [200, stopped] });
  renderApp("/b/1/videos/50");
  expect(await screen.findByRole("button", { name: "Carry on" })).toBeInTheDocument();
  expect(screen.queryByText(/Carry on · up to/)).toBeNull();
});
