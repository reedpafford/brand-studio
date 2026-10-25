import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const owner = { id: 1, email: "reed@b.co", name: "Reed", role: "owner", workspace_id: 1 };
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
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

test("a script is one row: its title, description, reference, length range and a chip for every version in words", async () => {
  fakeServer({ ...base, "GET /scripts": [200, [script()]] });
  open();
  expect(await screen.findByRole("heading", { name: "Bo tries salmon" })).toBeInTheDocument();
  expect(screen.getByText("Show a picky dog finally loving Iron Paws salmon.")).toBeInTheDocument();
  expect(screen.getByText(/Ref: The altar reel · about 24–30 s · 2 versions left to make/)).toBeInTheDocument();
  expect(screen.getByText("A · Video done")).toBeInTheDocument();
  expect(screen.getByText("B · Ready to make")).toBeInTheDocument();
  expect(screen.getByText("C · In production")).toBeInTheDocument();
  expect(screen.getByLabelText("Version A, video done").closest("a")).toHaveAttribute("href", "/b/1/projects/5");
  expect(screen.getByRole("link", { name: "Bo tries salmon" })).toHaveAttribute("href", "/b/1/scripts/7?step=publish");
  expect(screen.getByText("1 script")).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/\bv\d\b|project/i);
});

test("an editor starts on Ready to make, and Reed on everything; the brand home is the library", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /auth/me": [200, editor], "GET /scripts": [200, []] });
  open("/b/1");
  await screen.findByRole("heading", { name: "Scripts" });
  await vi.waitFor(() => expect(calls.some((c) => c.key === "GET /scripts")).toBe(true));
  expect(screen.getByLabelText("Status")).toHaveValue("published");
  expect(await screen.findByText("No scripts ready to make yet.")).toBeInTheDocument();
});

test("filters and search are sent to the server and live in the address; Clear filters resets them", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts": [200, []] });
  open("/b/1/scripts?status=in_production&len=15-30");
  await screen.findByRole("heading", { name: "Scripts" });
  await vi.waitFor(() => expect(calls.some((c) => c.key === "GET /scripts")).toBe(true));
  expect(screen.getByLabelText("Status")).toHaveValue("in_production");
  expect(screen.getByLabelText("Length")).toHaveValue("15-30");
  expect(await screen.findByText("Nothing matches these filters.")).toBeInTheDocument();
  await userEvent.click(screen.getAllByRole("button", { name: "Clear filters" })[0]);
  expect(screen.getByLabelText("Status")).toHaveValue("");
  expect(await screen.findByText("No scripts for Iron Paws yet.")).toBeInTheDocument();
});

test("search waits for typing to stop, then asks the server", async () => {
  const calls = fakeServer({ ...base, "GET /scripts": [200, [script()]] });
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

test("on a phone the filters sit behind one Filters button that opens a sheet, and says how many are on", async () => {
  fakeServer({ ...base, "GET /scripts": [200, []] });
  open("/b/1/scripts?status=done");
  const button = await screen.findByRole("button", { name: "Filters (1)" });
  await userEvent.click(button);
  const sheet = await screen.findByRole("dialog", { name: "Filters" });
  expect(within(sheet).getByLabelText("Status")).toHaveValue("done");
});

const full = (o: object = {}) => ({
  id: 7, brand_id: 1, title: "Bo tries salmon", description: "Show a picky dog.", reference_id: null, published: false, status: "draft", created_by_id: 1, created_by_name: "Reed", created_at: "2026-10-24T10:00:00Z", versions_left: 0,
  notes: "Keep it warm.", reference_replace: "", cast: [], versions: [{ slot: 0, status: "draft", title: "Bo tries salmon", seconds: 0, project_id: null, text: "", words: 0, target_seconds: null, premise: "", changes: [], problems: [], has_breakdown: false, approved_at: null }], ...o,
});

test("New script asks for a title and what it's for, then makes the draft and opens the script step", async () => {
  const calls = fakeServer({ ...base, "GET /scripts": [200, []], "POST /scripts": [201, full()], "GET /scripts/7": [200, full()] });
  open("/b/1/scripts/new");
  const button = await screen.findByRole("button", { name: "Create script" });
  expect(button).toBeDisabled();
  expect(button).toHaveAccessibleDescription("Add a title first");
  await userEvent.type(screen.getByLabelText("Title"), "Bo tries salmon");
  expect(screen.getByRole("button", { name: "Create script" })).toHaveAccessibleDescription("Say what it's for first");
  await userEvent.type(screen.getByLabelText("What it's for"), "Show a picky dog.");
  await userEvent.click(screen.getByRole("button", { name: "Create script" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts")?.body).toMatchObject({ brand_id: 1, title: "Bo tries salmon", description: "Show a picky dog.", text: "" }));
  expect(await screen.findByRole("heading", { name: "Script", level: 2 })).toBeInTheDocument();
});

test("a draft script's page: title, a draft badge, seven steps with the unbuilt ones locked, and the description to read or edit", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, full()], "PATCH /scripts/7": [200, full({ title: "Bo tries tuna" })] });
  open("/b/1/scripts/7");
  expect(await screen.findByRole("heading", { level: 1, name: /Bo tries salmon/ })).toBeInTheDocument();
  expect(screen.getByText("Draft · only you can see it")).toBeInTheDocument(); // Reed on his own draft
  const steps = screen.getByRole("list", { name: "Steps" });
  expect(within(steps).getAllByRole("button").map((b) => b.textContent?.replace(/^\d+/, ""))).toEqual(["Description", "Script", "Directions", "Variations", "Cast", "Breakdown", "Publish"]);
  expect(within(steps).getByRole("button", { name: "Directions" })).toHaveAccessibleDescription("Coming soon");
  expect(screen.getByText("Keep it warm.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Edit description" }));
  await userEvent.clear(screen.getByLabelText("Title"));
  await userEvent.type(screen.getByLabelText("Title"), "Bo tries tuna");
  await userEvent.click(screen.getByRole("button", { name: "Save description" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /scripts/7")?.body).toMatchObject({ title: "Bo tries tuna", description: "Show a picky dog." }));
});

test("the script step saves the words as the original; Next needs them", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, full()], "PUT /scripts/7/drafts/0": [200, full()] });
  open("/b/1/scripts/7?step=script");
  const next = await screen.findByRole("button", { name: "Next: Variations" });
  expect(next).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Your script"), "BO: Salmon?");
  await userEvent.click(screen.getByRole("button", { name: "Save script" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /scripts/7/drafts/0")?.body).toEqual({ text: "BO: Salmon?" }));
});

test("a published script is final: a lock badge, and no rename or edit buttons", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, full({ published: true, status: "published" })] });
  open("/b/1/scripts/7");
  expect(await screen.findByText("Published · final")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Rename" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Edit description" })).not.toBeInTheDocument();
});

test("the library has a New script button, and a draft's title opens its page", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts": [200, [script({ id: 7, published: false, status: "draft", versions: [v(0, "draft")] })]] });
  open();
  expect(await screen.findByRole("link", { name: "New script" })).toHaveAttribute("href", "/b/1/scripts/new");
  expect(await screen.findByRole("link", { name: "Bo tries salmon" })).toHaveAttribute("href", "/b/1/scripts/7");
});

/** A fake server whose list honours ?status (and the brand), like the real one. */
function honouringServer(rows: ReturnType<typeof script>[]) {
  const answers: Record<string, unknown> = { ...Object.fromEntries(Object.entries(base).map(([k, [, body]]) => [k, body])), "GET /auth/me": editor };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: Request | string, init?: RequestInit) => {
      const req = input instanceof Request ? input : new Request(new URL(input, "http://x"), init);
      const url = new URL(req.url);
      const key = `${req.method} ${url.pathname.replace(/^\/api/, "")}`;
      if (key === "GET /scripts") {
        const status = url.searchParams.get("status");
        const out = rows.filter((r) => !status || r.status === status);
        return new Response(JSON.stringify(out), { status: 200, headers: { "content-type": "application/json" } });
      }
      return new Response(JSON.stringify(answers[key] ?? { detail: "not faked" }), { status: key in answers ? 200 : 404, headers: { "content-type": "application/json" } });
    }),
  );
}

test("an editor's own draft shows under Your drafts even though the list asks for Ready to make", async () => {
  setViewport(1440);
  honouringServer([
    script({ id: 1, title: "Sam's draft", status: "draft", published: false, created_by_id: 2, created_by_name: "Sam", versions: [v(0, "draft")] }),
    script({ id: 2, title: "Reed's published one", status: "published", created_by_id: 1 }),
  ]);
  open();
  const drafts = await screen.findByRole("region", { name: "Your drafts" });
  expect(within(drafts).getByText("Sam's draft")).toBeInTheDocument();
  expect(await screen.findByText("Reed's published one")).toBeInTheDocument();
  expect(screen.getAllByText("Sam's draft")).toHaveLength(1); // not listed twice
});

test("a script's age is in plain words", async () => {
  const { age } = await import("./ScriptsPage");
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
  expect(within(panel).getByRole("button", { name: "Bo needs an approved sheet" })).toBeDisabled();
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
  expect(within(steps).getByRole("button", { name: "Publish" })).toHaveAccessibleDescription("Write the script first");
});

test("Publish: a card for the version, then Publish asks, approves the words and publishes", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /scripts/7": [200, withWords()],
    "GET /scripts/7/cast": [200, [slot({ locked: true, library_item_id: 4, sheet_file_id: 11 })]],
    "GET /scripts": [200, []],
    "POST /scripts/7/drafts/0/approve": [200, withWords()],
    "POST /scripts/7/publish": [200, withWords({ published: true, status: "published" })],
  });
  open("/b/1/scripts/7?step=publish");
  const card = await screen.findByLabelText("Version A");
  expect(within(card).getByText("MIA: Hell no!")).toBeInTheDocument();
  expect(within(card).getByText("Runs when an editor starts")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Publish 1 version" }));
  const ask = await screen.findByRole("alertdialog", { name: "Publish 1 version of Bo tries salmon?" });
  expect(calls.some((c) => c.key === "POST /scripts/7/publish")).toBe(false);
  await userEvent.click(within(ask).getByRole("button", { name: "Publish" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/publish")).toBe(true));
  expect(calls.findIndex((c) => c.key === "POST /scripts/7/drafts/0/approve")).toBeLessThan(calls.findIndex((c) => c.key === "POST /scripts/7/publish"));
  expect(await screen.findByText("Published. 1 version is ready to make.")).toBeInTheDocument();
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
  expect(await screen.findAllByText("Published · final")).not.toHaveLength(0);
  expect(screen.queryByRole("button", { name: /^Publish \d/ })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Duplicate script" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/duplicate")).toBe(true));
  expect(await screen.findByText("Duplicated as a new draft.")).toBeInTheDocument();
});

const reel = (n: number) => ({ id: `r${n}`, name: `Reel ${n}`, logline: n === 1 ? "Reel 1 is about a groom." : `A dog and a bag of salmon treats, take ${n}.`, seconds: 30 + n, style: "", brand: "", has_thumbnail: false });

test("the reference reels are compact rows with a search once there are more than 6; picking one asks what to change", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /references": [200, [1, 2, 3, 4, 5, 6, 7].map(reel)] });
  open("/b/1/scripts/new");
  const list = (await screen.findByText("Reference reel (optional)")).closest("fieldset")!;
  expect(within(list).getAllByRole("button", { pressed: false })).toHaveLength(7);
  expect(within(list).queryByText("Reel 1 is about a groom.")).not.toBeInTheDocument(); // only repeats the name
  expect(within(list).getByText(/take 2\./)).toBeInTheDocument();
  await userEvent.type(within(list).getByLabelText("Search the reels"), "Reel 5");
  expect(within(list).getAllByRole("button")).toHaveLength(1);
  await userEvent.click(within(list).getByRole("button"));
  expect(within(list).getByLabelText("What to change")).toBeInTheDocument();
});

test("while the description is being edited its Save is the one amber button, so Next steps aside", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, full()] });
  open("/b/1/scripts/7");
  expect(await screen.findByRole("button", { name: "Next: Script" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Edit description" }));
  expect(screen.queryByRole("button", { name: "Next: Script" })).not.toBeInTheDocument();
  expect(screen.getByText("For Iron Paws")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.getByRole("button", { name: "Next: Script" })).toBeInTheDocument();
});

test("the draft badge says who can see it: you, you and Reed, or whose draft it is", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /auth/me": [200, editor], "GET /scripts/7": [200, full({ created_by_id: 2, created_by_name: "Sam" })] });
  open("/b/1/scripts/7");
  expect(await screen.findByText("Draft · only you and Reed can see it")).toBeInTheDocument();
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
  fakeServer({ ...base, "GET /scripts/7": [200, full({ created_by_id: 2, created_by_name: "Sam" })] });
  open("/b/1/scripts/7");
  expect(await screen.findByText("Draft · Sam's, not published")).toBeInTheDocument();
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
  expect(screen.getByRole("button", { name: /Next: Cast/ })).toBeDisabled();
  expect(screen.getByRole("button", { name: /Next: Cast/ })).toHaveAccessibleDescription("Approve variation B first.");
  await userEvent.click(within(b).getByRole("button", { name: "Approve" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/drafts/1/approve")).toBe(true));
});

test("Variations: the lines that differ from the original are found by their words, ignoring blanks", async () => {
  const { changedLines } = await import("./VariationsStep");
  expect(changedLines("A\nB\nC", "A\nX\n\nC")).toEqual([false, true, false, false]);
});

test("a Ready to make chip opens the version panel, and Make this version reserves it and opens the video at Breakdown", async () => {
  setViewport(1440);
  const full = { ...script({ versions: [v(0, "approved", { text: "INT. KITCHEN\nBo sniffs the salmon.", has_breakdown: false })] }) };
  const calls = fakeServer({
    ...base,
    "GET /scripts": [200, [script({ versions: [v(0, "approved")] })]],
    "GET /scripts/7": [200, full],
    "GET /scripts/7/cast": [200, [{ id: 1, role: "Bo", locked: true, sheet_file_id: null }]],
    "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 3 }]],
    "POST /scripts/7/drafts/0/produce": [201, { project_id: 55, breakdown_job_id: 3 }],
    "GET /projects/55": [404, { detail: "x" }],
  });
  open();
  await userEvent.click(await screen.findByRole("link", { name: "Version A, ready to make" }));
  const panel = await screen.findByRole("dialog", { name: "Bo tries salmon · Version A" });
  expect(within(panel).getByText(/Bo sniffs the salmon/)).toBeInTheDocument();
  expect(within(panel).getByText("Bo · Locked look")).toBeInTheDocument();
  expect(within(panel).getByText("Planned automatically when you start")).toBeInTheDocument();
  // No saved breakdown: starting one is a paid call, so the button says its price.
  await userEvent.click(within(panel).getByRole("button", { name: /Make this version.*3 credits/ }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/drafts/0/produce")).toBe(true));
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

test("an In production chip opens the video for Reed and for its maker, and the panel for anyone else", async () => {
  setViewport(1440);
  const mk = (created_by_id: number) => ({ id: 31, brand_id: 1, name: "Bo", planned_seconds: 30, status: "active", goal: "", platform: "", aspect_ratio: "9:16", format: "", cast_ids: [], reference_file_id: null, estimate_credits: 0, budget_credits: 0, credits_used: 0, budget_pct: 0, created_by_id, created_by_name: "x" });
  const rows = [script({ versions: [v(0, "in_production", { project_id: 31 })] })];
  fakeServer({ ...base, "GET /auth/me": [200, editor], "GET /scripts": [200, rows], "GET /projects": [200, [mk(2)]] });
  open();
  await vi.waitFor(() => expect(screen.getByLabelText("Version A, in production").closest("a")).toHaveAttribute("href", "/b/1/projects/31"));
});

test("an editor past the week's allowance on their own script can't make it, and is told when it resets; on Reed's script the button just shows the price", async () => {
  setViewport(1440);
  const answers = (createdBy: number) => ({
    ...base,
    "GET /auth/me": [200, editor] as [number, unknown],
    "GET /scripts": [200, []] as [number, unknown],
    "GET /scripts/7": [200, script({ created_by_id: createdBy, versions: [v(0, "approved", { text: "Hi", has_breakdown: false })] })] as [number, unknown],
    "GET /scripts/7/cast": [200, []] as [number, unknown],
    "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 3 }]] as [number, unknown],
    "GET /credits/me": [200, { quick_clip_credits_used: 144, quick_clip_credits_allowed: 145 }] as [number, unknown],
  });
  fakeServer(answers(2));
  const { unmount } = render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/b/1/scripts?make=7.0"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  const panel = await screen.findByRole("dialog", { name: "Bo tries salmon · Version A" });
  const own = await within(panel).findByRole("button", { name: /Make this version.*3 credits/ });
  await vi.waitFor(() => expect(own).toBeDisabled());
  expect(within(panel).getByText("You've used this week's 145 credits. It resets Monday.")).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/Ask Reed/);
  unmount();

  fakeServer(answers(1));
  open("/b/1/scripts?make=7.0");
  const other = await screen.findByRole("dialog", { name: "Bo tries salmon · Version A" });
  expect(await within(other).findByRole("button", { name: /Make this version.*3 credits/ })).toBeEnabled();
});

test("Variations: picking 1 or 2 makes Write the one amber button, and says A's words become final", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, approvedOriginal()], "GET /scripts/7/variations/estimate": [200, { credits: 6 }] });
  open("/b/1/scripts/7?step=variations");
  expect(await screen.findByRole("button", { name: "Next: Cast" })).toBeInTheDocument(); // None: Next is the amber one
  await userEvent.click(await screen.findByRole("radio", { name: "1" }));
  expect(screen.queryByRole("button", { name: "Next: Cast" })).not.toBeInTheDocument();
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

test("Variations: an editor on their own script past the week's allowance can't Write, and is told when it resets", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /auth/me": [200, editor],
    "GET /scripts/7": [200, { ...approvedOriginal(), created_by_id: 2 }],
    "GET /scripts/7/variations/estimate": [200, { credits: 6 }],
    "GET /credits/me": [200, { quick_clip_credits_used: 144, quick_clip_credits_allowed: 145 }],
  });
  open("/b/1/scripts/7?step=variations");
  await userEvent.click(await screen.findByRole("radio", { name: "1" }));
  const write = await screen.findByRole("button", { name: /Write 1 variation/ });
  await vi.waitFor(() => expect(write).toBeDisabled());
  expect(write).toHaveAccessibleDescription("You've used this week's 145 credits. It resets Monday.");
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
  expect(within(panel).getByText("About 210 credits to make")).toBeInTheDocument();
  expect(within(panel).getByRole("button", { name: "Make this version" })).not.toHaveTextContent(/credit/); // a saved breakdown is free
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
  await userEvent.click(await screen.findByRole("button", { name: "Bulk create" }));
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

test("Bulk create for an editor: past the week's allowance Write all is disabled with when it resets, and there is no Ask Reed", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /auth/me": [200, editor],
    "GET /scripts": [200, []],
    "GET /credits/me": [200, { quick_clip_credits_used: 140, quick_clip_credits_allowed: 145 }],
    "POST /scripts/bulk": [201, [{ id: 11, title: "Salmon night" }, { id: 12, title: "Gym day" }]],
    "POST /scripts/write/estimate": [200, { count: 2, credits: 12, credits_left: 5 }],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Bulk create" }));
  const dialog = await screen.findByRole("dialog", { name: "Bulk create" });
  await userEvent.click(within(dialog).getByRole("button", { name: "Paste a list" }));
  await userEvent.type(within(dialog).getByLabelText("One script per line: Title — what it's for"), "Salmon night — Bo meets salmon{Enter}Gym day — Bo lifts");
  await userEvent.click(within(dialog).getByRole("button", { name: "Add these rows" }));
  await userEvent.click(within(dialog).getByRole("button", { name: "Make 2 drafts" }));
  const done = await screen.findByRole("dialog", { name: "Drafts made" });
  const write = await within(done).findByRole("button", { name: /Write all scripts.*12 credits/ });
  await vi.waitFor(() => expect(write).toBeDisabled());
  expect(write).toHaveAccessibleDescription("You've used this week's 145 credits. It resets Monday.");
  expect(document.body.textContent).not.toMatch(/Ask Reed/);
});

test("a pasted list: a line without a dash takes its first 6 words as the title and leaves the purpose to fill in", async () => {
  const { parseList } = await import("./BulkCreate");
  expect(parseList("Salmon night — Bo meets salmon\nBo walks to the park every single morning at dawn")).toEqual([
    { title: "Salmon night", description: "Bo meets salmon", reference: "" },
    { title: "Bo walks to the park every", description: "", reference: "" }, // no purpose given: the row is outlined until it has one
  ]);
});
