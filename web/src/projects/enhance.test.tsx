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

function open() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/b/1/projects/9?tab=script"]}>
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
  fakeServer({ ...base, "GET /jobs": [200, [{ id: 3, kind: "write-claude", status: "running", credits: 3, project_id: 9, created_at: "2026-10-23T10:00:00Z" }]] });
  open();
  expect(await screen.findByText("Reading your script…")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Enhance/ })).toBeDisabled();
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
  open();
  expect(await screen.findByText(/Line 2: The brand kit has no strawberry product\./)).toBeInTheDocument();
  expect(within(screen.getByLabelText("Notes")).getAllByRole("button")).toHaveLength(1);
  await userEvent.click(screen.getByRole("button", { name: "Got it: line 2" }));
  expect(screen.queryByLabelText("Notes")).not.toBeInTheDocument();
});

test("a failed run says the script is unchanged; a switched-off server explains itself", async () => {
  fakeServer({
    ...base,
    "GET /jobs": [200, [{ id: 3, kind: "write-claude", status: "failed", credits: 3, project_id: 9, created_at: "2026-10-23T10:00:00Z" }]],
    "POST /projects/9/script/enhance": [503, { detail: "Generation is switched off on this server." }],
  });
  open();
  expect(await screen.findByText(/Enhance didn't finish\. Your script is unchanged/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Enhance/ }));
  expect(await screen.findByText("Generation is switched off on this server.")).toBeInTheDocument();
});
