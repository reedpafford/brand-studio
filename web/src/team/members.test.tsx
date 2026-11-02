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

test("People is a table: each other person has a role picker and Remove; Reed's own row has neither", async () => {
  setViewport(1440);
  fakeServer(base());
  open();
  expect(await screen.findByRole("heading", { name: "People · 3" })).toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "Sam's role" })).toHaveValue("editor");
  expect(screen.getByRole("button", { name: "Remove Sam" })).toBeInTheDocument();
  expect(screen.queryByRole("combobox", { name: "Reed's role" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Remove Reed" })).toBeNull();
});

test("picking Owner asks first, changes the role, and Undo sets it back", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "PATCH /team/members/2": [200, {}] }));
  open();
  await userEvent.selectOptions(await screen.findByRole("combobox", { name: "Sam's role" }), "owner");
  const dialog = await screen.findByRole("alertdialog", { name: "Make Sam an owner?" });
  expect(dialog).toHaveTextContent("Owners see dollars, approve spending, and manage the team.");
  expect(calls.some((c) => c.key === "PATCH /team/members/2")).toBe(false);
  await userEvent.click(within(dialog).getByRole("button", { name: "Make owner" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /team/members/2")?.body).toEqual({ role: "owner" }));
  expect(await screen.findByText("Sam is now an owner.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "PATCH /team/members/2").at(-1)?.body).toEqual({ role: "editor" }));
});

test("picking Editor has its own words, and Keep leaves the role as it was", async () => {
  setViewport(1440);
  fakeServer(base());
  open();
  const role = await screen.findByRole("combobox", { name: "Jo's role" });
  await userEvent.selectOptions(role, "editor");
  const dialog = await screen.findByRole("alertdialog", { name: "Make Jo an editor?" });
  expect(dialog).toHaveTextContent("Jo stops seeing dollars and can't manage the team.");
  await userEvent.click(within(dialog).getByRole("button", { name: "Keep as owner" }));
  expect(role).toHaveValue("owner");
});

test("Remove has Undo, which brings the person back", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "DELETE /team/members/2": [204, null], "POST /team/members/2/restore": [200, {}] }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Remove Sam" }));
  await userEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Remove" }));
  expect(await screen.findByText("Sam removed.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /team/members/2/restore")).toBe(true));
  expect(await screen.findByText("Sam is back on the team.")).toBeInTheDocument();
});

test("Removed lists the people removed, each with Restore, and Restore brings them back", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "GET /team/members?removed=true": [200, [{ id: 9, email: "kim@b.co", name: "Kim", role: "editor" }]], "POST /team/members/9/restore": [200, {}] }));
  open();
  const removed = await screen.findByRole("region", { name: "Removed" });
  expect(within(removed).getByRole("heading", { name: "Removed · 1" })).toBeInTheDocument();
  expect(within(removed).getByText("kim@b.co")).toBeInTheDocument();
  await userEvent.click(within(removed).getByRole("button", { name: "Restore Kim" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /team/members/9/restore")).toBe(true));
  expect(await screen.findByText("Kim is back on the team.")).toBeInTheDocument();
});

test("with nobody removed there is no Removed list", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /team/members?removed=true": [200, []] }));
  open();
  await screen.findByText("Sam");
  expect(screen.queryByRole("region", { name: "Removed" })).toBeNull();
});

test("a new invite's link shows at the top with Copy link, and says it works once and ends in 7 days", async () => {
  setViewport(1440);
  const writeText = vi.fn().mockResolvedValue(undefined);
  vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText } });
  fakeServer(base({ "POST /team/invites": [200, { id: 4, email: "ed@b.co", role: "editor", expires_at: "2026-11-09T00:00:00Z", token: "tok7" }] }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Invite someone" }));
  await userEvent.type(screen.getByLabelText("Email to invite"), "ed@b.co");
  await userEvent.click(screen.getByRole("button", { name: "Create invite link" }));
  const card = await screen.findByRole("region", { name: "Invite link" });
  expect(card).toHaveTextContent("Invite link for an editor · ed@b.co");
  expect(card).toHaveTextContent("Works once · ends in 7 days");
  expect(within(card).getByLabelText("Invite link")).toHaveValue(`${location.origin}/invite/tok7`);
  await userEvent.click(within(card).getByRole("button", { name: "Copy link" }));
  expect(writeText).toHaveBeenCalledWith(`${location.origin}/invite/tok7`);
});
