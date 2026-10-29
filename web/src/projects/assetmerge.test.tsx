import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const editor = { id: 2, email: "e@b.co", name: "Eli", role: "editor", workspace_id: 1 };
const project = {
  id: 9, brand_id: 1, name: "Bo tries salmon · B", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "",
  cast_ids: [], reference_file_id: null, estimate_credits: 30, budget_credits: 600, credits_used: 0, budget_pct: 0, product_variants: {}, created_by_id: 2,
};
const script = { version: 5, source: "paste", words: 9, created_by_id: 2, created_at: "2026-10-23T10:00:00Z", text: "Bo eats." };
const breakdown = { id: 1, script_version: 5, source: "claude", stale: false, problems: [], breakdown: { hook: "Hook.", scenes: [{ id: 1, heading: "KITCHEN", look: "", shots: [] }], clips: [] } };
const asset = (o: object) => ({ kind: "character", ref: "char:5", role: "Bo", library_item_id: 5, name: "Bo", locked: false, sheet_status: "needs_approval", ready: false, ...o });
const item = (o: object) => ({ id: 5, kind: "character", name: "Bo", version: 1, sheet_file_id: 70, sheet_status: "needs_approval", ...o });
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, editor],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /projects/9": [200, project],
  "GET /projects/9/script": [200, script],
  "GET /projects/9/breakdown": [200, breakdown],
  "GET /projects/9/storyboard": [200, []],
  "GET /projects/9/clips": [200, []],
  "GET /projects/9/video": [404, { detail: "none" }],
  "GET /projects/9/assets": [200, [asset({})]],
  "GET /library/character/5": [200, item({})],
  "GET /library/character": [200, []],
  "GET /brands/1/screens": [200, []],
  "GET /credits/rates": [200, []],
  "GET /jobs": [200, []],
  "GET /models": [200, [{ id: "nano-banana-pro", kind: "image", name: "Nano Banana Pro", default: false, credits_per_unit: { "2K": 1.5 } }, { id: "nano-banana-2.1", kind: "image", name: "Nano Banana 2.1", default: true, credits_per_unit: { "1K": 3 } }]],
  "GET /credits/limits": [200, { weekly_quick_clip_credits: 145, per_video_max_credits: 729 }],
};

function open(query = "?step=assets") {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[`/b/1/videos/9${query}`]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

const kimchi = asset({ ref: "slot:32", slot_id: 32, role: "Kimchi", name: "", library_item_id: null, locked: true, sheet_status: "approved", ready: true, shots: 3 });
const friend = asset({ ref: "slot:33", slot_id: 33, role: "His friend with the supercar", name: "", library_item_id: null, sheet_status: "missing", shots: 2 });
const moved = { shots: ["1.2", "2.1"], lines: [{ version: "A", line: 4 }] };
const roles = { ...base, "GET /projects/9/assets": [200, [kimchi, friend]] as [number, unknown], "GET /projects/9/assets/maybe-same": [200, []] as [number, unknown] };
const menu = async (role: string) => userEvent.click(await screen.findByRole("button", { name: `More for ${role}` }));

test("Merge into… on a video's role: this video only, what moves, free, and Undo", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...roles,
    "GET /projects/9/assets/slots/33/merge/preview?into=32": [200, { moved, look_unused: { name: "His friend with the supercar" } }],
    "POST /projects/9/assets/slots/33/merge": [200, { moved, look_unused: null, token: 8, assets: [kimchi] }],
    "POST /projects/9/assets/merge/undo": [200, [kimchi, friend]],
  });
  open();
  await menu("His friend with the supercar");
  await userEvent.click(await screen.findByRole("menuitem", { name: "Merge into…" }));
  expect(await screen.findByText("This changes this video only.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("radio", { name: /Kimchi/ }));
  expect(await screen.findByText(/2 shots: 1.2, 2.1/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /^Merge · Free/ }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/assets/slots/33/merge")?.body).toEqual({ into_slot_id: 32 }));
  expect(await screen.findByText("Merged into Kimchi. 2 shots and 1 line moved.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/assets/merge/undo")?.body).toEqual({ token: 8 }));
});

test("an Undo the server refuses (the shots changed since) shows its words", async () => {
  setViewport(1440);
  fakeServer({
    ...roles,
    "GET /projects/9/assets/slots/33/merge/preview?into=32": [200, { moved, look_unused: null }],
    "POST /projects/9/assets/slots/33/merge": [200, { moved, look_unused: null, token: 8, assets: [kimchi] }],
    "POST /projects/9/assets/merge/undo": [409, { detail: "This can't be undone any more: the shots were changed after the merge." }],
  });
  open();
  await menu("His friend with the supercar");
  await userEvent.click(await screen.findByRole("menuitem", { name: "Merge into…" }));
  await userEvent.click(await screen.findByRole("radio", { name: /Kimchi/ }));
  await userEvent.click(screen.getByRole("button", { name: /^Merge · Free/ }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  expect(await screen.findByText("This can't be undone any more: the shots were changed after the merge.")).toBeInTheDocument();
});

test("a single role shows Merge into… disabled, with why", async () => {
  setViewport(1440);
  fakeServer({ ...roles, "GET /projects/9/assets": [200, [friend]] });
  open();
  await menu("His friend with the supercar");
  expect(await screen.findByRole("menuitem", { name: "Merge into…" })).toHaveAttribute("aria-disabled", "true");
  expect(screen.getByText("There's no other role to merge into.")).toBeInTheDocument();
});

test("a flagged pair shows the note and badges on Assets; Merge opens the dialog with the kept role picked", async () => {
  setViewport(1440);
  fakeServer({
    ...roles,
    "GET /projects/9/assets/maybe-same": [200, [{ a_slot_id: 32, b_slot_id: 33, into_slot_id: 32, why: "Both are described as Nate's friend." }]],
    "GET /projects/9/assets/slots/33/merge/preview?into=32": [200, { moved, look_unused: null }],
  });
  open();
  expect(await screen.findByText("These may be the same person: Kimchi and His friend with the supercar.")).toBeInTheDocument();
  expect(screen.getByText("May be the same as Kimchi")).toBeInTheDocument();
  const note = screen.getByText("These may be the same person: Kimchi and His friend with the supercar.").closest("details")!;
  expect(note.open).toBe(false); // one quiet line until opened
  await userEvent.click(screen.getByText("May be the same as Kimchi")); // the badge opens the note
  expect(note.open).toBe(true);
  await userEvent.click(screen.getByRole("button", { name: "Merge Kimchi and His friend with the supercar" }));
  expect(await screen.findByRole("radio", { name: /Kimchi/ })).toBeChecked();
});

test("They're different keeps both roles on this video, with an Undo that brings the pair back", async () => {
  setViewport(1440);
  const pair = { a_slot_id: 32, b_slot_id: 33, into_slot_id: 32, why: "Both are described as Nate's friend." };
  const calls = fakeServer({
    ...roles,
    "GET /projects/9/assets/maybe-same": [200, [pair]],
    "POST /projects/9/assets/maybe-same/dismiss": [200, []],
    "DELETE /projects/9/assets/maybe-same/dismiss": [200, [pair]],
  });
  open();
  await userEvent.click(await screen.findByText("These may be the same person: Kimchi and His friend with the supercar."));
  await userEvent.click(screen.getByRole("button", { name: "Kimchi and His friend with the supercar are different" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/assets/maybe-same/dismiss")?.body).toEqual({ a_slot_id: 32, b_slot_id: 33 }));
  expect(await screen.findByText("Kept as two roles.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "DELETE /projects/9/assets/maybe-same/dismiss")?.body).toEqual({ a_slot_id: 32, b_slot_id: 33 }));
});

test("a refused They're different shows the server's words", async () => {
  setViewport(1440);
  const pair = { a_slot_id: 32, b_slot_id: 33, into_slot_id: 32, why: "x" };
  fakeServer({ ...roles, "GET /projects/9/assets/maybe-same": [200, [pair]], "POST /projects/9/assets/maybe-same/dismiss": [404, { detail: "Those two roles aren't both in this video." }] });
  open();
  await userEvent.click(await screen.findByText(/^These may be the same person/));
  await userEvent.click(screen.getByRole("button", { name: /are different/ }));
  expect(await screen.findByText("Those two roles aren't both in this video.")).toBeInTheDocument();
});

test("a role the server merged by itself (Girl is the locked girlfriend) says so, with Undo", async () => {
  setViewport(390);
  const why = "Girl is Girlfriend in this video, so they're one role.";
  const calls = fakeServer({
    ...roles,
    "GET /projects/9/assets/maybe-same": [200, [{ a_slot_id: 32, b_slot_id: 40, into_slot_id: 32, why, undo_token: 11 }]],
    "POST /projects/9/assets/merge/undo": [200, [kimchi, friend]],
  });
  open();
  expect(await screen.findByText(why)).toBeInTheDocument();
  expect(screen.queryByText(/These may be the same person/)).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/assets/merge/undo")?.body).toEqual({ token: 11 }));
  expect(await screen.findByText("Kept as two roles.")).toBeInTheDocument();
});
