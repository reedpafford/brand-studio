import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";
import { owner } from "../test/people";

const editor = { ...owner, id: 2, name: "Eli", role: "editor" };
const brands = [{ id: 1, name: "fomo", colours: ["#ff0000"] }];
const project = { id: 9, brand_id: 1, name: "Mia buys the dip", planned_seconds: 30, status: "active", budget_credits: 100, credits_used: 90, budget_pct: 90, estimate_credits: 30 };
const now = new Date().toISOString();
const held = (o: object) => ({ id: 50, kind: "video", project_id: 9, credits: 27, status: "needs_owner_approval", created_at: now, finished_at: null, prompt_summary: "", step: "clip_take", brand_id: 1, ...o });
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, owner],
  "GET /brands": [200, brands],
  "GET /projects": [200, [project]],
  "GET /jobs": [200, [held({})]],
  "GET /production": [200, []],
  "GET /production/summary": [200, { in_production: 0, needs_attention: 0, changes_waiting: 0 }],
};

function open(path = "/approvals") {
  renderApp(path);
}

afterEach(() => vi.unstubAllGlobals());

test("an editor who opens Needs you lands on Home (their Videos), with no held work asked for", async () => {
  const calls = fakeServer({ ...base, "GET /auth/me": [200, editor], "GET /scripts": [200, []] });
  open();
  expect(await screen.findByRole("link", { name: "Videos", current: "page" })).toBeInTheDocument();
  expect(screen.queryByText("Page not found.")).toBeNull();
  expect(calls.some((c) => c.key === "GET /jobs/50/detail")).toBe(false);
});

test("a held job shows what it is, its credits and what it does to the budget, and Approve runs it", async () => {
  const calls = fakeServer({ ...base, "POST /jobs/50/approve": [200, held({ status: "queued" })] });
  open();
  expect(await screen.findByRole("heading", { name: "Needs you" })).toBeInTheDocument();
  expect(await screen.findByText(/Every brand · 1 thing · 1 request worth 27 credits/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Mia buys the dip" })).toHaveAttribute("href", "/b/1/projects/9");
  expect(screen.getByText(/27 credits · takes the video to 117% of its budget/)).toBeInTheDocument();
  expect(screen.getByText(/Over budget/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Approve a new take" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /jobs/50/approve")).toBe(true));
  expect(await screen.findByText("Approved. A new take is being made.")).toBeInTheDocument();
});

test("Decline asks first in a dialog, with an optional reason the editor sees, then declines and says nothing was charged", async () => {
  const calls = fakeServer({ ...base, "GET /jobs": [200, [held({ created_by_name: "Sam" })]], "POST /jobs/50/decline": [200, held({ status: "cancelled", declined: true })] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Decline a new take" }));
  const ask = await screen.findByRole("alertdialog", { name: "Decline a new take for Sam?" });
  expect(within(ask).getByText(/Nothing is charged\. Sam sees your reason and can ask again\./)).toBeInTheDocument();
  await userEvent.click(within(ask).getByRole("button", { name: "Keep it" }));
  expect(calls.some((c) => c.key === "POST /jobs/50/decline")).toBe(false);
  await userEvent.click(screen.getByRole("button", { name: "Decline a new take" }));
  const again = await screen.findByRole("alertdialog");
  await userEvent.type(within(again).getByLabelText("Reason (optional)"), "Over budget this week");
  await userEvent.click(within(again).getByRole("button", { name: "Decline" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /jobs/50/decline")?.body).toEqual({ reason: "Over budget this week" }));
  expect(await screen.findByText("Declined. Nothing was charged.")).toBeInTheDocument();
});

test("with nothing waiting, Needs you says held presses from editors show here (S42)", async () => {
  fakeServer({ ...base, "GET /jobs": [200, []], "GET /projects": [200, []] });
  open();
  expect(await screen.findByText(/an editor's press goes past a video's budget or their week, or they make songs, narration or music on a script, it waits here/)).toBeInTheDocument();
  expect(screen.queryByText(/never sent here/)).toBeNull();
});

test("Approve all asks with the total in credits and dollars, then approves every request", async () => {
  const calls = fakeServer({
    ...base,
    "GET /jobs": [200, [held({}), held({ id: 51, credits: 40 })]],
    "GET /jobs/50/detail": [200, { cost_usd: 2.36 }],
    "GET /jobs/51/detail": [200, { cost_usd: 3.5 }],
    "POST /jobs/50/approve": [200, held({ status: "queued" })],
    "POST /jobs/51/approve": [200, held({ id: 51, status: "queued" })],
  });
  open();
  const button = await screen.findByRole("button", { name: /^Approve all · up to 67 credits/ });
  await userEvent.click(button);
  const ask = await screen.findByRole("alertdialog", { name: /Approve 2 requests for 67 credits \(\$5\.86\)\?/ });
  expect(calls.some((c) => c.key.endsWith("/approve"))).toBe(false);
  await userEvent.click(within(ask).getByRole("button", { name: "Approve all" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key.endsWith("/approve"))).toHaveLength(2));
  expect(await screen.findByText("All done.")).toBeInTheDocument();
});

test("a held project has only Approve, says how to decline, and the toast counts the steps it started", async () => {
  const heldProject = { ...project, status: "needs_owner_approval", planned_seconds: 120 };
  const calls = fakeServer({
    ...base,
    "GET /projects": [200, [heldProject]],
    "GET /jobs": [200, [held({ id: 51 }), held({ id: 52 })]],
    "POST /projects/9/approve": [200, project],
  });
  open();
  expect(await screen.findByText(/Planned 120 s · budget 100 credits · 2 steps held inside/)).toBeInTheDocument();
  expect(screen.getByText(/To decline, ask whoever planned it/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Decline/ })).not.toBeInTheDocument();
  // The held jobs inside a held project are decided with it, so they are not separate rows.
  expect(screen.getAllByRole("listitem")).toHaveLength(1);
  await userEvent.click(screen.getByRole("button", { name: "Approve Mia buys the dip" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/approve")).toBe(true));
  // The fake server still lists both as held afterwards, so none started and both still need Reed.
  expect(await screen.findByText("Approved. 0 held steps started; 2 still need you.")).toBeInTheDocument();
});

test("with nothing waiting it says so", async () => {
  fakeServer({ ...base, "GET /jobs": [200, []], "GET /projects": [200, [project]] });
  open();
  expect(await screen.findByText("Nothing needs you.")).toBeInTheDocument();
});

test("the rail's Needs you counts held requests plus videos that need attention", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /production/summary": [200, { in_production: 3, needs_attention: 2, changes_waiting: 0 }] });
  open("/b/1/projects");
  const nav = await screen.findByRole("navigation", { name: "Main" });
  expect(await within(nav).findByRole("link", { name: /Needs you/ })).toHaveTextContent("3");
});

test("an editor's navigation has no Needs you", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /auth/me": [200, editor] });
  open("/b/1/projects");
  const nav = await screen.findByRole("navigation", { name: "Main" });
  await within(nav).findByRole("link", { name: "Scripts" });
  expect(within(nav).queryByRole("link", { name: /Needs you/ })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /Needs you/ })).not.toBeInTheDocument();
});

test("a Quick clip row says Quick clip once", async () => {
  fakeServer({ ...base, "GET /jobs": [200, [held({ id: 60, project_id: null, step: null, prompt_summary: "Mia hits the buy moment" })]] });
  open();
  await screen.findByText(/Mia hits the buy moment/);
  expect(within(screen.getByRole("list")).getAllByText("Quick clip")).toHaveLength(1);
});

const freestyle = (f: object = {}) =>
  held({ id: 70, project_id: null, step: null, created_by_id: 7, created_by_name: "Sam", prompt_summary: "Bo runs", freestyle: { id: 4, title: "Bo at the beach", type: "one_clip", said: "Bo runs\ninto the sea", change: false, ...f } });
const allowances: [number, unknown] = [200, [{ user_id: 7, name: "Sam", quick_clip_credits_used: 10, quick_clip_credits_allowed: 1 }]];

test("a held Freestyle row says Freestyle, its type and title, who asked, quotes the send and opens it (QA-9 on #1161)", async () => {
  fakeServer({ ...base, "GET /jobs": [200, [freestyle()]], "GET /credits/allowances": allowances });
  open();
  const list = await screen.findByRole("list");
  expect(await within(list).findByText("Freestyle · One clip · Bo at the beach")).toBeInTheDocument();
  expect(within(list).getByText(/asked by Sam, /)).toBeInTheDocument();
  expect(within(list).getByText("First send")).toBeInTheDocument();
  const said = within(list).getByText(/Bo runs/);
  expect(said.textContent).toBe('"Bo runs\ninto the sea"');
  expect(said).toHaveClass("whitespace-pre-line");
  expect(within(list).getByRole("link", { name: /^Open freestyle/ })).toHaveAttribute("href", "/freestyle/4");
  expect(within(list).getByRole("button", { name: "Approve freestyle" })).toBeInTheDocument();
  expect(within(list).getByRole("button", { name: "Decline freestyle" })).toBeInTheDocument();
  expect(list).not.toHaveTextContent("Quick clip");
  expect(screen.queryByText(/quick clips this week/)).toBeNull();
});

test("a held Dialogue freestyle says the whole price Reed's OK covers, in credits", async () => {
  fakeServer({ ...base, "GET /jobs": [200, [freestyle({ type: "dialogue", up_to: 33.2 })]] });
  open();
  expect(await screen.findByText("Freestyle · Dialogue · Bo at the beach")).toBeInTheDocument();
  expect(screen.getByText("Up to 34 credits · your OK covers the whole run")).toBeInTheDocument();
});

test("a held change in a Freestyle thread says Change asked", async () => {
  fakeServer({ ...base, "GET /jobs": [200, [freestyle({ change: true, said: "Make it sunset" })]] });
  open();
  expect(await screen.findByText("Change asked")).toBeInTheDocument();
  expect(screen.getByText('"Make it sunset"')).toBeInTheDocument();
  expect(screen.queryByText("First send")).toBeNull();
});

test("a held Freestyle change shows its own price and the running total, in credits", async () => {
  fakeServer({ ...base, "GET /jobs": [200, [freestyle({ type: "dialogue", change: true, said: "Slower ending", up_to: 12, total: 46, spent: 30 })]] });
  open();
  expect(await screen.findByText("Up to 12 credits for this change")).toBeInTheDocument();
  expect(screen.getByText("30 credits spent so far · 46 credits in all with this change")).toBeInTheDocument();
});

test("each row says who asked, and the owner sees the dollars next to the credits", async () => {
  fakeServer({
    ...base,
    "GET /jobs": [200, [held({ created_by_name: "Sam" })]],
    "GET /jobs/50/detail": [200, held({ created_by_name: "Sam", cost_usd: 2.36 })],
    "GET /projects": [200, [{ ...project, id: 11, name: "Big summer story", status: "needs_owner_approval", created_by_name: "Jo" }, project]],
  });
  open();
  expect(await screen.findByText(/asked by Sam, /)).toBeInTheDocument();
  expect(await screen.findByText(/27 credits \(\$2\.36\) · takes the video to/)).toBeInTheDocument();
  expect(screen.getByText("asked by Jo")).toBeInTheDocument();
  expect(screen.getByText("To decline, ask Jo to shorten the plan.")).toBeInTheDocument();
});

test("an editor who opens Needs you sees no held work and no dollars", async () => {
  fakeServer({ ...base, "GET /auth/me": [200, editor], "GET /jobs": [200, [held({ created_by_name: "Sam" })]], "GET /jobs/50/detail": [200, held({ cost_usd: 2.36 })] });
  open("/approvals");
  expect(await screen.findByRole("link", { name: "Videos", current: "page" })).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/\$/);
  expect(screen.queryByText(/A new take/)).not.toBeInTheDocument();
});

test("a held Quick clip says why it is held: that editor's week, from the allowances", async () => {
  fakeServer({ ...base, "GET /jobs": [200, [held({ id: 60, project_id: null, step: null, kind: "video", created_by_id: 7, created_by_name: "Sam", prompt_summary: "Mia hits the buy moment" })]], "GET /credits/allowances": [200, [{ user_id: 7, name: "Sam", quick_clip_credits_used: 10, quick_clip_credits_allowed: 1 }]] });
  open();
  expect(await screen.findByText("Sam's quick clips this week: 10 of 1 credit")).toBeInTheDocument();
});

test("if Approve all stops part way, the page refreshes and says how many went through", async () => {
  fakeServer({
    ...base,
    "GET /jobs": [200, [held({}), held({ id: 51, credits: 40 })]],
    "POST /jobs/50/approve": [200, held({ status: "queued" })],
    "POST /jobs/51/approve": [409, { detail: "Over this week's limit." }],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: /^Approve all/ }));
  await userEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Approve all" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("1 of 2 went through. Over this week's limit.");
});

test("at 390, a row's video link is a 44 px target (QA sweep)", async () => {
  setViewport(390);
  fakeServer(base);
  open();
  const link = await screen.findByRole("link", { name: "Mia buys the dip" });
  expect(link.className).toContain("min-h-11"); // 44 px on a phone; its text size on desktop
});

test("a link to one request (?job=51, from the page it waits on) lands on that row, marked and focused", async () => {
  fakeServer({ ...base, "GET /jobs": [200, [held({}), held({ id: 51, step: "frame", credits: 3 })]] });
  open("/approvals?job=51");
  const row = (await screen.findByRole("button", { name: "Approve a new still" })).closest("li")!;
  await vi.waitFor(() => expect(row).toHaveFocus());
  expect(row).toHaveAttribute("aria-current", "true");
  expect(screen.getByRole("button", { name: "Approve a new take" }).closest("li")).not.toHaveAttribute("aria-current");
});

test("a held request's '% of its budget' leaves the director's own time out, as the hold check does", async () => {
  fakeServer({ ...base, "GET /projects": [200, [{ ...project, credits_used: 90, director_credits: 60 }]] });
  open();
  expect(await screen.findByText(/27 credits · takes the video to 57% of its budget/)).toBeInTheDocument(); // (90 − 60 + 27) / 100
});

const stuckRow = { project_id: 21, brand: { id: 1, name: "fomo" }, script: { id: 3, title: "Treat time" }, letter: "A", editor: { id: 7, name: "Dee" }, step: "assets", last_activity_at: now, credits_used: 5, budget_credits: 100, spent_usd: 0.5, poster_file_id: null, flag: "idle", flag_since: new Date(Date.now() - 3 * 86_400_000).toISOString() };
const done = { project_id: 22, title: "Bo tries salmon · B", script_id: 4, version_letter: "B", legacy: false, person: { id: 7, name: "Dee" }, status: "done", spend_usd: 1, spend_estimated: false, credits: 10, finished_at: now, last_activity_at: now };

test("one list across brands, with tabs: a stuck video and a finished one with changes each open their video", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /production": [200, [stuckRow]],
    "GET /production/summary": [200, { in_production: 1, needs_attention: 1, changes_waiting: 1 }],
    "GET /usage/brands/1/videos": [200, { total: 2, next_cursor: null, people: [], items: [{ ...done, final_out_of_date: true }, { ...done, project_id: 23, final_out_of_date: false }] }],
  });
  open();
  const tabs = await screen.findByRole("tablist", { name: "Show" });
  expect(within(tabs).getAllByRole("tab").map((t) => t.textContent)).toEqual(["All 3", "Requests 1", "Stuck 1", "Changes waiting 1"]);
  expect(screen.getByText("Every brand · 3 things · 1 request worth 27 credits")).toBeInTheDocument();
  expect(screen.getAllByRole("listitem")).toHaveLength(3);
  expect(calls.find((c) => c.key === "GET /production")).toBeTruthy();
  await userEvent.click(within(tabs).getByRole("tab", { name: "Stuck 1" }));
  expect(screen.getAllByRole("listitem")).toHaveLength(1);
  expect(screen.getByText("No activity")).toBeInTheDocument(); // a dot and words
  expect(screen.getByText("At Cast · Nothing for 3 days · Dee")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open video Treat time · A" })).toHaveAttribute("href", "/b/1/videos/21");
  await userEvent.click(within(tabs).getByRole("tab", { name: "Changes waiting 1" }));
  expect(screen.getAllByRole("listitem")).toHaveLength(1); // only the out-of-date one
  expect(screen.getByRole("link", { name: "Open video Bo tries salmon · B" })).toHaveAttribute("href", "/b/1/videos/22?step=final");
  await userEvent.click(within(tabs).getByRole("tab", { name: "Requests 1" }));
  expect(screen.getByRole("button", { name: "Approve a new take" })).toBeInTheDocument();
});

test("the brands' video lists are read only when the summary says changes wait; an empty tab says so", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /jobs": [200, []] });
  open("/approvals?tab=stuck");
  expect(await screen.findByText("Nothing is stuck.")).toBeInTheDocument();
  expect(calls.some((c) => c.key.startsWith("GET /usage/"))).toBe(false);
});
