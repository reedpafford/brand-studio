import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";

const me = { id: 1, email: "a@b.co", name: "Ada", role: "owner", workspace_id: 1 };

function renderAt(path: string) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

test("signed-out visitors are sent to sign in", async () => {
  fakeServer({ "GET /auth/me": [401, { detail: "no" }] });
  renderAt("/");
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
});

test("signing in lands on the app", async () => {
  const signedIn: Record<string, [number, unknown]> = {
    "GET /auth/me": [401, {}],
    "POST /auth/login": [200, me],
    "GET /brands": [200, [{ id: 7, name: "fomo" }]],
    "GET /projects": [200, []],
  };
  const calls = fakeServer(signedIn);
  renderAt("/login");
  await userEvent.type(await screen.findByLabelText("Email"), "a@b.co");
  await userEvent.type(screen.getByLabelText("Password"), "correct horse battery");
  signedIn["GET /auth/me"] = [200, me];
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("heading", { name: "Projects" })).toBeInTheDocument();
  expect(calls.find((c) => c.key === "POST /auth/login")?.body).toEqual({
    email: "a@b.co",
    password: "correct horse battery",
  });
});

test("a wrong password shows the server's message", async () => {
  fakeServer({ "GET /auth/me": [401, {}], "POST /auth/login": [401, { detail: "Wrong email or password." }] });
  renderAt("/login");
  await userEvent.type(await screen.findByLabelText("Email"), "a@b.co");
  await userEvent.type(screen.getByLabelText("Password"), "nope");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Wrong email or password.");
});

const lookup = { workspace_name: "Studio", invited_by_name: "Reed", email: "ada@x.co", role: "editor" };

test("accepting an invite sends the link's token", async () => {
  const calls = fakeServer({ "GET /auth/me": [401, {}], "POST /auth/invite": [200, lookup], "POST /auth/accept-invite": [201, me] });
  renderAt("/invite/abc123");
  await userEvent.type(await screen.findByLabelText("Your name"), "Ada");
  await userEvent.type(screen.getByLabelText(/Choose a password/), "correct horse battery");
  await userEvent.click(screen.getByRole("button", { name: "Create my account" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /auth/accept-invite")).toBe(true));
  expect(calls.find((c) => c.key === "POST /auth/accept-invite")?.body).toMatchObject({ token: "abc123", name: "Ada" });
});

test("the invite page says who invited you, to which studio, and as what; the token is sent in the body", async () => {
  const calls = fakeServer({ "GET /auth/me": [401, {}], "POST /auth/invite": [200, lookup] });
  renderAt("/invite/abc123");
  expect(await screen.findByRole("heading", { name: "Join Studio" })).toBeInTheDocument();
  expect(screen.getByText("Reed invited you to Studio as an editor. Your email is ada@x.co.")).toBeInTheDocument();
  expect(calls.find((c) => c.key === "POST /auth/invite")?.body).toEqual({ token: "abc123" });
});

test("an invite link that is not valid says so and offers no form", async () => {
  fakeServer({ "GET /auth/me": [401, {}], "POST /auth/invite": [404, { detail: "This invite link is not valid any more." }] });
  renderAt("/invite/old");
  expect(await screen.findByRole("alert")).toHaveTextContent("This invite link is not valid any more.");
  expect(screen.getByText("Ask whoever invited you to send a new link.")).toBeInTheDocument();
  expect(screen.queryByLabelText("Your name")).not.toBeInTheDocument();
});

test("setup tells you when the studio already exists", async () => {
  fakeServer({ "GET /auth/me": [401, {}], "POST /auth/setup": [409, { detail: "Already set up." }] });
  renderAt("/setup");
  const entries: [string | RegExp, string][] = [
    [/Setup code/, "code"],
    ["Studio name", "Fomo"],
    ["Your name", "Ada"],
    ["Email", "a@b.co"],
    [/Password/, "correct horse battery"],
  ];
  for (const [label, value] of entries) await userEvent.type(await screen.findByLabelText(label), value);
  await userEvent.click(screen.getByRole("button", { name: "Create owner account" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Already set up.");
});
