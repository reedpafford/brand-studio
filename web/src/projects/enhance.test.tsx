import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";

const editor = { id: 2, email: "e@b.co", name: "Eli", role: "editor", workspace_id: 1 };
const project = {
  id: 9, brand_id: 1, name: "Mia buys the dip", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "",
  cast_ids: [], reference_file_id: null, estimate_credits: 30, budget_credits: 60, credits_used: 0, budget_pct: 0,
};
const script = { version: 4, source: "paste", words: 9, created_by_id: 2, created_at: "2026-10-23T10:00:00Z", text: "Mia scrolls her phone.\nMIA: Wait… it dipped?" };
const mark = (o: object) => ({ id: 1, key: "a", kind: "camera", line: 1, quote: "Mia scrolls", start: 0, end: 11, placement: "after", text: "Slow push-in on her face.", screen_id: null, reason: "Builds the hook.", status: "pending", ...o });
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, editor],
  "GET /brands": [200, [{ id: 1, name: "fomo", colours: [] }]],
  "GET /projects/9": [200, project],
  "GET /projects/9/script": [200, script],
  "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 3 }]],
  "GET /jobs": [200, []],
  "GET /projects/9/script/suggestions": [200, []],
  "GET /projects/9/script/notes": [200, []],
};

function open(query = "tab=script") {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[`/b/1/projects/9?${query}`]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

test("Enhance shows its cost and starts the run", async () => {
  const calls = fakeServer({ ...base, "POST /projects/9/script/enhance": [201, { id: 3, kind: "write-claude", status: "queued", credits: 3, project_id: 9 }] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "✦ Enhance · 3 credits" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/script/enhance")).toBe(true));
});

test("while Enhance runs the button is off and says why", async () => {
  fakeServer({ ...base, "GET /jobs": [200, [{ id: 3, kind: "write-claude", step: "enhance", status: "running", credits: 3, project_id: 9, created_at: "2026-10-23T10:00:00Z" }]] });
  open();
  expect(await screen.findByText("Reading your script…")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^✦ Enhance/ })).toBeDisabled();
});

test("suggestions sit under their lines as direction notes, and the script's own lines stay as they were", async () => {
  fakeServer({
    ...base,
    "GET /projects/9/script/suggestions": [200, [mark({}), mark({ id: 2, kind: "brand_screen", line: 2, text: "fomo screen: Chart down", reason: "Shows the dip.", placement: "after" })]],
  });
  open();
  const list = await screen.findByRole("list", { name: "Script text" });
  await vi.waitFor(() => expect(within(list).getAllByRole("listitem")).toHaveLength(4));
  const items = within(list).getAllByRole("listitem");
  expect(items.map((i) => i.textContent)).toEqual([
    "1Mia scrolls her phone.",
    expect.stringContaining("Slow push-in on her face."),
    "2MIA: Wait… it dipped?",
    expect.stringContaining("★ fomo screen: Chart down"),
  ]);
  expect(within(items[1]).getByText("Camera")).toBeInTheDocument();
  expect(within(items[3]).getByText("Brand screen")).toBeInTheDocument();
  expect(screen.getByText("Why: Builds the hook.")).toBeInTheDocument();
  // Only the suggestion's words carry the marker underline; the row and its buttons do not.
  const marked = screen.getByText(/Slow push-in on her face\./);
  expect(marked).toHaveClass("underline");
  expect(items[1]).not.toHaveClass("underline");
  expect(within(items[1]).getByRole("button", { name: /Accept/ }).parentElement?.closest(".underline")).toBeNull();
});

test("accept and reject are sent; apply shows once something is accepted", async () => {
  const calls = fakeServer({
    ...base,
    "GET /projects/9/script/suggestions": [200, [mark({}), mark({ id: 2, text: "Mia's eyes widen.", kind: "reaction", line: 2, status: "accepted" })]],
    "POST /projects/9/script/suggestions/1/accept": [200, mark({ status: "accepted" })],
    "POST /projects/9/script/apply": [200, { script: { ...script, version: 5, source: "enhance" } }],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Accept: Slow push-in on her face." }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/script/suggestions/1/accept")).toBe(true));
  await userEvent.click(screen.getByRole("button", { name: "Apply 1 accepted" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/script/apply")).toBe(true));
});

test("notes can only be dismissed with Got it", async () => {
  fakeServer({ ...base, "GET /projects/9/script/notes": [200, [{ line: 2, text: "The brand kit has no strawberry product." }]] });
  open("stage=enhance");
  expect(await screen.findByText(/Line 2: The brand kit has no strawberry product\./)).toBeInTheDocument();
  expect(within(screen.getByLabelText("Notes")).getAllByRole("button")).toHaveLength(1);
  await userEvent.click(screen.getByRole("button", { name: "Got it: line 2" }));
  expect(screen.queryByLabelText("Notes")).not.toBeInTheDocument();
});

test("a failed run says the script is unchanged; a switched-off server explains itself", async () => {
  fakeServer({
    ...base,
    "GET /jobs": [200, [{ id: 3, kind: "write-claude", step: "enhance", status: "failed", credits: 3, project_id: 9, created_at: "2026-10-23T10:00:00Z" }]],
    "POST /projects/9/script/enhance": [503, { detail: "Generation is switched off on this server." }],
  });
  open();
  expect(await screen.findByText(/Enhance didn't finish\. Your script is unchanged/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /^✦ Enhance/ }));
  expect(await screen.findByText("Generation is switched off on this server.")).toBeInTheDocument();
});

const many = (n: number, kind: string, from = 1) => Array.from({ length: n }, (_, i) => mark({ id: from + i, kind, line: 1, text: `${kind} note ${from + i}` }));

test("Accept all accepts every waiting suggestion, asking first when there are more than 5", async () => {
  const calls = fakeServer({
    ...base,
    "GET /projects/9/script/suggestions": [200, [...many(4, "camera"), ...many(3, "reaction", 5)]],
    ...Object.fromEntries(Array.from({ length: 7 }, (_, i) => [`POST /projects/9/script/suggestions/${i + 1}/accept`, [200, mark({})]])),
  });
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Accept all options" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Accept all (7)" }));
  expect(confirm).toHaveBeenCalledWith("Accept 7 suggestions?");
  await vi.waitFor(() => expect(calls.filter((c) => c.key.endsWith("/accept"))).toHaveLength(7));
});

test("Accept all by kind accepts only that kind, with no question for 5 or fewer", async () => {
  const calls = fakeServer({
    ...base,
    "GET /projects/9/script/suggestions": [200, [...many(2, "camera"), ...many(1, "reaction", 3)]],
    "POST /projects/9/script/suggestions/1/accept": [200, mark({})],
    "POST /projects/9/script/suggestions/2/accept": [200, mark({})],
  });
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Accept all options" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Accept all Camera (2)" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key.endsWith("/accept"))).toHaveLength(2));
  expect(confirm).not.toHaveBeenCalled();
  expect(calls.some((c) => c.key === "POST /projects/9/script/suggestions/3/accept")).toBe(false);
});

test("Apply says how many directions were added, and Undo saves the earlier words again", async () => {
  const calls = fakeServer({
    ...base,
    "GET /projects/9/script/suggestions": [200, [mark({ status: "accepted" }), mark({ id: 2, status: "accepted", line: 2 })]],
    "POST /projects/9/script/apply": [200, { script: { ...script, version: 5, source: "enhance" } }],
    "PUT /projects/9/script": [200, { ...script, version: 6 }],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Apply 2 accepted" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Added 2 directions as v5.");
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /projects/9/script")?.body).toEqual({ text: script.text }));
});

test("tapping a suggestion opens a sheet with the Why, and the Notes chip opens the notes in a sheet", async () => {
  fakeServer({
    ...base,
    "GET /projects/9/script/suggestions": [200, [mark({})]],
    "GET /projects/9/script/notes": [200, [{ line: 2, text: "The brand kit has no strawberry product." }]],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: /^▸ Slow push-in on her face\./ }));
  const sheet = await screen.findByRole("dialog", { name: "Camera" });
  expect(within(sheet).getByText("Why: Builds the hook.")).toBeInTheDocument();
  await userEvent.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  await userEvent.click(await screen.findByRole("button", { name: "Notes (1)" }));
  const notes = await screen.findByRole("dialog", { name: "Notes" });
  await userEvent.click(within(notes).getByRole("button", { name: "Got it: line 2" }));
  expect(within(notes).getByText("No notes.")).toBeInTheDocument();
});

test("the helper says 'directions', and phones get a 'Why?' hint after a suggestion that has a reason", async () => {
  fakeServer({ ...base, "GET /projects/9/script/suggestions": [200, [mark({ status: "accepted" }), mark({ id: 2, line: 2 })]] });
  open();
  expect(await screen.findByText(/Applying adds the accepted directions as a new version\./)).toBeInTheDocument();
  expect(screen.getByText("Why?")).toBeInTheDocument();
});

const three = [mark({ id: 1, kind: "camera", text: "Camera one", line: 1 }), mark({ id: 2, kind: "reaction", text: "Reaction two", line: 1 }), mark({ id: 3, kind: "camera", text: "Camera three", line: 2 })];

test("filter chips show a kind at a time, with counts", async () => {
  fakeServer({ ...base, "GET /projects/9/script/suggestions": [200, three] });
  open();
  const chips = await screen.findByRole("group", { name: "Show" });
  expect(within(chips).getByRole("button", { name: "All 3" })).toHaveAttribute("aria-pressed", "true");
  await userEvent.click(within(chips).getByRole("button", { name: "Camera 2" }));
  expect(screen.queryByText(/Reaction two/)).not.toBeInTheDocument();
  expect(screen.getAllByText(/Camera (one|three)/)).toHaveLength(2);
  await userEvent.click(within(chips).getByRole("button", { name: "All 3" }));
  expect(await screen.findByText(/Reaction two/)).toBeInTheDocument();
});

test("J and K move between suggestions, A accepts and R rejects the focused one, Esc lets go", async () => {
  const calls = fakeServer({
    ...base,
    "GET /projects/9/script/suggestions": [200, three],
    "POST /projects/9/script/suggestions/1/accept": [200, mark({})],
    "POST /projects/9/script/suggestions/2/reject": [200, mark({})],
  });
  open();
  await screen.findByText(/Camera one/);
  const focusedText = () => document.querySelector("[aria-current=true]")?.textContent ?? "";
  await userEvent.keyboard("j");
  expect(focusedText()).toContain("Camera one");
  await userEvent.keyboard("a");
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/script/suggestions/1/accept")).toBe(true));
  expect(focusedText()).toContain("Reaction two"); // accepting moved on to the next waiting one
  await userEvent.keyboard("r");
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/script/suggestions/2/reject")).toBe(true));
  expect(focusedText()).toContain("Camera three");
  await userEvent.keyboard("k");
  expect(focusedText()).toContain("Reaction two");
  await userEvent.keyboard("{Escape}");
  expect(document.querySelector("[aria-current=true]")).toBeNull();
});

test("the keys never act while you are typing in a box", async () => {
  const calls = fakeServer({ ...base, "GET /projects/9/script/suggestions": [200, three] });
  open();
  await screen.findByText(/Camera one/);
  await userEvent.click(await screen.findByRole("button", { name: "Edit" }));
  await userEvent.type(screen.getByLabelText("Your script"), "jjjaaarrr");
  expect(document.querySelector("[aria-current=true]")).toBeNull();
  expect(calls.some((c) => c.key.endsWith("/accept") || c.key.endsWith("/reject"))).toBe(false);
});

test("after A or R the keys move to the next waiting suggestion, so they can be pressed again", async () => {
  const calls = fakeServer({
    ...base,
    "GET /projects/9/script/suggestions": [200, three],
    "POST /projects/9/script/suggestions/1/accept": [200, mark({})],
    "POST /projects/9/script/suggestions/2/reject": [200, mark({})],
    "POST /projects/9/script/suggestions/3/accept": [200, mark({})],
  });
  open();
  await screen.findByText(/Camera one/);
  const focusedText = () => document.querySelector("[aria-current=true]")?.textContent ?? "";
  await userEvent.keyboard("j");
  await userEvent.keyboard("a"); // accepts Camera one, moves on
  expect(focusedText()).toContain("Reaction two");
  await userEvent.keyboard("r"); // rejects Reaction two, moves on
  expect(focusedText()).toContain("Camera three");
  await userEvent.keyboard("a");
  await vi.waitFor(() => expect(calls.filter((c) => /\/(accept|reject)$/.test(c.key))).toHaveLength(3));
});
