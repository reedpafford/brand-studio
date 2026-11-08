import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { cutOut } from "../test/cut";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";
import { editor } from "../test/people";

const project = {
  id: 9, brand_id: 1, name: "Bo tries salmon · B", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "",
  cast_ids: [], reference_file_id: null, estimate_credits: 30, budget_credits: 600, credits_used: 0, budget_pct: 0, product_variants: {}, created_by_id: 2,
};
const script = { version: 5, source: "paste", words: 9, created_by_id: 2, created_at: "2026-10-23T10:00:00Z", text: "Bo eats." };
const breakdown = { id: 1, script_version: 5, source: "claude", stale: false, problems: [], breakdown: { hook: "Hook.", scenes: [{ id: 1, heading: "KITCHEN", look: "", shots: [] }], clips: [] } };
const asset = (o: object) => ({ kind: "character", ref: "char:5", role: "Bo", library_item_id: 5, name: "Bo", locked: false, sheet_status: "needs_approval", ready: false, description: "", shots: 1, clip_ids: [], ...o });
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
  "GET /credits/limits": [200, { weekly_quick_clip_credits: 145 }],
};

function open(query = "?step=cast") {
  renderApp(`/b/1/videos/9${query}`);
}

afterEach(() => vi.unstubAllGlobals());

test("the preview panel's tabs (v6 S3), and Clips waits for the cast, saying why, with one press to Cast", async () => {
  setViewport(1440);
  fakeServer(base);
  open("?tab=clips");
  const tabs = await screen.findByRole("tablist", { name: "Preview" });
  expect(within(tabs).getAllByRole("tab").map((b) => b.textContent)).toEqual(["Cut", "Clips", "Cast 1", "Plan", "Script"]);
  expect(await screen.findByText("Approve the cast first (1 left).")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Open Cast" }));
  expect(screen.getByRole("tab", { name: "Cast 1", selected: true })).toBeInTheDocument();
});

const frame = { id: 1, clip_id: "c1", shot_id: "1.1", prompt: "p", reference_ids: [], problems: [], kept: [], file_id: 40, approved: true, stale: false, earlier: [], change: null };
const clip = (o: object) => ({ id: 3, clip_id: "c1", seconds: 8, prompt: "Bo sniffs the salmon", references: [], problems: [], kept: [], file_id: null, takes: [], picked_take_id: null, approved: false, stale: false, take_credits: 24, inserts: [], ...o });
const toClips = { ...base, "GET /projects/9/assets": [200, []] as [number, unknown], "GET /projects/9/storyboard": [200, [frame]] as [number, unknown] };

const take = (id: number, number: number) => ({ id, number, file_id: 50 + id, created_at: `2026-10-26T10:4${number}:00` });
const done = clip({ approved: true, file_id: 51, takes: [take(1, 1), take(2, 2)], picked_take_id: 2 });

test("the Cut tab (S3-09): Download MP4 is the one amber; every clip downloads as a zip", async () => {
  setViewport(1440);
  fakeServer({ ...toClips, "GET /projects/9/clips": [200, [done]], "GET /projects/9/video": [200, { file_id: 60, take_ids: [2], out_of_date: false }] });
  open("?step=downloads");
  const zip = await screen.findByRole("link", { name: "Download every clip (.zip)" });
  expect(zip).toHaveAttribute("href", "/api/projects/9/clips.zip");
  expect(zip.className).not.toContain("bg-accent ");
  expect(screen.getByRole("link", { name: "Download MP4" }).className).toContain("bg-accent ");
  expect(screen.getByRole("heading", { name: "Final cut" })).toBeInTheDocument(); // S3-09; each clip's takes download on Clips
});

test("after a breakdown edit, the finished video stays downloadable and Clips stays open, each saying out of date (#749 LW1)", async () => {
  setViewport(390);
  const edited = { ...toClips, "GET /projects/9/storyboard": [200, [{ ...frame, approved: false, stale: true }]] as [number, unknown], "GET /projects/9/clips": [200, [{ ...done, approved: false, stale: true }]] as [number, unknown], "GET /projects/9/video": [200, { file_id: 60, take_ids: [2], out_of_date: true }] as [number, unknown] };
  fakeServer(edited);
  open("?step=downloads");
  expect(await screen.findByRole("link", { name: "Download MP4" })).toHaveAttribute("href", expect.stringContaining("/files/60"));
  expect(screen.getByText("Out of date.")).toBeInTheDocument();
});

test("Flow-QA M2: a clip's new take, not approved by anyone, never stops Make it again (V6 has no per-clip Approve); a clip with no take does", async () => {
  setViewport(390);
  const routes = { ...toClips, "GET /projects/9/storyboard": [200, [{ ...frame, approved: false, stale: true }]] as [number, unknown], "GET /projects/9/video": [200, { file_id: 60, take_ids: [1], out_of_date: true }] as [number, unknown] };
  fakeServer({ ...routes, "GET /projects/9/clips": [200, [{ ...done, approved: false }]] });
  const first = renderApp("/b/1/videos/9?step=downloads");
  expect(await screen.findByRole("link", { name: "Download MP4" })).toHaveAttribute("href", expect.stringContaining("/files/60"));
  expect(screen.getByText("Out of date.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Make it again" })).toBeEnabled();
  first.unmount();
  // Once its cut has that take, the cut is current: unapproved never reads Out of date for good (QA on #1379).
  fakeServer({ ...routes, "GET /projects/9/clips": [200, [{ ...done, approved: false }]], "GET /projects/9/video": [200, { file_id: 61, take_ids: [2], out_of_date: false }] });
  const cut = renderApp("/b/1/videos/9?step=downloads");
  expect(await screen.findByRole("link", { name: "Download MP4" })).toHaveAttribute("href", expect.stringContaining("/files/61"));
  expect(screen.queryByText("Out of date.")).toBeNull();
  cut.unmount();
  fakeServer({ ...routes, "GET /projects/9/clips": [200, [{ ...done, approved: false, picked_take_id: null }]] });
  open("?step=downloads");
  expect(await screen.findByRole("button", { name: "Make it again" })).toHaveAccessibleDescription("Make every clip’s take first (1 left)");
});

test("the Cut tab watches the cut, and Edit opens the cut editor (screen 10)", async () => {
  setViewport(1440);
  fakeServer({ ...toClips, "GET /projects/9/clips": [200, [done]], "GET /projects/9/video": [200, { number: 2, file_id: 90, take_ids: [2], out_of_date: false }], "GET /projects/9/cut": [200, cutOut()] });
  open("?step=downloads");
  expect(await screen.findByRole("radio", { name: "Watch" })).toBeChecked();
  expect(screen.getByLabelText("The cut")).toBeInTheDocument();
  const chat = screen.getByRole("region", { name: "Chat" });
  expect(chat.className).toContain("w-[min(600px,50%)]");
  await userEvent.click(screen.getByRole("radio", { name: "Edit" }));
  expect(await screen.findByLabelText("Cut editor")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Cut 2" })).toBeInTheDocument();
  expect(chat.className).toContain("w-[400px]"); // the editor gets the boards' 792px panel (S7)
  await userEvent.click(screen.getByRole("radio", { name: "Watch" }));
  expect(chat.className).toContain("w-[min(600px,50%)]");
});

test("the Cut tab puts the clips together by itself the first time, for free", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...toClips, "GET /projects/9/clips": [200, [done]], "GET /projects/9/cut": [200, cutOut({ number: null, file_id: null, versions: [] })], "POST /projects/9/cut": [202, cutOut({ number: null, file_id: null, making: { number: 1, percent: 0, doing: "putting the clips together", about_seconds: 10, changes: 0 } })] });
  open("?step=downloads");
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /projects/9/cut")).toHaveLength(1));
});

test("someone who only looks at the video never starts its first cut", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...toClips, "GET /projects/9": [200, { ...project, created_by_id: 99, created_by_name: "Maya" }], "GET /projects/9/clips": [200, [done]], "GET /projects/9/cut": [200, cutOut({ number: null, file_id: null, versions: [], can_edit: true })] }); // only that it's someone else's video stops it
  open("?step=downloads");
  expect(await screen.findByLabelText("Cut editor")).toBeInTheDocument();
  await new Promise((r) => setTimeout(r, 300));
  expect(calls.filter((c) => c.key === "POST /projects/9/cut")).toHaveLength(0);
});

test("a video made from a library version opens on the new page", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9": [200, { ...project, script_draft_id: 4 }], "GET /projects/9/assets": [200, []] });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/b/1/projects/9?step=breakdown"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(await screen.findByRole("tab", { name: "Plan", selected: true })).toBeInTheDocument();
  expect(screen.getByRole("tablist", { name: "Preview" })).toHaveTextContent("Cut");
});

test("on a phone the cut plays full width with Download MP4 under it (P-05)", async () => {
  setViewport(390);
  fakeServer({ ...toClips, "GET /projects/9/clips": [200, [done]], "GET /projects/9/video": [200, { file_id: 60, take_ids: [2], out_of_date: false }] });
  open("?step=downloads");
  expect(await screen.findByRole("tab", { name: "Preview", selected: true })).toBeInTheDocument();
  expect(await screen.findByRole("link", { name: "Download MP4" })).toHaveAttribute("href", expect.stringContaining("/files/60"));
});


const own = (o: object = {}) => asset({ ref: "slot:3", slot_id: 3, library_item_id: 12, own_look_id: 12, only_here: "video", role: "Coach", name: "Coach", sheet_status: "needs_approval", ...o });

test("an approved look that contradicts the role's words: Update to match saves to this video's look, the owner can put the script right too, each with Undo", async () => {
  setViewport(390);
  const fit = { seen: "The approved look is a French bulldog.", name: "Biscuit, the French bulldog", description: "A stocky French bulldog, the narrator", notes: "A golden retriever, the narrator", update_look: true, update_script: true, note: "" };
  const calls = fakeServer({
    ...base,
    "GET /projects/9/assets": [200, [own({ role: "Biscuit, the golden retriever", description: "A golden retriever, the narrator", sheet_status: "approved", ready: true, sheet_file_id: 71, text_fit: fit })]],
    "GET /library/character/12": [200, item({ id: 12, name: "Biscuit", sheet_status: "approved" })],
    "PATCH /projects/9/assets/slots/3": [200, []],
  });
  open();
  const note = await screen.findByRole("note", { name: "Role words for Biscuit, the golden retriever" });
  expect(within(note).getByText("The approved look is a French bulldog.")).toBeInTheDocument();
  const box = within(note).getByLabelText("How this video describes them");
  expect(box).toHaveValue("A stocky French bulldog, the narrator");
  await userEvent.type(box, " who loves salmon");
  await userEvent.click(within(note).getByRole("button", { name: "Update to match" }));
  const patches = () => calls.filter((c) => c.key === "PATCH /projects/9/assets/slots/3").map((c) => c.body);
  await vi.waitFor(() => expect(patches()).toEqual([{ notes: "A stocky French bulldog, the narrator who loves salmon" }]));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(patches().at(-1)).toEqual({ notes: "A golden retriever, the narrator" }));
  await userEvent.click(within(note).getByRole("button", { name: "Update the script's role too" }));
  await vi.waitFor(() => expect(patches().at(-1)).toEqual({ role: "Biscuit, the French bulldog", description: "A stocky French bulldog, the narrator" }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(patches().at(-1)).toEqual({ role: "Biscuit, the golden retriever", description: "A golden retriever, the narrator" }));
});

test("Downloads agrees with the lists: a take from an older look marks the finished video Out of date, and Make it again waits for a new take or Keep anyway (N6)", async () => {
  setViewport(390);
  fakeServer({ ...toClips, "GET /projects/9/clips": [200, [{ ...done, take_stale: true }]], "GET /projects/9/video": [200, { file_id: 60, take_ids: [2], out_of_date: false }] });
  open("?step=downloads");
  expect(await screen.findByRole("link", { name: "Download MP4" })).toHaveAttribute("href", expect.stringContaining("/files/60"));
  expect(screen.getByText("Out of date.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Make it again" })).toHaveAccessibleDescription("Make another take on Clips, or keep the older look (1 left)");
  expect(screen.getByText("A clip's take shows an older look from Cast & places. This MP4 still downloads.")).toBeInTheDocument(); // never "free" beside a button that waits
  expect(screen.queryByText(/Clips changed since/)).toBeNull();
});


test("a storyboard made before the shots changed stays open, and its stills wait for new shots in Plan", async () => {
  setViewport(1440);
  fakeServer({ ...toClips, "GET /projects/9/breakdown": [200, { ...breakdown, stale: true }], "GET /projects/9/storyboard": [200, [{ ...frame, approved: false, earlier: [], change: null }, { ...frame, id: 2, clip_id: "c2", approved: false, file_id: null, still_credits: 4, earlier: [], change: null }]] });
  open("?step=storyboard");
  expect(await screen.findByText("The plan changed after these were made. The director makes new shots from it first.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Open Plan" })).toBeInTheDocument();
});




test("with nothing made yet and a look not ready, Clips says why and opens Cast in one press", async () => {
  setViewport(1440);
  fakeServer({ ...toClips, "GET /projects/9/storyboard": [200, []], "GET /projects/9/assets": [200, [asset({})]] });
  open("?step=storyboard");
  await userEvent.click(await screen.findByRole("button", { name: "Open Cast" }));
  expect(await screen.findByLabelText("Bo")).toBeInTheDocument();
});

test("Clips names Plan, where the shots live, when problems in them are in the way", async () => {
  setViewport(1440);
  fakeServer({ ...toClips, "GET /projects/9/storyboard": [200, []], "GET /projects/9/breakdown": [200, { ...breakdown, problems: ["c1: the shot has no action", "c2: the shot has no setting"] }] });
  open("?step=clips");
  expect(await screen.findByText("Fix the 2 problems in Plan first.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Open Plan" })).toBeInTheDocument();
});


test("on the video page too, a shot with no script lines shows no Show line button and does not break Breakdown", async () => {
  setViewport(1440);
  const wordless = { ...breakdown, breakdown: { ...breakdown.breakdown, scenes: [{ id: 1, heading: "KITCHEN", look: "", shots: [{ id: "1.1", script_lines: [], speaker: null, line: null, action: "Bo looks up.", reaction: null, camera: "Wide", seconds: 2, character_ids: [], place_id: null, moment: null, screen_ids: [] }] }], clips: [{ id: "c1", shot_ids: ["1.1"], seconds: 2, seam: "end" }] } };
  fakeServer({ ...toClips, "GET /projects/9/breakdown": [200, wordless] });
  open("?step=breakdown");
  const silent = await screen.findByLabelText("Shot 1.1");
  expect(within(silent).queryByRole("button", { name: /in the script$/ })).toBeNull();
});


/** Hold one request until `release` is called, answering with `status`; everything else goes to the fake server. */

test("changing the shape after stills exist asks in the app, says the stills keep their shape, and is free", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...toClips, "GET /projects/9/storyboard": [200, [{ ...frame, earlier: [] }]], "PATCH /projects/9": [200, project] });
  open("?step=plan"); // the shape row is on Plan (Look inside)
  await userEvent.click(await screen.findByRole("button", { name: "1:1" }));
  const ask = screen.getByRole("alertdialog", { name: "Change to 1:1?" });
  expect(ask).toHaveTextContent("The 1 still was drawn for 9:16 and stays that way.");
  await userEvent.click(within(ask).getByRole("button", { name: "Not yet" }));
  expect(calls.some((c) => c.key === "PATCH /projects/9")).toBe(false);
  await userEvent.click(screen.getByRole("button", { name: "1:1" }));
  await userEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Change the shape · free" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /projects/9")?.body).toEqual({ aspect_ratio: "1:1" }));
});

test("old addresses keep working: ?step=breakdown opens Plan, ?step=assets opens Cast", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/assets": [200, []] });
  for (const [from, tab] of [["?step=breakdown", "Plan"], ["?step=assets", "Cast"]]) {
    const { unmount } = render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={[`/b/1/videos/9${from}`]}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByRole("tab", { name: tab, selected: true })).toBeInTheDocument();
    unmount();
  }
});

test("a video not made from a script version has no Director tab: it opens on its steps", async () => {
  setViewport(1440);
  fakeServer(base);
  open("");
  expect(await screen.findByRole("tab", { name: "Plan", selected: true })).toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "Director" })).toBeNull();
});
