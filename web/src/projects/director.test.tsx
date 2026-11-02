import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { ToastProvider } from "../toast";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { DirectorPanel, NOT_PLAIN } from "./DirectorPanel";

const owner = { id: 1, email: "o@b.co", name: "Olu", role: "owner", workspace_id: 1 };
const editor = { ...owner, id: 2, role: "editor" };
const at = new Date().toISOString();
const turn = (n: number, o: object = {}) => ({ turn: n, tool: "storyboard", why: "The looks are approved, so the storyboard comes next.", result: "Making the storyboard.", status: "succeeded", created_at: at, ...o });
const run = (o: object = {}) => ({ status: "running", ended: "", turns: [turn(1, { tool: "plan", result: "Making the shots.", why: "There are no shots yet." }), turn(2)], spent_usd: 0.42, credits: 31, start_blocked: "The director is already building this video.", ...o });
const take = (id: number) => ({ id, number: id, file_id: id, created_at: at, verdict: "clean" });
const clips = (made: number, of: number) => Array.from({ length: of }, (_, i) => ({ id: i + 1, clip_id: `c${i + 1}`, seconds: 5, takes: i < made ? [take(i + 1)] : [], picked_take_id: null }));
const routes = (o: Record<string, [number, unknown]> = {}) => ({ "GET /auth/me": [200, owner] as [number, unknown], "GET /projects/9/clips": [200, []] as [number, unknown], "GET /projects/9/video": [404, { detail: "none" }] as [number, unknown], ...o });

function show(onOpenClips = () => {}) {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <MemoryRouter>
          <DirectorPanel projectId={9} aspect="9:16" name="Cat buys the dip" onOpenClips={onOpenClips} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}
afterEach(() => vi.unstubAllGlobals());

test("at 390, an editor presses Make it and sees the progress line in credits, and each move with its reason", async () => {
  setViewport(390);
  const calls = fakeServer(routes({ "GET /auth/me": [200, editor], "GET /projects/9/director": [200, run({ status: "none", turns: [], credits: 0, spent_usd: null, start_blocked: "" })], "POST /projects/9/director": [201, run({ spent_usd: null })] }));
  show();
  await userEvent.click(await screen.findByRole("button", { name: "Make it" }));
  expect(calls.some((c) => c.key === "POST /projects/9/director")).toBe(true);
  expect(await screen.findByText("Making the storyboard · up to 31 credits so far · you can leave this page")).toBeInTheDocument();
  expect(screen.getByText("Making the shots.")).toBeInTheDocument();
  expect(screen.getByText("The looks are approved, so the storyboard comes next.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Stop" })).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/\$|ask (Reed|the owner)/i);
});

test("making clips, the line counts them: Making clips: 6 of 9", async () => {
  fakeServer(routes({ "GET /projects/9/clips": [200, clips(6, 9)], "GET /projects/9/director": [200, run({ spent_usd: null, credits: 42, turns: [turn(1, { tool: "make_take", result: "Making 9 takes." })] })] }));
  show();
  expect(await screen.findByText("Making clips: 6 of 9 · up to 42 credits so far · you can leave this page")).toBeInTheDocument();
});

test("Make it is disabled with the server's plain reason when the script isn't published", async () => {
  fakeServer(routes({ "GET /projects/9/director": [200, run({ status: "none", turns: [], start_blocked: "The director builds from a published script. Publish it first." })] }));
  show();
  expect(await screen.findByRole("button", { name: "Make it" })).toBeDisabled();
  expect(screen.getByText("The director builds from a published script. Publish it first.")).toBeInTheDocument();
});

test("the owner sees the director's own time in dollars; even if the server sent it, an editor never does", async () => {
  setViewport(1440);
  fakeServer(routes({ "GET /projects/9/director": [200, run()] }));
  show();
  expect(await screen.findByText(/up to 31 credits so far · the director's own time \$0\.42/)).toBeInTheDocument();
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
  fakeServer(routes({ "GET /auth/me": [200, editor], "GET /projects/9/director": [200, run()] }));
  show();
  expect(await screen.findByText(/up to 31 credits so far/)).toBeInTheDocument();
  expect(document.body.textContent).not.toContain("$");
});

test("a held move says Waiting for approval", async () => {
  fakeServer(routes({ "GET /projects/9/director": [200, run({ turns: [turn(1), turn(2, { tool: null, why: "", result: "", status: "needs_owner_approval" })] })] }));
  show();
  expect(await screen.findByText("Waiting for approval")).toBeInTheDocument();
  expect(screen.getByText(/^Waiting for the owner's OK · up to 31 credits/)).toBeInTheDocument();
});

test("Stop asks first, says what still finishes, and stops the run", async () => {
  const calls = fakeServer(routes({ "GET /projects/9/director": [200, run()], "POST /projects/9/director/stop": [200, run({ status: "ended", ended: "Stopped.", start_blocked: "" })] }));
  show();
  await userEvent.click(await screen.findByRole("button", { name: "Stop" }));
  expect(screen.getByText(/What it already started still finishes, and nothing is undone/)).toBeInTheDocument();
  await userEvent.click(screen.getAllByRole("button", { name: "Stop" }).at(-1)!);
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/director/stop")).toBe(true));
  expect(await screen.findByText(/^Stopped\. · up to 31 credits for this run/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Make it again" })).toBeEnabled();
});

test("at 390, the delivered cut plays and downloads, with the total, the note, what it redid and why, and All clips", async () => {
  setViewport(390);
  const done = run({
    status: "delivered",
    start_blocked: "",
    credits: 58,
    spent_usd: null,
    turns: [
      turn(1, { tool: "make_take", result: "Making 3 takes.", why: "Every clip needs a take." }),
      turn(2, { tool: "make_take", result: "Making 1 take.", why: "Take 1 of c3 is flagged: the label is hard to read." }),
      turn(3, { tool: "deliver", why: "Every take checked clean; take 2 of clip 3 has the clearest product shot.", result: "Delivered." }),
    ],
  });
  const inside = vi.fn();
  fakeServer(routes({ "GET /auth/me": [200, editor], "GET /projects/9/director": [200, done], "GET /projects/9/clips": [200, [18, 20, 16].map((n, i) => ({ id: i + 1, clip_id: `c${i + 1}`, seconds: n, takes: [take(i + 1)], picked_take_id: i + 1 }))], "GET /projects/9/video": [200, { id: 3, file_id: 77, song_take_id: null, narration: null, created_at: at }] }));
  show(inside);
  expect(await screen.findByLabelText("The finished video")).toBeInTheDocument();
  expect(screen.getByText("Delivered")).toBeInTheDocument();
  expect(screen.getAllByText("Every take checked clean; take 2 of clip 3 has the clearest product shot.")[0]).toBeVisible(); // the note, and again in Every move
  expect(screen.getByText("54 s · up to 58 credits for this run")).toBeInTheDocument(); // its length, and never below the charge
  expect(screen.getByText("What it redid on its own (1)")).toBeInTheDocument();
  expect(screen.getAllByText("Take 1 of clip 3 is flagged: the label is hard to read.")[0]).toBeVisible();
  expect(screen.getByRole("link", { name: /Download MP4/ })).toHaveAttribute("download", "cat-buys-the-dip.mp4");
  await userEvent.click(screen.getByRole("button", { name: "All clips" }));
  expect(inside).toHaveBeenCalled();
  expect(document.body.textContent).not.toContain("$");
});

test("the conversation shows the newest 8, and Show earlier opens the rest", async () => {
  setViewport(390);
  fakeServer(routes({ "GET /projects/9/director": [200, run({ turns: Array.from({ length: 12 }, (_, i) => turn(i + 1, { result: `Move ${i + 1}.` })) })] }));
  show();
  expect(await screen.findByText("Move 12.")).toBeInTheDocument();
  expect(screen.queryByText("Move 4.")).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Show earlier (4)" }));
  expect(screen.getByText("Move 1.")).toBeInTheDocument();
});

const item = (id: string, o: object = {}) => ({ id, kind: "move", at, who: "Director", text: "Made the cut.", status: "done", ...o });

test("after a delivery, a person asks for a change: it's sent, shows in the thread, and the director's moves follow with their reasons", async () => {
  setViewport(1440);
  const before = [item("t1", { text: "Made the plan.", why: "There were no shots yet." }), item("t2", { text: "Every take checked clean." })];
  const delivered = run({ status: "delivered", start_blocked: "", thread: before });
  const after = run({ thread: [...before, { id: "m0", kind: "message", at, who: "Olu", text: "Make clip 1 slower.", status: null }, item("t3", { text: "Waiting for the owner's OK.", status: "held" })] });
  const calls = fakeServer(routes({ "GET /projects/9/director": [200, delivered], "POST /projects/9/director/messages": [201, after] }));
  show();
  expect(await screen.findByText("There were no shots yet.")).toBeInTheDocument(); // a move's reason under it
  const box = screen.getByLabelText("Tell the director what to change");
  expect(screen.getByRole("button", { name: "Send to the director" })).toBeDisabled(); // nothing to send yet
  await userEvent.type(box, "Make clip 1 slower.{Enter}");
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/director/messages")?.body).toEqual({ text: "Make clip 1 slower." }));
  const thread = await screen.findByRole("list", { name: "Conversation with the director" });
  expect(within(thread).getByText("Make clip 1 slower.")).toBeInTheDocument();
  expect(within(thread).getByRole("link", { name: "See it in Needs you" })).toHaveAttribute("href", "/approvals");
  expect(box).toHaveValue("");
});

test("after a delivery a message is saved, not run: Make it again makes the change (the Producer, 2 Nov)", async () => {
  setViewport(1440);
  const before = [item("t1", { text: "Every take checked clean." })];
  const savedThread = [...before, { id: "m0", kind: "message", at, who: "Olu", text: "Make clip 1 slower.", status: null, why: "" }];
  const saved = run({ status: "delivered", start_blocked: "", thread: savedThread, unread: 1 });
  const calls = fakeServer(routes({ "GET /projects/9/director": [200, run({ status: "delivered", start_blocked: "", thread: before })], "POST /projects/9/director/messages": [201, saved], "POST /projects/9/director": [201, run({ thread: savedThread })] }));
  show();
  await userEvent.type(await screen.findByLabelText("Tell the director what to change"), "Make clip 1 slower.{Enter}");
  expect(await screen.findByText("Saved. Press Make it again to make this change.")).toBeInTheDocument();
  expect(calls.some((c) => c.key === "POST /projects/9/director")).toBe(false); // the message alone starts nothing
  await userEvent.click(screen.getByRole("button", { name: "Make it again" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/director")).toBe(true));
});

test("after a Stop the press reads Start again with this note; too many messages says so plainly", async () => {
  setViewport(1440);
  const stopped = run({ status: "ended", ended: "Stopped.", start_blocked: "", unread: 1, thread: [item("t1"), { id: "m0", kind: "message", at, who: "Olu", text: "Shorter, please.", status: null, why: "" }] });
  fakeServer(routes({ "GET /projects/9/director": [200, stopped], "POST /projects/9/director/messages": [429, { detail: "Too many messages; wait a moment" }] }));
  show();
  expect(await screen.findByRole("button", { name: "Start again with this note" })).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Tell the director what to change"), "And louder.{Enter}");
  expect(await screen.findByRole("alert")).toHaveTextContent("Too many messages; wait a moment");
});

test("during a run a note says the director reads it on its next move; a double press sends one note; an editor's held move says it waits for approval, with no owner link (QA-11)", async () => {
  setViewport(390);
  const going = run({ thread: [item("t1", { text: "Made the plan." })] });
  const sent = run({ thread: [item("t1", { text: "Made the plan." }), item("t2", { text: "Waiting for the owner's OK.", status: "held" }), { id: "m0", kind: "message", at, who: "Olu", text: "Warmer light.", status: null, why: "" }] });
  const calls = fakeServer(routes({ "GET /auth/me": [200, editor], "GET /projects/9/director": [200, going], "POST /projects/9/director/messages": [201, sent] }));
  show();
  await userEvent.type(await screen.findByLabelText("Tell the director what to change"), "Warmer light.");
  await userEvent.dblClick(screen.getByRole("button", { name: "Send to the director" }));
  expect(await screen.findByText("The director will read this on its next move.")).toBeInTheDocument();
  expect(calls.filter((c) => c.key === "POST /projects/9/director/messages")).toHaveLength(1);
  expect(screen.queryByRole("alert")).toBeNull();
  const thread = screen.getByRole("list", { name: "Conversation with the director" });
  expect(within(thread).getByText("Waiting for approval.")).toBeInTheDocument();
  expect(within(thread).queryByRole("link", { name: "See it in Needs you" })).toBeNull();
});

test("each note says whether a move has answered it yet", async () => {
  setViewport(1440);
  const thread = [{ id: "m0", kind: "message", at, who: "Olu", text: "Warmer light.", status: null, why: "", answered: true }, item("t1", { text: "Warmed the light.", answered: null }), { id: "m1", kind: "message", at, who: "Olu", text: "Shorter.", status: null, why: "", answered: false }];
  fakeServer(routes({ "GET /projects/9/director": [200, run({ thread })] }));
  show();
  const list = await screen.findByRole("list", { name: "Conversation with the director" });
  expect(within(list).getAllByText(/· Answered$/)).toHaveLength(1);
  expect(within(list).getAllByText(/· Open$/)).toHaveLength(1); // and never on a move
});

test("a refused move reads as plain words, without the server's Refused: prefix (Advice on #1176)", async () => {
  fakeServer(routes({ "GET /projects/9/director": [200, run({ turns: [turn(1, { result: "Refused: the cast is locked, so it stays." })] })] }));
  show();
  expect(await screen.findByText("The cast is locked, so it stays.")).toBeInTheDocument();
  expect(screen.queryByText(/Refused:/)).toBeNull();
});

test("before the first run there's no message box: Make it starts the director", async () => {
  fakeServer(routes({ "GET /projects/9/director": [200, run({ status: "none", turns: [], start_blocked: "" })] }));
  show();
  expect(await screen.findByRole("button", { name: "Make it" })).toBeInTheDocument();
  expect(screen.queryByLabelText("Tell the director what to change")).toBeNull();
});

test("move lines are plain words: no tool names, codes, ids or JSON on screen; said is shown when the server sends it", async () => {
  setViewport(390);
  const raw = [
    turn(1, { tool: "make_take", result: "Making 1 take.", why: "c2 is flagged: the boss looks calm." }),
    turn(2, { tool: "pick_take", result: "Picked take 12 for c2.", why: "It's the newest clean take." }),
    turn(3, { tool: "make_take", result: "Refused: there's no tool called make_takes.", why: '{"tool": "make_take", "clip_id": "c9"}' }),
    turn(4, { tool: "final_cut", result: "Made the cut.", said: "Putting the cut together.", why: "Every clip has a picked take." }),
  ];
  fakeServer(routes({ "GET /projects/9/clips": [200, [{ id: 2, clip_id: "c2", seconds: 5, takes: [{ ...take(12), number: 3 }], picked_take_id: 12 }]], "GET /projects/9/director": [200, run({ turns: raw })] }));
  show();
  expect(await screen.findByText("clip 2 is flagged: the boss looks calm.")).toBeInTheDocument();
  expect(screen.getByText("Picked take 3 for clip 2.")).toBeInTheDocument(); // the take's number, not its id
  expect(screen.getByText("Making clips.")).toBeInTheDocument(); // an unplain line falls back to its step
  expect(screen.getByText("Putting the cut together.")).toBeInTheDocument(); // said, over result
  const moves = screen.getByText("Picked take 3 for clip 2.").closest("ol")!;
  expect(moves.textContent).not.toMatch(NOT_PLAIN);
  expect(moves.textContent).not.toMatch(/make_take|pick_take|final_cut|clip_id|\bc\d+\b|\{/);
});

test("the locks it builds around: a press locks or unlocks one and keeps the outfits; Screens only shows", async () => {
  setViewport(1440);
  const locks = { cast: true, look: false, length: false, song: false, end_line: false, screens: [] };
  const outfits = { "char:1": "red coat" };
  const calls = fakeServer(routes({ "GET /projects/9/director": [200, run({ status: "none", turns: [] })], "GET /projects/9/locks": [200, { locks, outfits }], "PUT /projects/9/locks": [200, { locks: { ...locks, look: true }, outfits }] }));
  show();
  const chips = await screen.findByRole("list", { name: "Locked" });
  expect(within(chips).getByRole("button", { name: "Cast" })).toHaveAttribute("aria-pressed", "true");
  await userEvent.click(within(chips).getByRole("button", { name: "Look" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /projects/9/locks")?.body).toEqual({ locks: { ...locks, look: true }, outfits }));
  expect(await within(chips).findByRole("button", { name: "Look", pressed: true })).toBeInTheDocument();
  expect(within(chips).queryByRole("button", { name: /Screens/ })).toBeNull();
  expect(within(chips).getByText("Screens")).toBeInTheDocument();
});
