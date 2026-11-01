import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";
import { editor, owner } from "../test/people";

const project = {
  id: 9, brand_id: 1, name: "Bo tries salmon", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "",
  cast_ids: [], reference_file_id: null, estimate_credits: 30, budget_credits: 600, credits_used: 0, budget_pct: 0, product_variants: {}, created_by_id: 2,
};
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, editor],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /projects/9": [200, project],
  "GET /projects/9/script": [200, { version: 5, source: "paste", words: 2, created_by_id: 2, created_at: "2026-10-23T10:00:00Z", text: "Bo eats." }],
  "GET /projects/9/breakdown": [200, { id: 1, script_version: 5, source: "claude", stale: false, problems: [], breakdown: { hook: "", scenes: [], clips: [] } }],
  "GET /projects/9/storyboard": [200, []],
  "GET /projects/9/clips": [200, []],
  "GET /projects/9/video": [404, { detail: "none" }],
  "GET /projects/9/assets": [200, []],
  "GET /jobs": [200, []],
  "GET /credits/rates": [200, []],
};
const turn = (n: number, result: string, why = "", status = "succeeded") => ({ turn: n, tool: "make_shots", why, result, status, created_at: "2026-11-01T10:00:00Z" });
const run = (o: object) => ({ status: "none", ended: "", turns: [], credits: 0, spent_usd: null, start_blocked: "", ...o });

afterEach(() => vi.unstubAllGlobals());

test("before a run, the steps show first; Director offers Make it now, which starts the run", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /projects/9/director": [200, run({})], "POST /projects/9/director": [201, run({ status: "running", turns: [turn(1, "Making the shots.")] })] });
  renderApp("/b/1/videos/9");
  expect(await screen.findByRole("tab", { name: "Look inside", selected: true })).toBeInTheDocument();
  expect(screen.getByRole("list", { name: "Steps" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("tab", { name: "Director" }));
  await userEvent.click(await screen.findByRole("button", { name: "Make it now" }));
  expect(await screen.findByText("Working")).toBeInTheDocument();
  expect(calls.some((c) => c.key === "POST /projects/9/director")).toBe(true);
  expect(within(screen.getByRole("list", { name: "What the director did" })).getByText(/Making the shots\./)).toBeInTheDocument();
});

test("Make it now says why it can't start (the server's own words)", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/director": [200, run({ start_blocked: "Publish the script first." })] });
  renderApp("/b/1/videos/9?view=director");
  expect(await screen.findByRole("button", { name: "Make it now" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Make it now" })).toHaveAccessibleDescription(/Publish the script first\./);
});

test("a running director is the first view: what it's doing, its log newest first, its cost, and Stop", async () => {
  setViewport(390);
  const calls = fakeServer({
    ...base,
    "GET /projects/9/director": [200, run({ status: "running", credits: 12.5, turns: [turn(1, "Made the shots.", "The script has 3 scenes."), turn(2, "Making the stills.")] })],
    "POST /projects/9/director/stop": [200, run({ status: "ended", ended: "You stopped it.", turns: [turn(1, "Made the shots."), turn(2, "Making the stills.")] })],
  });
  renderApp("/b/1/videos/9");
  expect(await screen.findByRole("tab", { name: "Director", selected: true })).toBeInTheDocument();
  expect(within(screen.getByRole("region", { name: "Director" })).getByRole("status")).toHaveTextContent(/Working · Making the stills\.up to 12\.5 credits/);
  expect(screen.queryByRole("list", { name: "Steps" })).not.toBeInTheDocument();
  const log = within(screen.getByRole("list", { name: "What the director did" })).getAllByRole("listitem");
  expect(log[0]).toHaveTextContent("2. Making the stills.");
  expect(log[1]).toHaveTextContent("The script has 3 scenes.");
  await userEvent.click(screen.getByRole("button", { name: "Stop" }));
  expect(await screen.findByText(/You stopped it\. What it already made is kept\./)).toBeInTheDocument();
  expect(calls.some((c) => c.key === "POST /projects/9/director/stop")).toBe(true);
  // Look inside still opens the steps.
  await userEvent.click(screen.getByRole("tab", { name: "Look inside" }));
  expect(await screen.findByRole("button", { name: /Step 1 of 4/ })).toBeInTheDocument();
});

test("a delivered run shows the delivery note; the owner also sees the director's own time in dollars", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /auth/me": [200, owner], "GET /projects/9/director": [200, run({ status: "delivered", credits: 40, spent_usd: 1.234, turns: [turn(1, "Made the shots."), turn(2, "Delivered.", "Redid clip 2: the dog's collar changed colour.")] })] });
  renderApp("/b/1/videos/9");
  expect(await screen.findByRole("heading", { name: "Delivery note" })).toBeInTheDocument();
  expect(screen.getByText("Redid clip 2: the dog's collar changed colour.", { selector: "p.whitespace-pre-line" })).toBeInTheDocument();
  expect(screen.getByText("40 credits · $1.23 director time")).toBeInTheDocument();
});

test("with no director for this person (the server says no), the page is the steps, with no view tabs", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/director": [403, { detail: "Only Eli or the owner can change this video." }] });
  renderApp("/b/1/videos/9");
  expect(await screen.findByRole("list", { name: "Steps" })).toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "Director" })).not.toBeInTheDocument();
});
