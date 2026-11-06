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
const summary = { period: "week", starts_at: "2026-10-19T00:00:00Z", previous: { spend_usd: 71.72, finished: 4, cost_per_finished_usd: 12.25 }, spend_usd: 84.12, spend_estimated: false, finished: 6, cost_per_finished_usd: 11.4, in_progress: 9, unassigned_spend_usd: 1.2, freestyle_spend_usd: 3.4, director_spend_usd: 0, spend_credits: 841.2, unassigned_credits: 12, freestyle: { credits: 34, spend_usd: 3.4, videos: 2 } };
const row = (o: object = {}) => ({ brand_id: 1, name: "Iron Paws", colour: "#3a7", archived: false, spend_usd: 52.3, spend_estimated: false, finished: 4, cost_per_finished_usd: 11.05, in_progress: 3, scripts: 12, versions_left: 7, last_activity_at: new Date(Date.now() - 2 * 3600_000).toISOString(), credits: 523, videos: 5, ...o });
const month = new Date().toISOString().slice(0, 7);
const brands = (items: object[], total = items.length, next: string | null = null) => ({ total, next_cursor: next, items });

function open(path = "/usage") {
  renderApp(path);
}
afterEach(() => vi.unstubAllGlobals());

test("Usage (v5 D_Usage): three cards for the month, and By brand reads Brand · Credits · Dollars · Videos · Share with a Freestyle row", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /usage/summary": [200, summary],
    "GET /usage/brands": [200, brands([row(), row({ brand_id: 2, name: "fomo", spend_usd: 30.62, spend_estimated: true, credits: 284.2, videos: 3 })])],
  });
  open();
  const totals = await screen.findByRole("group", { name: "Totals" });
  expect(await within(totals).findByText("842 credits")).toBeInTheDocument(); // whole credits, rounded up
  expect(within(totals).getByText("$84.12")).toBeInTheDocument();
  expect(within(totals).getByText("Spent this month")).toBeInTheDocument();
  const table = await screen.findByRole("table", { name: "By brand" });
  expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Brand", "Credits", "Dollars", "Videos", "Share", "Restore"]);
  const iron = within(table).getByRole("link", { name: "Iron Paws" });
  expect(iron).toHaveAttribute("href", "/usage/brands/1");
  expect(iron.closest("tr")).toHaveTextContent("523$52.305");
  expect(within(table).getByText("≈ $30.62")).toHaveAttribute("title", expect.stringMatching(/estimate/));
  const fs = within(table).getByText("Freestyle").closest("tr")!;
  expect(fs).toHaveTextContent("(no brand picked)");
  expect(fs).toHaveTextContent("34$3.402");
  expect(within(table).getByRole("img", { name: "62% of the month's credits" })).toBeInTheDocument(); // 523 of 841.2
  const other = within(table).getByText("Other").closest("tr")!; // Next-Lead: the rows add up to the month's spend
  expect(other).toHaveTextContent("(no brand or video)");
  expect(other).toHaveTextContent("12$1.20—");
  expect(calls.find((c) => c.key === "GET /usage/summary")?.url).toContain(`month=${month}`);
  expect(calls.find((c) => c.key === "GET /usage/brands")?.url).toContain(`month=${month}`);
});

test("Usage: picking a month asks the server for that month, puts it in the address, and the CSV follows it", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /usage/summary": [200, summary], "GET /usage/brands": [200, brands([row()], 40, "c2")], "GET /usage/people": [200, []] });
  open();
  const picker = await screen.findByRole("combobox", { name: "Month" });
  const last = (picker as HTMLSelectElement).options[1].value;
  await userEvent.selectOptions(picker, last);
  await vi.waitFor(() => expect(calls.some((c) => c.key === "GET /usage/summary" && c.url.includes(`month=${last}`))).toBe(true));
  expect(calls.some((c) => c.key === "GET /usage/people" && c.url.includes(`month=${last}`))).toBe(true);
  expect(screen.getByRole("link", { name: "Download CSV" })).toHaveAttribute("href", `/api/usage/charges.csv?month=${last}`);
  await userEvent.click(await screen.findByRole("button", { name: "Show more" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "GET /usage/brands").length).toBeGreaterThan(2));
});

test("Usage on a phone: each brand is a card with credits, dollars, videos and its share, then Freestyle", async () => {
  setViewport(390);
  fakeServer({ ...base, "GET /usage/summary": [200, summary], "GET /usage/brands": [200, brands([row({ videos: 1 })])] });
  open();
  const card = await screen.findByRole("link", { name: /Iron Paws/ });
  expect(card).toHaveTextContent("523 credits · $52.30 · 1 video");
  expect(within(card).getByRole("img", { name: "62% of the month's credits" })).toBeInTheDocument();
  expect(screen.getByText("Freestyle").closest("li")).toHaveTextContent("34 credits · $3.40 · 2 videos");
});

const mine = {
  credits: 61, quick_clip_credits: 8, script_credits: 3,
  videos: [
    { project_id: 9, title: "Bo tries salmon · B", status: "in_production", state: "making", brand_id: 1, credits: 40, budget_credits: 600, folder_id: null, finished_at: null, last_activity_at: "2026-10-28T10:00:00Z" },
    { project_id: 10, title: "Kimchi at the vet · A", status: "done", state: "delivered", brand_id: 2, credits: 10, budget_credits: 120, folder_id: null, finished_at: "2026-10-27T10:00:00Z", last_activity_at: "2026-10-27T10:00:00Z" },
  ],
  projects: [], scripts: [{ script_id: 7, title: "Bo tries salmon", credits: 3, brand_id: 2 }], sends: [], waiting_credits: 0, videos_and_freestyles: 3,
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
  expect(within(videos).getByRole("link", { name: /Bo tries salmon · B.*Making.*spent 40/ })).toHaveAttribute("href", "/b/1/videos/9");
  expect(within(videos).getByRole("link", { name: /Kimchi at the vet · A.*Delivered/ })).toHaveAttribute("href", "/b/2/videos/10"); // every brand, each row to its own
  expect(screen.getByRole("link", { name: 'Writing "Bo tries salmon"' })).toHaveAttribute("href", "/b/2/scripts/7"); // in its own brand (#1255)
  expect(document.body.textContent).not.toMatch(/\$/);
  const spent = within(screen.getByRole("group", { name: "Totals" })).getByText("Spent this month").parentElement!;
  expect(spent).toHaveTextContent("61 credits");
  expect(spent).toHaveTextContent("On 3 videos and freestyles");
  expect(urls()[0]).toContain(`month=${month}`);
  expect(urls()[0]).not.toContain("brand_id");
  const picker = screen.getByRole("combobox", { name: "Month" });
  const last = (picker as HTMLSelectElement).options[1];
  await userEvent.selectOptions(picker, last.value);
  await vi.waitFor(() => expect(urls().some((u) => u.includes(`month=${last.value}`))).toBe(true));
  expect(await screen.findByText(`Spent in ${last.textContent}`)).toBeInTheDocument();
});

test("Usage: an editor's account menu links My credits; the owner's links Usage instead", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /auth/me": [200, editor], "GET /usage/mine": [200, mine] });
  open("/b/1/videos");
  await userEvent.click(await screen.findByRole("button", { name: "Account menu" }));
  expect(screen.getByRole("link", { name: "My credits" })).toHaveAttribute("href", "/usage/mine");
  expect(screen.queryByRole("link", { name: "Usage" })).toBeNull();
});

test("Usage: no brands has its own words, and a month with no freestyles has no Freestyle row", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /usage/summary": [200, { ...summary, spend_usd: 0, spend_credits: 0, freestyle: { credits: 0, spend_usd: 0, videos: 0 } }], "GET /usage/brands": [200, brands([])] });
  open();
  expect(await screen.findByText("No brands yet.")).toBeInTheDocument();
  expect(await screen.findByText("0 credits")).toBeInTheDocument();
  expect(screen.queryByText("Freestyle")).toBeNull();
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
  await userEvent.click(screen.getByText("See every charge"));
  expect(await screen.findByText("Clip 3 take 2 · Bo tries salmon · B")).toBeInTheDocument();
  expect(screen.getByText("$2.36")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Show more" })).toBeInTheDocument();
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
  await userEvent.click(await screen.findByText("See every charge"));
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
  await userEvent.click(await screen.findByText("See every charge"));
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
  await userEvent.click(await screen.findByText("See every charge"));
  const lines = await screen.findAllByText(/credits?/);
  expect(lines.some((n) => n.textContent === "0 credits")).toBe(true);
  expect(screen.getByText(/1 credit ·/)).toBeInTheDocument();
});

test("Usage (v5 D_Usage): what waits for the owner's OK is a card that links to Needs you, and each brand's share of the spend is a bar", async () => {
  setViewport(1440);
  // Needs you's Money: a start card (its whole run, up to 204) and a held press outside any video (up to 6).
  const start = { video: {}, brand: { id: 1, name: "fomo" }, ask: { id: 7, kind: "start", can: ["make_it"], money: { up_to: { credits: 204, usd: 12.24 } } } };
  const send = { job_id: 50, brand: null, what: "Quick clip", made_by: "Sam", up_to: { credits: 6, usd: 0.36 }, held: "", at: new Date().toISOString(), script_id: null };
  fakeServer({ ...base, "GET /needs-you": [200, { total: 2, brands: [], questions: [], money: [start], sends: [send], stuck: [] }], "GET /usage/summary": [200, summary], "GET /usage/brands": [200, brands([row()])] });
  open();
  const totals = await screen.findByRole("group", { name: "Totals" });
  expect(await within(totals).findByText("up to $12.60")).toBeInTheDocument(); // the owner: dollars (rule 4)
  expect(within(totals).getByRole("link", { name: "2 in Needs you" })).toHaveAttribute("href", "/approvals");
  expect(await screen.findByRole("img", { name: "62% of the month's credits" })).toBeInTheDocument(); // 52.30 of 84.12
});

test("Usage (v5 D_Usage, #1208): the director's own time is its own card, in dollars, outside the credit budget", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /usage/summary": [200, { ...summary, director_spend_usd: 6.4 }], "GET /usage/brands": [200, brands([row()])] });
  open();
  const totals = await screen.findByRole("group", { name: "Totals" });
  expect(await within(totals).findByText("$6.40")).toBeInTheDocument();
  expect(within(totals).getByText("Outside the credit budget")).toBeInTheDocument();
});

test("My credits counts every send waiting for the owner, from the server, and lists sends with Declined and its reason (#1232, QA-3 on #1218)", async () => {
  setViewport(1440);
  const at = "2026-11-02T20:00:00Z";
  const sends = [
    { freestyle_id: 4, title: "Garden scene", brand: "", status: "waiting", up_to_credits: 143.06, reason: "", created_at: at },
    { freestyle_id: 5, title: "Rain on neon", brand: "fomo", status: "waiting", up_to_credits: 4, reason: "", created_at: at },
    { job_id: 70, title: "Another take", brand: "fomo", status: "waiting", up_to_credits: 5.6, reason: "", created_at: at },
    { freestyle_id: 6, title: "Gym bro", brand: "", status: "declined", up_to_credits: 20, reason: "Let's keep this one short", created_at: at },
  ];
  fakeServer({ ...base, "GET /auth/me": [200, editor], "GET /usage/summary": [404, { detail: "Not found" }], "GET /usage/mine": [200, { ...mine, sends, waiting_credits: 152.66 }] });
  open("/usage/mine");
  expect(await screen.findByText("up to 153 credits")).toBeInTheDocument(); // QA-3's case: 143.06 + 4 + 5.6, in whole credits as Needs you shows
  expect(screen.getByText("3 sends. No generation starts until it's approved.")).toBeInTheDocument();
  const list = screen.getByRole("list", { name: "My sends" });
  expect(within(list).getAllByText("Waiting for the owner's OK")).toHaveLength(3);
  expect(within(list).getByText("Declined")).toBeInTheDocument();
  expect(within(list).getByText('"Let\'s keep this one short"')).toBeInTheDocument();
  expect(within(list).getByRole("link", { name: "Garden scene" })).toHaveClass("min-h-11"); // a 44 px press on a phone (QA-3 on #1241)
  expect(document.body.textContent).not.toMatch(/\$/);
});

test("Usage's By person lists each person's credits, dollars, videos and week (#1232)", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /usage/summary": [200, summary], "GET /usage/brands": [200, brands([row()])], [`GET /usage/people?month=${month}`]: [200, [
    { user_id: 2, name: "Dee", role: "editor", credits: 804, spend_usd: 80.4, videos: 7, week_used: 40, week_allowance: 100 },
    { user_id: 1, name: "Reed", role: "owner", credits: 448, spend_usd: 44.8, videos: 5, week_used: 0, week_allowance: null },
  ]] });
  open();
  const people = await screen.findByRole("region", { name: "By person" });
  const dee = (await within(people).findByText("Dee")).closest("tr")!;
  expect(within(dee).getByText("804")).toBeInTheDocument(); // whole credits, no unit (D_Usage)
  expect(dee).toHaveTextContent("$80.40");
  expect(dee).toHaveTextContent("40 of 100 quick credits");
  expect(within(people).getByText("No limit")).toBeInTheDocument();
});

test("My credits' rows read 'spent N' with the director's time included, in whole credits, and 'up to N approved' muted where the owner approved a run (the Producer, 3 Nov)", async () => {
  setViewport(1440);
  const videos = [
    { project_id: 9, title: "Garden scene", status: "in_production", state: "making", brand_id: 1, credits: 97.33, director_credits: 70.4, budget_credits: 729, folder_id: null, finished_at: null, last_activity_at: "2026-10-28T10:00:00Z" },
    { project_id: 10, title: "Bo at the beach", status: "done", state: "delivered", brand_id: 1, credits: 50, director_credits: 20, approved_up_to: 204, budget_credits: 400, folder_id: null, finished_at: null, last_activity_at: "2026-10-28T10:00:00Z" },
    { project_id: 11, title: "Bo in the rain", status: "in_production", state: "stopped", brand_id: 1, credits: 4, budget_credits: 400, folder_id: null, finished_at: null, last_activity_at: "2026-10-28T10:00:00Z" },
  ];
  fakeServer({ ...base, "GET /auth/me": [200, editor], "GET /usage/summary": [404, { detail: "Not found" }], "GET /usage/mine": [200, { ...mine, videos }] });
  open("/usage/mine");
  const list = await screen.findByRole("list", { name: "My videos" });
  const garden = within(list).getByRole("link", { name: /Garden scene/ });
  expect(garden).toHaveTextContent("spent 98");
  expect(garden).not.toHaveTextContent(/director time|of 729/);
  const beach = within(list).getByRole("link", { name: /Bo at the beach/ });
  expect(beach).toHaveTextContent("spent 50");
  expect(beach).toHaveTextContent("up to 204 approved");
  expect(within(beach).getByText("Delivered")).toBeInTheDocument();
  expect(within(list).getByRole("link", { name: /Bo in the rain/ })).toHaveTextContent("Stopped"); // the server's state, in words
});

test("Usage's Download CSV gives this month's charges (v5 D_Usage, #1247)", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /usage/summary": [200, summary], "GET /usage/brands": [200, brands([row()])], [`GET /usage/people?month=${month}`]: [200, []] });
  open();
  const csv = await screen.findByRole("link", { name: "Download CSV" });
  expect(csv).toHaveAttribute("href", `/api/usage/charges.csv?month=${new Date().toISOString().slice(0, 7)}`);
  expect(csv).toHaveAttribute("download");
});

test("By person and My credits never show '-0' for nothing used (UX-Auditor on #1246)", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /usage/summary": [200, summary], "GET /usage/brands": [200, brands([row()])], [`GET /usage/people?month=${month}`]: [200, [{ user_id: 2, name: "Dee", role: "editor", credits: 0, spend_usd: 0, videos: 0, week_used: 0, week_allowance: 97 }]] });
  open();
  const people = await screen.findByRole("region", { name: "By person" });
  const dee = (await within(people).findByText("Dee")).closest("tr")!;
  expect(dee).toHaveTextContent("0 of 97 quick credits");
  expect(dee.textContent).not.toMatch(/-0/);
});

test("My credits lists a send held before anything was spent under Sends only, not again as a video (Next-Lead on #1264)", async () => {
  setViewport(1440);
  const at = "2026-10-28T10:00:00Z";
  const videos = [
    { project_id: 12, title: "Garden scene", status: "in_production", state: "waiting", brand_id: 1, credits: 0, budget_credits: 400, folder_id: null, finished_at: null, last_activity_at: at },
    { project_id: 13, title: "Bo at the gym", status: "in_production", state: "waiting", brand_id: 1, credits: 30, budget_credits: 400, folder_id: null, finished_at: null, last_activity_at: at },
  ];
  const sends = [{ freestyle_id: 4, title: "Garden scene", brand: "", status: "waiting", up_to_credits: 143, reason: "", created_at: at }];
  fakeServer({ ...base, "GET /auth/me": [200, editor], "GET /usage/summary": [404, { detail: "Not found" }], "GET /usage/mine": [200, { ...mine, videos, sends }] });
  open("/usage/mine");
  const list = await screen.findByRole("list", { name: "My videos" });
  expect(within(list).queryByText("Garden scene")).toBeNull();
  expect(within(list).getByRole("link", { name: /Bo at the gym/ })).toHaveTextContent("spent 30"); // a later step held after spending stays a video
  expect(within(screen.getByRole("list", { name: "My sends" })).getByText("Garden scene")).toBeInTheDocument();
});
