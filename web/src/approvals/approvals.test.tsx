import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const owner = { id: 1, email: "reed@b.co", name: "Reed", role: "owner", workspace_id: 1 };
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
};

function open(path = "/approvals") {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

test("an editor who opens Approvals gets Page not found and no calls for held work", async () => {
  const calls = fakeServer({ ...base, "GET /auth/me": [200, editor] });
  open();
  expect(await screen.findByText("Page not found.")).toBeInTheDocument();
  expect(calls.some((c) => c.key === "GET /jobs")).toBe(false);
});

test("a held job shows what it is, its credits and what it does to the budget, and Approve runs it", async () => {
  const calls = fakeServer({ ...base, "POST /jobs/50/approve": [200, held({ status: "queued" })] });
  open();
  expect(await screen.findByText("Approvals")).toBeInTheDocument();
  expect(await screen.findByText(/1 waiting · 27 credits/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Mia buys the dip" })).toHaveAttribute("href", "/b/1/projects/9");
  expect(screen.getByText(/27 credits · takes the project to 117% of its budget/)).toBeInTheDocument();
  expect(screen.getByText(/Over budget/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Approve Clip take" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /jobs/50/approve")).toBe(true));
  expect(await screen.findByText("Approved. Clip take is starting.")).toBeInTheDocument();
});

test("Decline asks first in a dialog, then cancels and says nothing was charged", async () => {
  const calls = fakeServer({ ...base, "GET /jobs": [200, [held({ created_by_name: "Sam" })]], "POST /jobs/50/cancel": [200, held({ status: "cancelled" })] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Decline Clip take" }));
  const ask = await screen.findByRole("alertdialog", { name: "Decline Sam's clip take?" });
  expect(within(ask).getByText(/Nothing is charged\. Sam can ask again\./)).toBeInTheDocument();
  await userEvent.click(within(ask).getByRole("button", { name: "Keep it" }));
  expect(calls.some((c) => c.key === "POST /jobs/50/cancel")).toBe(false);
  await userEvent.click(screen.getByRole("button", { name: "Decline Clip take" }));
  await userEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Decline" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /jobs/50/cancel")).toBe(true));
  expect(await screen.findByText("Declined. Nothing was charged.")).toBeInTheDocument();
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
  const button = await screen.findByRole("button", { name: /^Approve all · 67 credits/ });
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
  expect(await screen.findByText("Nothing waiting.")).toBeInTheDocument();
});

test("the owner sees a count on Approvals in the top bar and the rail; an editor sees no Approvals link", async () => {
  setViewport(1440);
  fakeServer({ ...base });
  open("/b/1/projects");
  const nav = await screen.findByRole("navigation", { name: "Main" });
  expect(await within(nav).findByRole("link", { name: /Approvals/ })).toHaveTextContent("1");
});

test("an editor's navigation has no Approvals", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /auth/me": [200, editor] });
  open("/b/1/projects");
  const nav = await screen.findByRole("navigation", { name: "Main" });
  await within(nav).findByRole("link", { name: "Scripts" });
  expect(within(nav).queryByRole("link", { name: /Approvals/ })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /Approvals/ })).not.toBeInTheDocument();
});

test("a Quick clip row says Quick clip once", async () => {
  fakeServer({ ...base, "GET /jobs": [200, [held({ id: 60, project_id: null, step: null, prompt_summary: "Mia hits the buy moment" })]] });
  open();
  await screen.findByText(/Mia hits the buy moment/);
  expect(within(screen.getByRole("list")).getAllByText("Quick clip")).toHaveLength(1);
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
  expect(await screen.findByText(/27 credits \(\$2\.36\) · takes the project to/)).toBeInTheDocument();
  expect(screen.getByText("asked by Jo")).toBeInTheDocument();
  expect(screen.getByText("To decline, ask Jo to shorten the plan.")).toBeInTheDocument();
});

test("an editor who opens Approvals sees no held work and no dollars", async () => {
  fakeServer({ ...base, "GET /auth/me": [200, editor], "GET /jobs": [200, [held({ created_by_name: "Sam" })]], "GET /jobs/50/detail": [200, held({ cost_usd: 2.36 })] });
  open("/approvals");
  expect(await screen.findByText("Page not found.")).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/\$/);
  expect(screen.queryByText(/Clip take/)).not.toBeInTheDocument();
});

test("a held Quick clip says why it is held: past the editor's weekly allowance", async () => {
  fakeServer({ ...base, "GET /jobs": [200, [held({ id: 60, project_id: null, step: null, kind: "video", created_by_name: "Sam", prompt_summary: "Mia hits the buy moment" })]], "GET /credits/limits": [200, { weekly_quick_clip_credits: 150, per_video_max_credits: 340 }] });
  open();
  expect(await screen.findByText("Past Sam's weekly allowance (150 credits)")).toBeInTheDocument();
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
