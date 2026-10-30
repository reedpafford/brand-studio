import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";
import { owner } from "../test/people";

const editor = { ...owner, id: 2, name: "Sam", role: "editor" };
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, owner],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /scripts": [200, []],
  "GET /projects": [200, []],
};
const summary = { period: "week", starts_at: "2026-10-19T00:00:00Z", previous: { spend_usd: 71.72, finished: 4, cost_per_finished_usd: 12.25 }, spend_usd: 84.12, spend_estimated: false, finished: 6, cost_per_finished_usd: 11.4, in_progress: 9, unassigned_spend_usd: 1.2 };
const row = (o: object = {}) => ({ brand_id: 1, name: "Iron Paws", colour: "#3a7", archived: false, spend_usd: 52.3, spend_estimated: false, finished: 4, cost_per_finished_usd: 11.05, in_progress: 3, scripts: 12, versions_left: 7, last_activity_at: new Date(Date.now() - 2 * 3600_000).toISOString(), ...o });
const brands = (items: object[], total = items.length, next: string | null = null) => ({ total, next_cursor: next, items });

function open(path = "/usage") {
  renderApp(path);
}
afterEach(() => vi.unstubAllGlobals());

test("Usage: four totals with the comparison, and a row per brand that links to it; a new brand shows zeros and a dash", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /usage/summary": [200, summary],
    "GET /usage/brands": [200, brands([row(), row({ brand_id: 2, name: "fomo", spend_usd: 30.62, spend_estimated: true, finished: 2, cost_per_finished_usd: 12.1 }), row({ brand_id: 3, name: "Night Owl", spend_usd: 0, finished: 0, cost_per_finished_usd: null, in_progress: 0, scripts: 0, versions_left: 0, last_activity_at: null })])],
  });
  open();
  const totals = await screen.findByRole("group", { name: "Totals" });
  expect(await within(totals).findByText("$84.12")).toBeInTheDocument();
  expect(within(totals).getByText("+$12.40 on last week")).toBeInTheDocument();
  expect(within(totals).getByText("6 videos")).toBeInTheDocument();
  expect(within(totals).getByText("+2 on last week")).toBeInTheDocument();
  expect(within(totals).getByText("−$0.85 on last week")).toBeInTheDocument();
  expect(screen.getByText(/^Week of \d+ Oct$/)).toBeInTheDocument();
  const link = await screen.findByRole("link", { name: "Iron Paws: $52.30 spent, 4 finished" });
  expect(link).toHaveAttribute("href", "/usage/brands/1");
  expect(screen.getByText("≈ $30.62")).toHaveAttribute("title", expect.stringMatching(/estimate/));
  const owl = screen.getByRole("link", { name: "Night Owl: $0.00 spent, 0 finished" }).closest("tr")!;
  expect(within(owl).getAllByText("—")).toHaveLength(2); // no cost per video, no last activity
  expect(screen.getByText("3 brands")).toBeInTheDocument();
  expect(screen.getByText("Not tied to one brand: $1.20 · character looks used by several brands")).toBeInTheDocument();
});

test("Usage: the period, search and sort live in the address and go to the server; Show more asks for the next 25", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /usage/summary": [200, { ...summary, previous: null, period: "all" }],
    "GET /usage/brands": [200, brands([row()], 40, "c2")],
  });
  open("/usage?period=all&sort=name");
  await screen.findByRole("link", { name: /Iron Paws/ });
  expect(screen.getByLabelText("Sort")).toHaveValue("name");
  expect(screen.queryByText(/on last/)).not.toBeInTheDocument(); // All time compares with nothing
  await userEvent.type(screen.getByRole("searchbox"), "iron");
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "GET /usage/brands").length).toBeGreaterThan(1));
  await userEvent.click(await screen.findByRole("button", { name: "Show more" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "GET /usage/brands").length).toBeGreaterThan(2));
});

test("Usage on a phone: brand cards with the sentence, and one Filters button for sort and archived", async () => {
  fakeServer({ ...base, "GET /usage/summary": [200, summary], "GET /usage/brands": [200, brands([row()])] });
  open();
  const card = await screen.findByRole("link", { name: "Iron Paws: $52.30 spent, 4 finished" });
  expect(within(card).getByText(/\$52\.30 spent · 4 finished · \$11\.05 each/)).toBeInTheDocument();
  expect(within(card).getByText("3 in progress · 12 scripts · 7 versions left")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Filters" }));
  const sheet = await screen.findByRole("dialog", { name: "Filters" });
  expect(within(sheet).getByLabelText("Sort")).toHaveValue("spend");
  expect(within(sheet).getByLabelText("Show archived")).not.toBeChecked();
});

const mine = {
  credits: 61, quick_clip_credits: 8, script_credits: 3,
  videos: [
    { project_id: 9, title: "Bo tries salmon · B", status: "in_production", credits: 40, budget_credits: 600, folder_id: null, finished_at: null, last_activity_at: "2026-10-28T10:00:00Z" },
    { project_id: 10, title: "Kimchi at the vet · A", status: "done", credits: 10, budget_credits: 120, folder_id: null, finished_at: "2026-10-27T10:00:00Z", last_activity_at: "2026-10-27T10:00:00Z" },
  ],
  projects: [], scripts: [{ script_id: 7, title: "Bo tries salmon", credits: 3 }],
  week: { used: 72, allowance: 145, lines: [{ label: "Videos", credits: 50 }, { label: "Quick clips", credits: 8 }, { label: "Scripts", credits: 3 }, { label: "A look", credits: 11 }] },
};

test("Usage: an editor is sent to My credits, which lists their week, videos, quick clips and scripts in credits, never a dollar (OR4)", async () => {
  setViewport(390);
  fakeServer({ ...base, "GET /auth/me": [200, editor], "GET /usage/summary": [404, { detail: "Not found" }], "GET /usage/brands": [404, { detail: "Not found" }], "GET /usage/mine": [200, mine] });
  const urls = () => (fetch as unknown as { mock: { calls: [Request | string][] } }).mock.calls.map(([r]) => (typeof r === "string" ? r : r.url)).filter((u) => u.includes("/usage/mine"));
  open();
  expect(await screen.findByRole("heading", { name: "My credits" })).toBeInTheDocument();
  expect(await screen.findByText("72 credits of 145 credits used")).toBeInTheDocument();
  const week = screen.getByRole("list", { name: "This week's charges" });
  expect(within(week).getAllByRole("listitem").map((li) => li.textContent)).toEqual(["Videos50 credits", "Quick clips8 credits", "Scripts3 credits", "A look11 credits"]);
  const videos = screen.getByRole("list", { name: "My videos" });
  expect(within(videos).getByRole("link", { name: /Bo tries salmon · B.*Being made.*40 credits of 600 credits/ })).toHaveAttribute("href", "/b/1/videos/9");
  expect(within(videos).getByText("Finished")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: 'Writing "Bo tries salmon"' })).toHaveAttribute("href", "/b/1/scripts/7");
  expect(document.body.textContent).not.toMatch(/\$/);
  expect(urls()[0]).toContain("brand_id=1");
  await userEvent.click(screen.getByRole("radio", { name: "This month" }));
  await vi.waitFor(() => expect(urls().some((u) => u.includes("period=month"))).toBe(true));
});

test("Usage: an editor's account menu links My credits; the owner's links Usage instead", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /auth/me": [200, editor], "GET /usage/mine": [200, mine] });
  open("/b/1/videos");
  await userEvent.click(await screen.findByRole("button", { name: "Account menu" }));
  expect(screen.getByRole("link", { name: "My credits" })).toHaveAttribute("href", "/usage/mine");
  expect(screen.queryByRole("link", { name: "Usage" })).toBeNull();
});

test("Usage: nothing spent says so, and no brands has its own words", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /usage/summary": [200, { ...summary, spend_usd: 0, finished: 0, cost_per_finished_usd: null, in_progress: 0, unassigned_spend_usd: 0, previous: null }], "GET /usage/brands": [200, brands([])] });
  open();
  expect(await screen.findByText("Nothing was spent this week.")).toBeInTheDocument();
  expect(await screen.findByText("No brands yet.")).toBeInTheDocument();
});

test("One brand's Usage: its own totals and the line under them", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /usage/summary": [200, summary], "GET /usage/brands/1": [200, { ...row(), previous: { spend_usd: 44.2, finished: 3, cost_per_finished_usd: 12.25 }, editors_active: 3 }] });
  open("/usage/brands/1");
  expect(await screen.findByRole("heading", { name: "Iron Paws" })).toBeInTheDocument();
  expect(await within(screen.getByRole("group", { name: "Totals" })).findByText("$52.30")).toBeInTheDocument();
  expect(screen.getByText("12 scripts · 7 versions left to make · 3 people made videos this week")).toBeInTheDocument();
  expect(within(screen.getByRole("main")).getByRole("link", { name: "Usage" })).toHaveAttribute("href", "/usage");
});

test("the rail has Usage for Reed", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /usage/summary": [200, summary], "GET /usage/brands": [200, brands([])] });
  open("/b/1/scripts");
  expect(await screen.findByRole("link", { name: "Usage" })).toHaveAttribute("href", "/usage");
});

const video = (o: object = {}) => ({ project_id: 31, title: "Bo tries salmon", script_id: 7, version_letter: "B", legacy: false, person: { id: 2, name: "Sam" }, status: "done", spend_usd: 11.8, spend_estimated: false, credits: 134, finished_at: "2026-10-21T10:00:00Z", last_activity_at: "2026-10-21T10:00:00Z", ...o });
const brandBase = (extra: Record<string, [number, unknown]> = {}) => ({
  ...base,
  "GET /usage/summary": [200, summary] as [number, unknown],
  "GET /usage/brands/1": [200, { ...row(), previous: null, editors_active: 3 }] as [number, unknown],
  "GET /usage/brands/1/videos": [200, { total: 31, next_cursor: null, people: [{ id: 2, name: "Sam" }], items: [video(), video({ project_id: 32, title: "Paws launch", version_letter: null, script_id: null, legacy: true, person: { id: 1, name: "Reed" }, status: "failed", spend_usd: 3.1, credits: 35, finished_at: null })] }] as [number, unknown],
  "GET /usage/brands/1/scripts": [200, { total: 12, next_cursor: null, authors: [{ id: 1, name: "Reed" }], items: [{ id: 7, brand_id: 1, title: "Bo tries salmon", description: "", reference_id: null, published: true, status: "published", created_by_id: 1, created_by_name: "Reed", created_at: "2026-10-20T10:00:00Z", versions_left: 1, spend_usd: 19.4, spend_estimated: false, changed_at: "2026-10-23T10:00:00Z", versions: [{ slot: 0, status: "done", title: "", seconds: 0, project_id: 31 }, { slot: 1, status: "in_production", title: "", seconds: 0, project_id: 33, editor: { id: 2, name: "Sam" } }, { slot: 2, status: "approved", title: "", seconds: 0, project_id: null }] }] }] as [number, unknown],
  ...extra,
});

test("One brand's Videos: a row per video with who, status in words, the whole video's spend, and the period says which videos", async () => {
  setViewport(1440);
  fakeServer(brandBase());
  open("/usage/brands/1");
  expect(await screen.findByRole("tab", { name: "Videos 31" })).toHaveAttribute("aria-selected", "true");
  expect(await screen.findByRole("tab", { name: "Scripts 12" })).toBeInTheDocument();
  const done = (await screen.findByRole("link", { name: "Bo tries salmon · B" })).closest("tr")!;
  expect(within(done).getByText("Sam")).toBeInTheDocument();
  expect(within(done).getByText("Finished")).toBeInTheDocument();
  expect(within(done).getByText("$11.80")).toBeInTheDocument();
  expect(within(done).getByText("134")).toBeInTheDocument();
  expect(screen.getByText("(earlier way)")).toBeInTheDocument();
  expect(within(screen.getByRole("table")).getByText("Didn't finish")).toBeInTheDocument();
  expect(screen.getByText("Videos with activity this week · 31")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Bo tries salmon · B" })).toHaveAttribute("href", "/b/1/projects/31");
});

test("One brand's Scripts tab: author, version chips that open what the library opens, versions left, spend", async () => {
  setViewport(1440);
  fakeServer(brandBase());
  open("/usage/brands/1?tab=scripts");
  const script = (await screen.findByRole("link", { name: "Bo tries salmon" })).closest("li")!;
  expect(script.querySelector("a[href='/b/1/scripts/7?step=publish']")).not.toBeNull();
  expect(within(script).getByText("Reed")).toBeInTheDocument();
  expect(within(script).getByText("1 left")).toBeInTheDocument();
  expect(within(script).getByText("$19.40")).toBeInTheDocument();
  expect(within(script).getByLabelText("Version A, finished").closest("a")).toHaveAttribute("href", "/b/1/projects/31");
  expect(within(script).getByLabelText("Version B, in production by Sam")).toBeInTheDocument();
  expect(within(script).getByLabelText("Version C, ready to make").closest("a")).toHaveAttribute("href", "/b/1/scripts?make=7.2");
});

test("Every charge is closed until opened, then lists the charges in plain words and asks for more", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /usage/summary": [200, summary],
    "GET /usage/brands": [200, brands([row()])],
    "GET /usage/charges": [200, { next_cursor: "c2", items: [{ at: "2026-10-24T10:00:00Z", person: { id: 2, name: "Sam" }, brand: { id: 1, name: "Iron Paws" }, what: "Clip 3 take 2 · Bo tries salmon · B", credits: 27, cost_usd: 2.36, estimated: false, status: "succeeded" }] }],
  });
  open();
  await screen.findByRole("link", { name: /Iron Paws/ });
  expect(calls.some((c) => c.key === "GET /usage/charges")).toBe(false);
  await userEvent.click(screen.getByText("Every charge"));
  expect(await screen.findByText("Clip 3 take 2 · Bo tries salmon · B")).toBeInTheDocument();
  expect(screen.getByText("$2.36")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Show more" })).toBeInTheDocument();
});

test("Usage cards say '1 version left' and '1 script' in the singular, and a brand with no colour gets a neutral dot", async () => {
  fakeServer({ ...base, "GET /usage/summary": [200, summary], "GET /usage/brands": [200, brands([row({ scripts: 1, versions_left: 1, colour: null })])] });
  open();
  const card = await screen.findByRole("link", { name: /Iron Paws/ });
  expect(within(card).getByText("3 in progress · 1 script · 1 version left")).toBeInTheDocument();
  expect(card.querySelector("span[aria-hidden].bg-faint")).not.toBeNull();
});

test("a finished video whose clips changed since says Finished · changes waiting in Usage, not plain Finished (#749 LW2)", async () => {
  setViewport(390);
  fakeServer(brandBase({ "GET /usage/brands/1/videos": [200, { total: 2, next_cursor: null, people: [], items: [video({ title: "Bo tries salmon · B", status: "done", finished_at: "2026-10-24T10:00:00Z", final_out_of_date: true }), video({ project_id: 33, title: "Bo tries cod · C", status: "done", finished_at: "2026-10-24T10:00:00Z", final_out_of_date: false })] }] }));
  open("/usage/brands/1");
  const changed = await screen.findByRole("link", { name: /Bo tries salmon · B/ });
  expect(within(changed).getByText("Finished · changes waiting")).toBeInTheDocument();
  expect(within(changed).queryByText("Finished")).toBeNull();
  expect(within(screen.getByRole("link", { name: /Bo tries cod · C/ })).getByText("Finished")).toBeInTheDocument();
});

test("a video title doesn't double its letter when the server already put it there", async () => {
  setViewport(1440);
  fakeServer(brandBase({ "GET /usage/brands/1/videos": [200, { total: 1, next_cursor: null, people: [], items: [video({ title: "Bo tries salmon · B" })] }] }));
  open("/usage/brands/1");
  expect(await screen.findByRole("link", { name: "Bo tries salmon · B" })).toBeInTheDocument();
  expect(screen.queryByText(/· B · B/)).not.toBeInTheDocument();
});

test("on a phone a script card is one link, with one meta line under the chips", async () => {
  fakeServer(brandBase());
  open("/usage/brands/1?tab=scripts");
  const title = await screen.findByRole("link", { name: "Bo tries salmon" });
  expect(title).toHaveAttribute("href", "/b/1/scripts/7?step=publish");
  expect(title.className).toMatch(/after:absolute/); // the whole card is the link
  expect(screen.getByText(/^Reed · \$19\.40 · 1 left · /)).toBeInTheDocument();
});

const charge = (o: object = {}) => ({ id: 41, at: "2026-10-24T10:00:00Z", person: { id: 2, name: "Sam" }, brand: { id: 1, name: "Iron Paws" }, what: "Clip 3 take 2 · Bo tries salmon · B", credits: 27, cost_usd: 2.36, estimated: false, status: "succeeded", refunded: null, ...o });

test("Reed gives credits back from a charge's menu: a reason is required, the old number is struck, the badge and the toast say so, and it can't be done twice", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /usage/summary": [200, summary],
    "GET /usage/brands": [200, brands([row()])],
    "GET /usage/charges": [200, { next_cursor: null, items: [charge(), charge({ id: 42, what: "Quick clip", credits: 0 }), charge({ id: 43, what: "Clip 1 take 1", credits: 0, refunded: { credits: 27, reason: "Wrong cast in the shot", at: "2026-10-26T10:00:00Z" } })] }],
    "POST /usage/charges/41/refund": [200, { job_id: 5, credits: 27.4, reason: "Wrong cast in the shot", by: { id: 1, name: "Reed" }, at: "2026-10-26T10:00:00Z" }],
  });
  open();
  await userEvent.click(await screen.findByText("Every charge"));
  await screen.findByText("Clip 3 take 2 · Bo tries salmon · B");
  expect(screen.getAllByRole("button", { name: /^Actions for/ })).toHaveLength(1); // not on a 0-credit charge, nor one already given back
  const back = screen.getByText("Credits given back"); // the one that was: the original number struck through, the reason as the tooltip
  expect(back.closest("[title]")).toHaveAttribute("title", "Wrong cast in the shot");
  expect(back.closest("td")?.querySelector("del")).toHaveTextContent("27");
  await userEvent.click(screen.getByRole("button", { name: "Actions for Clip 3 take 2 · Bo tries salmon · B" }));
  await userEvent.click(await screen.findByRole("menuitem", { name: "Give credits back" }));
  expect(await screen.findByText("Give back 27 credits?")).toBeInTheDocument();
  expect(screen.getByText(/stays on the bill: the service was still paid/)).toBeInTheDocument();
  const action = screen.getByRole("button", { name: "Give credits back" });
  expect(action).toBeDisabled();
  expect(action).toHaveAccessibleDescription("Say why");
  await userEvent.type(screen.getByLabelText("Reason"), "Wrong cast in the shot");
  await userEvent.click(screen.getByRole("button", { name: "Give credits back" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /usage/charges/41/refund")?.body).toEqual({ reason: "Wrong cast in the shot" }));
  expect(await screen.findByText("28 credits given back.")).toBeInTheDocument(); // in words, rounded up
});

test("a charge that was already given back shows the server's words if it's tried again", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /usage/summary": [200, summary],
    "GET /usage/brands": [200, brands([row()])],
    "GET /usage/charges": [200, { next_cursor: null, items: [charge()] }],
    "POST /usage/charges/41/refund": [409, { detail: "Those credits were already given back." }],
  });
  open();
  await userEvent.click(await screen.findByText("Every charge"));
  await userEvent.click(await screen.findByRole("button", { name: /^Actions for/ }));
  await userEvent.click(await screen.findByRole("menuitem", { name: "Give credits back" }));
  await userEvent.type(screen.getByLabelText("Reason"), "x");
  await userEvent.click(screen.getByRole("button", { name: "Give credits back" }));
  expect(await screen.findByText("Those credits were already given back.")).toBeInTheDocument();
});

test("on a phone the line reads '0 credits' before the badge, and one credit is singular", async () => {
  setViewport(390);
  fakeServer({
    ...base,
    "GET /usage/summary": [200, summary],
    "GET /usage/brands": [200, brands([row()])],
    "GET /usage/charges": [200, { next_cursor: null, items: [charge({ credits: 0, refunded: { credits: 1, reason: "x", at: "2026-10-26T10:00:00Z" } }), charge({ id: 44, what: "Quick clip", credits: 1 })] }],
  });
  open();
  await userEvent.click(await screen.findByText("Every charge"));
  const lines = await screen.findAllByText(/credits?/);
  expect(lines.some((n) => n.textContent === "0 credits")).toBe(true);
  expect(screen.getByText(/1 credit ·/)).toBeInTheDocument();
});
