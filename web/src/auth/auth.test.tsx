import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { renderApp } from "../test/render";

const me = { id: 1, email: "a@b.co", name: "Ada", role: "owner", workspace_id: 1 };

function renderAt(path: string) {
  renderApp(path);
}

afterEach(() => vi.unstubAllGlobals());

test("signed-out visitors are sent to sign in", async () => {
  fakeServer({ "GET /auth/me": [401, { detail: "no" }] });
  renderAt("/");
  expect(await screen.findByRole("heading", { name: "Sign in to Brand Studio" })).toBeInTheDocument();
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
  expect(await screen.findByRole("button", { name: "Brand: fomo" })).toBeInTheDocument(); // in the app, on its brand
  expect(calls.find((c) => c.key === "POST /auth/login")?.body).toEqual({
    email: "a@b.co",
    password: "correct horse battery",
  });
});

test("a wrong password says so in v5's words, as plain red text under the fields; the labels are muted", async () => {
  fakeServer({ "GET /auth/me": [401, {}], "POST /auth/login": [401, { detail: "Wrong email or password." }] });
  renderAt("/login");
  await userEvent.type(await screen.findByLabelText("Email"), "a@b.co");
  await userEvent.type(screen.getByLabelText("Password"), "nope");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("That email and password don't match.");
  expect(screen.getByRole("alert")).toHaveClass("text-danger");
  expect(document.querySelector("form label")).toHaveClass("text-sm"); // 13 px
  expect(document.querySelector("form")).toHaveClass("[&_label]:text-muted");
});

const lookup = { workspace_name: "Studio", invited_by_name: "Ada", owner_name: "Reed", email: "ada@x.co", role: "editor" };

test("accepting an invite sends the link's token", async () => {
  const calls = fakeServer({ "GET /auth/me": [401, {}], "POST /auth/invite": [200, lookup], "POST /auth/accept-invite": [201, me] });
  renderAt("/invite/abc123");
  await userEvent.type(await screen.findByLabelText("Your name"), "Ada");
  await userEvent.type(screen.getByLabelText(/Choose a password/), "correct horse battery");
  await userEvent.click(screen.getByRole("button", { name: "Join" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /auth/accept-invite")).toBe(true));
  expect(calls.find((c) => c.key === "POST /auth/accept-invite")?.body).toMatchObject({ token: "abc123", name: "Ada" });
});

test("the invite page says who invited you, to which studio, and as what; the token is sent in the body", async () => {
  const calls = fakeServer({ "GET /auth/me": [401, {}], "POST /auth/invite": [200, lookup] });
  renderAt("/invite/abc123");
  expect(await screen.findByRole("heading", { name: "Join Studio" })).toBeInTheDocument();
  expect(screen.getByText("Ada invited you as an editor. You can write scripts and make videos; Ada approves anything past your weekly credits.")).toBeInTheDocument();
  const email = screen.getByLabelText("Email"); // v5 A_Invite: the invite's email, read-only, above Your name
  expect(email).toHaveValue("ada@x.co");
  expect(email).toHaveAttribute("readonly");
  expect(screen.getAllByRole("textbox")[0]).toBe(email);
  expect(calls.find((c) => c.key === "POST /auth/invite")?.body).toEqual({ token: "abc123" });
});

test("an invite link that is not valid says so and offers no form", async () => {
  fakeServer({ "GET /auth/me": [401, {}], "POST /auth/invite": [404, { detail: "This invite link is not valid any more." }] });
  renderAt("/invite/old");
  // v5 A_Invite: one line, sending nobody to the owner (rule 22).
  expect(await screen.findByRole("alert")).toHaveTextContent("This invite has been used or has run out. You'll need a new link.");
  expect(screen.queryByText(/owner|Ask /)).toBeNull();
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
  await userEvent.click(screen.getByRole("button", { name: "Create the studio" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Already set up.");
});

test("a dropped connection on the invite page says it could not check, with Try again, not that the invite is invalid", async () => {
  fakeServer({ "GET /auth/me": [401, {}], "POST /auth/invite": [500, { detail: "Server error" }] });
  renderAt("/invite/abc123");
  expect(await screen.findByRole("heading", { name: "Could not check your invite" })).toBeInTheDocument();
  expect(screen.queryByText("Invite not valid")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
});

test("the password is a plain password box: no eye, no counter (v5 A_SignIn, A_Setup)", async () => {
  fakeServer({ "GET /auth/me": [401, {}] });
  renderAt("/login");
  const password = await screen.findByLabelText("Password");
  expect(password).toHaveAttribute("type", "password");
  expect(screen.queryByRole("button", { name: "Show password" })).toBeNull();
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

test("a bad sign-in puts the focus back on Email, and the footer says how to get an account", async () => {
  fakeServer({ "GET /auth/me": [401, {}], "POST /auth/login": [401, { detail: "Wrong email or password." }] });
  renderAt("/login");
  await userEvent.type(await screen.findByLabelText("Email"), "a@b.co");
  await userEvent.type(screen.getByLabelText("Password"), "nope");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await screen.findByRole("alert");
  expect(screen.getByLabelText("Email")).toHaveFocus();
  expect(screen.getByText("No account? You'll need an invite link.")).toBeInTheDocument();
});

test("the setup password says at least 10 characters and the browser holds a shorter one; there's no Sign in line", async () => {
  fakeServer({ "GET /auth/me": [401, {}] });
  renderAt("/setup");
  const box = await screen.findByLabelText("Password (at least 10 characters)");
  expect(box).toHaveAttribute("minLength", "10");
  expect(screen.queryByText(/^Already set up/)).toBeNull();
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

test("an invite to a studio stored as a slug says Join {owner}'s studio, in the title, the line and the welcome", async () => {
  fakeServer({ "GET /auth/me": [401, {}], "POST /auth/invite": [200, { ...lookup, workspace_name: "owner-reed", invited_by_name: "Reed", owner_name: "Reed" }], "POST /auth/accept-invite": [201, me] });
  renderAt("/invite/abc123");
  expect(await screen.findByRole("heading", { name: "Join Reed's studio" })).toBeInTheDocument();
  expect(screen.getByText(/^Reed invited you as an editor/)).toBeInTheDocument();
  expect(screen.queryByText(/owner-reed/)).toBeNull();
});

test("the setup page says it shows once and who you'll be, and asks for the code last (v5 A_Setup)", async () => {
  fakeServer({ "GET /auth/me": [401, {}] });
  renderAt("/setup");
  expect(await screen.findByRole("heading", { name: "Set up your studio" })).toBeInTheDocument();
  expect(screen.getByText("First run · this page shows once")).toBeInTheDocument();
  expect(screen.getByText("You'll be the owner: you approve what editors spend and set the budgets.")).toBeInTheDocument();
  const labels = [...document.querySelectorAll("form label")].map((l) => l.textContent);
  expect(labels.at(0)).toBe("Studio name");
  expect(labels.at(-1)).toBe("Setup code (from the server's environment)");
});

test("a refused email invite puts the focus on Your name, not the read-only email", async () => {
  fakeServer({ "GET /auth/me": [401, {}], "POST /auth/invite": [200, lookup], "POST /auth/accept-invite": [400, { detail: "This invite link is not valid any more." }] });
  renderAt("/invite/abc123");
  await userEvent.type(await screen.findByLabelText("Your name"), "Ada");
  await userEvent.type(screen.getByLabelText(/Choose a password/), "correct horse battery");
  await userEvent.click(screen.getByRole("button", { name: "Join" }));
  expect(await screen.findByRole("alert")).toBeInTheDocument();
  expect(screen.getByLabelText("Your name")).toHaveFocus();
});

test("the studio's standing editor link asks for an email and sends it; an email already in use says so (#1247)", async () => {
  const calls = fakeServer({ "GET /auth/me": [401, {}], "POST /auth/invite": [200, { ...lookup, email: "" }], "POST /auth/accept-invite": [409, { detail: "That email already has an account here, so this link can't use it. Sign in, or join with another email." }] });
  renderAt("/invite/link9");
  await userEvent.type(await screen.findByLabelText("Email"), "new@x.co");
  await userEvent.type(screen.getByLabelText("Your name"), "Neo");
  await userEvent.type(screen.getByLabelText(/Choose a password/), "correct horse battery");
  await userEvent.click(screen.getByRole("button", { name: "Join" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("That email already has an account here, so this link can't use it. Sign in, or join with another email.");
  expect(calls.find((c) => c.key === "POST /auth/accept-invite")?.body).toMatchObject({ token: "link9", email: "new@x.co", name: "Neo" });
  expect(screen.queryByText(/Your email is/)).toBeNull();
});

test("a standing link that was used or stopped shows the server's words when the form is sent (#1247)", async () => {
  fakeServer({ "GET /auth/me": [401, {}], "POST /auth/invite": [200, { ...lookup, email: "" }], "POST /auth/accept-invite": [400, { detail: "This invite link is not valid any more." }] });
  renderAt("/invite/link9");
  await userEvent.type(await screen.findByLabelText("Email"), "new@x.co");
  await userEvent.type(screen.getByLabelText("Your name"), "Neo");
  await userEvent.type(screen.getByLabelText(/Choose a password/), "correct horse battery");
  await userEvent.click(screen.getByRole("button", { name: "Join" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("This invite link is not valid any more.");
});
