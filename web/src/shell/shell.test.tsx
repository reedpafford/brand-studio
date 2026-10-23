import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";

const owner = { id: 1, email: "reed@b.co", name: "Reed", role: "owner", workspace_id: 1 };
const editor = { ...owner, id: 2, name: "Eli", role: "editor" };
const brands = [
  { id: 1, name: "fomo" },
  { id: 2, name: "Iron Paws" },
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

test("the first brand opens, and the switcher changes brand", async () => {
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands] });
  renderAt("/");
  expect(await screen.findByRole("heading", { name: "fomo" })).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText("Brand"), "Iron Paws");
  expect(await screen.findByRole("heading", { name: "Iron Paws" })).toBeInTheDocument();
});

test("the last brand you used opens next time", async () => {
  localStorage.setItem("bs.lastBrand", "2");
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, brands] });
  renderAt("/");
  expect(await screen.findByRole("heading", { name: "Iron Paws" })).toBeInTheDocument();
});

test("the owner can invite and gets the link once", async () => {
  const calls = fakeServer({
    "GET /auth/me": [200, owner],
    "GET /brands": [200, brands],
    "GET /team/members": [200, members],
    "GET /team/invites": [200, []],
    "POST /team/invites": [201, { id: 3, email: "new@b.co", role: "editor", expires_at: "2026-11-01T00:00:00Z", token: "tok123" }],
  });
  renderAt("/team");
  await userEvent.type(await screen.findByLabelText("Email to invite"), "new@b.co");
  await userEvent.click(screen.getByRole("button", { name: "Create invite link" }));
  expect(await screen.findByLabelText("Invite link")).toHaveValue(`${location.origin}/invite/tok123`);
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
  await userEvent.click(await screen.findByRole("button", { name: "Sign out" }));
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
});
