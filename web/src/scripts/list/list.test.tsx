import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../../test/server";
import { setViewport } from "../../test/viewport";
import { renderApp } from "../../test/render";
import { owner } from "../../test/people";

const v = (slot: number, status: string, o: object = {}) => ({ slot, status, title: "Bo tries salmon", seconds: 0, project_id: null, flavours: {}, flavours_gone: [], ...o });
const script = (o: object = {}) => ({
  id: 7, brand_id: 1, title: "Bo tries salmon", kind: "story", description: "", reference_id: null, published: true, status: "published", folder_id: null,
  created_by_id: 1, created_by_name: "Reed", created_at: "2026-10-24T10:00:00Z", versions_left: 1, versions: [v(0, "approved")], running: false, reel_imported: false, ...o,
});
const folder = (id: number, name: string) => ({ id, brand_id: 1, name, created_by_id: 1, items: { scripts: 1, videos: 0, clips: 0 }, can_manage: true });
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, owner],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /references": [200, []],
  "GET /projects": [200, []],
  "GET /jobs": [200, []],
};
afterEach(() => vi.unstubAllGlobals());

test("the stage tabs show the server's count for each stage, and a tab is the Status filter in the address", async () => {
  setViewport(1440);
  const asked: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: Request | string, init?: RequestInit) => {
      const req = input instanceof Request ? input : new Request(new URL(input, "http://x"), init);
      const url = new URL(req.url);
      const key = `${req.method} ${url.pathname.replace(/^\/api/, "")}`;
      const json = (body: unknown, headers: Record<string, string> = {}) => new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json", ...headers } });
      if (key === "GET /scripts") {
        const status = url.searchParams.get("status") ?? "";
        if (url.searchParams.get("limit") !== "1") asked.push(status);
        return json([script()], { "X-Total-Count": String({ "": 12, draft: 4, published: 6, in_production: 1, done: 1 }[status] ?? 0) });
      }
      return json(base[key]?.[1] ?? []);
    }),
  );
  renderApp("/b/1/scripts");
  expect(await screen.findByRole("tab", { name: "All 12" })).toHaveAttribute("aria-selected", "true");
  expect(await screen.findByRole("tab", { name: "Writing 4" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Ready to make 6" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("tab", { name: "Writing 4" }));
  await vi.waitFor(() => expect(asked).toContain("draft"));
  expect(screen.getByRole("tab", { name: "Writing 4" })).toHaveAttribute("aria-selected", "true");
});

test("scripts are grouped by project with a count each; No project starts open with its rows, and closes", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /brands/1/folders": [200, [folder(3, "Spring launch")]],
    "GET /scripts": [200, [script({ id: 7, title: "Bo tries salmon", folder_id: 3 }), script({ id: 8, title: "Morning walk" }), script({ id: 9, title: "Pool day" })]],
  });
  renderApp("/b/1/scripts");
  const spring = await screen.findByRole("region", { name: "Spring launch" });
  expect(within(spring).getByRole("button", { name: /^Spring launch 1$/ })).toHaveAttribute("aria-expanded", "true");
  expect(within(spring).getByText("Bo tries salmon")).toBeInTheDocument();
  const loose = screen.getByRole("region", { name: "No project" });
  const toggle = within(loose).getByRole("button", { name: /^No project 2$/ });
  expect(toggle).toHaveAttribute("aria-expanded", "true"); // C_Scripts: "No project 17" is open (QA-3 on #1260)
  expect(within(loose).getByText("Morning walk")).toBeInTheDocument();
  await userEvent.click(toggle);
  expect(screen.queryByText("Morning walk")).toBeNull();
});

test("picked scripts move to a project together, with Undo putting each back", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /brands/1/folders": [200, [folder(3, "Spring launch")]],
    "GET /scripts": [200, [script({ id: 7, title: "Bo tries salmon", folder_id: 3 }), script({ id: 8, title: "Morning walk", folder_id: 3 })]],
    "POST /folders/file": [200, { was_folder_id: 3 }],
  });
  renderApp("/b/1/scripts");
  await userEvent.click(await screen.findByRole("checkbox", { name: "Select Bo tries salmon" }));
  await userEvent.click(screen.getByRole("checkbox", { name: "Select Morning walk" }));
  const bar = screen.getByRole("region", { name: "Selected scripts" });
  expect(within(bar).getByText("2 selected")).toBeInTheDocument();
  await userEvent.click(within(bar).getByRole("button", { name: "Move to project" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "No project" }));
  expect(await screen.findByText("Moved 2 scripts to No project.")).toBeInTheDocument();
  expect(calls.filter((c) => c.key === "POST /folders/file").map((c) => c.body)).toEqual([{ kind: "script", id: 7, folder_id: null }, { kind: "script", id: 8, folder_id: null }]);
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /folders/file").slice(2).map((c) => c.body)).toEqual([{ kind: "script", id: 7, folder_id: 3 }, { kind: "script", id: 8, folder_id: 3 }]));
});

test("Archive asks first, then archives every picked script, with Undo restoring them", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts": [200, [script({ id: 7 }), script({ id: 8, title: "Morning walk" })]], "DELETE /scripts/7": [204, null], "DELETE /scripts/8": [204, null], "POST /scripts/7/restore": [200, {}], "POST /scripts/8/restore": [200, {}] });
  renderApp("/b/1/scripts");
  await userEvent.click(await screen.findByRole("checkbox", { name: "Select Bo tries salmon" }));
  await userEvent.click(screen.getByRole("checkbox", { name: "Select Morning walk" }));
  await userEvent.click(within(screen.getByRole("region", { name: "Selected scripts" })).getByRole("button", { name: "Archive" }));
  const ask = screen.getByRole("alertdialog", { name: "Archive 2 scripts?" });
  expect(calls.some((c) => c.key.startsWith("DELETE"))).toBe(false);
  await userEvent.click(within(ask).getByRole("button", { name: "Archive" }));
  expect(await screen.findByText("Archived 2 scripts.")).toBeInTheDocument();
  expect(calls.filter((c) => c.key.startsWith("DELETE")).map((c) => c.key)).toEqual(["DELETE /scripts/7", "DELETE /scripts/8"]);
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key.endsWith("/restore")).length).toBe(2));
});

const full = (o: object = {}) => ({
  ...script(), notes: "", reference_replace: "", new_lines: false, look: "house", language: "en", maybe_same: [],
  cast: [{ id: 1, role: "Bo", kind: "character", description: "", position: 0, appears_in: [], library_item_id: 4, sheet_file_id: null, locked: true, facts: {} }],
  versions: [
    { ...v(0, "in_production", { project_id: 5, editor: { id: 2, name: "Eli" } }), text: "BO: Salmon? Again?", premise: "", has_breakdown: true, clips: 6, seconds: 30, estimate_credits: 60 },
    { ...v(1, "approved"), text: "BO: Fine.", premise: "Shorter ending", has_breakdown: false, clips: 0, estimate_credits: 50 },
  ],
  ...o,
});
const project = { id: 5, brand_id: 1, name: "Bo tries salmon · A", script_draft_id: 7, step: "clips", finished_at: null, needs_you: true, waiting_on: "1 clip ready to check", credits_used: 220, budget_credits: 600, director_credits: 0, archived_at: null, final_out_of_date: false, created_by_id: 2, created_by_name: "Eli" };

test("a published script opens on Overview (v5 C_ScriptOverview): each version's video, maker, credits and press; its words; its facts", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, full()], "GET /projects": [200, [project]], "GET /scripts/7/cast": [200, []], "GET /credits/rates": [200, [{ kind: "write-claude", credits_per_unit: 6 }]], "GET /scripts/7/drafts/1/plan": [404, {}] });
  renderApp("/b/1/scripts/7");
  const a = await screen.findByRole("listitem", { name: "Version A" });
  expect(await within(a).findByText("Needs you")).toBeInTheDocument();
  expect(within(a).getByText("Eli")).toBeInTheDocument();
  expect(within(a).getByText("spent 220 credits")).toBeInTheDocument();
  expect(within(a).getByRole("link", { name: "Open video" })).toHaveAttribute("href", "/b/1/videos/5");
  const b = screen.getByRole("listitem", { name: "Version B" });
  expect(within(b).getByText("No video yet")).toBeInTheDocument();
  expect(within(b).getByText("about 50 credits (planned)")).toBeInTheDocument();
  // The words of the version to make next, in Courier, and the script's facts beside the table.
  expect(screen.getByRole("heading", { name: "Script · version B" })).toBeInTheDocument();
  expect(screen.getByText("BO: Fine.")).toBeInTheDocument();
  const about = screen.getByRole("complementary", { name: "About this script" });
  expect(within(about).getByText("Bo")).toBeInTheDocument();
  expect(within(about).getByText("All locked")).toBeInTheDocument();
  expect(within(about).getByText("Published")).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/\$/);
  // Make a video opens the Make a video panel on that version (#1194's), not a second copy of it.
  await userEvent.click(within(b).getByRole("button", { name: "Make a video" }));
  const panel = await screen.findByRole("dialog", { name: "Make a video from Bo tries salmon" });
  expect(within(panel).getByRole("radio", { name: /^B/ })).toBeChecked();
});

test("the Overview's credits count the director's time too, and a video with nothing spent yet says '0 credits so far', never 'free' (QA on #1237)", async () => {
  setViewport(1440);
  const making = { ...project, id: 6, name: "Bo tries salmon · B", credits_used: 0, director_credits: 0, needs_you: false, waiting_on: null };
  const versions = full().versions.map((x) => (x.slot === 1 ? { ...x, status: "in_production", project_id: 6 } : x));
  fakeServer({ ...base, "GET /scripts/7": [200, full({ versions })], "GET /projects": [200, [{ ...project, credits_used: 99, director_credits: 73 }, making]], "GET /scripts/7/cast": [200, []] });
  renderApp("/b/1/scripts/7");
  expect(await within(await screen.findByRole("listitem", { name: "Version A" })).findByText("spent 99 credits")).toBeInTheDocument(); // as the video's chat says it
  const b = screen.getByRole("listitem", { name: "Version B" });
  expect(await within(b).findByText("0 credits so far")).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/\bfree\b/);
});

test("an unpublished script opens on Overview too: Publish to library, Make a video · up to N on the next version, and Open the steps", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, full({ published: false, status: "draft" })], "GET /projects": [200, [project]], "GET /scripts/7/cast": [200, []], "GET /freestyles/estimate": [200, { credits: 187.4 }], "GET /scripts/7/drafts/0/suggestions": [200, []], "GET /scripts/7/drafts/0/notes": [200, []] });
  renderApp("/b/1/scripts/7");
  expect(await screen.findByRole("listitem", { name: "Version A" })).toBeInTheDocument();
  expect(screen.getByText("Overview")).toHaveAttribute("aria-current", "page");
  expect(screen.queryByRole("group", { name: "Script settings" })).toBeNull(); // the settings and the six steps sit behind Open the steps
  // The price is the version shown's, the same as the panel's press, and it says "up to" before it's pressed.
  const make = await screen.findByRole("button", { name: "Make a video · up to 188 credits" });
  await userEvent.click(make);
  const panel = await screen.findByRole("dialog", { name: "Make a video from Bo tries salmon" });
  expect(within(panel).getByRole("radio", { name: /^B/ })).toBeChecked();
  await userEvent.click(within(panel).getByRole("button", { name: "Close" }));
  // Publish to library opens the Publish page (#1238's G_Publish), which asks before publishing.
  await userEvent.click(screen.getByRole("button", { name: "Publish to library" }));
  expect(await screen.findByText("Publish to the library")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Back to overview" }));
  await userEvent.click(await screen.findByRole("button", { name: "Open the steps: Script · Directions · Variations · Breakdown · Cast" }));
  expect(await screen.findByRole("group", { name: "Script settings" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Back to overview" })).toBeInTheDocument();
});

test("a published script has no Publish to library; a script with no words yet opens on its first step", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, full()], "GET /scripts/7/cast": [200, []], "GET /freestyles/estimate": [200, { credits: 50 }] });
  renderApp("/b/1/scripts/7");
  expect(await screen.findByRole("listitem", { name: "Version A" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Publish to library" })).toBeNull();
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
  const empty = full({ published: false, status: "draft", versions: [{ ...full().versions[1], slot: 0, status: "draft", text: "" }] });
  fakeServer({ ...base, "GET /scripts/7": [200, empty], "GET /scripts/7/cast": [200, []] });
  renderApp("/b/1/scripts/7");
  expect(await screen.findByLabelText("Script · version A")).toBeInTheDocument();
  expect(screen.queryByText("Overview")).toBeNull();
});
