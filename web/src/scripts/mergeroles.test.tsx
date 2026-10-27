import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const owner = { id: 1, email: "reed@b.co", name: "Reed", role: "owner", workspace_id: 1 };
const script = {
  id: 7, brand_id: 1, title: "Bo tries salmon", description: "x", reference_id: null, reel_imported: false, new_lines: false, published: false, status: "draft", created_by_id: 1, created_by_name: "Reed", created_at: "2026-10-24T10:00:00Z", versions_left: 0, notes: "", reference_replace: "", cast: [], maybe_same: [],
  versions: [{ slot: 0, status: "approved", title: "x", seconds: 0, project_id: null, text: "MIA: Hell no!", words: 3, target_seconds: null, premise: "", changes: [], problems: [], has_breakdown: false, approved_at: null }],
};
const slot = (id: number, role: string, o: object = {}) => ({ id, role, kind: "Helper", appears_in: [0], description: "", position: id, library_item_id: null, sheet_file_id: null, locked: false, ...o });
const kimchi = slot(32, "Kimchi", { locked: true, facts: { age_range: { value: "late 20s", inferred: false }, gender: { value: "man", inferred: false }, occupation: null } });
const friend = slot(33, "His friend with the supercar");
const moved = { shots: ["1.2", "2.1", "3.4"], lines: [{ version: "A", line: 4 }, { version: "A", line: 7 }, { version: "B", line: 4 }], look_unused: null };
const char = (o: object = {}) => ({ id: 5, name: "Bo", image_file_ids: [], sheet_status: "none", sheet_file_id: null, ...o });
const base = (o: Record<string, [number, unknown]> = {}): Record<string, [number, unknown]> => ({
  "GET /auth/me": [200, owner],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /references": [200, []],
  "GET /projects": [200, []],
  "GET /jobs": [200, []],
  "GET /scripts/7": [200, script],
  "GET /scripts/7/cast": [200, [kimchi, friend]],
  "GET /scripts/7/cast/read": [200, { running: false, problems: [] }],
  "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 4 }]],
  "GET /models": [200, [{ id: "nano-banana-pro", kind: "image", name: "x", credits_per_unit: { "2K": 3 } }]],
  "GET /library/character": [200, [char()]],
  ...o,
});
function open() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/b/1/scripts/7?step=cast"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
afterEach(() => vi.unstubAllGlobals());


const menu = async (role: string) => userEvent.click(await screen.findByRole("button", { name: `More for ${role}` }));

test("Merge into… lists the other roles, shows what moves, merges for free, and Undo puts it back", async () => {
  setViewport(1440);
  const calls = fakeServer(base({
    "GET /scripts/7/cast/33/merge/preview?into=32": [200, { moved, look_unused: { name: "His friend with the supercar" } }],
    "POST /scripts/7/cast/33/merge": [200, { moved, look_unused: null, token: 5, cast: [kimchi] }],
    "POST /scripts/7/cast/merge/undo": [200, [kimchi, friend]],
  }));
  open();
  await menu("His friend with the supercar");
  await userEvent.click(await screen.findByRole("menuitem", { name: "Merge into…" }));
  expect(await screen.findByText("Merge His friend with the supercar into…")).toBeInTheDocument();
  expect(within(screen.getByRole("alertdialog")).getByText("Locked")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^Merge · Free/ })).toBeDisabled();
  await userEvent.click(screen.getByRole("radio", { name: /Kimchi/ }));
  expect(await screen.findByText(/A lines 4 and 7, B line 4/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /^Merge · Free/ }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts/7/cast/33/merge")?.body).toEqual({ into_slot_id: 32 }));
  expect(await screen.findByText("Merged into Kimchi. 3 shots and 3 lines moved.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts/7/cast/merge/undo")?.body).toEqual({ token: 5 }));
});

test("with only one role, Merge into… is disabled and says why", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts/7/cast": [200, [kimchi]] }));
  open();
  await menu("Kimchi");
  expect(await screen.findByRole("menuitem", { name: "Merge into…" })).toHaveAttribute("aria-disabled", "true");
  expect(screen.getByText("There's no other role to merge into.")).toBeInTheDocument();
});

const flagged = { ...script, maybe_same: [{ a_slot_id: 32, b_slot_id: 33, into_slot_id: 32, why: "Both are described as Nate's friend, and they're never in the same shot." }] };

test("a flagged pair shows a note with the reason; They're different keeps both with an Undo", async () => {
  setViewport(1440);
  const calls = fakeServer(base({
    "GET /scripts/7": [200, flagged],
    "POST /scripts/7/cast/maybe-same/dismiss": [200, []],
    "DELETE /scripts/7/cast/maybe-same/dismiss": [200, flagged.maybe_same],
  }));
  open();
  expect(await screen.findByText("These may be the same person: Kimchi and His friend with the supercar.")).toBeInTheDocument();
  expect(screen.getByText(/never in the same shot/)).toBeInTheDocument();
  expect(screen.getByText("May be the same as His friend with the supercar")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Kimchi and His friend with the supercar are different" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts/7/cast/maybe-same/dismiss")?.body).toEqual({ a_slot_id: 32, b_slot_id: 33 }));
  expect(await screen.findByText("Kept as two roles.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /scripts/7/cast/maybe-same/dismiss")).toBe(true));
});

test("Merge on the note opens the dialog for the other role with the kept one already picked", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts/7": [200, flagged], "GET /scripts/7/cast/33/merge/preview?into=32": [200, { moved, look_unused: null }] }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Merge Kimchi and His friend with the supercar" }));
  expect(await screen.findByText("Merge His friend with the supercar into…")).toBeInTheDocument();
  expect(screen.getByRole("radio", { name: /Kimchi/ })).toBeChecked();
});

test("a flagged pair never blocks the step: no note, no badge when nothing is flagged", async () => {
  setViewport(1440);
  fakeServer(base());
  open();
  await screen.findByText("Kimchi");
  expect(screen.queryByText(/may be the same person/i)).toBeNull();
  expect(screen.queryByText(/May be the same as/)).toBeNull();
});
