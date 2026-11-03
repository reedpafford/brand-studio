import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const owner = { id: 1, email: "reed@b.co", name: "Reed", role: "owner", workspace_id: 1 };
const editor = { ...owner, id: 2, name: "Eli", role: "editor" };
const brands = [
  { id: 1, name: "fomo", colours: ["#ff5500"] },
  { id: 2, name: "Iron Paws", colours: [] },
];
const members = [
  { id: 1, email: "reed@b.co", name: "Reed", role: "owner" },
  { id: 2, email: "eli@b.co", name: "Eli", role: "editor" },
];

function renderAt(path: string) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

const pickBrand = async (name: string) => {
  await userEvent.click(screen.getByRole("button", { name: /^Brand: / }));
  await userEvent.click(await screen.findByRole("menuitemradio", { name }));
};

test("the first brand opens on its Scripts, and the switcher menu changes brand and keeps the section", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []], "GET /library/character": [200, []] });
  renderAt("/");
  expect(await screen.findByRole("heading", { name: "Scripts" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Brand: fomo" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Brand: fomo" }));
  expect(screen.getByRole("menuitemradio", { name: "fomo" })).toHaveAttribute("aria-checked", "true");
  expect(screen.getByRole("menuitem", { name: "New brand" })).toBeInTheDocument();
  expect(screen.queryByText("Brands are set up by the owner.")).toBeNull();
  await userEvent.click(screen.getByRole("menuitemradio", { name: "Iron Paws" }));
  expect(await screen.findByText("No scripts for Iron Paws yet.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Brand: Iron Paws" })).toBeInTheDocument();
  // Cast & places in one brand becomes Cast & places in the other.
  await userEvent.click(within(screen.getByRole("navigation", { name: "Main" })).getByRole("link", { name: "Cast & places" }));
  await screen.findByRole("heading", { name: "Cast & places" });
  await pickBrand("fomo");
  expect(await screen.findByRole("heading", { name: "Cast & places" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Cast & places" })).toHaveAttribute("href", "/b/1/library");
});

test("the brand's colour is applied, and cleared for a brand without one", async () => {
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []] });
  renderAt("/b/1");
  await screen.findByRole("heading", { name: "Scripts" });
  expect(document.documentElement.style.getPropertyValue("--brand")).toBe("#ff5500");
  await pickBrand("Iron Paws");
  await screen.findByText("No scripts for Iron Paws yet.");
  expect(document.documentElement.style.getPropertyValue("--brand")).toBe("");
});

test("the team page keeps the brand you were in", async () => {
  setViewport(1440);
  localStorage.setItem("bs.lastBrand", "2");
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /team/members": [200, members], "GET /team/invites": [200, []] });
  renderAt("/team");
  expect(await screen.findByRole("button", { name: "Brand: Iron Paws" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Brand" })).toHaveAttribute("href", "/b/2/brand");
});

test("the last brand you used opens next time", async () => {
  localStorage.setItem("bs.lastBrand", "2");
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []] });
  renderAt("/");
  expect(await screen.findByText("No scripts for Iron Paws yet.")).toBeInTheDocument();
});

test("an editor sees the team but cannot invite or remove", async () => {
  const calls = fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, brands], "GET /team/members": [200, members] });
  renderAt("/team");
  expect(await screen.findByText("Reed")).toBeInTheDocument();
  expect(screen.queryByLabelText("Email to invite")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Remove/ })).not.toBeInTheDocument();
  expect(calls.some((c) => c.key === "GET /team/invites")).toBe(false);
});

test("signing out returns to sign in", async () => {
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "POST /auth/logout": [204, null] });
  renderAt("/");
  await userEvent.click(await screen.findByRole("button", { name: "Account menu" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Sign out" }));
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
});

test("an unknown brand in the address does not pretend to be selected", async () => {
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands] });
  renderAt("/b/999");
  expect(await screen.findByRole("button", { name: "Choose a brand" })).toBeInTheDocument();
});

test("a failed remove tells you", async () => {
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /team/members": [200, members], "GET /team/invites": [200, []], "DELETE /team/members/2": [500, {}] });
  renderAt("/team");
  await userEvent.click(await screen.findByRole("button", { name: "Remove Eli" }));
  const ask = await screen.findByRole("alertdialog", { name: "Remove Eli from the team?" });
  expect(within(ask).getByText("Their videos stay.")).toBeInTheDocument();
  await userEvent.click(within(ask).getByRole("button", { name: "Remove" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't remove that person.");
});

test("on a phone there are five tabs (Videos first), no More, and Reed gets a Needs you bell with the count, and Settings in the account menu", async () => {
  setViewport(390);
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /jobs": [200, [{ id: 5, kind: "video", status: "needs_owner_approval", project_id: null, credits: 4, created_at: "2026-10-24T10:00:00Z" }]], "GET /scripts": [200, []], "GET /projects": [200, []] });
  renderAt("/b/1/projects");
  const tabs = await screen.findByRole("navigation", { name: "Tabs" });
  expect(screen.getByRole("banner", { name: "Top bar" })).toBeInTheDocument(); // a phone has the shell's top bar; desktop has none
  expect(within(tabs).getAllByRole("link").map((l) => l.textContent)).toEqual(["Videos", "Scripts", "New", "Cast", "Brand"]);
  expect(within(tabs).getByRole("link", { name: "Videos" })).toHaveAttribute("aria-current", "page"); // an earlier-way video sits under Videos
  expect(within(tabs).getByRole("link", { name: "Cast" })).toHaveAttribute("href", "/b/1/library");
  expect(within(tabs).getByRole("link", { name: "Brand" })).toHaveAttribute("href", "/b/1/brand");
  expect(within(tabs).queryByRole("button", { name: "More" })).not.toBeInTheDocument();
  expect(await screen.findByRole("link", { name: "Needs you, 1 waiting" })).toHaveAttribute("href", "/approvals");
  await userEvent.click(screen.getByRole("button", { name: "Account menu" }));
  const account = await screen.findByRole("dialog", { name: "Account" }); // a sheet on a phone
  expect(within(account).getByRole("link", { name: "Settings" })).toHaveAttribute("href", "/settings");
  expect(within(account).queryByRole("link", { name: /^(Looks|Languages)$/ })).toBeNull();
  expect(screen.queryByRole("navigation", { name: "Main" })).not.toBeInTheDocument();
});

test("with nothing waiting, Reed sees no Needs you in the top bar or the rail, at 390 and on desktop (Reed, 30 Oct)", async () => {
  for (const width of [390, 1440]) {
    setViewport(width);
    const calls = fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /jobs": [200, []], "GET /scripts": [200, []], "GET /projects": [200, []] });
    renderAt("/b/1/projects");
    await screen.findByRole("link", { name: "Videos" });
    if (width === 1440) await within(screen.getByRole("navigation", { name: "Main" })).findByRole("link", { name: "In production" });
    await vi.waitFor(() => expect(calls.some((c) => c.key === "GET /jobs")).toBe(true));
    await new Promise((r) => setTimeout(r, 50)); // the answer is drawn
    expect(screen.queryByRole("link", { name: /Needs you/ })).not.toBeInTheDocument();
    cleanup();
    vi.unstubAllGlobals();
  }
});

test("when only a changed video waits, Reed still reaches Needs you: the bell and the rail row count it (QA-9 on #1154)", async () => {
  for (const width of [390, 1440]) {
    setViewport(width);
    fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /jobs": [200, []], "GET /scripts": [200, []], "GET /projects": [200, []], "GET /production/summary": [200, { in_production: 0, needs_attention: 0, changes_waiting: 1 }] });
    renderAt("/b/1/projects");
    const needsYou = await screen.findByRole("link", { name: width === 390 ? "Needs you, 1 waiting" : /^Needs you/ });
    expect(needsYou).toHaveAttribute("href", "/approvals");
    if (width === 1440) expect(needsYou).toHaveTextContent("1");
    cleanup();
    vi.unstubAllGlobals();
  }
});

test("an editor has no Needs you bell", async () => {
  setViewport(390);
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []] });
  renderAt("/b/1/projects");
  await screen.findByRole("navigation", { name: "Tabs" });
  expect(screen.queryByRole("link", { name: /Needs you/ })).not.toBeInTheDocument();
});

test("the account menu (bottom of the rail) has the theme choices and Sign out; Team is a rail row, not in the menu; Escape closes it", async () => {
  setViewport(1440);
  localStorage.removeItem("bs.theme");
  document.documentElement.removeAttribute("data-theme");
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /projects": [200, []], "POST /auth/logout": [204, null] });
  renderAt("/b/1/projects");
  const menu = await screen.findByRole("button", { name: "Account menu" });
  await userEvent.click(menu);
  expect(screen.getByText("reed@b.co")).toBeInTheDocument();
  expect(within(screen.getByRole("menu", { name: "Account" })).queryByRole("link", { name: "Team" })).toBeNull();
  expect(within(screen.getByRole("navigation", { name: "Main" })).getByRole("link", { name: "Team" })).toHaveAttribute("href", "/team");
  expect(screen.getByRole("menuitemradio", { name: "Dark" })).toHaveAttribute("aria-checked", "true");
  await userEvent.click(screen.getByRole("menuitemradio", { name: "Light" }));
  expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  expect(screen.getByRole("menuitemradio", { name: "Light" })).toHaveAttribute("aria-checked", "true");
  await userEvent.click(screen.getByRole("menuitemradio", { name: "System" }));
  expect(document.documentElement.getAttribute("data-theme")).toBe("system");
  await userEvent.keyboard("{Escape}");
  expect(screen.queryByRole("menuitem", { name: "Sign out" })).not.toBeInTheDocument();
  expect(menu).toHaveFocus();
  document.documentElement.removeAttribute("data-theme");
});

test("an editor's account menu has no Team link", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []] });
  renderAt("/b/1/projects");
  await userEvent.click(await screen.findByRole("button", { name: "Account menu" }));
  expect(within(screen.getByRole("menu", { name: "Account" })).queryByRole("link", { name: "Team" })).not.toBeInTheDocument();
  expect(screen.getByRole("menuitem", { name: "Sign out" })).toBeInTheDocument();
});

test("on desktop one rail (nav A): the brand switcher, Make and Library, Studio for Reed only, the account at the bottom; no top bar", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []], "GET /jobs": [200, [{ id: 5, kind: "video", status: "needs_owner_approval", project_id: null, credits: 4, created_at: "2026-10-24T10:00:00Z" }]] });
  renderAt("/b/1/projects");
  const rail = await screen.findByRole("navigation", { name: "Main" });
  expect(await within(rail).findByText("fomo")).toBeInTheDocument();
  expect(within(rail).getAllByRole("link").map((l) => l.textContent?.replace(/\d+ waiting$/, "").trim())).toEqual(["New videoN", "Videos", "Scripts", "Cast & places", "Media", "Brand", "Needs you", "In production", "Usage", "Team", "Settings"]);
  expect(within(rail).getByRole("button", { name: "Brand: fomo" })).toBeInTheDocument();
  expect(within(rail).getByRole("button", { name: "Account menu" })).toBeInTheDocument();
  expect(screen.queryByRole("banner", { name: "Top bar" })).not.toBeInTheDocument(); // the shell's own top bar; a page's PageTop is a header too
  expect(within(rail).getByRole("link", { name: "Videos" })).toHaveAttribute("aria-current", "page");
  expect(await within(rail).findByRole("link", { name: /Needs you/ })).toHaveTextContent("1");
  expect(screen.getAllByRole("link", { name: /Needs you/ })).toHaveLength(1); // only the rail row: no top bar on desktop
  expect(screen.queryByRole("navigation", { name: "Tabs" })).not.toBeInTheDocument();
});

test("an editor's rail has no Studio group", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []] });
  renderAt("/b/1/projects");
  const rail = await screen.findByRole("navigation", { name: "Main" });
  expect(within(rail).getAllByRole("link")).toHaveLength(6);
  expect(within(rail).queryByRole("link", { name: /Needs you|Team|Settings/ })).not.toBeInTheDocument();
  expect(screen.queryByText("STUDIO")).not.toBeInTheDocument();
});

test("between 1024 and 1279 the rail is icons only, each with a name", async () => {
  setViewport(1100);
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []] });
  renderAt("/b/1/projects");
  const rail = await screen.findByRole("navigation", { name: "Main" });
  expect(within(rail).getByRole("link", { name: "Cast & places" })).toHaveAttribute("title", "Cast & places");
  expect(within(rail).getByRole("link", { name: "Scripts" }).textContent).toBe("");
});

test("the old Kit and Screens addresses land on the Brand page", async () => {
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /projects": [200, []], "GET /brands/1/screens": [200, []] });
  renderAt("/b/1/screens");
  expect(await screen.findByRole("tab", { name: "App screens", selected: true })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Look" })).toBeInTheDocument();
});

test("with no brands there is an empty state, not a blank page", async () => {
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, []] });
  renderAt("/b/1");
  expect(await screen.findByRole("heading", { name: "No brands yet" })).toBeInTheDocument();
  expect(screen.getByText(/The owner adds brands/)).toBeInTheDocument();
});

test("offline, a banner says nothing was lost", async () => {
  vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []] });
  renderAt("/b/1/projects");
  expect(await screen.findByText("You're offline.")).toBeInTheDocument();
  expect(screen.getByText("Reconnect to keep working; nothing was lost.")).toBeInTheDocument();
});

test("a waiting invite has Copy a new link: it asks for a fresh link and copies it, and says the old one stops working", async () => {
  const calls = fakeServer({
    "GET /auth/me": [200, owner],
    "GET /brands": [200, brands],
    "GET /team/members": [200, members],
    "GET /team/invites": [200, [{ id: 3, email: "jo@b.co", role: "editor", expires_at: "2026-10-31T12:00:00Z" }]],
    "POST /team/invites/3/link": [200, { id: 3, email: "jo@b.co", role: "editor", expires_at: "2026-11-01T12:00:00Z", token: "fresh9" }],
  });
  renderAt("/team");
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.assign(navigator, { clipboard: { writeText } });
  await userEvent.click(await screen.findByRole("button", { name: "Copy a new link for jo@b.co" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /team/invites/3/link")).toBe(true));
  await vi.waitFor(() => expect(writeText).toHaveBeenCalledWith(`${location.origin}/invite/fresh9`));
  expect(await screen.findByText("Link copied. The old link no longer works.")).toBeInTheDocument();
});

test("if the clipboard says no, the fresh link is shown in a read-only field to copy by hand", async () => {
  fakeServer({
    "GET /auth/me": [200, owner],
    "GET /brands": [200, brands],
    "GET /team/members": [200, members],
    "GET /team/invites": [200, [{ id: 3, email: "jo@b.co", role: "editor", expires_at: "2026-10-31T12:00:00Z" }]],
    "POST /team/invites/3/link": [200, { id: 3, email: "jo@b.co", role: "editor", expires_at: "2026-11-01T12:00:00Z", token: "fresh9" }],
  });
  renderAt("/team");
  Object.assign(navigator, { clipboard: { writeText: vi.fn().mockRejectedValue(new Error("no")) } });
  await userEvent.click(await screen.findByRole("button", { name: "Copy a new link for jo@b.co" }));
  const field = await screen.findByLabelText("Invite link for jo@b.co");
  expect(field).toHaveValue(`${location.origin}/invite/fresh9`);
  expect(field).toHaveAttribute("readonly");
});

test("an editor's brand menu lists the brands, with no New brand and no owner-only note", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []] });
  renderAt("/");
  await userEvent.click(await screen.findByRole("button", { name: /^Brand: / }));
  expect(await within(screen.getByRole("menu")).findByText("Iron Paws")).toBeInTheDocument();
  expect(screen.queryByText("Brands are set up by the owner.")).toBeNull();
  expect(screen.queryByRole("menuitem", { name: "New brand" })).toBeNull();
});

test("Reed's New brand is its own page: a name, a colour, and it opens the brand's Look", async () => {
  setViewport(1440);
  const calls = fakeServer({
    "GET /auth/me": [200, owner],
    "GET /brands": [200, brands],
    "GET /scripts": [200, []],
    "GET /projects": [200, []],
    "POST /brands": [201, { id: 9, name: "Night Owl", colours: ["#2F6B4F"], site_read_job_id: null, site_read_problem: "" }],
    "GET /brands/9/screens": [200, []],
  });
  renderAt("/");
  await userEvent.click(await screen.findByRole("button", { name: /^Brand: / }));
  await userEvent.click(screen.getByRole("menuitem", { name: "New brand" }));
  const form = await screen.findByRole("form", { name: "New brand" });
  expect(within(form).getByRole("button", { name: "Make the brand" })).toHaveAccessibleDescription("Give it a name first");
  await userEvent.type(within(form).getByLabelText("Name"), "Night Owl");
  const colour = within(form).getByLabelText("Colour");
  await userEvent.clear(colour);
  await userEvent.type(colour, "#2f6b4f");
  await userEvent.click(within(form).getByRole("button", { name: "Make the brand" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /brands")?.body).toMatchObject({ name: "Night Owl", website: null, colours: ["#2F6B4F"] }));
  expect(await screen.findByText("Night Owl is ready. Add its look next.")).toBeInTheDocument();
});

test("New brand with a website says what reading it costs, and opens on Import from website", async () => {
  setViewport(1440);
  const calls = fakeServer({
    "GET /auth/me": [200, owner],
    "GET /brands": [200, brands],
    "GET /brands/site-read/estimate": [200, { credits: 3 }],
    "POST /brands": [201, { id: 9, name: "Calm Co.", colours: ["#5E63D6"], site_read_job_id: 40, site_read_problem: "" }],
    "GET /brands/9/screens": [200, []],
  });
  renderAt("/brands/new");
  const form = await screen.findByRole("form", { name: "New brand" });
  await userEvent.type(within(form).getByLabelText("Name"), "Calm Co.");
  await userEvent.type(within(form).getByLabelText("Website (optional)"), "calm dot co");
  await userEvent.click(within(form).getByRole("button", { name: "Make the brand" }));
  expect(within(form).getByText("Paste a web address (https://…)")).toBeInTheDocument();
  expect(calls.some((c) => c.key === "POST /brands")).toBe(false);
  await userEvent.clear(within(form).getByLabelText("Website (optional)"));
  await userEvent.type(within(form).getByLabelText("Website (optional)"), "https://calm.co");
  await userEvent.click(await within(form).findByRole("button", { name: "Make the brand · up to 3 credits" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /brands")?.body).toMatchObject({ website: "https://calm.co" }));
  expect(await screen.findByText("Calm Co. is ready. Reading its site…")).toBeInTheDocument();
});

test("a brand name that is taken shows the server's words under the field", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "POST /brands": [409, { detail: "A brand with that name already exists." }] });
  renderAt("/brands/new");
  const form = await screen.findByRole("form", { name: "New brand" });
  await userEvent.type(within(form).getByLabelText("Name"), "fomo");
  await userEvent.click(within(form).getByRole("button", { name: "Make the brand" }));
  expect(await within(form).findByText("A brand with that name already exists.")).toBeInTheDocument();
});

test("Studio pages and an editor's My credits keep the full rail, on the first brand when none was picked yet (v5 A_Shell)", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /team/members": [200, members], "GET /team/invites": [200, []] });
  renderAt("/team");
  const nav = await screen.findByRole("navigation", { name: "Main" });
  expect(await within(nav).findByRole("button", { name: "Brand: fomo" })).toBeInTheDocument();
  expect(within(nav).getByRole("link", { name: "Videos" })).toHaveAttribute("href", "/b/1/videos");
  expect(within(nav).getByRole("link", { name: "Cast & places" })).toBeInTheDocument();
  cleanup();
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, brands], "GET /usage/mine": [200, { credits: 0, quick_clip_credits: 0, script_credits: 0, videos: [], projects: [], scripts: [], sends: [], waiting_credits: 0, week: { used: 0, allowance: 100, lines: [] } }] });
  renderAt("/usage/mine");
  const editorNav = await screen.findByRole("navigation", { name: "Main" });
  expect(await within(editorNav).findByRole("link", { name: "Scripts" })).toBeInTheDocument();
  expect(within(editorNav).queryByRole("button", { name: "Choose a brand" })).toBeNull();
});

test("an editor's account menu names their role and how much of the week is left (v5 A_Account)", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, brands], "GET /projects": [200, []], "GET /credits/me": [200, { quick_clip_credits_used: 58, quick_clip_credits_allowed: 200, resets_on: "2026-11-09", projects: [] }] });
  renderAt("/b/1/projects");
  await userEvent.click(await screen.findByRole("button", { name: "Account menu" }));
  const menu = screen.getByRole("menu", { name: "Account" });
  expect(within(menu).getByText("· Editor")).toBeInTheDocument();
  expect(await within(menu).findByText("142 of 200 left")).toBeInTheDocument();
  expect(within(menu).getByRole("menuitemradio", { name: "System" })).toBeInTheDocument();
});
