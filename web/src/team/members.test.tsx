import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";
import { owner } from "../test/people";

const members = [
  { id: 1, email: "reed@b.co", name: "Reed", role: "owner" },
  { id: 2, email: "sam@b.co", name: "Sam", role: "editor" },
  { id: 3, email: "jo@b.co", name: "Jo", role: "owner" },
];
const base = (o: Record<string, [number, unknown]> = {}): Record<string, [number, unknown]> => ({
  "GET /auth/me": [200, owner],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /team/members": [200, members],
  "GET /team/invites": [200, []],
  "GET /credits/limits": [200, { weekly_quick_clip_credits: 145, per_video_max_credits: 729 }],
  "GET /credits/allowances": [200, []],
  ...o,
});
function open() {
  renderApp("/team");
}
afterEach(() => vi.unstubAllGlobals());

test("each other person has a menu with Make owner or Make editor, and Remove; Reed's own row has none", async () => {
  setViewport(1440);
  fakeServer(base());
  open();
  await screen.findByText("Sam");
  expect(screen.queryByRole("button", { name: "More for Reed" })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "More for Sam" }));
  expect(screen.getByRole("menuitem", { name: "Make owner" })).toBeInTheDocument();
  expect(screen.getByRole("menuitem", { name: "Remove" })).toBeInTheDocument();
});

test("Make owner asks first, changes the role, and Undo sets it back", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "PATCH /team/members/2": [200, {}] }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "More for Sam" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Make owner" }));
  const dialog = await screen.findByRole("alertdialog", { name: "Make Sam an owner?" });
  expect(dialog).toHaveTextContent("Owners see dollars, approve spending, and manage the team.");
  expect(calls.some((c) => c.key === "PATCH /team/members/2")).toBe(false);
  await userEvent.click(within(dialog).getByRole("button", { name: "Make owner" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /team/members/2")?.body).toEqual({ role: "owner" }));
  expect(await screen.findByText("Sam is now an owner.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "PATCH /team/members/2").at(-1)?.body).toEqual({ role: "editor" }));
});

test("Make editor has its own words", async () => {
  setViewport(1440);
  fakeServer(base());
  open();
  await userEvent.click(await screen.findByRole("button", { name: "More for Jo" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Make editor" }));
  const dialog = await screen.findByRole("alertdialog", { name: "Make Jo an editor?" });
  expect(dialog).toHaveTextContent("Jo stops seeing dollars and can't manage the team.");
  expect(within(dialog).getByRole("button", { name: "Keep as owner" })).toBeInTheDocument();
});

test("Remove has Undo, which brings the person back", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "DELETE /team/members/2": [204, null], "POST /team/members/2/restore": [200, {}] }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "More for Sam" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Remove" }));
  await userEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Remove" }));
  expect(await screen.findByText("Sam removed.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /team/members/2/restore")).toBe(true));
  expect(await screen.findByText("Sam is back on the team.")).toBeInTheDocument();
});

test("Show removed lists the people removed, each with Restore, and Restore brings them back", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "GET /team/members?removed=true": [200, [{ id: 9, email: "kim@b.co", name: "Kim", role: "editor" }]], "POST /team/members/9/restore": [200, {}] }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Show removed (1)" }));
  expect(screen.getByText("kim@b.co · Removed")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Restore Kim" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /team/members/9/restore")).toBe(true));
  expect(await screen.findByText("Kim is back on the team.")).toBeInTheDocument();
});

test("with nobody removed there is no Show removed button", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /team/members?removed=true": [200, []] }));
  open();
  await screen.findByText("Sam");
  expect(screen.queryByRole("button", { name: /Show removed/ })).toBeNull();
});
