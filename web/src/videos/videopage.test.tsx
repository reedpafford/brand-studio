import { act, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { editor, owner } from "../test/people";
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
  expect(screen.getByPlaceholderText(/^Say what to change: “shorter end”/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Stop" })).toBeNull();
});

test("the owner's note after a delivery is saved; Make it again makes it (a note never starts a run by itself)", async () => {
  setViewport(1440);
  const done = fs({ status: "delivered", file_id: 8, thread: [item("m1", "message", "Reed", SCRIPT), item("t2", "move", "Director", "Every take checked clean.", "done", later)] });
  const delivered = run({ status: "delivered", turns: [{ turn: 3, tool: "deliver", why: "", result: "Delivered.", status: "succeeded", created_at: later }] });
  const noted = { ...delivered, unread: 1, thread: [item("m0", "message", "Reed", "Cut 2 seconds.", null, "2026-11-04T10:30:00Z")] };
  const calls = server(owner, done, delivered, { "POST /projects/50/director/messages": [201, noted], "POST /projects/50/director": [201, run()] });
  renderApp("/b/1/videos/50");
  const box = await ready();
  expect(screen.getByRole("button", { name: "Send to the director" })).toBeDisabled(); // nothing to send yet
  await userEvent.type(box, "Cut 2 seconds.{Enter}");
  expect(await screen.findByText("Saved. Press Make it again to make this change.")).toBeInTheDocument();
  expect(calls.find((c) => c.key === "POST /projects/50/director/messages")?.body).toEqual({ text: "Cut 2 seconds." });
  expect(within(screen.getByRole("list", { name: "Conversation with the director" })).getByText("Cut 2 seconds.")).toBeInTheDocument();
  expect(calls.some((c) => c.key === "POST /projects/50/director")).toBe(false);
  await userEvent.click(screen.getByRole("button", { name: "Make it again · up to 40 credits" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/50/director")).toBe(true));
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

test("an editor's change waits for the owner: its price shows, never up to free, and Withdraw change takes it back", async () => {
  setViewport(1440);
  const waiting = fs({ status: "waiting", created_by_name: "Eli", file_id: 8, thread: [item("m1", "message", "Eli", SCRIPT), item("m2", "message", "Eli", "Punchier ending.", null, later), item("t3", "move", "Director", "Waiting for the owner's OK.", "held", later)] });
  const heldJob = { id: 31, kind: "claude", project_id: 50, credits: 3, status: "needs_owner_approval", created_at: later, finished_at: null, freestyle: { id: 9, title: "Beer gut doctor rant", type: "dialogue", said: "Punchier ending.", change: true, up_to: 139.46, total: 280, spent: 82 } };
  const calls = server(editor, waiting, run({ run_price: 0, turns: [{ turn: 0, tool: null, why: "", result: "", status: "needs_owner_approval", created_at: later }] }), { "GET /projects/50": [200, { ...project, created_by_id: 2 }], "POST /freestyles/9/withdraw": [200, { ...waiting, status: "delivered" }], "GET /jobs?status=needs_owner_approval": [200, [heldJob]] });
  renderApp("/b/1/videos/50");
  expect(await screen.findByText("Change asked · waiting for the owner")).toBeInTheDocument();
  expect(await screen.findByText("up to 140 credits")).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/up to free|\$\d/);
  await userEvent.click(screen.getByRole("button", { name: "Withdraw change" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /freestyles/9/withdraw")).toBe(true));
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

test("while the first move runs the header reads Working, not the server's lagging Needs you · Start it; the start card's Make it is the press", async () => {
  setViewport(1440);
  server(owner, null, run({ turns: [{ turn: 0, tool: null, why: "", result: "", status: "running", created_at: at }] }), { "GET /projects/50/idea": [200, head({ status: status("needs_you", "Needs you", "Start it") })] });
  const first = renderApp("/b/1/videos/50");
  expect(await within(await screen.findByRole("banner")).findByText("Working · starting")).toBeInTheDocument();
  first.unmount();
  const calls = server(owner, null, run({ status: "ended", turns: [], make_it: 77, run_price: 140, thread: [item("t1", "move", "Director", "The treatment.", "done")] }), { "GET /projects/50/idea": [200, head({ status: status("needs_you", "Needs you", "Start it") })], "POST /asks/77/answer": [200, {}] });
  renderApp("/b/1/videos/50");
  await userEvent.click(await screen.findByRole("button", { name: "Make it · up to 140 credits" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /asks/77/answer")?.body).toEqual({ how: "make_it" }));
  expect(screen.queryByRole("button", { name: /^Make it again/ })).toBeNull();
});
