import { render, screen, within } from "@testing-library/react";
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
  expect(screen.getByText("Brands are set up by Reed.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("menuitemradio", { name: "Iron Paws" }));
  expect(await screen.findByText("No scripts for Iron Paws yet.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Brand: Iron Paws" })).toBeInTheDocument();
  // Cast & places in one brand becomes Cast & places in the other.
  await userEvent.click(within(screen.getByRole("navigation", { name: "Main" })).getByRole("link", { name: "Cast & places" }));
  await screen.findByRole("heading", { name: "Library" });
  await pickBrand("fomo");
  expect(await screen.findByRole("heading", { name: "Library" })).toBeInTheDocument();
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

test("the owner can invite and gets the link once", async () => {
  const calls = fakeServer({
    "GET /auth/me": [200, owner],
    "GET /brands": [200, brands],
    "GET /team/members": [200, members],
    "GET /team/invites": [200, []],
    "POST /team/invites": [201, { id: 3, email: "new@b.co", role: "editor", expires_at: "2026-11-01T12:00:00Z", token: "tok123" }],
  });
  renderAt("/team");
  await userEvent.type(await screen.findByLabelText("Email to invite"), "new@b.co");
  await userEvent.click(screen.getByRole("button", { name: "Create invite link" }));
  expect(await screen.findByLabelText("Invite link")).toHaveValue(`${location.origin}/invite/tok123`);
  expect(screen.getByText(/Works once\. Expires/)).toBeInTheDocument();
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.assign(navigator, { clipboard: { writeText } });
  await userEvent.click(screen.getByRole("button", { name: "Copy link" }));
  expect(writeText).toHaveBeenCalledWith(`${location.origin}/invite/tok123`);
  expect(await screen.findByRole("button", { name: "Copied" })).toBeInTheDocument();
  expect(calls.find((c) => c.key === "POST /team/invites")?.body).toEqual({ email: "new@b.co", role: "editor" });
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
  vi.spyOn(window, "confirm").mockReturnValue(true);
  renderAt("/team");
  await userEvent.click(await screen.findByRole("button", { name: "Remove Eli" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not remove that person");
});

test("on a phone there are four tabs, no More, and Reed gets an Approvals bell with the count", async () => {
  setViewport(390);
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /jobs": [200, [{ id: 5, kind: "video", status: "needs_owner_approval", project_id: null, credits: 4, created_at: "2026-10-24T10:00:00Z" }]], "GET /scripts": [200, []], "GET /projects": [200, []] });
  renderAt("/b/1/projects");
  const tabs = await screen.findByRole("navigation", { name: "Tabs" });
  expect(within(tabs).getAllByRole("link").map((l) => l.textContent)).toEqual(["Scripts", "Quick clip", "Cast", "Brand"]);
  expect(within(tabs).getByRole("link", { name: "Cast" })).toHaveAttribute("href", "/b/1/library");
  expect(within(tabs).getByRole("link", { name: "Brand" })).toHaveAttribute("href", "/b/1/brand");
  expect(within(tabs).queryByRole("button", { name: "More" })).not.toBeInTheDocument();
  expect(await screen.findByRole("link", { name: "Approvals, 1 waiting" })).toHaveAttribute("href", "/approvals");
  expect(screen.queryByRole("navigation", { name: "Main" })).not.toBeInTheDocument();
});

test("an editor has no Approvals bell", async () => {
  setViewport(390);
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []] });
  renderAt("/b/1/projects");
  await screen.findByRole("navigation", { name: "Tabs" });
  expect(screen.queryByRole("link", { name: /Approvals/ })).not.toBeInTheDocument();
});

test("the account menu has Team for Reed only, the theme choices, and Sign out; Escape closes it", async () => {
  setViewport(1440);
  localStorage.removeItem("bs.theme");
  document.documentElement.removeAttribute("data-theme");
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /projects": [200, []], "POST /auth/logout": [204, null] });
  renderAt("/b/1/projects");
  const menu = await screen.findByRole("button", { name: "Account menu" });
  await userEvent.click(menu);
  expect(screen.getByText("reed@b.co")).toBeInTheDocument();
  expect(within(screen.getByRole("menu", { name: "Account" })).getByRole("link", { name: "Team" })).toHaveAttribute("href", "/team");
  expect(screen.getByRole("menuitemradio", { name: "Dark" })).toHaveAttribute("aria-checked", "true");
  await userEvent.click(screen.getByRole("menuitemradio", { name: "Light" }));
  expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  expect(screen.getByRole("menuitemradio", { name: "Light" })).toHaveAttribute("aria-checked", "true");
  await userEvent.click(screen.getByRole("menuitemradio", { name: "Match my device" }));
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

test("on desktop the rail has the four brand sections, and Studio (Approvals with its count, Team) for Reed only", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []], "GET /jobs": [200, [{ id: 5, kind: "video", status: "needs_owner_approval", project_id: null, credits: 4, created_at: "2026-10-24T10:00:00Z" }]] });
  renderAt("/b/1/projects");
  const rail = await screen.findByRole("navigation", { name: "Main" });
  expect(await within(rail).findByText("fomo")).toBeInTheDocument();
  expect(within(rail).getAllByRole("link").map((l) => l.textContent?.replace(/\d+ waiting$/, "").trim())).toEqual(["Scripts", "Quick clip", "Cast & places", "Brand", "Approvals", "Team"]);
  expect(within(rail).getByRole("link", { name: "Scripts" })).toHaveAttribute("aria-current", "page");
  expect(await within(rail).findByRole("link", { name: /Approvals/ })).toHaveTextContent("1");
  expect(screen.getAllByRole("link", { name: /Approvals/ })).toHaveLength(2); // the rail item and the top-bar pill both go to /approvals
  expect(screen.queryByRole("navigation", { name: "Tabs" })).not.toBeInTheDocument();
});

test("an editor's rail has no Studio group", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, editor], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []] });
  renderAt("/b/1/projects");
  const rail = await screen.findByRole("navigation", { name: "Main" });
  expect(within(rail).getAllByRole("link")).toHaveLength(4);
  expect(within(rail).queryByRole("link", { name: /Approvals|Team/ })).not.toBeInTheDocument();
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
  expect(screen.getByText(/Reed adds brands/)).toBeInTheDocument();
});

test("offline, a banner says nothing was lost", async () => {
  vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /scripts": [200, []], "GET /projects": [200, []] });
  renderAt("/b/1/projects");
  expect(await screen.findByText("You're offline.")).toBeInTheDocument();
  expect(screen.getByText("Reconnect to keep working; nothing was lost.")).toBeInTheDocument();
});
