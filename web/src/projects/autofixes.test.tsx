import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const editor = { id: 2, email: "e@b.co", name: "Eli", role: "editor", workspace_id: 1 };
const project = {
  id: 9, brand_id: 1, name: "Mia buys the dip", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "",
  cast_ids: [], reference_file_id: null, estimate_credits: 30, budget_credits: 600, credits_used: 0, budget_pct: 0, created_by_id: 2,
};
const script = { version: 5, source: "paste", words: 9, created_by_id: 2, created_at: "2026-10-23T10:00:00Z", text: "Mia scrolls." };
const breakdown = { id: 1, script_version: 5, source: "claude", stale: false, problems: [], breakdown: { hook: "Hook.", scenes: [{ id: 1, heading: "KITCHEN", look: "", shots: [] }], clips: [] } };
const frames = [
  { id: 1, clip_id: "c1", shot_id: "1.1", prompt: "p", reference_ids: [], problems: [], file_id: 40, approved: true, stale: false },
  { id: 2, clip_id: "c2", shot_id: "2.1", prompt: "p", reference_ids: [], problems: [], file_id: 41, approved: true, stale: false },
];
const clip = (o: object) => ({ id: 1, clip_id: "c1", seconds: 8, prompt: "Mia taps buy", references: [], problems: [], file_id: null, takes: [], picked_take_id: null, approved: false, stale: false, take_credits: 24, inserts: [], ...o });
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, editor],
  "GET /brands": [200, [{ id: 1, name: "fomo", colours: [] }]],
  "GET /projects/9": [200, project],
  "GET /projects/9/script": [200, script],
  "GET /projects/9/breakdown": [200, breakdown],
  "GET /projects/9/storyboard": [200, frames],
  "GET /projects/9/script/suggestions": [200, []],
  "GET /projects/9/script/notes": [200, []],
  "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 6 }, { kind: "video", unit: "second", credits_per_unit: 3 }]],
  "GET /projects/9/clips/prompts/price": [200, { clip_ids: ["c1"], credits: 6 }], // a Claude call per few clips
  "GET /jobs": [200, []],
  "GET /projects/9/video": [404, { detail: "none" }],
  "GET /library/character": [200, []],
  "GET /library/place": [200, []],
  "GET /library/prop": [200, []],
  "GET /brands/1/screens": [200, []],
};

function open(query = "?stage=clips") {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[`/b/1/projects/9${query}`]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

test("a clip the server tried again on its own says why, muted, under its status", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/clips": [200, [clip({ retrying: "refused" }), clip({ id: 2, clip_id: "c2", retrying: "busy" })]] });
  open();
  expect(within(await screen.findByLabelText("Clip c1")).getByText("Tried again on its own: the first try was refused.")).toBeInTheDocument();
  expect(within(screen.getByLabelText("Clip c2")).getByText("Tried again on its own: the service was busy.")).toBeInTheDocument();
});

test("a wording fix made for you shows under the prompt with Undo, which asks the server to put the words back", async () => {
  setViewport(390);
  const calls = fakeServer({ ...base, "GET /projects/9/clips": [200, [clip({ auto_fix: { fixed: ['removed "9:16"', 'changed "says" to "gestures"'], undone: false, before: "Mia taps buy 9:16" } })]], "POST /projects/9/clips/1/auto-fix/undo": [200, clip({})] });
  open();
  const card = await screen.findByLabelText("Clip c1");
  const note = within(card).getByRole("note", { name: "Fixed for you" });
  expect(note).toHaveTextContent('Fixed for you: removed "9:16" and changed "says" to "gestures".');
  await userEvent.click(within(note).getByRole("button", { name: "See the change" }));
  expect(within(note).getByRole("button", { name: "Hide the change" })).toHaveAttribute("aria-expanded", "true");
  await userEvent.click(within(note).getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/clips/1/auto-fix/undo")).toBe(true));
});

test("an undone fix, or none, shows no line", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/clips": [200, [clip({ auto_fix: { fixed: ['removed "9:16"'], undone: true } }), clip({ id: 2, clip_id: "c2" })]] });
  open();
  await screen.findByLabelText("Clip c1");
  expect(screen.queryByRole("note", { name: "Fixed for you" })).toBeNull();
  expect(screen.queryByText(/tried again once/)).toBeNull();
  expect(screen.queryByText(/Tried again on its own/)).toBeNull();
});

test("after the retried take finishes, a muted line says the newest take was tried again once on its own", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/clips": [200, [clip({ retried: "busy", file_id: 70, takes: [{ id: 5, number: 1, file_id: 70 }], picked_take_id: 5 })]] });
  open();
  expect(within(await screen.findByLabelText("Clip c1")).getByText("The newest take was tried again once on its own: the service was busy.")).toBeInTheDocument();
});

test("a fix without the earlier words offers Undo but no See the change", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/clips": [200, [clip({ auto_fix: { fixed: ['removed "logo text"'], undone: false } })]] });
  open();
  const note = await screen.findByRole("note", { name: "Fixed for you" });
  expect(within(note).queryByRole("button", { name: "See the change" })).toBeNull();
  expect(within(note).getByRole("button", { name: "Undo" })).toBeInTheDocument();
});

test("an Undo the server refuses (the prompt was edited since) says why in its words, not a loop of try again", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/clips": [200, [clip({ auto_fix: { fixed: ['removed "9:16"'], undone: false } })]], "POST /projects/9/clips/1/auto-fix/undo": [409, { detail: "The prompt has changed since the fix, so there's nothing to undo." }] });
  open();
  const note = await screen.findByRole("note", { name: "Fixed for you" });
  await userEvent.click(within(note).getByRole("button", { name: "Undo" }));
  expect(await screen.findByText("The prompt has changed since the fix, so there's nothing to undo.")).toBeInTheDocument();
  expect(screen.queryByText(/try again/)).toBeNull();
});
