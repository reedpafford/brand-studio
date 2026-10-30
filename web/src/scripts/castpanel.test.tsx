import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";
import { owner } from "../test/people";

const script = {
  id: 7, brand_id: 1, title: "Bo tries salmon", description: "x", reference_id: null, reel_imported: false, new_lines: false, published: false, status: "draft", created_by_id: 1, created_by_name: "Reed", created_at: "2026-10-24T10:00:00Z", versions_left: 0, notes: "", reference_replace: "", cast: [],
  versions: [{ slot: 0, status: "approved", title: "x", seconds: 0, project_id: null, text: "MIA: Hell no!", words: 3, target_seconds: null, premise: "", changes: [], problems: [], has_breakdown: false, approved_at: null }],
};
const slot = { id: 31, role: "Mia", kind: "Main", appears_in: [0], description: "Late 20s.", position: 0, library_item_id: null, sheet_file_id: null, locked: false };
const char = (o: object = {}) => ({ id: 5, name: "Bo", image_file_ids: [], sheet_status: "none", sheet_file_id: null, ...o });
const base = (o: Record<string, [number, unknown]> = {}): Record<string, [number, unknown]> => ({
  "GET /auth/me": [200, owner],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /references": [200, []],
  "GET /projects": [200, []],
  "GET /jobs": [200, []],
  "GET /scripts/7": [200, script],
  "GET /scripts/7/cast": [200, []],
  "GET /scripts/7/cast/read": [200, { running: false, problems: [] }],
  "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 4 }]],
  "GET /models": [200, [{ id: "nano-banana-pro", kind: "image", name: "x", credits_per_unit: { "2K": 3 } }]],
  "GET /library/character": [200, [char()]],
  ...o,
});
function open() {
  renderApp("/b/1/scripts/7?step=cast");
}
afterEach(() => vi.unstubAllGlobals());

test("an empty cast offers Find roles in the script at its price, and pressing it starts the read", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "POST /scripts/7/cast/read": [201, { id: 90, kind: "write-claude", status: "queued" }] }));
  open();
  expect(await screen.findByText("Claude can find the roles in your script.")).toBeInTheDocument();
  await userEvent.click(await screen.findByRole("button", { name: "Find roles in the script · up to 4 credits" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/cast/read")).toBe(true));
});

// One App per test: a second tree mounted beside the first kept polling and raced it (the flake on #926).
test("while roles are being found it says so", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts/7/cast/read": [200, { running: true, problems: [] }] }));
  open();
  expect(await screen.findByText("Finding the roles…")).toBeInTheDocument();
});

test("with roles there is Find roles again, after a confirm", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "GET /scripts/7/cast": [200, [slot]], "POST /scripts/7/cast/read": [201, { id: 91, kind: "write-claude", status: "queued" }] }));
  open();
  await userEvent.click((await screen.findAllByRole("button", { name: "Find roles again · up to 4 credits" })).at(-1)!);
  const dialog = await screen.findByRole("alertdialog", { name: "Find the roles again?" });
  expect(dialog).toHaveTextContent("Locked roles stay locked; roles you added stay.");
  await userEvent.click(within(dialog).getByRole("button", { name: "Find roles" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/cast/read")).toBe(true));
});

test("in Lock to a look, a character without a sheet gets Make sheet at its price right there", async () => {
  setViewport(1440);
  const calls = fakeServer(base({ "GET /scripts/7/cast": [200, [slot]], "POST /library/character/5/sheet": [201, { id: 92, kind: "image", status: "queued" }] }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Lock Mia to a look" }));
  const panel = await screen.findByRole("dialog", { name: "Lock Mia to a look" });
  expect(within(panel).getByText("No approved sheet yet")).toBeInTheDocument();
  await userEvent.click(within(panel).getByRole("button", { name: "Make sheet · up to 3 credits" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /library/character/5/sheet")?.body).toMatchObject({ change: "" }));
});

test("a sheet that needs approval is approved in the panel, and approving locks the role to it", async () => {
  setViewport(1440);
  const calls = fakeServer(base({
    "GET /scripts/7/cast": [200, [slot]],
    "GET /library/character": [200, [char({ sheet_status: "needs_approval", sheet_file_id: 12 })]],
    "POST /library/character/5/sheet/approve": [200, {}],
    "POST /scripts/7/cast/31/lock": [200, { ...slot, locked: true, library_item_id: 5 }],
  }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Lock Mia to a look" }));
  const panel = await screen.findByRole("dialog", { name: "Lock Mia to a look" });
  await userEvent.click(within(panel).getByRole("button", { name: "Approve Bo's sheet" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts/7/cast/31/lock")?.body).toEqual({ library_item_id: 5 }));
  expect(calls.some((c) => c.key === "POST /library/character/5/sheet/approve")).toBe(true);
});

test("Find roles waits for the script to be approved, and says so up front", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts/7": [200, { ...script, versions: [{ ...script.versions[0], status: "draft" }] }] }));
  open();
  await vi.waitFor(() => expect(screen.getByRole("button", { name: /^Find roles in the script/ })).toHaveAccessibleDescription("Approve the script first"));
  expect(screen.getByRole("button", { name: /^Find roles in the script/ })).toBeDisabled();
});

test("an editor past the week's allowance can't press Find roles", async () => {
  setViewport(1440);
  const editor = { ...owner, id: 2, role: "editor" };
  fakeServer(base({ "GET /auth/me": [200, editor], "GET /scripts/7": [200, { ...script, created_by_id: 2 }], "GET /credits/me": [200, { quick_clip_credits_used: 145, quick_clip_credits_allowed: 145 }] }));
  open();
  await vi.waitFor(() => expect(screen.getByRole("button", { name: /^Find roles in the script/ })).toHaveAccessibleDescription("You've used this week's 145 credits. It resets on Monday."));
  expect(screen.getByRole("button", { name: /^Find roles in the script/ })).toBeDisabled();
});

test("a refused Find roles shows the server's reason alone", async () => {
  setViewport(1440);
  fakeServer(base({ "POST /scripts/7/cast/read": [409, { detail: "The cast is already being read for this script." }] }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Find roles in the script · up to 4 credits" }));
  expect(await screen.findByText("The cast is already being read for this script.")).toBeInTheDocument();
  expect(screen.queryByText(/weren't found/)).toBeNull();
});

test("a role on the Cast step leads with its age, gender and job, a guess marked", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts/7/cast": [200, [{ ...slot, facts: { age_range: { value: "Late 20s", inferred: true }, gender: { value: "woman", inferred: false }, occupation: { value: "nurse", inferred: false } } }]] }));
  open();
  const facts = await screen.findByText((_, el) => el?.tagName === "P" && el.textContent === "Late 20s (a guess) · woman · nurse");
  expect(facts.querySelector(".text-faint")).toHaveTextContent("(a guess)");
});

test("a role with no facts shows no facts line", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts/7/cast": [200, [{ ...slot, facts: {} }]] }));
  open();
  await screen.findByText("Late 20s.");
  expect(screen.queryByText(/\(a guess\)/)).toBeNull();
});

test("a first fact the server sends in lower case starts with a capital", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts/7/cast": [200, [{ ...slot, facts: { age_range: { value: "late 20s", inferred: false } } }]] }));
  open();
  expect(await screen.findByText("Late 20s")).toBeInTheDocument();
});

test("a script with no variations is approved right on the Cast step, with an Undo, and then Find roles opens", async () => {
  setViewport(1440);
  let approved = false;
  const withStatus = (status: string) => ({ ...script, versions: [{ ...script.versions[0], status }] });
  const routes = base({ "POST /scripts/7/drafts/0/approve": [200, withStatus("approved")], "DELETE /scripts/7/drafts/0/approve": [200, withStatus("draft")] });
  Object.defineProperty(routes, "GET /scripts/7", { enumerable: true, get: () => [200, { ...script, versions: [{ ...script.versions[0], status: approved ? "approved" : "draft" }] }] });
  const calls = fakeServer(routes);
  open();
  const find = () => screen.getByRole("button", { name: /^Find roles in the script/ });
  await vi.waitFor(() => expect(find()).toBeDisabled());
  approved = true;
  await userEvent.click(await screen.findByRole("button", { name: "Approve the script" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/drafts/0/approve")).toBe(true));
  expect(await screen.findByText("Script approved. Its words are final.")).toBeInTheDocument();
  await vi.waitFor(() => expect(find()).toBeEnabled()); // Find roles is open now
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /scripts/7/drafts/0/approve")).toBe(true));
});

test("an unlocked role says each video makes its own look, and about what it costs", async () => {
  setViewport(1440);
  fakeServer(base({ "GET /scripts/7/cast": [200, [slot]] }));
  open();
  expect(await screen.findByText("Not locked: each video makes its own look (about 3 credits each).")).toBeInTheDocument();
});

test("on a song, Find roles reads the lyrics as they are: no Approve step first (the Producer's row 4)", async () => {
  setViewport(390);
  const song = { ...script, kind: "song", versions: [{ ...script.versions[0], status: "draft", text: "[Verse]\nMia sings to Bo" }] };
  const take = { id: 1, number: 1, status: "ready", failed_reason: null, retry_helps: true, file_id: 40, seconds: 31, made_at: "2026-10-28T10:42:00Z", preferred: true, out_of_date: false, peaks: [0.5], advice: [], timing_guessed: false, refused_for: null, video_credits: 34, over_cap: false, fits_until: null, trim_to: null };
  fakeServer(base({ "GET /scripts/7": [200, song], "GET /scripts/7/drafts/0/songs": [200, { songs_on: true, estimate_credits: 1, takes: [take] }] }));
  open();
  const find = await screen.findByRole("button", { name: /^Find roles in the script · up to/ });
  await vi.waitFor(() => expect(find).toBeEnabled());
  expect(screen.queryByRole("button", { name: /^Approve the (script|words)/ })).toBeNull();
});
