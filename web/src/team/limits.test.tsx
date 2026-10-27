import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const owner = { id: 1, email: "reed@b.co", name: "Reed", role: "owner", workspace_id: 1 };
const base = (o: Record<string, [number, unknown]> = {}): Record<string, [number, unknown]> => ({
  "GET /auth/me": [200, owner],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /team/members": [200, [{ id: 1, name: "Reed", email: "reed@b.co", role: "owner" }]],
  "GET /team/invites": [200, []],
  "GET /workspace": [200, { id: 1, name: "Iron Paws Studio" }],
  "GET /credits/limits": [200, { weekly_quick_clip_credits: 145, per_video_max_credits: 729 }],
  "GET /credits/allowances": [200, [{ user_id: 2, name: "Sam", quick_clip_credits_used: 120, quick_clip_credits_allowed: 145 }]],
  ...o,
});
function open() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/team"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
afterEach(() => vi.unstubAllGlobals());

test("Credit limits shows both limits with dollars, and Save limits is disabled until something changes", async () => {
  setViewport(1440);
  fakeServer(base());
  open();
  expect(await screen.findByLabelText("Editors' weekly allowance")).toHaveValue("145");
  expect(screen.getByLabelText("Most one video can cost")).toHaveValue("729");
  expect(screen.getByText(/≈ \$14\.91 a week/)).toBeInTheDocument();
  expect(screen.getByText(/≈ \$74\.94/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Save limits" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Save limits" })).toHaveAccessibleDescription("No changes yet");
});

test("raising the cap saves both values, and Undo saves the old ones back", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "PUT /credits/limits": [200, { weekly_quick_clip_credits: 145, per_video_max_credits: 800 }] }));
  open();
  const cap = await screen.findByLabelText("Most one video can cost");
  await userEvent.clear(cap);
  await userEvent.type(cap, "800");
  await userEvent.click(screen.getByRole("button", { name: "Save limits" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /credits/limits")?.body).toEqual({ weekly_quick_clip_credits: 145, per_video_max_credits: 800 }));
  expect(await screen.findByText("Limits saved.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "PUT /credits/limits").at(-1)?.body).toEqual({ weekly_quick_clip_credits: 145, per_video_max_credits: 729 }));
});

test("lowering the allowance below what an editor has used asks first, in plain words", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "PUT /credits/limits": [200, { weekly_quick_clip_credits: 100, per_video_max_credits: 729 }] }));
  open();
  const weekly = await screen.findByLabelText("Editors' weekly allowance");
  await userEvent.clear(weekly);
  await userEvent.type(weekly, "100");
  await userEvent.click(screen.getByRole("button", { name: "Save limits" }));
  const dialog = await screen.findByRole("alertdialog", { name: "Lower the weekly allowance?" });
  expect(dialog).toHaveTextContent("Sam has used 120 credits this week. With 100, Sam can't make anything more until Monday.");
  expect(calls.some((c) => c.key === "PUT /credits/limits")).toBe(false);
  await userEvent.click(within(dialog).getByRole("button", { name: "Save 100" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "PUT /credits/limits")).toBe(true));
});

test("a value that isn't a whole number says so and can't be saved", async () => {
  setViewport(1440);
  fakeServer(base());
  open();
  const weekly = await screen.findByLabelText("Editors' weekly allowance");
  await userEvent.clear(weekly);
  await userEvent.type(weekly, "12.5");
  expect(screen.getByText("Use a whole number of credits.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Save limits" })).toBeDisabled();
});

test("an editor doesn't see Credit limits", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /auth/me": [200, { ...owner, id: 2, role: "editor" }] }));
  open();
  await screen.findByRole("heading", { name: "People" });
  expect(screen.queryByRole("region", { name: "Credit limits" })).toBeNull();
});

test("Studio name is filled, Save waits for a change, and Undo puts the old name back", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "PUT /workspace": [200, { id: 1, name: "Reed's studio" }] }));
  open();
  const name = await screen.findByLabelText("Studio name");
  expect(name).toHaveValue("Iron Paws Studio");
  expect(screen.getByText("Shown on invite links.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Save" })).toHaveAccessibleDescription("No changes yet");
  await userEvent.clear(name);
  await userEvent.type(name, "Reed's studio");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /workspace")?.body).toEqual({ name: "Reed's studio" }));
  expect(await screen.findByText("Studio name saved.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "PUT /workspace").at(-1)?.body).toEqual({ name: "Iron Paws Studio" }));
});

test("a studio stored as a slug shows as Reed's studio, and Save is ready", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /workspace": [200, { id: 1, name: "owner-reed" }] }));
  open();
  expect(await screen.findByLabelText("Studio name")).toHaveValue("Reed's studio");
  expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();
});
