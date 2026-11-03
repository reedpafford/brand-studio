import { cleanup, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";
import { owner } from "../test/people";

const editor = { id: 2, email: "sam@b.co", name: "Sam", role: "editor", workspace_id: 1 };
const brands = [{ id: 1, name: "Iron Paws", colours: [] }, { id: 2, name: "fomo", colours: [] }];
const v = (slot: number, status: string, o: object = {}) => ({ slot, status, title: "Bo tries salmon", seconds: 0, project_id: null, ...o });
const script = (o: object = {}) => ({
  id: 7, brand_id: 1, title: "Bo tries salmon", description: "Show a picky dog finally loving Iron Paws salmon.", reference_id: "altar", published: true, status: "published",
  created_by_id: 1, created_by_name: "Reed", created_at: "2026-10-24T10:00:00Z", versions_left: 2, versions: [v(0, "done", { seconds: 24, project_id: 5 }), v(1, "approved", { seconds: 30 }), v(2, "in_production")], ...o,
});
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, owner],
  "GET /brands": [200, brands],
  "GET /references": [200, [{ id: "altar", name: "The altar reel", logline: "", seconds: 45, style: "", brand: "", has_thumbnail: false }]],
  "GET /projects": [200, []],
};

function open(path = "/b/1/scripts") {
  renderApp(path);
}

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const full = (o: object = {}) => ({
  id: 7, brand_id: 1, title: "Bo tries salmon", description: "Show a picky dog.", reference_id: null, published: false, status: "draft", created_by_id: 1, created_by_name: "Reed", created_at: "2026-10-24T10:00:00Z", versions_left: 0,
  notes: "Keep it warm.", reference_replace: "", cast: [], versions: [{ slot: 0, status: "draft", title: "Bo tries salmon", seconds: 0, project_id: null, text: "", words: 0, target_seconds: null, premise: "", changes: [], problems: [], has_breakdown: false, approved_at: null }], ...o,
});

const reelOut = (o: object = {}) => ({ script_id: 7, status: "ready", source: "link", url: "https://www.instagram.com/reel/Abc123/", seconds: 45, shots: 50, transcript: [{ text: "Hell no." }, { text: "I do." }], video_file_id: 3, contact_file_id: 4, problem: "", problem_code: null, ...o });

test("a script is one row (v5 C_Scripts): its title, each version as a dot then 'A Finished', who it waits on and its owner", async () => {
  fakeServer({ ...base, "GET /scripts": [200, [script()]] });
  open();
  expect(await screen.findByRole("heading", { name: "Bo tries salmon" })).toBeInTheDocument();
  const versions = screen.getByRole("list", { name: "Versions" });
  expect(within(versions).getByText("A Finished")).toBeInTheDocument();
  expect(within(versions).getByText("B Ready to make")).toBeInTheDocument();
  expect(within(versions).getByText("C Making")).toBeInTheDocument();
  expect(screen.getByLabelText("Version A, finished").closest("a")).toHaveAttribute("href", "/b/1/projects/5");
  expect(screen.getByText("An editor to pick it up")).toBeInTheDocument(); // B is ready and nobody has started it
  expect(screen.getByText("Reed")).toBeInTheDocument(); // the owner column
  expect(screen.getByRole("link", { name: "Bo tries salmon" })).toHaveAttribute("href", "/b/1/scripts/7");
  expect(document.body.textContent).not.toMatch(/\bv\d\b/);
});

test("an editor's brand opens on their videos; on Scripts they start on Ready to make", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /auth/me": [200, editor], "GET /scripts": [200, []], "GET /projects": [200, []] });
  open("/b/1");
  expect(await screen.findByRole("heading", { name: "Videos" })).toBeInTheDocument();
  await userEvent.click(screen.getAllByRole("link", { name: "Scripts" })[0]);
  await screen.findByRole("heading", { name: "Scripts" });
  await vi.waitFor(() => expect(calls.some((c) => c.key === "GET /scripts")).toBe(true));
  expect(screen.getByRole("tab", { name: /Ready to make/ })).toHaveAttribute("aria-selected", "true");
  expect(await screen.findByText("Nothing ready to make yet.")).toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: /^All/ })).toBeNull(); // E_EditorScripts: no All tab
});

test("the stage, Group and Sort live in the address and go to the server; Clear filters resets them", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts": [200, []] });
  open("/b/1/scripts?status=in_production&sort=title");
  await screen.findByRole("heading", { name: "Scripts" });
  await vi.waitFor(() => expect(calls.some((c) => c.key === "GET /scripts")).toBe(true));
  expect(screen.getByRole("tab", { name: /In production/ })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("button", { name: "Sort: Title A–Z ▾" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Group: Project ▾" })).toBeInTheDocument();
  expect(await screen.findByText("Nothing matches these filters.")).toBeInTheDocument();
  await userEvent.click(screen.getAllByRole("button", { name: "Clear filters" })[0]);
  expect(screen.getByRole("tab", { name: /All/ })).toHaveAttribute("aria-selected", "true");
  expect(await screen.findByText("No scripts for Iron Paws yet.")).toBeInTheDocument();
});
test("an editor's search waits for typing to stop, then asks the server", async () => {
  const calls = fakeServer({ ...base, "GET /auth/me": [200, editor], "GET /scripts": [200, [script()]] });
  open();
  await userEvent.type(await screen.findByRole("searchbox"), "salmon");
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "GET /scripts").length).toBeGreaterThan(1));
});

test("a failed load says so with Try again", async () => {
  fakeServer({ ...base, "GET /scripts": [500, { detail: "boom" }] });
  open();
  expect(await screen.findByText("Couldn't load your scripts.", {}, { timeout: 10_000 })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
}, 20_000);

test("videos made before scripts stay reachable under a closed disclosure", async () => {
  const old = { id: 9, brand_id: 1, name: "Old reel", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "", cast_ids: [], reference_file_id: null, estimate_credits: 30, budget_credits: 60, credits_used: 5, budget_pct: 8 };
  fakeServer({ ...base, "GET /scripts": [200, []], "GET /projects": [200, [old]] });
  open();
  const section = await screen.findByRole("region", { name: "Videos made before scripts" });
  expect(await within(section).findByText("Videos made before scripts (1)")).toBeInTheDocument();
  expect(within(section).getByRole("link", { name: "New video (the earlier way)" })).toHaveAttribute("href", "/b/1/projects/new");
});

test("New script: picking Dialogue saves nothing; the first word typed saves it and opens its page with the words still being typed, not yet saved", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts": [200, []], "POST /scripts": [201, full({ title: "Untitled script" })], "GET /scripts/7": [200, full({ title: "Untitled script" })] });
  open("/b/1/scripts");
  await userEvent.click(await screen.findByRole("button", { name: "New script" }));
  await userEvent.click(screen.getByRole("menuitem", { name: /Dialogue/ }));
  // The script page's frame shows at once (v5 C_NewScript): the breadcrumb, the settings and the steps, later ones locked.
  expect(await screen.findByRole("navigation", { name: "Breadcrumb" })).toHaveTextContent("Scripts›New script");
  expect(screen.getByRole("button", { name: "Type: Dialogue" })).toBeInTheDocument();
  expect(screen.getByTitle("Each video picks its shape")).toHaveTextContent("Shape Per video: each video picks its shape"); // read only (Next-Lead)
  expect(screen.getByText("Nothing is saved until you type or pick a setting. Lines with a NAME: are dialogue.")).toBeInTheDocument();
  expect(within(screen.getByRole("list", { name: "Steps" })).getByRole("button", { name: /Cast/ })).toHaveAccessibleDescription("Write a few lines first");
  // No dead press: every later step is locked with its reason, Variations too (QA-3 on #1191).
  expect(within(screen.getByRole("list", { name: "Steps" })).getByRole("button", { name: /Variations/ })).toHaveAccessibleDescription("Write a few lines first");
  expect(calls.filter((c) => c.key === "POST /scripts")).toHaveLength(0);
  await userEvent.type(screen.getByLabelText("Write or paste the script"), "B");
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts")?.body).toMatchObject({ brand_id: 1, title: "Untitled script", description: "", text: "", kind: "story" }));
  const editor = await screen.findByLabelText("Script · version A");
  expect(editor).toHaveFocus(); // the cursor came along, so typing goes on where it was
  await userEvent.keyboard("o");
  expect(editor).toHaveValue("Bo");
  expect(screen.getByText("Not saved yet")).toBeInTheDocument();
  expect(calls.filter((c) => c.key === "POST /scripts")).toHaveLength(1);
});

test("New script at 390 and desktop: the header shows on load and opening saves nothing; a Look pick saves the script with that look, a Project pick files it", async () => {
  const looks = [{ id: "house", name: "House", blurb: "", on: true, sample_still_id: null }, { id: "noir", name: "Noir", blurb: "", on: true, sample_still_id: null }];
  for (const width of [1440, 390]) {
    setViewport(width);
    const calls = fakeServer({ ...base, "GET /looks": [200, looks], "GET /brands/1/folders": [200, [{ id: 3, name: "Launch", brand_id: 1, counts: {} }]], "POST /scripts": [201, full({ title: "Untitled script" })], "GET /scripts/7": [200, full({ title: "Untitled script" })], "POST /folders/file": [200, { was_folder_id: null }] });
    const { unmount } = renderApp("/b/1/scripts/new?kind=story");
    await userEvent.click(await screen.findByRole("button", { name: /Style: House/ }));
    expect(calls.filter((c) => c.key === "POST /scripts")).toHaveLength(0);
    await userEvent.click(within(await screen.findByRole("dialog", { name: "Style" })).getAllByRole("button", { name: "Use this style" })[0]);
    await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts")?.body).toMatchObject({ kind: "story", look: "noir" }));
    unmount();
  }
  const calls = fakeServer({ ...base, "GET /looks": [200, looks], "GET /brands/1/folders": [200, [{ id: 3, name: "Launch", brand_id: 1, counts: {} }]], "POST /scripts": [201, full({ title: "Untitled script" })], "GET /scripts/7": [200, full({ title: "Untitled script" })], "POST /folders/file": [200, { was_folder_id: null }] });
  renderApp("/b/1/scripts/new?kind=story");
  await userEvent.click(await screen.findByRole("button", { name: /Project: none/ }));
  await userEvent.click(await screen.findByRole("menuitem", { name: "Launch" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /folders/file")?.body).toMatchObject({ kind: "script", id: 7, folder_id: 3 }));
});

test("New script: the script page opens with its editor already there, so no letter falls between the two boxes", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts": [200, []], "POST /scripts": [201, full({ title: "Untitled script" })] });
  // The script's own load never answers: the page must not need it to show the editor.
  const fake = globalThis.fetch;
  vi.stubGlobal("fetch", (input: Request | string, init?: RequestInit) => {
    const req = input instanceof Request ? input : new Request(new URL(input, "http://x"), init);
    return req.method === "GET" && new URL(req.url).pathname.endsWith("/scripts/7") ? new Promise<Response>(() => {}) : fake(input, init);
  });
  open("/b/1/scripts/new?kind=story");
  await userEvent.type(await screen.findByLabelText("Write or paste the script"), "B");
  expect(await screen.findByLabelText("Script · version A")).toBeInTheDocument();
  await userEvent.keyboard("o tries"); // straight on, into whatever has the cursor
  expect(screen.getByLabelText("Script · version A")).toHaveValue("Bo tries");
  expect(calls.filter((c) => c.key === "POST /scripts")).toHaveLength(1);
});

test("New script: backing out before a word is typed leaves nothing behind (flows S1 U)", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts": [200, []] });
  open("/b/1/scripts/new?kind=story");
  await userEvent.type(await screen.findByLabelText("Write or paste the script"), "   "); // spaces aren't a word
  await userEvent.click(within(screen.getByRole("main")).getByRole("link", { name: "Scripts" }));
  expect((await screen.findAllByRole("button", { name: "New script" }))[0]).toBeInTheDocument(); // the page top's, and the empty list's
  expect(calls.filter((c) => c.key === "POST /scripts")).toHaveLength(0);
});

test("a draft script's page: the breadcrumb, the five v5 steps, and About this script closed but there to edit", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, full()], "PATCH /scripts/7": [200, full({ title: "Bo tries tuna" })] });
  open("/b/1/scripts/7");
  expect(await screen.findByRole("navigation", { name: "Breadcrumb" })).toHaveTextContent("Scripts›Bo tries salmon›Steps");
  const steps = screen.getByRole("list", { name: "Steps" });
  expect(within(steps).getAllByRole("button").map((b) => b.textContent?.replace(/^\d+/, ""))).toEqual(["Script", "Directions", "Variations", "Breakdown", "Cast"]);
  expect(within(steps).getByRole("button", { name: /Directions/ })).toHaveAccessibleDescription("Write the script first");
  expect(within(steps).getByRole("button", { name: /Breakdown/ })).toHaveAccessibleDescription("Write the script first");
  const about = screen.getByText("About this script").closest("details")!;
  expect(about.open).toBe(false); // closed, with the title and what it's for in its line
  await userEvent.click(screen.getByText("About this script"));
  expect(screen.getByLabelText("Notes (optional)")).toHaveValue("Keep it warm.");
  await userEvent.clear(screen.getByLabelText("Title"));
  await userEvent.type(screen.getByLabelText("Title"), "Bo tries tuna");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /scripts/7")?.body).toMatchObject({ title: "Bo tries tuna", description: "Show a picky dog." }));
});

test("the script step autosaves the words as the original a moment after typing stops, with their counts; Next needs them", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, full()], "PUT /scripts/7/drafts/0": [200, full({ versions: [{ ...full().versions[0], text: "BO: Salmon?" }] })] });
  open("/b/1/scripts/7?step=script");
  const next = await screen.findByRole("button", { name: "Next: Directions" });
  expect(next).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Script · version A"), "BO: Salmon?");
  expect(screen.getByText("Not saved yet")).toBeInTheDocument();
  expect(screen.getByText("1 speaker · 1 line")).toBeInTheDocument();
  expect(screen.getByText("2 words · about 0 s")).toBeInTheDocument();
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /scripts/7/drafts/0")?.body).toEqual({ text: "BO: Salmon?" }), { timeout: 3000 });
  expect(await screen.findByText(/^Saved \d/)).toBeInTheDocument();
});

test("a published script is final: its type reads, and there are no rename or edit buttons", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, full({ published: true, status: "published" })] });
  open("/b/1/scripts/7?step=script");
  expect(await screen.findByText("Type: Dialogue")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Rename" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Edit description" })).not.toBeInTheDocument();
});

test("on a published script the owner can still edit the title, what it's for and the notes, and only those", async () => {
  setViewport(390);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, full({ published: true, status: "published" })], "PATCH /scripts/7": [200, full({ published: true, status: "published", title: "Bo tries tuna" })] });
  open("/b/1/scripts/7?step=script");
  await userEvent.click(await screen.findByText("About this script"));
  expect(screen.queryByText("Reference reel (optional)")).toBeNull(); // the reference stays final
  await userEvent.clear(screen.getByLabelText("Title"));
  await userEvent.type(screen.getByLabelText("Title"), "Bo tries tuna");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /scripts/7")?.body).toEqual({ title: "Bo tries tuna", description: "Show a picky dog.", notes: "Keep it warm." }));
});

test("an editor reads a published script's About, with nothing to edit", async () => {
  setViewport(390);
  fakeServer({ ...base, "GET /auth/me": [200, editor], "GET /scripts/7": [200, full({ published: true, status: "published", created_by_id: 2, created_by_name: "Sam" })] });
  open("/b/1/scripts/7?step=script");
  await userEvent.click(await screen.findByText("About this script"));
  expect(screen.getByText("Keep it warm.")).toBeInTheDocument();
  expect(screen.queryByLabelText("Title")).toBeNull();
  expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
});

test("the library has a New script button, and a draft's title opens its page", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts": [200, [script({ id: 7, published: false, status: "draft", versions: [v(0, "draft")] })]] });
  open();
  expect(await screen.findByRole("button", { name: "New script" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Import a reel" })).toHaveAttribute("href", "/b/1/scripts/import");
  expect(await screen.findByRole("link", { name: "Bo tries salmon" })).toHaveAttribute("href", "/b/1/scripts/7");
});

test("a script's age is in plain words", async () => {
  const { age } = await import("./status");
  const now = new Date("2026-10-25T12:00:00Z").getTime();
  expect(age("2026-10-25T11:59:59Z", now)).toBe("just now");
  expect(age("2026-10-25T11:55:00Z", now)).toBe("5 min ago");
  expect(age("2026-10-25T09:00:00Z", now)).toBe("3 h ago");
  expect(age("2026-10-24T09:00:00Z", now)).toBe("yesterday");
  expect(age("2026-10-22T09:00:00Z", now)).toBe("3 days ago");
  expect(age("2026-09-01T09:00:00Z", now)).toMatch(/1 Sep|Sep 1/);
});

const chars = [
  { id: 4, name: "Mia", image_file_ids: [11], sheet_status: "approved" },
  { id: 5, name: "Bo", image_file_ids: [], sheet_status: "none" },
];
const slot = (o: object = {}) => ({ id: 31, role: "Mia", kind: "Main", appears_in: [0, 1, 2], description: "Late 20s, confident.", position: 0, library_item_id: null, sheet_file_id: null, locked: false, ...o });
const withWords = (o: object = {}) => full({ versions: [{ ...full().versions[0], text: "MIA: Hell no!", words: 3, status: "draft" }], ...o });

test("Cast: a role can be added, locked to a character with an approved sheet, and unlocked; Bo needs a sheet first", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /scripts/7": [200, withWords()],
    "GET /scripts/7/cast": [200, [slot()]],
    "GET /library/character": [200, chars],
    "POST /scripts/7/cast": [201, slot({ id: 32, role: "Bo" })],
    "POST /scripts/7/cast/31/lock": [200, slot({ locked: true, library_item_id: 4 })],
  });
  open("/b/1/scripts/7?step=cast");
  expect(await screen.findByText("1 role · 0 locked")).toBeInTheDocument();
  expect(screen.getByText("Main")).toBeInTheDocument();
  expect(screen.getByText("In A, B and C")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Lock Mia to a look" }));
  const panel = await screen.findByRole("dialog", { name: "Lock Mia to a look" });
  expect(within(panel).getByRole("button", { name: "Bo has no approved sheet yet" })).toBeDisabled();
  expect(within(panel).getByText("No approved sheet yet")).toBeInTheDocument();
  await userEvent.click(within(panel).getByRole("button", { name: "Lock to Mia" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts/7/cast/31/lock")?.body).toEqual({ library_item_id: 4 }));
  await userEvent.click(screen.getByRole("button", { name: "Add a role" }));
  const add = await screen.findByRole("dialog", { name: "Add a role" });
  await userEvent.type(within(add).getByLabelText("Role"), "Bo");
  await userEvent.selectOptions(within(add).getByLabelText("Kind"), "Helper");
  await userEvent.click(within(add).getByRole("button", { name: "Add role" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts/7/cast")?.body).toMatchObject({ role: "Bo", kind: "Helper" }));
});

test("Cast: a locked role says so, with Change and Unlock; Remove role asks first", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /scripts/7": [200, withWords()],
    "GET /scripts/7/cast": [200, [slot({ locked: true, library_item_id: 4, sheet_file_id: 11 })]],
    "GET /library/character": [200, chars],
    "DELETE /scripts/7/cast/31/lock": [204, null],
    "DELETE /scripts/7/cast/31": [204, null],
  });
  open("/b/1/scripts/7?step=cast");
  expect(await screen.findByText("Locked to Mia")).toBeInTheDocument();
  expect(screen.getByText("Used as-is in every version.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Unlock Mia" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /scripts/7/cast/31/lock")).toBe(true));
  await userEvent.click(screen.getByRole("button", { name: "More for Mia" }));
  await userEvent.click(await screen.findByRole("menuitem", { name: "Remove role" }));
  const ask = await screen.findByRole("alertdialog", { name: "Remove Mia from the cast?" });
  expect(calls.some((c) => c.key === "DELETE /scripts/7/cast/31")).toBe(false);
  await userEvent.click(within(ask).getByRole("button", { name: "Remove" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /scripts/7/cast/31")).toBe(true));
});

test("the picker locks Characters and Publish until the script has words", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, full()] });
  open("/b/1/scripts/7");
  const steps = await screen.findByRole("list", { name: "Steps" });
  expect(within(steps).getByRole("button", { name: "Cast" })).toHaveAccessibleDescription("Write the script first");
  expect(within(steps).getByRole("button", { name: "Breakdown" })).toHaveAccessibleDescription("Write the script first");
  expect(within(steps).queryByRole("button", { name: "Publish" })).toBeNull(); // v5: Publish to library, not a step in the bar
});

test("Publish waits for every version to be approved, as Variations says; its card approves it in one press, then Publish asks and publishes", async () => {
  setViewport(390);
  const approved = withWords({ versions: [{ ...withWords().versions[0], status: "approved" }] });
  const calls = fakeServer({
    ...base,
    "GET /scripts/7": [200, withWords()],
    "GET /scripts/7/cast": [200, [slot({ locked: true, library_item_id: 4, sheet_file_id: 11 })]],
    "GET /scripts": [200, []],
    "POST /scripts/7/drafts/0/approve": [200, approved],
    "POST /scripts/7/publish": [200, withWords({ published: true, status: "published" })],
  });
  open("/b/1/scripts/7?step=publish");
  const card = await screen.findByLabelText("Version A");
  expect(within(card).getByText("MIA: Hell no!")).toBeInTheDocument();
  expect(within(card).getByText("Not approved yet")).toBeInTheDocument();
  const publish = screen.getByRole("button", { name: "Publish 1 version" });
  expect(publish).toBeDisabled();
  expect(publish).toHaveAccessibleDescription("Approve every version first (1 left)");
  await userEvent.click(within(card).getByRole("button", { name: "Approve version A" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/drafts/0/approve")).toBe(true));
  expect(await within(card).findByText("Approved")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Publish 1 version" }));
  const ask = await screen.findByRole("alertdialog", { name: "Publish 1 version of Bo tries salmon?" });
  await userEvent.click(within(ask).getByRole("button", { name: "Publish" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/publish")).toBe(true));
  expect(calls.filter((c) => c.key === "POST /scripts/7/drafts/0/approve")).toHaveLength(1); // Publish itself approves nothing
  expect(await screen.findByText("Published. 1 version is ready to make.")).toBeInTheDocument();
});

test("an approval on a Publish card can be undone before publishing (#764 QA-2)", async () => {
  setViewport(390);
  const approved = withWords({ versions: [{ ...withWords().versions[0], status: "approved" }] });
  const calls = fakeServer({
    ...base,
    "GET /scripts/7": [200, approved],
    "GET /scripts/7/cast": [200, []],
    "GET /scripts": [200, []],
    "DELETE /scripts/7/drafts/0/approve": [200, withWords()],
  });
  open("/b/1/scripts/7?step=publish");
  const card = await screen.findByLabelText("Version A");
  expect(screen.getByRole("button", { name: "Publish 1 version" })).toBeEnabled();
  await userEvent.click(within(card).getByRole("button", { name: "Undo approval of version A" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /scripts/7/drafts/0/approve")).toBe(true));
  expect(await within(card).findByText("Not approved yet")).toBeInTheDocument();
  expect(within(card).getByRole("button", { name: "Approve version A" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Publish 1 version" })).toHaveAccessibleDescription("Approve every version first (1 left)");
});

test("a published script's Publish page is read-only, with Duplicate script", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /scripts/7": [200, withWords({ published: true, status: "published" })],
    "GET /scripts/7/cast": [200, []],
    "GET /scripts": [200, []],
    "POST /scripts/7/duplicate": [201, full({ id: 8 })],
    "GET /scripts/8": [200, full({ id: 8 })],
  });
  open("/b/1/scripts/7?step=publish");
  await screen.findByRole("button", { name: "Duplicate script" });
  expect(screen.queryByRole("button", { name: /^Publish \d/ })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Duplicate script" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/duplicate")).toBe(true));
  expect(await screen.findByText("Duplicated as a new draft.")).toBeInTheDocument();
});

const reel = (n: number) => ({ id: `r${n}`, name: `Reel ${n}`, logline: n === 1 ? "Reel 1 is about a groom." : `A dog and a bag of salmon treats, take ${n}.`, seconds: 30 + n, style: "", brand: "", has_thumbnail: false });

test("the reference reels are compact rows with a search once there are more than 6; picking one asks what to change", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, full()], "GET /references": [200, [1, 2, 3, 4, 5, 6, 7].map(reel)] });
  open("/b/1/scripts/7");
  await userEvent.click(await screen.findByText("About this script"));
  const list = (await screen.findByText("Reference reel (optional)")).closest("fieldset")!;
  expect(within(list).getAllByRole("button", { pressed: false })).toHaveLength(7);
  expect(within(list).queryByText("Reel 1 is about a groom.")).not.toBeInTheDocument(); // only repeats the name
  expect(within(list).getByText(/take 2\./)).toBeInTheDocument();
  await userEvent.type(within(list).getByLabelText("Search the reels"), "Reel 5");
  expect(within(list).getAllByRole("button")).toHaveLength(1);
  await userEvent.click(within(list).getByRole("button"));
  expect(within(list).getByLabelText("What to change")).toBeInTheDocument();
});

test("leaving the box saves the words, so Next goes straight on; a save that failed asks before leaving and Stay keeps the words", async () => {
  setViewport(1440);
  const before = full({ versions: [{ ...full().versions[0], text: "BO: Salmon?", status: "draft" }] });
  const saved = full({ versions: [{ ...full().versions[0], text: "BO: Salmon? More.", status: "draft" }] });
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, before], "PUT /scripts/7/drafts/0": [200, saved], "GET /scripts/7/drafts/0/suggestions": [200, []], "GET /scripts/7/drafts/0/notes": [200, []], "GET /scripts/7/drafts/0/enhance/estimate": [200, { credits: 3 }] });
  open("/b/1/scripts/7?step=script");
  await userEvent.type(await screen.findByLabelText("Script · version A"), " More.");
  await userEvent.click(screen.getByRole("button", { name: "Next: Directions" }));
  expect(await screen.findByRole("heading", { name: "Suggested directions" })).toBeInTheDocument();
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /scripts/7/drafts/0")?.body).toEqual({ text: "BO: Salmon? More." }));
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
  fakeServer({ ...base, "GET /scripts/7": [200, before], "PUT /scripts/7/drafts/0": [500, { detail: "The server is busy." }] });
  open("/b/1/scripts/7?step=script");
  await userEvent.type(await screen.findByLabelText("Script · version A"), " More.");
  await userEvent.tab();
  expect(await screen.findByRole("alert")).toHaveTextContent("Not saved: The server is busy.");
  await userEvent.click(screen.getByRole("button", { name: "Next: Directions" }));
  expect(await screen.findByRole("alertdialog", { name: "Leave without saving?" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Stay" }));
  expect(screen.getByLabelText("Script · version A")).toHaveValue("BO: Salmon? More.");
});

const ver = (slot: number, o: object = {}) => ({ ...full().versions[0], slot, text: "", status: "draft", changes: [], ...o });
const approvedOriginal = (extra: object[] = []) => full({ versions: [ver(0, { text: "SCENE 1 — CHURCH\nMIA: Hell no.\nShe walks out.", status: "approved" }), ...extra] });

test("Variations: None skips them; 1 or 2 shows the price, approves the original and asks for the variations", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /scripts/7": [200, approvedOriginal()],
    "GET /scripts/7/variations/estimate": [200, { credits: 6 }],
    "POST /scripts/7/variations": [201, { id: 90, kind: "write-claude", status: "queued", credits: 6, project_id: null }],
    "GET /jobs": [200, []],
  });
  open("/b/1/scripts/7?step=variations");
  expect(await screen.findByRole("radio", { name: "None", checked: true })).toBeInTheDocument();
  expect(screen.getByText("Optional. Most scripts go out as one version.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^Write/ })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("radio", { name: "2" }));
  await userEvent.type(screen.getByLabelText("Direction (optional)"), "a car showroom");
  await userEvent.click(await screen.findByRole("button", { name: /Write 2 variations.*6 credits/ }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts/7/variations")?.body).toEqual({ slots: [1, 2], note: "a car showroom" }));
  expect(await screen.findByRole("status", { name: "Writing variations" })).toBeInTheDocument();
});

test("Variations side by side: changed lines are marked, a draft can be approved, and Next waits for it", async () => {
  setViewport(1440);
  const withB = approvedOriginal([ver(1, { text: "SCENE 1 — SHOWROOM\nMIA: Hell no.\nShe walks out.", changes: ["a car showroom instead of the church"] })]);
  const calls = fakeServer({
    ...base,
    "GET /scripts/7": [200, withB],
    "GET /scripts/7/variations/estimate": [200, { credits: 6 }],
    "POST /scripts/7/drafts/1/approve": [200, approvedOriginal([ver(1, { text: "x", status: "approved" })])],
  });
  open("/b/1/scripts/7?step=variations");
  const b = await screen.findByLabelText("Version B");
  expect(within(b).getByText("What changed: a car showroom instead of the church")).toBeInTheDocument();
  const marked = Array.from(b.querySelectorAll("span.bg-mark")).map((e) => e.textContent);
  expect(marked).toEqual(["SCENE 1 — SHOWROOM"]);
  expect(screen.getByRole("button", { name: /Next: Breakdown/ })).toBeDisabled();
  expect(screen.getByRole("button", { name: /Next: Breakdown/ })).toHaveAccessibleDescription("Approve or remove variation B first.");
  await userEvent.click(within(b).getByRole("button", { name: "Approve" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/drafts/1/approve")).toBe(true));
});

test("Variations: Approve all approves the written drafts, says which version was left, and Undo sends back exactly those", async () => {
  setViewport(1440);
  const drafts = approvedOriginal([ver(1, { text: "SCENE 1\nMIA: Hell no." }), ver(2, { text: "SCENE 1\nMIA: Never." })]);
  const calls = fakeServer({
    ...base,
    "GET /scripts/7": [200, drafts],
    "GET /scripts/7/variations/estimate": [200, { credits: 6 }],
    "POST /scripts/7/drafts/approve-all": [200, { approved: [1], skipped: [{ id: 2, label: "C", reason: "still writing" }] }],
    "POST /scripts/7/drafts/approve-all/undo": [200, drafts],
  });
  open("/b/1/scripts/7?step=variations");
  await userEvent.click(await screen.findByRole("button", { name: "Approve all" }));
  expect(await screen.findByText(/Approved 1\./)).toHaveTextContent("Approved 1. 1 not approved: C: still writing");
  expect(await screen.findByText("Approved 1 version.")).toBeInTheDocument(); // the toast, with Undo
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts/7/drafts/approve-all/undo")?.body).toEqual({ ids: [1] }));
});

test("Variations: with one version still to be written, the button counts only the ones it can approve", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, approvedOriginal([ver(1, { text: "SCENE 1\nMIA: Hell no." }), ver(2, { text: "" })])], "GET /scripts/7/variations/estimate": [200, { credits: 6 }] });
  open("/b/1/scripts/7?step=variations");
  expect(await screen.findByRole("button", { name: "Approve 1" })).toBeInTheDocument();
});

test("Variations: the lines that differ from the original are found by their words, ignoring blanks", async () => {
  const { changedLines } = await import("./VariationsStep");
  expect(changedLines("A\nB\nC", "A\nX\n\nC")).toEqual([false, true, false, false]);
});

test("a Ready to make chip opens the version panel, and Make this version reserves it and opens the video at Breakdown", async () => {
  setViewport(1440);
  const full = { ...script({ versions: [v(0, "approved", { text: "INT. KITCHEN\nBo sniffs the salmon.", has_breakdown: false, estimate_credits: 21 })] }) };
  const calls = fakeServer({
    ...base,
    "GET /scripts": [200, [script({ versions: [v(0, "approved")] })]],
    "GET /scripts/7": [200, full],
    "GET /scripts/7/cast": [200, [{ id: 1, role: "Bo", locked: true, sheet_file_id: null }]],
    "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 3 }]],
    "POST /scripts/7/drafts/0/produce": [201, { project_id: 55, breakdown_job_id: null, plan_job_id: 3 }],
    "GET /projects/55": [404, { detail: "x" }],
  });
  open();
  await userEvent.click(await screen.findByRole("link", { name: "Version A, ready to make" }));
  const panel = await screen.findByRole("dialog", { name: "Bo tries salmon · Version A" });
  expect(within(panel).getByText(/Bo sniffs the salmon/)).toBeInTheDocument();
  expect(within(panel).getByText("Bo · Locked look")).toBeInTheDocument();
  expect(within(panel).getByText("The plan is made when you start")).toBeInTheDocument();
  expect(within(panel).getByText("Starting costs 3 (the plan) · the whole video about 21 credits (planned)")).toBeInTheDocument(); // one line (#749 LW5)
  // No saved breakdown: starting one is a paid call, so the button says its price.
  await userEvent.click(within(panel).getByRole("button", { name: /Make this version.*3 credits/ }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/drafts/0/produce")).toBe(true));
  expect(await screen.findByText("Version A is yours. Next: the plan.")).toBeInTheDocument(); // #941: the plan is made first
});

test("Make this version is free when a breakdown is already saved", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /scripts": [200, [script({ versions: [v(0, "approved")] })]],
    "GET /scripts/7": [200, script({ versions: [v(0, "approved", { text: "Hi", has_breakdown: true })] })],
    "GET /scripts/7/cast": [200, []],
    "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 3 }]],
  });
  open("/b/1/scripts?make=7.0");
  const panel = await screen.findByRole("dialog", { name: "Bo tries salmon · Version A" });
  const button = await within(panel).findByRole("button", { name: "Make this version" });
  expect(button).not.toHaveTextContent(/credit/);
});

test("Variations: picking 1 or 2 shows Write and says A's words become final; Next to Breakdown stays", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, approvedOriginal()], "GET /scripts/7/variations/estimate": [200, { credits: 6 }] });
  open("/b/1/scripts/7?step=variations");
  expect(await screen.findByRole("button", { name: "Next: Breakdown" })).toBeInTheDocument(); // None: Next is the amber one
  await userEvent.click(await screen.findByRole("radio", { name: "1" }));
  expect(screen.getByRole("button", { name: "Next: Breakdown" })).toBeEnabled(); // Next always just goes on; Write is a separate button
  expect(screen.getByText("Writing variations makes A's words final.")).toBeInTheDocument();
});

test("Variations: leaving mid-write and coming back shows the writing state, not Write again", async () => {
  setViewport(1440);
  sessionStorage.setItem("variations-job-7", JSON.stringify({ id: 90, slots: [1, 2] }));
  fakeServer({
    ...base,
    "GET /scripts/7": [200, approvedOriginal()],
    "GET /scripts/7/variations/estimate": [200, { credits: 6 }],
    "GET /jobs": [200, [{ id: 90, kind: "write-claude", step: "variations", status: "running", credits: 6, project_id: null, created_at: "2026-10-25T10:00:00Z" }]],
  });
  open("/b/1/scripts/7?step=variations");
  expect(await screen.findByRole("status", { name: "Writing variations" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^Write/ })).not.toBeInTheDocument();
  sessionStorage.clear();
});

test("Variations: Regenerate keeps every column's words and only that column is busy", async () => {
  setViewport(1440);
  sessionStorage.setItem("variations-job-7", JSON.stringify({ id: 91, slots: [2] }));
  const withBC = approvedOriginal([ver(1, { text: "B words", status: "approved" }), ver(2, { text: "C words" })]);
  fakeServer({
    ...base,
    "GET /scripts/7": [200, withBC],
    "GET /scripts/7/variations/estimate": [200, { credits: 6 }],
    "GET /jobs": [200, [{ id: 91, kind: "write-claude", step: "variations", status: "running", credits: 6, project_id: null, created_at: "2026-10-25T10:00:00Z" }]],
  });
  open("/b/1/scripts/7?step=variations");
  const c = await screen.findByLabelText("Version C");
  expect(within(c).getByText("C words")).toBeInTheDocument();
  expect(within(screen.getByLabelText("Version B")).getByText("B words")).toBeInTheDocument();
  expect(within(c).getByRole("button", { name: /Regenerate/ })).toBeDisabled();
  sessionStorage.clear();
});

test("the version panel says what it is a variation of, who planned the breakdown, how many clips, and about what it costs", async () => {
  setViewport(1440);
  const detail = script({ versions: [v(0, "done", { project_id: 5 }), v(1, "approved", { text: "B words", has_breakdown: true, seconds: 28, clips: 4, planned_by: { id: 1, name: "Reed" }, variation_of: "A", estimate_credits: 210 })] });
  fakeServer({
    ...base,
    "GET /scripts": [200, [script({ versions: [v(0, "done", { project_id: 5 }), v(1, "approved")] })]],
    "GET /scripts/7": [200, detail],
    "GET /scripts/7/cast": [200, []],
    "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 3 }]],
  });
  open("/b/1/scripts?make=7.1");
  const panel = await screen.findByRole("dialog", { name: "Bo tries salmon · Version B" });
  expect(await within(panel).findByText("Variation of A")).toBeInTheDocument();
  expect(within(panel).getByText("Planned by Reed · 28 s · 4 clips")).toBeInTheDocument();
  expect(within(panel).getByText("Starting is free · the whole video about 210 credits (planned)")).toBeInTheDocument();
  expect(within(panel).getByRole("button", { name: "Make this version" })).not.toHaveTextContent(/credit/); // a saved breakdown is free
});

test("Variations: an approved variation can be un-approved, and a draft can be removed after a question", async () => {
  setViewport(1440);
  const both = approvedOriginal([ver(1, { text: "B words", status: "approved" }), ver(2, { text: "C words" })]);
  const calls = fakeServer({
    ...base,
    "GET /scripts/7": [200, both],
    "GET /scripts/7/variations/estimate": [200, { credits: 6 }],
    "GET /scripts/7/drafts/2/history": [200, []],
    "DELETE /scripts/7/drafts/1/approve": [200, approvedOriginal([ver(1, { text: "B words" }), ver(2, { text: "C words" })])],
    "DELETE /scripts/7/drafts/2": [200, approvedOriginal([ver(1, { text: "B words", status: "approved" })])],
  });
  open("/b/1/scripts/7?step=variations");
  const b = await screen.findByLabelText("Version B", { exact: true });
  await userEvent.click(within(b).getByRole("button", { name: "Undo approval" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /scripts/7/drafts/1/approve")).toBe(true));
  const c = screen.getByLabelText("Version C", { exact: true });
  await userEvent.click(within(c).getByRole("button", { name: "More for version C" }));
  await userEvent.click(await screen.findByRole("menuitem", { name: "Remove variation C" }));
  const ask = await screen.findByRole("alertdialog", { name: "Remove variation C?" });
  expect(within(ask).getByText("It won't be made.")).toBeInTheDocument();
  await userEvent.click(within(ask).getByRole("button", { name: "Remove" }));
  await vi.waitFor(() => expect(calls.some((c2) => c2.key === "DELETE /scripts/7/drafts/2")).toBe(true));
});

test("Variations: earlier texts of a draft can be brought back", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /scripts/7": [200, approvedOriginal([ver(1, { text: "B now" })])],
    "GET /scripts/7/variations/estimate": [200, { credits: 6 }],
    "GET /scripts/7/drafts/1/history": [200, [{ id: 5, text: "B before", title: "", words: 2, source: "variations", created_at: "2026-10-25T10:00:00Z", created_by_name: "Reed" }, { id: 6, text: "B now", title: "", words: 2, source: "edit", created_at: "2026-10-25T11:00:00Z", created_by_name: "Reed" }]],
    "PUT /scripts/7/drafts/1": [200, approvedOriginal([ver(1, { text: "B before" })])],
  });
  open("/b/1/scripts/7?step=variations");
  const b = await screen.findByLabelText("Version B", { exact: true });
  await userEvent.click(await within(b).findByRole("button", { name: "Earlier: 1" })); // the text on screen isn't listed
  expect(await screen.findByText("B before")).toBeInTheDocument(); // the first line that differs, to tell entries apart
  await userEvent.click(await screen.findByRole("menuitem", { name: /written · 2 words/ }));
  expect(await screen.findByText("Brought back the written text from earlier.")).toBeInTheDocument();
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /scripts/7/drafts/1")?.body).toEqual({ text: "B before" }));
});

test("Variations: a write that is going for this script shows as writing from the job list alone", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /scripts/7": [200, approvedOriginal()],
    "GET /scripts/7/variations/estimate": [200, { credits: 6 }],
    "GET /jobs": [200, [{ id: 3, kind: "write-claude", step: "variations", script_id: 7, status: "running", credits: 6, project_id: null, created_at: "2026-10-25T10:00:00Z" }, { id: 4, kind: "write-claude", step: "variations", script_id: 8, status: "running", credits: 6, project_id: null, created_at: "2026-10-25T10:00:00Z" }]],
  });
  open("/b/1/scripts/7?step=variations");
  expect(await screen.findByRole("status", { name: "Writing variations" })).toBeInTheDocument();
});

test("Variations: a write going for another script doesn't stop this one", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /scripts/7": [200, approvedOriginal()],
    "GET /scripts/7/variations/estimate": [200, { credits: 6 }],
    "GET /jobs": [200, [{ id: 4, kind: "write-claude", step: "variations", script_id: 8, status: "running", credits: 6, project_id: null, created_at: "2026-10-25T10:00:00Z" }]],
  });
  open("/b/1/scripts/7?step=variations");
  expect(await screen.findByRole("radio", { name: "None" })).toBeInTheDocument();
  expect(screen.queryByRole("status", { name: "Writing variations" })).not.toBeInTheDocument();
});

test("Variations: another editor's script doesn't offer Earlier texts, and never asks for them", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /auth/me": [200, editor],
    "GET /scripts/7": [200, { ...approvedOriginal([ver(1, { text: "B now" })]), created_by_id: 1 }],
    "GET /scripts/7/variations/estimate": [200, { credits: 6 }],
    "GET /scripts/7/drafts/1/history": [403, { detail: "No" }],
  });
  open("/b/1/scripts/7?step=variations");
  await screen.findByLabelText("Version B", { exact: true });
  expect(screen.queryByRole("button", { name: /Earlier/ })).not.toBeInTheDocument();
  expect(calls.some((c) => c.key === "GET /scripts/7/drafts/1/history")).toBe(false);
});

test("a video made from a library version isn't listed under Videos made before scripts", async () => {
  const mk = (id: number, o: object = {}) => ({ id, brand_id: 1, name: `Reel ${id}`, planned_seconds: 30, status: "active", goal: "", platform: "", aspect_ratio: "9:16", format: "", cast_ids: [], reference_file_id: null, estimate_credits: 0, budget_credits: 0, credits_used: 0, budget_pct: 0, ...o });
  fakeServer({ ...base, "GET /scripts": [200, []], "GET /projects": [200, [mk(1), mk(2, { script_draft_id: 9 })]] });
  open();
  const section = await screen.findByRole("region", { name: "Videos made before scripts" });
  expect(await within(section).findByText("Videos made before scripts (1)")).toBeInTheDocument();
});

test("a script with one version started and another still ready stays in the editor's main list", async () => {
  setViewport(1440);
  const half = script({ id: 5, title: "Half made", status: "in_production", versions: [v(0, "in_production", { project_id: 40, editor: { id: 2, name: "Sam" } }), v(1, "approved")] });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: Request | string, init?: RequestInit) => {
      const req = input instanceof Request ? input : new Request(new URL(input, "http://x"), init);
      const url = new URL(req.url);
      const key = `${req.method} ${url.pathname.replace(/^\/api/, "")}`;
      const ok = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
      if (key === "GET /scripts") return ok(url.searchParams.get("status") === "in_production" ? [half] : []); // Ready to make leaves it out
      if (key === "GET /auth/me") return ok(editor);
      return ok(key in base ? base[key][1] : []);
    }),
  );
  open();
  expect(await screen.findByText("Half made")).toBeInTheDocument();
  expect(screen.queryByText("Nothing ready to make yet.")).not.toBeInTheDocument();
});

test("the library pages from the server: the total comes from its header, and Show more asks for the next rows", async () => {
  setViewport(1440);
  const asked: string[] = [];
  const all = Array.from({ length: 35 }, (_, i) => script({ id: 100 + i, title: `Script ${i + 1}` }));
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: Request | string, init?: RequestInit) => {
      const req = input instanceof Request ? input : new Request(new URL(input, "http://x"), init);
      const url = new URL(req.url);
      const key = `${req.method} ${url.pathname.replace(/^\/api/, "")}`;
      const json = (body: unknown, headers: Record<string, string> = {}) => new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json", ...headers } });
      if (key === "GET /scripts") {
        if (url.searchParams.get("limit") !== "1") asked.push(`${url.searchParams.get("offset")}/${url.searchParams.get("limit")}/${url.searchParams.get("reference_id") ?? ""}/${url.searchParams.get("sort") ?? ""}`);
        const off = Number(url.searchParams.get("offset") ?? 0);
        return json(all.slice(off, off + Number(url.searchParams.get("limit") ?? 30)), { "X-Total-Count": String(all.length) });
      }
      return json(key === "GET /auth/me" ? owner : (base[key]?.[1] ?? []));
    }),
  );
  open("/b/1/scripts?sort=title&group=none");
  await vi.waitFor(() => expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(30));
  await userEvent.click(screen.getByRole("button", { name: "Show more" }));
  await vi.waitFor(() => expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(35));
  expect(asked).toEqual(["0/30//title", "30/30//title"]);
  expect(screen.queryByRole("button", { name: "Show more" })).not.toBeInTheDocument();
});

test("Bulk create: pasted lines become rows, every row needs a title and what it's for, then drafts are made and Write all asks Claude at one price", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /scripts": [200, []],
    "POST /scripts/bulk": [201, [{ id: 11, title: "Salmon night" }, { id: 12, title: "Gym day with Bo" }]],
    "POST /scripts/write/estimate": [200, { count: 2, credits: 12, credits_left: null }],
    "POST /scripts/write": [201, [{ id: 1, status: "queued" }, { id: 2, status: "queued" }]],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "More for scripts" })); // v5: Bulk create sits in the page's ⋯ menu
  await userEvent.click(screen.getByRole("menuitem", { name: "Bulk create" }));
  const dialog = await screen.findByRole("dialog", { name: "Bulk create" });
  expect(within(dialog).getAllByLabelText(/^Title \d$/)).toHaveLength(3);
  await userEvent.click(within(dialog).getByRole("button", { name: "Make 3 drafts" }));
  expect(await within(dialog).findByText(/Give every row a title and what it's for \(3 rows need it\)/)).toBeInTheDocument();
  await userEvent.click(within(dialog).getByRole("button", { name: "Paste a list" }));
  await userEvent.type(within(dialog).getByLabelText("One script per line: Title — what it's for"), "Salmon night — Bo meets salmon{Enter}Gym day with Bo — Bo lifts");
  await userEvent.click(within(dialog).getByRole("button", { name: "Add these rows" }));
  expect(within(dialog).getAllByLabelText(/^Title \d$/)).toHaveLength(2);
  await userEvent.click(within(dialog).getByRole("button", { name: "Make 2 drafts" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts/bulk")?.body).toMatchObject({ scripts: [{ brand_id: 1, title: "Salmon night", description: "Bo meets salmon" }, { title: "Gym day with Bo" }] }));
  const done = await screen.findByRole("dialog", { name: "Drafts made" });
  expect(await within(done).findByText("About 12 credits (2 scripts × 6)")).toBeInTheDocument();
  await userEvent.click(await within(done).findByRole("button", { name: /Write all scripts.*12 credits/ }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts/write")?.body).toEqual({ script_ids: [11, 12] }));
  expect(await screen.findByText("Writing 2 scripts. They'll show as drafts when they're ready.")).toBeInTheDocument();
});

test("a pasted list: a line without a dash takes its first 6 words as the title and leaves the purpose to fill in", async () => {
  const { parseList } = await import("./BulkCreate");
  expect(parseList("Salmon night — Bo meets salmon\nBo walks to the park every single morning at dawn")).toEqual([
    { title: "Salmon night", description: "Bo meets salmon", reference: "" },
    { title: "Bo walks to the park every", description: "", reference: "" }, // no purpose given: the row is outlined until it has one
  ]);
});

test("an editor's list keeps Title A–Z when a half-made script is added to it", async () => {
  setViewport(1440);
  const half = script({ id: 5, title: "Alpha half made", created_at: "2026-10-01T10:00:00Z", status: "in_production", versions: [v(0, "in_production", { project_id: 40, editor: { id: 2, name: "Sam" } }), v(1, "approved")] });
  const zed = script({ id: 6, title: "Zed ready", created_at: "2026-10-20T10:00:00Z", versions: [v(0, "approved")] });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: Request | string, init?: RequestInit) => {
      const req = input instanceof Request ? input : new Request(new URL(input, "http://x"), init);
      const url = new URL(req.url);
      const key = `${req.method} ${url.pathname.replace(/^\/api/, "")}`;
      const ok = (body: unknown, headers: Record<string, string> = {}) => new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json", ...headers } });
      if (key === "GET /scripts") return url.searchParams.get("status") === "in_production" ? ok([half]) : ok([zed], { "X-Total-Count": "1" });
      if (key === "GET /auth/me") return ok(editor);
      return ok(base[key]?.[1] ?? []);
    }),
  );
  open("/b/1/scripts?sort=title");
  await screen.findByText("Zed ready");
  const titles = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
  expect(titles.indexOf("Alpha half made")).toBeLessThan(titles.indexOf("Zed ready"));
});

test("New script: Import a reel takes a reel link or a video, checks the link first, and makes the script at once", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "POST /scripts/import/link": [201, reelOut({ status: "preparing" })], "GET /scripts/7": [200, full({ id: 7 })], "GET /scripts/7/import": [200, reelOut({ status: "preparing" })] });
  open("/b/1/scripts/import");
  expect(await screen.findByRole("button", { name: "Get the reel" })).toHaveAccessibleDescription("Paste a link to the reel first, or upload a video above"); // greyed out, and says why
  await userEvent.type(await screen.findByLabelText("Link to the reel"), "https://example.com/video");
  await userEvent.click(screen.getByRole("button", { name: "Get the reel" }));
  expect(await screen.findByText("That isn't an Instagram reel link.")).toBeInTheDocument();
  expect(calls.some((c) => c.key === "POST /scripts/import/link")).toBe(false);
  await userEvent.clear(screen.getByLabelText("Link to the reel"));
  await userEvent.type(screen.getByLabelText("Link to the reel"), "https://www.instagram.com/p/Abc123/");
  expect(screen.getByText("Keeps the reel's beats and timing, with fresh words")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("switch", { name: "Write new lines in the same style" }));
  await userEvent.click(screen.getByRole("button", { name: "Get the reel" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts/import/link")?.body).toMatchObject({ brand_id: 1, url: "https://www.instagram.com/p/Abc123/", new_lines: true }));
  expect(await screen.findByText("Getting the reel…")).toBeInTheDocument();
});

test("a script made from a reel shows what was found, and a failed fetch says why and offers to upload", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, full()], "GET /scripts/7/import": [200, reelOut()] });
  open("/b/1/scripts/7");
  expect(await screen.findByText("Got the reel")).toBeInTheDocument();
  expect(screen.getByText("45 s · 50 shots · 2 lines of dialogue")).toBeInTheDocument();
  expect(screen.getByText("instagram.com/reel/Abc123/")).toBeInTheDocument();
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
  fakeServer({ ...base, "GET /scripts/7": [200, full()], "GET /scripts/7/import": [200, reelOut({ status: "failed", problem_code: "blocked", problem: "" })] });
  open("/b/1/scripts/7");
  expect(await screen.findByText("Instagram didn't let us download it. Upload the video instead.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Upload a video" })).toBeInTheDocument();
});

test("each reel problem has its own words and button", async () => {
  setViewport(1440);
  for (const [code, text, button] of [["gone", "That reel is private or was removed.", "Upload a video"], ["bad_file", "That file isn't a video we can read. Use an MP4 or MOV up to 90 seconds.", "Choose another file"], ["too_long", "That video is longer than 90 seconds. Reels up to 90 seconds can be read.", "Choose another file"]] as const) {
    vi.unstubAllGlobals();
    document.body.innerHTML = "";
    fakeServer({ ...base, "GET /scripts/7": [200, full()], "GET /scripts/7/import": [200, reelOut({ status: "failed", problem_code: code })] });
    open("/b/1/scripts/7");
    expect(await screen.findByText(text)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: button })).toBeInTheDocument();
  }
});

test("a script that isn't from a reel has no reel block", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, full()], "GET /scripts/7/import": [404, { detail: "This script isn't made from a reel." }] });
  open("/b/1/scripts/7");
  await screen.findByLabelText("Script · version A");
  expect(screen.queryByText("Got the reel")).not.toBeInTheDocument();
});

const est = (credits: number, left: number | null = null) => ({ credits, credits_left: left });

test("a prepared reel shows its price and the one amber Read this reel · N credits; pressing it starts the read", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /scripts/7": [200, full()],
    "GET /scripts/7/import": [200, reelOut({ estimate: est(7) })],
    "POST /scripts/7/import/read": [201, reelOut({ status: "reading", steps_done: [], estimate: est(7) })],
  });
  open("/b/1/scripts/7");
  expect(await screen.findByText("Reading it costs up to 7 credits.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Read this reel.*7 credits/ }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/import/read")).toBe(true));
  const rows = await screen.findByRole("list", { name: "Reading the reel" });
  expect(within(rows).getByText("Finding the shots and writing the breakdown")).toBeInTheDocument();
});

test("while reading, finished steps are ticked and the current one spins", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, full()], "GET /scripts/7/import": [200, reelOut({ status: "reading", steps_done: ["watch"], estimate: est(7) })] });
  open("/b/1/scripts/7");
  const rows = await screen.findByRole("list", { name: "Reading the reel" });
  const row = (label: string) => within(rows).getByText(label).closest("li")!;
  expect(row("Finding the shots and writing the breakdown")).toHaveTextContent("done");
  expect(row("Writing the script")).toHaveTextContent("now");
  expect(row("Filling in the cast")).toHaveTextContent("next");
  expect(screen.getByText("It keeps going if you leave this page.")).toBeInTheDocument();
});

test("a failed step says which, that the credits were returned, offers Try again at the price left, and says a retried step is charged again", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /scripts/7": [200, full()],
    "GET /scripts/7/import": [200, reelOut({ status: "failed", failed_step: "write", steps_done: ["watch"], estimate: est(4) })],
    "POST /scripts/7/import/read": [201, reelOut({ status: "reading", steps_done: ["watch"], estimate: est(4) })],
  });
  open("/b/1/scripts/7");
  expect(await screen.findByText("The script didn't finish. Credits for this step were returned.")).toBeInTheDocument();
  expect(screen.getByText(/A step that is run again is charged again\./)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Try again.*4 credits/ }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/import/read")).toBe(true));
});

test("a read reel shows the done card", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, full()], "GET /scripts/7/import": [200, reelOut({ status: "done", steps_done: ["watch", "write", "cast"] })] });
  open("/b/1/scripts/7");
  expect(await screen.findByText("Reel read")).toBeInTheDocument();
  expect(screen.getByText("The script and the cast are filled in. Check them, then approve.")).toBeInTheDocument();
});

test("Next waits until the reel is read, so Read this reel is the one amber button", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, full()], "GET /scripts/7/import": [200, reelOut({ estimate: est(7) })] });
  open("/b/1/scripts/7");
  await screen.findByRole("button", { name: /Read this reel/ });
  expect(screen.queryByRole("button", { name: /^Next/ })).not.toBeInTheDocument();
});

test("on a phone Read this reel takes the action bar, and is not in the card", async () => {
  fakeServer({ ...base, "GET /scripts/7": [200, full()], "GET /scripts/7/import": [200, reelOut({ estimate: est(7) })] });
  open("/b/1/scripts/7");
  const button = await screen.findByRole("button", { name: /Read this reel.*7 credits/ });
  expect(screen.getAllByRole("button", { name: /Read this reel/ })).toHaveLength(1);
  expect(button.closest("main")).toBeNull(); // it sits in the shell's action bar, outside the page body
});

test("the server's own words for a problem are shown (a silent video isn't called unreadable), and the code only picks the button", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, full()], "GET /scripts/7/import": [200, reelOut({ status: "failed", problem_code: "bad_file", problem: "This video has no sound. Reels are read from their dialogue, so use one with an audio track." })] });
  open("/b/1/scripts/7");
  expect(await screen.findByText("This video has no sound. Reels are read from their dialogue, so use one with an audio track.")).toBeInTheDocument();
  expect(screen.queryByText(/isn't a video we can read/)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Choose another file" })).toBeInTheDocument();
});

test("the estimate in words rounds up like the button's price", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, full()], "GET /scripts/7/import": [200, reelOut({ estimate: est(6.4) })] });
  open("/b/1/scripts/7");
  expect(await screen.findByText("Reading it costs up to 7 credits.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Read this reel.*7 credits/ })).toBeInTheDocument();
});

test("a step that failed twice says how often it has been tried before the next press, and the server's words for the failure are used", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, full()], "GET /scripts/7/import": [200, reelOut({ status: "failed", failed_step: "watch", problem: "Watching the reel didn't finish. Nothing more was charged; try again.", estimate: { credits: 5, credits_left: null, tries: 2 } })] });
  open("/b/1/scripts/7");
  expect(await screen.findByText("Watching the reel didn't finish. Nothing more was charged; try again.")).toBeInTheDocument();
  expect(screen.getByText(/It has been tried 2 times already\./)).toBeInTheDocument();
});

test("an imported reel's Script screen shows the Title box straight away and saves a new title", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /scripts/7": [200, full({ title: "Untitled reel" })],
    "GET /scripts/7/import": [200, reelOut({ estimate: est(7) })],
    "PATCH /scripts/7": [200, full({ title: "Bo's salmon reel" })],
  });
  open("/b/1/scripts/7");
  const title = await screen.findByRole("textbox", { name: "Title" });
  expect(title).toHaveValue("Untitled reel");
  expect(screen.queryByRole("button", { name: "Save title" })).not.toBeInTheDocument();
  await userEvent.clear(title);
  await userEvent.type(title, "Bo's salmon reel");
  await userEvent.click(screen.getByRole("button", { name: "Save title" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /scripts/7")?.body).toEqual({ title: "Bo's salmon reel" }));
});

test("while a paid reel read runs, the Script screen shows Reading the reel", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /scripts/7": [200, full()],
    "GET /scripts/7/import": [200, reelOut({ status: "reading", steps_done: [], estimate: est(7) })],
    "GET /jobs": [200, [{ id: 5, kind: "write-claude", status: "running", script_id: 7, created_at: new Date(Date.now() - 70_000).toISOString() }]],
  });
  open("/b/1/scripts/7?step=script");
  expect(await screen.findByRole("list", { name: "Reading the reel" })).toBeInTheDocument();
});

const doneReel = (o: object = {}) => reelOut({ status: "done", steps_done: ["watch", "write", "cast"], read_again_credits: 6.2, edited_since_fill: false, new_fill_ready: false, ...o });

test("Read it again opens a panel with the note box and the price first, sends the note, and the reading shows", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /scripts/7": [200, full()],
    "GET /scripts/7/import": [200, doneReel()],
    "POST /scripts/7/import/read-again": [201, doneReel({ status: "reading", steps_done: [] })],
  });
  open("/b/1/scripts/7");
  await userEvent.click(await screen.findByRole("button", { name: "Read it again" }));
  const panel = await screen.findByRole("dialog", { name: "Read it again" });
  await userEvent.type(within(panel).getByLabelText("What did it get wrong? (optional)"), "shot 3 is the groom");
  await userEvent.click(within(panel).getByRole("button", { name: "Read it again · up to 7 credits" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts/7/import/read-again")?.body).toEqual({ note: "shot 3 is the groom" }));
  expect(await screen.findByRole("list", { name: "Reading the reel" })).toBeInTheDocument();
});

test("a note that changes the words is refused in the server's words and stays in the box", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /scripts/7": [200, full()],
    "GET /scripts/7/import": [200, doneReel()],
    "POST /scripts/7/import/read-again": [422, { detail: "Notes can fix who's speaking, the shots and the camera, but not the words said in the reel. Change the words in the script instead." }],
  });
  open("/b/1/scripts/7");
  await userEvent.click(await screen.findByRole("button", { name: "Read it again" }));
  const panel = await screen.findByRole("dialog", { name: "Read it again" });
  const box = within(panel).getByLabelText("What did it get wrong? (optional)");
  await userEvent.type(box, "make him say hello");
  await userEvent.click(within(panel).getByRole("button", { name: /Read it again · / }));
  expect(await within(panel).findByText(/Notes can fix who's speaking/)).toBeInTheDocument();
  expect(box).toHaveValue("make him say hello");
});

test("past the week, Read it again shows the server's reason and nothing is held", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /scripts/7": [200, full()],
    "GET /scripts/7/import": [200, doneReel()],
    "POST /scripts/7/import/read-again": [409, { detail: "Reading it again needs 7 credits; you have 2 left this week. It resets on Monday." }],
  });
  open("/b/1/scripts/7");
  await userEvent.click(await screen.findByRole("button", { name: "Read it again" }));
  await userEvent.click(await within(await screen.findByRole("dialog", { name: "Read it again" })).findByRole("button", { name: /Read it again · / }));
  expect(await screen.findByText(/you have 2 left this week\. It resets on Monday\./)).toBeInTheDocument();
});

test("when a new breakdown is ready but the script was edited, the edits are kept and Fill the script again asks first", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /scripts/7": [200, full()],
    "GET /scripts/7/import": [200, doneReel({ edited_since_fill: true, new_fill_ready: true })],
    "POST /scripts/7/fill-from-reel": [200, doneReel()],
  });
  open("/b/1/scripts/7");
  expect(await screen.findByText("New breakdown ready. Your script edits are kept.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Fill the script again" }));
  const ask = await screen.findByRole("alertdialog", { name: "Replace your script with the reel's?" });
  expect(within(ask).getByText("Your current words move to this version's history.")).toBeInTheDocument();
  await userEvent.click(within(ask).getByRole("button", { name: "Keep my script" }));
  expect(calls.some((c) => c.key === "POST /scripts/7/fill-from-reel")).toBe(false);
  await userEvent.click(screen.getByRole("button", { name: "Fill the script again" }));
  await userEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Replace" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/fill-from-reel")).toBe(true));
});

test("Undo on the fill puts the words from before back", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /scripts/7": [200, full({ versions: [{ ...full().versions[0], text: "My edited words." }] })],
    "GET /scripts/7/import": [200, doneReel({ edited_since_fill: true, new_fill_ready: true })],
    "POST /scripts/7/fill-from-reel": [200, doneReel()],
    "PUT /scripts/7/drafts/0": [200, full()],
  });
  open("/b/1/scripts/7?step=script");
  await userEvent.click(await screen.findByRole("button", { name: "Fill the script again" }));
  await userEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Replace" }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /scripts/7/drafts/0")?.body).toEqual({ text: "My edited words." }));
});

const reelScript = (o: object = {}, rewritten: object[] = [{ line_index: 1, text: "I bought 40 shares of one coin.", was: "I bought 40 hoodies to resell." }]) =>
  full({ reel_imported: true, new_lines: false, versions: [{ ...full().versions[0], text: "BO: Hell no.\nBO: I bought 40 shares of one coin.\nBO: I do.", words: 12, rewritten, approved_at: null }], ...o });

test("a reel-made script marks the rewritten lines with the reel's original under each, a legend and the banner", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, reelScript()], "GET /scripts/7/import": [200, reelOut({ status: "done", steps_done: ["watch", "write", "cast"] })] });
  open("/b/1/scripts/7?step=script");
  expect(await screen.findByText("From the reel: 1 line kept, 1 rewritten for Iron Paws. Check them, then approve.")).toBeInTheDocument();
  expect(screen.getByText("Marked lines were rewritten for Iron Paws. Everything else is said as in the reel.")).toBeInTheDocument();
  const marked = screen.getByText("BO: I bought 40 shares of one coin.");
  expect(marked).toHaveClass("bg-mark");
  expect(screen.getByText("BO: Hell no.")).not.toHaveClass("bg-mark");
  expect(screen.getByText("Was: I bought 40 hoodies to resell.")).toBeInTheDocument();
});

test("with new lines on there are no marks, and the legend says the lines are new in the reel's style", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, reelScript({ new_lines: true }, [])], "GET /scripts/7/import": [200, reelOut({ status: "done", steps_done: ["watch", "write", "cast"] })] });
  open("/b/1/scripts/7?step=script");
  expect(await screen.findByText("New lines, in the style of the reel.")).toBeInTheDocument();
  expect(screen.queryByText(/^Was:/)).toBeNull();
  expect(screen.queryByText(/^From the reel:/)).toBeNull();
});

const shot = (n: number, o: object = {}) => ({ n, start: n * 0.4 - 0.4, end: n * 0.4, framing: "wide three-shot, eye level", camera: "static", action: `Action ${n}`, speaker: "", line: "", dropped: false, ...o });
const review = (o: object = {}) => ({
  logline: "A groom is dumped at the altar for a richer man.",
  hook_seconds: 4.88,
  hook: "Cold open mid-climax: 'I do' answered by a screamed 'HELL NO!'",
  seconds: 45,
  shots: [shot(1, { speaker: "groom", line: "I do." }), shot(2, { action: "Bride screams", speaker: "bride", line: "HELL NO!" }), shot(3), shot(4), shot(5, { dropped: true, action: "Handheld phone clips" })],
  dropped: 1,
  lines: 2,
  montages: [{ first: 3, last: 4, seconds: 0.8 }],
  video_file_id: 3,
  ...o,
});

test("Review the breakdown: the reel, each shot with its time, a still and what happens, dropped live action muted, a montage that opens, Lines only, and the script filled from it", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, full()], "GET /scripts/7/import/breakdown": [200, review()], "GET /scripts/7/import": [200, reelOut({ status: "done", steps_done: ["watch", "write", "cast"] })] });
  open("/b/1/scripts/7/reel");
  const shots = await screen.findByRole("region", { name: "Shots" });
  expect(screen.getByLabelText("The reel")).toHaveAttribute("src", expect.stringContaining("/files/3"));
  expect(screen.getByText("From instagram.com/reel/Abc123/")).toBeInTheDocument();
  expect(within(shots).getByText(/I do\."$/)).toBeInTheDocument();
  expect(within(shots).getByRole("button", { name: "Shot 1, 0:00 to 0:00.4" })).toBeInTheDocument();
  expect(within(shots).getByText("Dropped · live action")).toBeInTheDocument();
  expect(within(shots).getByText(/shots 3–4 · montage · 0.8 s/).closest("summary")!.querySelector("svg")).not.toBeNull(); // the chevron says it opens
  expect(within(shots).queryByRole("tab", { name: "Dropped" })).toBeNull();
  await userEvent.click(within(shots).getByRole("tab", { name: "Lines only" }));
  expect(within(shots).queryByText(/^Action 3/)).toBeNull();
  expect(within(shots).getByText(/HELL NO!"$/)).toBeInTheDocument();
  const filled = screen.getByRole("region", { name: "Script filled from the reel" });
  expect(within(filled).getByText("Adapt it to Iron Paws before you go on.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Start over" })).toHaveAttribute("href", "/b/1/scripts/import");
});

test("Use this script goes to the Script step with the toast", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, full()], "GET /scripts/7/import/breakdown": [200, review()], "GET /scripts/7/import": [200, reelOut({ status: "done", steps_done: ["watch", "write", "cast"] })] });
  open("/b/1/scripts/7/reel");
  await userEvent.click(await screen.findByRole("button", { name: "Use this script" }));
  expect(await screen.findByText(/Script filled from the reel\. Adapt it for/)).toBeInTheDocument();
});

test("a reel that hasn't been read yet says so in the server's words", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, full()], "GET /scripts/7/import/breakdown": [409, { detail: "The reel hasn't been read yet." }] });
  open("/b/1/scripts/7/reel");
  expect(await screen.findByText("The reel hasn't been read yet.")).toBeInTheDocument();
});

test("the done card has Review the breakdown, which opens the review", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, full()], "GET /scripts/7/import": [200, reelOut({ status: "done", steps_done: ["watch", "write", "cast"] })] });
  open("/b/1/scripts/7");
  expect(await screen.findByRole("link", { name: "Review the breakdown" })).toHaveAttribute("href", "/b/1/scripts/7/reel");
});

test("a script made from an imported reel carries a Reel chip in the library; one that isn't doesn't", async () => {
  setViewport(1440);
  const reel = script({ id: 31, title: "Altar swap", reel_imported: true, versions: [v(0, "draft")] });
  const plain = script({ id: 32, title: "Plain script", reel_imported: false, versions: [v(0, "draft")] });
  fakeServer({ ...base, "GET /scripts": [200, [reel, plain]] });
  open();
  const row = (await screen.findByRole("heading", { name: "Altar swap" })).closest("li")!;
  expect(within(row).getByText("Reel")).toBeInTheDocument();
  expect(within(screen.getByRole("heading", { name: "Plain script" }).closest("li")!).queryByText("Reel")).toBeNull();
});

test("Bulk create, Reel links: one link per line, bad lines are named and block the button, then one draft per reel is made and Write all reads and writes at one price", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /scripts": [200, []],
    "POST /scripts/bulk": [201, [{ id: 11, title: "Untitled reel", reel: { status: "ready", seconds: 45 } }, { id: 12, title: "Untitled reel", reel: { status: "failed", seconds: null, fetch_error: "Instagram didn't let us download it." } }]],
    "POST /scripts/write/estimate": [200, { count: 2, credits: 35, credits_left: null, reading: 1, read_credits: 5, writing: 2, write_credits: 30, waiting: [], failed: [12], reels: { links: 1, videos: 0 } }],
    "POST /scripts/write": [201, [{ id: 1, status: "queued" }, { id: 2, status: "queued" }]],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "More for scripts" })); // v5: Bulk create sits in the page's ⋯ menu
  await userEvent.click(screen.getByRole("menuitem", { name: "Bulk create" }));
  const dialog = await screen.findByRole("dialog", { name: "Bulk create" });
  await userEvent.click(within(dialog).getByRole("radio", { name: "Reels" }));
  expect(within(dialog).queryByLabelText(/^Title \d$/)).toBeNull();
  expect(within(dialog).getByRole("button", { name: "Make 0 drafts" })).toHaveAccessibleDescription("Add a reel link or a video first");
  await userEvent.type(within(dialog).getByLabelText("Paste reel links, one per line"), "https://www.instagram.com/reel/Abc123/{Enter}https://example.com/nope{Enter}https://www.instagram.com/reel/Def456/");
  expect(within(dialog).getByText("Line 2 isn't a reel link")).toBeInTheDocument();
  const make = within(dialog).getByRole("button", { name: "Make 2 drafts" }); // counts only the two real reel links
  expect(make).toBeDisabled(); // a bad line blocks it, and says why
  expect(make).toHaveAccessibleDescription("Fix the lines that aren't reel links");
  expect(calls.some((c) => c.key === "POST /scripts/bulk")).toBe(false);
  const box = within(dialog).getByLabelText("Paste reel links, one per line");
  await userEvent.clear(box);
  await userEvent.type(box, "https://www.instagram.com/reel/Abc123/{Enter}https://www.instagram.com/p/Def456/");
  await userEvent.click(within(dialog).getByRole("switch", { name: "Write new lines in the same style" }));
  await userEvent.type(within(dialog).getByLabelText("What to change (optional)"), "reselling becomes trading");
  await userEvent.click(within(dialog).getByRole("button", { name: "Make 2 drafts" }));
  await vi.waitFor(() =>
    expect(calls.find((c) => c.key === "POST /scripts/bulk")?.body).toMatchObject({
      scripts: [
        { brand_id: 1, reel_url: "https://www.instagram.com/reel/Abc123/", new_lines: true, reference_replace: "reselling becomes trading" },
        { reel_url: "https://www.instagram.com/p/Def456/", new_lines: true },
      ],
    }),
  );
  const done = await screen.findByRole("dialog", { name: "Drafts made" });
  expect(await within(done).findByText("About 35 credits: reading 1 reel (5) and writing 2 scripts and casts (30)")).toBeInTheDocument();
  expect(within(done).getByText("Couldn't get the reel")).toBeInTheDocument();
  expect(within(done).getByText("Reel · 45 s")).toBeInTheDocument();
  await userEvent.click(await within(done).findByRole("button", { name: /Write all scripts.*35 credits/ }));
  expect(await screen.findByText("Reading 2 reels and writing their scripts. They'll show as drafts when they're ready.")).toBeInTheDocument();
});

test("the library chip says how long the reel is, that it is being read, or that it couldn't be got", async () => {
  setViewport(1440);
  const rows = [
    script({ id: 41, title: "Ready one", reel_imported: true, reel: { status: "done", seconds: 45.2 }, versions: [v(0, "draft")] }),
    script({ id: 42, title: "Reading one", reel_imported: true, reel: { status: "reading", seconds: 30 }, versions: [v(0, "draft")] }),
    script({ id: 43, title: "Failed one", reel_imported: true, reel: { status: "failed", seconds: null, fetch_error: "That reel is private or was removed." }, versions: [v(0, "draft")] }),
  ];
  fakeServer({ ...base, "GET /scripts": [200, rows] });
  open();
  const inRow = async (title: string) => within((await screen.findByRole("heading", { name: title })).closest("li")!);
  expect((await inRow("Ready one")).getByText("Reel · 45 s")).toBeInTheDocument();
  expect((await inRow("Reading one")).getByText("Reading the reel…")).toBeInTheDocument();
  const failed = (await inRow("Failed one")).getByText("Couldn't get the reel");
  expect(failed.closest("[title]")).toHaveAttribute("title", "That reel is private or was removed.");
});

test("approved words can't be edited, so the Script step shows Words final with Undo approval to edit (never a dead Edit)", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /scripts/7": [200, approvedOriginal()],
    "DELETE /scripts/7/drafts/0/approve": [200, withWords()],
  });
  open("/b/1/scripts/7?step=script");
  expect(await screen.findByText("Words final")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Undo approval to edit" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /scripts/7/drafts/0/approve")).toBe(true));
});

test("About saves with only a title: what it's for is optional (a new draft starts without it)", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, full({ title: "Untitled script", description: "" })], "PATCH /scripts/7": [200, full({ title: "Bo tries tuna", description: "" })] });
  open("/b/1/scripts/7");
  await userEvent.click(await screen.findByText("About this script"));
  await userEvent.clear(screen.getByLabelText("Title"));
  await userEvent.type(screen.getByLabelText("Title"), "Bo tries tuna");
  const save = screen.getByRole("button", { name: "Save" });
  expect(save).toBeEnabled();
  await userEvent.click(save);
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /scripts/7")?.body).toMatchObject({ title: "Bo tries tuna", description: "" }));
});

test("an old /scripts/new link goes to the Scripts list", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts": [200, []] });
  open("/b/1/scripts/new");
  expect(await screen.findByRole("heading", { name: "Scripts", level: 1 })).toBeInTheDocument();
});

// VS1 on Make this version (#956): the video's settings row, its picks held in the panel and sent with the press.
const catalogue = [
  { id: "seedance", kind: "video", name: "Seedance", default: true, credits_per_unit: { "480p": 1 }, lip_sync: true },
  { id: "kling", kind: "video", name: "Kling", default: false, credits_per_unit: { "480p": 2.5 }, lip_sync: false },
  { id: "nano-banana-2.1", kind: "image", name: "Nano Banana 2.1", default: true, credits_per_unit: { "1K": 3 } },
];
const makeServer = (o: Record<string, [number, unknown]> = {}) => ({
  ...base,
  "GET /scripts": [200, [script({ versions: [v(0, "approved")] })]] as [number, unknown],
  "GET /scripts/7": [200, script({ look: "house", language: "en", versions: [v(0, "approved", { has_breakdown: false, estimate_credits: 21 })] })] as [number, unknown],
  "GET /scripts/7/cast": [200, []] as [number, unknown],
  "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 3 }]] as [number, unknown],
  "GET /models": [200, catalogue] as [number, unknown],
  "GET /brands/1/screens": [200, [{ id: 1, product: "Iron Paws", variant: "Salmon" }, { id: 2, product: "Iron Paws", variant: "Chicken" }]] as [number, unknown],
  "POST /scripts/7/drafts/0/estimate": [200, { credits: 21, over_cap: false, reason: null }] as [number, unknown],
  "POST /scripts/7/drafts/0/produce": [201, { project_id: 55, breakdown_job_id: null }] as [number, unknown],
  "GET /projects/55": [404, { detail: "x" }] as [number, unknown],
  ...o,
});

test("Make this version shows the video's settings, and a pick moves the price line", async () => {
  setViewport(1440);
  fakeServer(makeServer({ "GET /looks": [200, [{ id: "house", name: "House", blurb: "", on: true, sample_still_id: null }]] }));
  open();
  await userEvent.click(await screen.findByRole("link", { name: "Version A, ready to make" }));
  const panel = await screen.findByRole("dialog", { name: "Bo tries salmon · Version A" });
  const row = await within(panel).findByRole("region", { name: "Video settings" });
  expect(within(row).getByText("Language: English (from the script)")).toBeInTheDocument();
  expect(within(row).getByRole("button", { name: /Flavour: Auto/ })).toBeInTheDocument(); // no default, no pick
  // The video keeps the script's style (Reed's walk item 7): a locked line, no Look pick.
  expect(within(row).getByText((_, el) => el?.firstElementChild?.textContent === "Style:" && el.textContent === "Style: House · set on the script")).toBeInTheDocument();
  expect(within(row).queryByRole("button", { name: /Look:/ })).toBeNull();
  // The estimate for the new pick; Kling can't lip-sync, and says so in the picker.
  fakeServer(makeServer({ "POST /scripts/7/drafts/0/estimate": [200, { credits: 34, over_cap: false, reason: null }] }));
  await userEvent.click(within(row).getByRole("button", { name: /Video model: Auto/ }));
  const models = await screen.findByRole("dialog", { name: "Video model" });
  expect(within(models).getByRole("button", { name: /Kling/ })).toHaveTextContent("No lip-sync");
  await userEvent.click(within(models).getByRole("button", { name: /Kling/ }));
  expect(await within(panel).findByText("Starting costs 3 (the plan) · the whole video about 34 credits (planned)")).toBeInTheDocument();
  expect(within(row).getByRole("button", { name: /Video model: Kling/ })).toBeInTheDocument();
});

test("Make this version sends the picks as its body, and none when nothing was changed", async () => {
  setViewport(1440);
  const calls = fakeServer(makeServer());
  open();
  await userEvent.click(await screen.findByRole("link", { name: "Version A, ready to make" }));
  const panel = await screen.findByRole("dialog", { name: "Bo tries salmon · Version A" });
  const row = await within(panel).findByRole("region", { name: "Video settings" });
  await userEvent.click(within(row).getByRole("button", { name: /Flavour: Auto/ }));
  await userEvent.click(within(await screen.findByRole("dialog", { name: "Flavour" })).getByRole("button", { name: "Chicken" }));
  await userEvent.click(await within(panel).findByRole("button", { name: /Make this version/ }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts/7/drafts/0/produce")?.body).toEqual({ product_variants: { "Iron Paws": "Chicken" } }));
});

test("over the video limit, Make this version is held back with the reason", async () => {
  setViewport(1440);
  const reason = "That would go over the video limit of 729 credits.";
  fakeServer(makeServer({ "POST /scripts/7/drafts/0/estimate": [200, { credits: 800, over_cap: true, reason }] }));
  open();
  await userEvent.click(await screen.findByRole("link", { name: "Version A, ready to make" }));
  const panel = await screen.findByRole("dialog", { name: "Bo tries salmon · Version A" });
  const make = await within(panel).findByRole("button", { name: /Make this version/ });
  await vi.waitFor(() => expect(make).toBeDisabled());
  expect(panel).toHaveTextContent(reason);
});

test("on a phone the settings are one line that opens a sheet", async () => {
  setViewport(390);
  fakeServer(makeServer());
  open();
  await userEvent.click(await screen.findByRole("link", { name: "Version A, ready to make" }));
  const panel = await screen.findByRole("dialog", { name: "Bo tries salmon · Version A" });
  await userEvent.click(await within(panel).findByRole("button", { name: /^Settings: 9:16 · Auto · .*Auto · Auto$/ }));
  expect(await screen.findByRole("dialog", { name: "Video settings" })).toBeInTheDocument();
});

test("with the owner's plan approved, Make this version says the shots come next and what they cost", async () => {
  setViewport(390);
  const full = { ...script({ versions: [v(0, "approved", { text: "INT. KITCHEN\nBo sniffs the salmon.", has_breakdown: false, estimate_credits: 21 })] }) };
  const calls = fakeServer({
    ...base,
    "GET /scripts": [200, [script({ versions: [v(0, "approved")] })]],
    "GET /scripts/7": [200, full],
    "GET /scripts/7/cast": [200, []],
    "GET /scripts/7/drafts/0/plan": [200, { status: "approved", scenes: [] }],
    "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 3 }]],
    "POST /scripts/7/drafts/0/produce": [201, { project_id: 55, breakdown_job_id: 4 }],
    "GET /projects/55": [404, { detail: "x" }],
  });
  open();
  await userEvent.click(await screen.findByRole("link", { name: "Version A, ready to make" }));
  const panel = await screen.findByRole("dialog", { name: "Bo tries salmon · Version A" });
  expect(await within(panel).findByText("From the owner's plan: the shots are made when you start")).toBeInTheDocument();
  expect(within(panel).getByText("Starting costs 3 (the shots) · the whole video about 21 credits (planned)")).toBeInTheDocument();
  await userEvent.click(within(panel).getByRole("button", { name: /Make this version.*3 credits/ }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/drafts/0/produce")).toBe(true));
  expect(await screen.findByText("Version A is yours. Next: the shots.")).toBeInTheDocument();
});

test("a version's default flavour is the row's; one the server marks gone (flavours_gone) shows as Auto", async () => {
  setViewport(1440);
  const withDefaults = (flavours: object, flavours_gone: string[] = []) => [200, script({ look: "house", language: "en", versions: [v(0, "approved", { has_breakdown: false, estimate_credits: 21, flavours, flavours_gone })] })] as [number, unknown];
  fakeServer(makeServer({ "GET /scripts/7": withDefaults({ "Iron Paws": "Chicken" }) }));
  open();
  await userEvent.click(await screen.findByRole("link", { name: "Version A, ready to make" }));
  let row = await within(await screen.findByRole("dialog", { name: "Bo tries salmon · Version A" })).findByRole("region", { name: "Video settings" });
  expect(within(row).getByRole("button", { name: /Flavour: Chicken/ })).toBeInTheDocument();
  cleanup();
  // The server marks a default gone (#991): Auto, even where the web might still see the flavour (one rule, the server's).
  fakeServer(makeServer({ "GET /scripts/7": withDefaults({ "Iron Paws": "Salmon" }, ["Iron Paws"]) }));
  open();
  await userEvent.click(await screen.findByRole("link", { name: "Version A, ready to make" }));
  row = await within(await screen.findByRole("dialog", { name: "Bo tries salmon · Version A" })).findByRole("region", { name: "Video settings" });
  expect(within(row).getByRole("button", { name: /Flavour: Auto/ })).toBeInTheDocument();
  expect(within(row).queryByRole("button", { name: /Flavour: Salmon/ })).toBeNull();
});

test("the owner's title link still opens the script's own steps", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts": [200, [script()]] });
  open();
  expect(await screen.findByRole("link", { name: "Bo tries salmon" })).toHaveAttribute("href", "/b/1/scripts/7"); // its Overview
});

