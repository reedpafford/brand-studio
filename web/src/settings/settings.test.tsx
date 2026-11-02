import { cleanup, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";
import { owner } from "../test/people";

const base = (o: Record<string, [number, unknown]> = {}): Record<string, [number, unknown]> => ({
  "GET /auth/me": [200, owner],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /team/members": [200, [{ id: 1, name: "Reed", email: "reed@b.co", role: "owner" }]],
  "GET /team/invites": [200, []],
  "GET /workspace": [200, { id: 1, name: "Iron Paws Studio" }],
  "GET /credits/limits": [200, { weekly_quick_clip_credits: 145, per_video_max_credits: 729 }],
  "GET /credits/allowances": [200, [{ user_id: 2, name: "Sam", quick_clip_credits_used: 120, quick_clip_credits_allowed: 145 }]],
  "GET /usage/summary?period=month": [200, { director_spend_usd: 6.4 }],
  ...o,
});
function open(tab = "limits") {
  renderApp(`/settings?tab=${tab}`);
}
afterEach(() => vi.unstubAllGlobals());

test("Limits shows both limits in credits, says editors' new videos always ask, and the director's time this month in dollars; Save waits for a change", async () => {
  setViewport(1440);
  fakeServer(base());
  open();
  expect(await screen.findByLabelText("Each editor's own week")).toHaveValue("145");
  expect(screen.getByLabelText("Most one video may spend")).toHaveValue("729");
  const limits = screen.getByRole("region", { name: "Limits" });
  expect(limits).toHaveTextContent("Always asks you");
  expect(await within(limits).findByText("$6.40 this month")).toBeInTheDocument();
  expect(limits).not.toHaveTextContent(/monthly budget/i);
  expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Save" })).toHaveAccessibleDescription("No changes yet");
});

test("raising the cap saves both values, and Undo saves the old ones back", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "PUT /credits/limits": [200, { weekly_quick_clip_credits: 145, per_video_max_credits: 800 }] }));
  open();
  const cap = await screen.findByLabelText("Most one video may spend");
  await userEvent.clear(cap);
  await userEvent.type(cap, "800");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /credits/limits")?.body).toEqual({ weekly_quick_clip_credits: 145, per_video_max_credits: 800 }));
  expect(await screen.findByText("Limits saved.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "PUT /credits/limits").at(-1)?.body).toEqual({ weekly_quick_clip_credits: 145, per_video_max_credits: 729 }));
});

test("lowering the allowance below what an editor has used asks first, in plain words", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "PUT /credits/limits": [200, { weekly_quick_clip_credits: 100, per_video_max_credits: 729 }] }));
  open();
  const weekly = await screen.findByLabelText("Each editor's own week");
  await userEvent.clear(weekly);
  await userEvent.type(weekly, "100");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
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
  const weekly = await screen.findByLabelText("Each editor's own week");
  await userEvent.clear(weekly);
  await userEvent.type(weekly, "12.5");
  expect(screen.getByText("Use a whole number of credits.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
});

test("Settings is the owner's: an editor sees no tabs, no looks, languages or limits", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /auth/me": [200, { ...owner, id: 2, role: "editor" }] }));
  open();
  expect(await screen.findByText("Only the owner manages settings.")).toBeInTheDocument();
  expect(screen.queryByRole("tablist")).toBeNull();
  expect(screen.queryByRole("region", { name: "Limits" })).toBeNull();
});

test("Settings has four tabs, Studio first; /looks, /languages and the old ?tab=name land on their tabs", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /looks": [200, []], "GET /languages": [200, []] }));
  renderApp("/languages");
  const tabs = await screen.findByRole("tablist", { name: "Settings" });
  expect(within(tabs).getAllByRole("tab").map((t) => t.textContent)).toEqual(["Studio", "Limits", "Styles", "Languages"]);
  expect(within(tabs).getByRole("tab", { name: "Languages" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("region", { name: "Languages" })).toBeInTheDocument();
  await userEvent.click(within(tabs).getByRole("tab", { name: "Limits" }));
  expect(await screen.findByLabelText("Each editor's own week")).toBeInTheDocument();
  cleanup();
  renderApp("/settings?tab=name");
  expect(await screen.findByLabelText("Studio name")).toBeInTheDocument();
});

test("Studio name is filled, Save waits for a change, and Undo puts the old name back", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "PUT /workspace": [200, { id: 1, name: "Reed's studio" }] }));
  open("studio");
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
  open("studio");
  expect(await screen.findByLabelText("Studio name")).toHaveValue("Reed's studio");
  expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();
});
