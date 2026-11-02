import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { editor, owner } from "../test/people";
import { renderApp } from "../test/render";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { TreatmentCard } from "./Treatment";

// The director-first video's chat view (v5 B_VideoWaiting … B_ChangeHeld): a video made through a freestyle.
const at = "2026-11-02T10:00:00Z";
const later = "2026-11-02T10:05:00Z";
const item = (id: string, kind: string, who: string, text: string, status: string | null = null, when = at) => ({ id, kind, at: when, who, text, status, why: "" });
const SCRIPT = "BO: Is that... salmon?";
const fs = (o: object = {}) => ({ id: 9, title: "Bo tries salmon", type: "dialogue", look: "house", shape: "9:16", brand_id: 1, status: "working", created_by_name: "Reed", created_at: at, credits: 61.2, file_id: null, up_to: 204, project_id: 50, script_id: 3, thread: [item("m1", "message", "Reed", SCRIPT), item("t1", "move", "Director", "Made the plan.", "done")], ...o });
const run = (o: object = {}) => ({ status: "running", ended: "", turns: [{ turn: 0, tool: "make_take", why: "", result: "", status: "succeeded", created_at: at }], credits: 61, spent_usd: null, start_blocked: "", thread: [], unread: 0, run_price: 40, ...o });
const project = { id: 50, brand_id: 1, name: "Bo tries salmon · freestyle 9", freestyle_id: 9, aspect_ratio: "9:16" };
function server(me: object, f: object, r: object, routes: Record<string, [number, unknown]> = {}) {
  return fakeServer({
    "GET /auth/me": [200, me],
    "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
    "GET /looks": [200, [{ id: "house", name: "House", blurb: "", on: true, own_sample: false, lanes: [] }]],
    "GET /jobs": [200, []],
    "GET /projects/50": [200, project],
    "GET /freestyles/9": [200, f],
    "GET /projects/50/director": [200, r],
    "GET /projects/50/clips": [200, []],
    "GET /projects/50/locks": [200, { locks: { cast: true }, outfits: {} }],
    ...routes,
  });
}
afterEach(() => vi.unstubAllGlobals());

test("while the director works: Working, its progress with what it has spent, the locks, and Stop asks first", async () => {
  setViewport(1440);
  const calls = server(owner, fs(), run(), { "POST /freestyles/9/stop": [200, fs({ status: "stopped" })] });
  renderApp("/b/1/videos/50");
  expect(await screen.findByText(/^Making clips · 62 credits spent so far · you can leave this page$/)).toBeInTheDocument();
  expect(screen.getByText("Working")).toBeInTheDocument();
  expect(await screen.findByRole("list", { name: "Locked" })).toBeInTheDocument();
  expect(screen.getByText("The director will read this on its next move.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Open the steps" })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Stop" }));
  await userEvent.click(within(screen.getByRole("alertdialog", { name: "Stop the director?" })).getByRole("button", { name: "Stop" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /freestyles/9/stop")).toBe(true));
});

test("delivered: the cut sits in the thread under Delivered., with its note; the owner's note is saved and Make it again makes it", async () => {
  setViewport(1440);
  const done = fs({ status: "delivered", file_id: 8, thread: [item("m1", "message", "Reed", SCRIPT), item("t2", "move", "Director", "Every take checked clean.", "done", later)] });
  const delivered = run({ status: "delivered", turns: [{ turn: 3, tool: "deliver", why: "", result: "Delivered.", status: "succeeded", created_at: later }] });
  const noted = { ...delivered, unread: 1, thread: [item("m0", "message", "Reed", "Cut 2 seconds.", null, "2026-11-02T10:06:00Z")] };
  const calls = server(owner, done, delivered, { "POST /projects/50/director/messages": [201, noted], "POST /projects/50/director": [201, run()] });
  renderApp("/b/1/videos/50");
  const thread = await screen.findByRole("list", { name: "Thread" });
  expect(await within(thread).findByLabelText("The cut")).toHaveAttribute("src", "/api/files/8");
  expect(within(thread).getByText("Delivered.")).toBeInTheDocument();
  expect(within(thread).getByText("Every take checked clean.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Download MP4" })).toHaveAttribute("download", "bo-tries-salmon.mp4");
  await userEvent.type(screen.getByLabelText("Tell the director what to change"), "Cut 2 seconds.{Enter}");
  expect(await screen.findByText("Saved. Press Make it again to make this change.")).toBeInTheDocument();
  expect(within(thread).getByText("Cut 2 seconds.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Make it again · up to 40 credits" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/50/director")).toBe(true));
});

test("an editor's change waits for the owner: the last cut stays, the change's price shows, and Withdraw change takes it back", async () => {
  setViewport(1440);
  const waiting = fs({ status: "waiting", created_by_name: "Eli", file_id: 8, thread: [item("m1", "message", "Eli", SCRIPT), item("m2", "message", "Eli", "Punchier ending.", null, later), item("t3", "move", "Director", "Waiting for the owner's OK.", "held", later)] });
  const calls = server(editor, waiting, run({ turns: [{ turn: 0, tool: null, why: "", result: "", status: "needs_owner_approval", created_at: later }] }), { "POST /freestyles/9/withdraw": [200, { ...waiting, status: "delivered" }] });
  renderApp("/b/1/videos/50");
  expect(await screen.findByText("Change waiting for approval")).toBeInTheDocument();
  expect(screen.getByText("Change asked · waiting for the owner")).toBeInTheDocument();
  expect(screen.getByText("up to 40 credits")).toBeInTheDocument();
  expect(screen.getByText("Another change waits for the owner too.")).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/\$|Reed/);
  await userEvent.click(screen.getByRole("button", { name: "Withdraw change" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /freestyles/9/withdraw")).toBe(true));
});

test("made from a script, it shows the script and version it came from; the box opens once the owner approves", async () => {
  setViewport(1440);
  const script = { id: 3, title: "Bo tries salmon", created_at: "2026-10-30T10:00:00Z", versions: [{ slot: 1, project_id: null, text: SCRIPT, seconds: 35 }] };
  server(editor, fs({ status: "waiting", created_by_name: "Eli", thread: [item("m1", "message", "Eli", SCRIPT), item("t1", "move", "Director", "Waiting for the owner's OK.", "held")] }), run({ status: "none", turns: [] }), { "GET /scripts/3": [200, script], "GET /projects/50": [404, { detail: "No such project." }] });
  renderApp("/b/1/freestyle/9");
  expect(await screen.findByText("From script Bo tries salmon · version B")).toBeInTheDocument();
  expect(screen.getByText("0:35 · 1 line")).toBeInTheDocument();
  expect(screen.getByText("Bo tries salmon · B")).toBeInTheDocument();
  expect(screen.getByText("Opens once the owner approves")).toBeInTheDocument();
  expect(screen.queryByLabelText("Tell the director what to change")).toBeNull();
});

test("a treatment card: the hook as its title, the story, why it holds, numbered beats with their purpose, and Changed", () => {
  render(<TreatmentCard t={{ hook: "A dog gasps at salmon", story: "Bo finds salmon in his bowl.", why: "The reveal lands on the bag.", beats: [{ text: "Bo sniffs", purpose: "Hook" }, { text: "The bag", purpose: "Payoff" }], changed: true }} />);
  const card = screen.getByRole("region", { name: "Treatment" });
  expect(within(card).getByRole("heading", { name: "A dog gasps at salmon" })).toBeInTheDocument();
  expect(within(card).getByText("Changed")).toBeInTheDocument();
  expect(within(card).getByText("The reveal lands on the bag.")).toBeInTheDocument();
  expect(within(card).getAllByRole("listitem").map((l) => l.textContent)).toEqual(["1Bo sniffsHook", "2The bagPayoff"]);
});
