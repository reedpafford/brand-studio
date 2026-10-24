import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";

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

test("the first brand opens on its Projects, and the switcher changes brand", async () => {
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /projects": [200, []] });
  renderAt("/");
  expect(await screen.findByRole("heading", { name: "Projects" })).toBeInTheDocument();
  expect(screen.getByLabelText("Brand")).toHaveValue("1");
  await userEvent.selectOptions(screen.getByLabelText("Brand"), "Iron Paws");
  expect(await screen.findByText("No videos for Iron Paws yet.")).toBeInTheDocument();
  expect(screen.getByLabelText("Brand")).toHaveValue("2");
});

test("the brand's colour is applied, and cleared for a brand without one", async () => {
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /projects": [200, []] });
  renderAt("/b/1");
  await screen.findByRole("heading", { name: "Projects" });
  expect(document.documentElement.style.getPropertyValue("--brand")).toBe("#ff5500");
  await userEvent.selectOptions(screen.getByLabelText("Brand"), "Iron Paws");
  await screen.findByText("No videos for Iron Paws yet.");
  expect(document.documentElement.style.getPropertyValue("--brand")).toBe("");
});

test("the team page keeps the brand you were in", async () => {
  localStorage.setItem("bs.lastBrand", "2");
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /team/members": [200, members], "GET /team/invites": [200, []] });
  renderAt("/team");
  expect(await screen.findByLabelText("Brand")).toHaveValue("2");
  expect(screen.getByRole("link", { name: "Kit" })).toHaveAttribute("href", "/b/2/kit");
});

test("the last brand you used opens next time", async () => {
  localStorage.setItem("bs.lastBrand", "2");
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /projects": [200, []] });
  renderAt("/");
  expect(await screen.findByText("No videos for Iron Paws yet.")).toBeInTheDocument();
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
  await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
});

test("an unknown brand in the address does not pretend to be selected", async () => {
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands] });
  renderAt("/b/999");
  expect(await screen.findByLabelText("Brand")).toHaveValue("");
});

test("a failed remove tells you", async () => {
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /team/members": [200, members], "GET /team/invites": [200, []], "DELETE /team/members/2": [500, {}] });
  vi.spyOn(window, "confirm").mockReturnValue(true);
  renderAt("/team");
  await userEvent.click(await screen.findByRole("button", { name: "Remove Eli" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not remove that person");
});

test("on a phone the tab bar reaches every section through More", async () => {
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands] });
  renderAt("/b/1");
  const tabs = await screen.findByRole("navigation", { name: "Tabs" });
  expect(within(tabs).getByRole("link", { name: "Clip" })).toHaveAttribute("href", "/b/1/clip");
  expect(within(tabs).getByRole("link", { name: "Library" })).toHaveAttribute("href", "/b/1/library");
  await userEvent.click(within(tabs).getByRole("button", { name: "More" }));
  expect(screen.getByRole("link", { name: "Brand kit" })).toHaveAttribute("href", "/b/1/kit");
  expect(screen.getAllByRole("link", { name: "Team" }).length).toBeGreaterThan(0);
});

test("the More menu closes on Escape or a tap outside, and can switch theme and sign out", async () => {
  localStorage.removeItem("bs.theme");
  document.documentElement.removeAttribute("data-theme");
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "POST /auth/logout": [204, null] });
  renderAt("/b/1");
  const tabs = await screen.findByRole("navigation", { name: "Tabs" });
  const more = within(tabs).getByRole("button", { name: "More" });
  await userEvent.click(more);
  await userEvent.keyboard("{Escape}");
  expect(screen.queryByRole("link", { name: "Brand kit" })).not.toBeInTheDocument();
  await userEvent.click(more);
  await userEvent.click(screen.getByRole("button", { name: "Close menu" }));
  expect(screen.queryByRole("link", { name: "Brand kit" })).not.toBeInTheDocument();
  await userEvent.click(more);
  // Dark is the default; each press goes dark → light → system.
  await userEvent.click(screen.getByRole("button", { name: "Theme: Dark" }));
  expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  document.documentElement.removeAttribute("data-theme");
});

test("More is highlighted on a page it holds", async () => {
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /team/members": [200, members], "GET /team/invites": [200, []] });
  renderAt("/team");
  const tabs = await screen.findByRole("navigation", { name: "Tabs" });
  expect(within(tabs).getByRole("button", { name: "More" })).toHaveClass("text-accent-text");
});
