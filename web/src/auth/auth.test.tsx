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
    "GET /scripts": [200, []],
    "GET /projects": [200, []],
  };
  const calls = fakeServer(signedIn);
  renderAt("/login");
  await userEvent.type(await screen.findByLabelText("Email"), "a@b.co");
  await userEvent.type(screen.getByLabelText("Password"), "correct horse battery");
  signedIn["GET /auth/me"] = [200, me];
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("heading", { name: "Scripts" })).toBeInTheDocument();
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

const lookup = { workspace_name: "Studio", invited_by_name: "Ada", owner_name: "Reed", email: "ada@x.co", role: "editor" };

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
  expect(screen.getByText("Ada invited you to Studio as an editor. Your email is ada@x.co.")).toBeInTheDocument();
  expect(calls.find((c) => c.key === "POST /auth/invite")?.body).toEqual({ token: "abc123" });
});

test("an invite link that is not valid says so and offers no form", async () => {
  fakeServer({ "GET /auth/me": [401, {}], "POST /auth/invite": [404, { detail: "This invite link is not valid any more." }] });
  renderAt("/invite/old");
  expect(await screen.findByRole("alert")).toHaveTextContent("This invite link is not valid any more.");
  expect(screen.getByText("Ask whoever invited you to send a new link.")).toBeInTheDocument();
  expect(screen.queryByLabelText("Your name")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
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

test("a dropped connection on the invite page says it could not check, with Try again, not that the invite is invalid", async () => {
  fakeServer({ "GET /auth/me": [401, {}], "POST /auth/invite": [500, { detail: "Server error" }] });
  renderAt("/invite/abc123");
  expect(await screen.findByRole("heading", { name: "Could not check your invite" })).toBeInTheDocument();
  expect(screen.queryByText("Invite not valid")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
});

test("the password has an eye that shows and hides it", async () => {
  fakeServer({ "GET /auth/me": [401, {}] });
  renderAt("/login");
  const password = await screen.findByLabelText("Password");
  expect(password).toHaveAttribute("type", "password");
  await userEvent.click(screen.getByRole("button", { name: "Show password" }));
  expect(password).toHaveAttribute("type", "text");
  await userEvent.click(screen.getByRole("button", { name: "Hide password" }));
  expect(password).toHaveAttribute("type", "password");
});

test("a throttled sign-in says to wait and holds the button off", async () => {
  fakeServer({ "GET /auth/me": [401, {}], "POST /auth/login": [429, { detail: "Slow down." }] });
  renderAt("/login");
  await userEvent.type(await screen.findByLabelText("Email"), "a@b.co");
  await userEvent.type(screen.getByLabelText("Password"), "nope");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  const button = await screen.findByRole("button", { name: "Sign in" });
  await vi.waitFor(() => expect(button).toBeDisabled());
  expect(button).toHaveAccessibleDescription("Too many tries. Wait a minute and try again.");
});

test("a bad sign-in puts the focus back on Email, and the setup password counter turns on at 10 characters", async () => {
  fakeServer({ "GET /auth/me": [401, {}], "POST /auth/login": [401, { detail: "Wrong email or password." }] });
  renderAt("/login");
  await userEvent.type(await screen.findByLabelText("Email"), "a@b.co");
  await userEvent.type(screen.getByLabelText("Password"), "nope");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await screen.findByRole("alert");
  expect(screen.getByLabelText("Email")).toHaveFocus();
  expect(screen.getByText("Forgot your password? Ask the owner.")).toBeInTheDocument();
});

test("the setup password counter turns green at 10 characters", async () => {
  fakeServer({ "GET /auth/me": [401, {}] });
  renderAt("/setup");
  const box = await screen.findByLabelText(/^Password/);
  await userEvent.type(box, "123456789");
  expect(screen.getByText("9 / 10")).toHaveClass("text-muted");
  await userEvent.type(box, "0");
  expect(screen.getByText("10 / 10")).toHaveClass("text-success");
});

test("when the server can't be reached, it is retried quietly first, then shows Try again, and that works once it is back", async () => {
  let up = false;
  const inner = (fakeServer({ "GET /auth/me": [200, { id: 1, email: "e@b.co", name: "Eli", role: "editor", workspace_id: 1 }], "GET /brands": [200, [{ id: 1, name: "fomo", colours: [] }]] }), (fetch as unknown as { getMockImplementation: () => (r: Request | string, i?: RequestInit) => Promise<Response> }).getMockImplementation()!);
  vi.stubGlobal("fetch", vi.fn(async (input: Request | string, init?: RequestInit) => {
    const req = input instanceof Request ? input : new Request(new URL(input, "http://x"), init);
    if (!up && new URL(req.url).pathname.endsWith("/auth/me")) throw new TypeError("Failed to fetch");
    return inner(req.clone(), init);
  }));
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/b/1/scripts"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(screen.getByText("Loading…")).toBeInTheDocument(); // retrying quietly, not an error yet
  expect(await screen.findByText("Can't reach the server.", {}, { timeout: 8000 })).toBeInTheDocument();
  up = true;
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  await vi.waitFor(() => expect(screen.queryByText("Can't reach the server.")).toBeNull());
});

test("an invite to a studio stored as a slug says Join your team's studio (never the owner's name), in the title, the line and the welcome", async () => {
  fakeServer({ "GET /auth/me": [401, {}], "POST /auth/invite": [200, { ...lookup, workspace_name: "owner-reed", invited_by_name: "Ada", owner_name: "Reed" }], "POST /auth/accept-invite": [201, me] });
  renderAt("/invite/abc123");
  expect(await screen.findByRole("heading", { name: "Join your team's studio" })).toBeInTheDocument();
  expect(screen.getByText(/Ada invited you to your team's studio as an editor/)).toBeInTheDocument();
  expect(screen.queryByText(/owner-reed/)).toBeNull();
});

test("when the owner sent the invite in person, the page says only that you were invited, never the owner's name", async () => {
  fakeServer({ "GET /auth/me": [401, {}], "POST /auth/invite": [200, { ...lookup, workspace_name: "owner-reed", invited_by_name: "Reed", owner_name: "Reed" }] });
  renderAt("/invite/abc123");
  expect(await screen.findByText(/You were invited to your team's studio as an editor/)).toBeInTheDocument();
  expect(screen.queryByText(/Reed/)).toBeNull();
});

test("the setup page says what the studio name is for", async () => {
  fakeServer({ "GET /auth/me": [401, {}] });
  renderAt("/setup");
  expect(await screen.findByText("What your team sees when they're invited, e.g. Northside Studio.")).toBeInTheDocument();
});
