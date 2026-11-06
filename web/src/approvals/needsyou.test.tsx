import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";
import { owner } from "../test/people";

const editor = { ...owner, id: 2, name: "Kel", role: "editor" };
const brands = [{ id: 1, name: "Resilia", colours: ["#2f7a4f"] }, { id: 2, name: "fomo", colours: ["#ff0000"] }];
const ago = (min: number) => new Date(Date.now() - min * 60_000).toISOString();
const resilia = { id: 1, name: "Resilia" };
const video = (id: number, title: string, o: object = {}) => ({ id, title, still_file_id: id * 10, made_by: "Reed", send: false, about: "", ...o });
const card = (o: object) => ({ topic: "", why: "", state: "open", by_owner: false, saved_in: "", saved: [], pick: null, choices: [], decide_at: null, generate: null, clone: null, options: [], options_spent: null, answer: null, answered_by: "", answered_at: null, closed: "", money: null, can: [], ...o });
const price = (usd: number, credits = usd * 10) => ({ credits, usd });
const question = {
  video: video(11, "Bloated after pizza"),
  brand: resilia,
  ask: card({ id: 101, project_id: 11, kind: "presenter", question: "Who should be the presenter?", pick: "item:5", created_at: ago(12),
    saved: [{ id: "item:5", name: "Mark", note: "", file_id: 501, used_in: 6 }, { id: "item:6", name: "Dana", note: "", file_id: 502, used_in: 2 }],
    can: ["reply", "saved", "upload"] }),
};
const money = (sent: string) => ({ up_to: price(2.1), spent: price(16.3), budget: price(16.86), past: price(1.54), usual: null, clips: [{ clip: "9", still_file_id: null }, { clip: "12", still_file_id: null }], sent_at: sent, held: "", what: "Redo clips 9 and 12", over: "the budget" });
const budget = {
  video: video(12, "Why IPAs hit harder", { made_by: "Kel" }),
  brand: resilia,
  ask: card({ id: 102, project_id: 12, kind: "budget", question: "Redo clips 9 and 12? That goes $1.54 past the budget.", why: "Redoing them takes this video to up to $18.40 ($16.30 spent plus up to $2.10); its budget is $16.86.",
    money: money(ago(31)), can: ["approve", "keep"], created_at: ago(31) }),
};
const start = {
  video: video(13, "Gut check", { made_by: "Kel", send: true, about: "Pasted script, Skeleton style, 45 s" }),
  brand: resilia,
  ask: card({ id: 103, project_id: 13, kind: "start", question: "Make it for up to $16.40?", money: { ...money(ago(60)), up_to: price(16.4), past: null, what: "" }, can: ["make_it", "decline"], created_at: ago(60) }),
};
const stuck = {
  video: video(14, "Night-time bloat"),
  brand: resilia,
  at: ago(120),
  what: "Clip 4 couldn’t be made",
  why: "It’s 115 s; the model makes 12 s. Split it at the sentence breaks (free).",
  fix: { kind: "split", label: "Split it", price: "free", clip_id: 40, frame_id: null, problem: "clip c4: 115 s is outside 4–12 s" },
};
const inbox = { total: 4, brands: [{ ...resilia, count: 4 }, { id: 2, name: "fomo", count: 0 }], questions: [question], money: [budget, start], sends: [], stuck: [stuck] };
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, owner],
  "GET /brands": [200, brands],
  "GET /needs-you": [200, inbox],
};

afterEach(() => vi.unstubAllGlobals());

test("S9-01: the owner's inbox across brands, Questions, Money and Stuck, with the brand filter and its counts", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /needs-you?brand_id=2": [200, { ...inbox, questions: [], money: [], stuck: [] }] });
  renderApp("/approvals");
  expect(await screen.findByRole("heading", { name: "Needs you", level: 1 })).toBeInTheDocument();
  expect(screen.getByText(/Answer here or in the video’s chat; it’s the same answer\./)).toBeInTheDocument();
  expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual(["Questions", "Money", "Stuck"]);
  const filter = screen.getByRole("radiogroup", { name: "Brand" });
  expect(within(filter).getAllByRole("radio").map((r) => r.textContent)).toEqual(["All brands", "Resilia4", "fomo0"]);
  // The budget card: what it makes, how far past, whose video, and the one indigo press.
  expect(screen.getByRole("heading", { name: "Redo clips 9 and 12 · $1.54 past the budget" })).toBeInTheDocument();
  expect(screen.getByText(/^Kel’s video\. Redoing them takes this video to up to \$18\.40 \(\$16\.30 spent plus up to \$2\.10\)/)).toBeInTheDocument();
  const approve = screen.getByRole("button", { name: "Approve · up to $2.10 more" });
  expect(approve.className).toContain("bg-accent");
  // An editor's send: whose, what, and nothing spent until the owner approves.
  expect(screen.getByText("Gut check (Kel’s send)")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Kel’s new video · up to $16.40" })).toBeInTheDocument();
  expect(screen.getByText("Pasted script, Skeleton style, 45 s. Nothing is spent until you approve.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Approve and start" }).className).not.toContain("bg-accent"); // one indigo press
  expect(screen.getByRole("link", { name: "Read the script: Gut check" })).toHaveAttribute("href", "/b/1/videos/13?tab=script");
  expect(screen.getByRole("button", { name: "Split it · free" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Approve all/ })).toBeNull(); // rule 21
  await userEvent.click(within(filter).getByRole("radio", { name: "fomo0" }));
  await vi.waitFor(() => expect(calls.some((c) => c.url.endsWith("/needs-you?brand_id=2"))).toBe(true));
  expect(await screen.findByText("Nothing needs you in fomo.")).toBeInTheDocument();
});

test("answering a question here is the same answer as in the chat: Use Mark, or pick another first", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "POST /asks/101/answer": [200, { ...question.ask, state: "answered" }] });
  renderApp("/approvals");
  const mark = await screen.findByRole("button", { name: "Mark" });
  expect(mark).toHaveAttribute("aria-pressed", "true"); // the director's pick
  await userEvent.click(screen.getByRole("button", { name: "Dana" }));
  await userEvent.click(screen.getByRole("button", { name: "Use Dana" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /asks/101/answer")?.body).toEqual({ how: "saved", option: "item:6" }));
  expect(await screen.findByText("Answered. The director carries on.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open the chat: Bloated after pizza" })).toHaveAttribute("href", "/b/1/videos/11");
});

test("the one indigo press is the first money card the owner can approve", async () => {
  setViewport(1440);
  const theirs = { ...budget, ask: { ...budget.ask, id: 104, can: [] } }; // an editor's own: nothing to press here
  fakeServer({ ...base, "GET /needs-you": [200, { ...inbox, money: [theirs, start] }] });
  renderApp("/approvals");
  expect((await screen.findByRole("button", { name: "Approve and start" })).className).toContain("bg-accent");
});

test("money presses answer the card: Approve, Decline (keeps it as it is), and Approve and start an editor's send", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "POST /asks/102/answer": [200, budget.ask], "POST /asks/103/answer": [200, start.ask] });
  renderApp("/approvals");
  await userEvent.click(await screen.findByRole("button", { name: "Approve · up to $2.10 more" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /asks/102/answer").map((c) => c.body)).toEqual([{ how: "approve" }]));
  const money = within(screen.getByRole("region", { name: "Money" }));
  await userEvent.click(money.getAllByRole("button", { name: "Decline" })[0]);
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /asks/102/answer").map((c) => c.body)).toEqual([{ how: "approve" }, { how: "keep" }]));
  await userEvent.click(screen.getByRole("button", { name: "Approve and start" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /asks/103/answer")?.body).toEqual({ how: "make_it" }));
});

test("a stuck video's one-click fix runs the same press as its card in the chat", async () => {
  setViewport(1440);
  const again = { ...stuck, fix: { kind: "again", label: "Try again", price: "$0.42", clip_id: 40, frame_id: null, problem: null } };
  const calls = fakeServer({
    ...base,
    "GET /needs-you": [200, { ...inbox, questions: [], money: [], stuck: [stuck, { ...again, video: video(15, "Gut glow-up") }] }],
    "POST /projects/14/breakdown/fix": [200, {}],
    "POST /projects/15/clips/40/generate": [201, { id: 9 }],
  });
  renderApp("/approvals");
  await userEvent.click(await screen.findByRole("button", { name: "Split it · free" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/14/breakdown/fix")?.body).toEqual({ problems: ["clip c4: 115 s is outside 4–12 s"] }));
  await userEvent.click(screen.getByRole("button", { name: "Try again · up to $0.42" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/15/clips/40/generate")).toBe(true));
});

test("a stopped run carries on, and a failed still is drawn again, each at its price", async () => {
  setViewport(1440);
  const carry = { ...stuck, video: video(16, "Gut glow-up"), what: "The director stopped", fix: { kind: "carry_on", label: "Carry on", price: "$10.74", clip_id: null, frame_id: null, problem: null } };
  const redraw = { ...stuck, video: video(17, "3 signs your gut is angry"), what: "Clip 2's still couldn’t be made", fix: { kind: "redraw", label: "Draw it again", price: "$0.04", clip_id: null, frame_id: 8, problem: null } };
  const calls = fakeServer({
    ...base,
    "GET /needs-you": [200, { ...inbox, questions: [], money: [], stuck: [carry, redraw] }],
    "POST /projects/16/director": [201, {}],
    "POST /projects/17/storyboard/frames/8/render": [201, { id: 3 }],
  });
  renderApp("/approvals");
  await userEvent.click(await screen.findByRole("button", { name: "Carry on · up to $10.74" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/16/director")).toBe(true));
  await userEvent.click(screen.getByRole("button", { name: "Draw it again · up to $0.04" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/17/storyboard/frames/8/render")).toBe(true));
});

test("a press held outside any video waits under Money, and a link to it lands on it", async () => {
  setViewport(1440);
  const send = { job_id: 50, brand: resilia, what: "Gut · song", made_by: "Kel", up_to: price(0.8), held: "Waiting for the owner's OK: songs on a script.", at: ago(5), script_id: 7 };
  const calls = fakeServer({ ...base, "GET /needs-you": [200, { ...inbox, total: 1, questions: [], money: [], stuck: [], sends: [send] }], "POST /jobs/50/decline": [200, {}], "POST /jobs/50/approve": [200, {}] });
  renderApp("/approvals?job=50");
  expect(await screen.findByRole("heading", { name: "Gut · song · up to $0.80" })).toBeInTheDocument();
  expect(document.getElementById("job-50")).toHaveFocus();
  expect(screen.getByRole("button", { name: "Approve · up to $0.80" }).className).toContain("bg-accent");
  expect(screen.getByRole("link", { name: "Read the script" })).toHaveAttribute("href", "/b/1/scripts/7");
  await userEvent.click(screen.getByRole("button", { name: "Approve · up to $0.80" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /jobs/50/approve")).toBe(true));
  await userEvent.click(screen.getByRole("button", { name: "Decline" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /jobs/50/decline")?.body).toEqual({ reason: "" }));
});

test("P-14: on a phone, every card in one list with its short presses, \"4 waiting · every brand\", no filter", async () => {
  setViewport(390);
  fakeServer(base);
  renderApp("/approvals");
  expect(await screen.findByText("4 waiting · every brand")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Needs you", level: 1 }).closest("header")).toHaveClass("border-b"); // P-14's header bar
  expect(screen.queryByRole("radiogroup", { name: "Brand" })).toBeNull();
  expect(screen.queryByRole("heading", { level: 2 })).toBeNull();
  expect(screen.getByRole("heading", { name: "Redo 2 clips · $1.54 past the budget" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Approve · up to $2.10" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Start it · up to $16.40" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Approve · up to $16.40" })).toBeInTheDocument();
  expect(screen.getByText("Gut check, Kel’s send · Resilia")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open the chat: Bloated after pizza" })).toHaveTextContent("Open");
});

test("an editor never sees Needs you: the address takes them to My requests", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /auth/me": [200, editor], "GET /jobs": [200, []], "GET /projects": [200, []] });
  renderApp("/approvals");
  expect(await screen.findByRole("heading", { name: "My requests" })).toBeInTheDocument();
  expect(calls.some((c) => c.key === "GET /needs-you")).toBe(false);
});

test("with nothing waiting, it says so", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /needs-you": [200, { total: 0, brands: [{ ...resilia, count: 0 }], questions: [], money: [], sends: [], stuck: [] }] });
  renderApp("/approvals");
  expect(await screen.findByText("Nothing needs you.")).toBeInTheDocument();
});

test("rule 34: on a later run the budget card goes past that run's own approved price, in its own figures", async () => {
  setViewport(1440);
  const later = { ...budget, ask: { ...budget.ask, why: "Redoing them takes this run to up to $3.10 ($2.20 spent in this run plus up to $0.90); this run's approved price is $2.50.",
    money: { ...money(ago(31)), spent: price(2.2), up_to: price(0.9), budget: price(2.5), past: price(0.6), over: "the $2.50 approved for this run" } } };
  fakeServer({ ...base, "GET /needs-you": [200, { ...inbox, questions: [], stuck: [], money: [later] }] });
  renderApp("/approvals");
  expect(await screen.findByRole("heading", { name: "Redo clips 9 and 12 · $0.60 past the $2.50 approved for this run" })).toBeInTheDocument();
  expect(screen.getByText(/this run's approved price is \$2\.50\.$/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Approve · up to $0.90 more" })).toBeInTheDocument();
});

test("rule 34 on a phone: a later run's budget card is titled shorter, past this run's price", async () => {
  setViewport(390);
  const later = { ...budget, ask: { ...budget.ask, money: { ...money(ago(31)), past: price(0.6), over: "the $2.50 approved for this run" } } };
  fakeServer({ ...base, "GET /needs-you": [200, { ...inbox, questions: [], stuck: [], money: [later] }] });
  renderApp("/approvals");
  expect(await screen.findByRole("heading", { name: "Redo 2 clips · $0.60 past this run’s price" })).toBeInTheDocument();
});

test("S2-04: an editor's New video waiting for the owner is in My requests with its up to, counted in the rail", async () => {
  setViewport(1440);
  const send = { id: 31, status: "needs_owner_approval", project_id: 13, credits: 3, kind: "write-claude", step: "director", created_at: ago(5), held: "Waiting for the owner's OK: every freestyle send is checked first.", freestyle: { id: 9, title: "Gut check", change: false, up_to: 164, total: 164 } };
  const calls = fakeServer({ ...base, "GET /auth/me": [200, editor], "GET /jobs": [200, [send]], "GET /projects": [200, []] });
  renderApp("/requests");
  expect(await screen.findByText("Gut check")).toBeInTheDocument();
  expect(screen.getByText(/^New video, waiting for the owner's OK/)).toHaveTextContent(/164 credits$/);
  expect(calls.find((c) => c.key === "GET /jobs")?.url).toContain("freestyle=true"); // sends are requests too
  expect(within(screen.getByRole("navigation", { name: "Main" })).getByRole("link", { name: /My requests/ })).toHaveTextContent("1");
});
