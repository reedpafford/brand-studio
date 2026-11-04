import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";
import { editor } from "../test/people";
import { clipCard, pickClip } from "../test/clips";

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
  expect(await screen.findByText("Approve the cast first (1 left)")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Open Cast" }));
  expect(screen.getByRole("tab", { name: "Cast 1", selected: true })).toBeInTheDocument();
});

test("a look that needs approval points to Cast & places and never approves a shared character here", async () => {
  setViewport(1440);
  fakeServer(base);
  open();
  const card = await screen.findByLabelText("Bo");
  expect(within(card).queryByRole("button")).toBeNull();
  expect(within(card).getByRole("link", { name: "Make its look in Cast & places" })).toHaveAttribute("href", expect.stringMatching(/^\/b\/1\/library\/characters\/5\?back=/));
});

test("a locked role is already approved and has no buttons", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/assets": [200, [asset({ locked: true, sheet_status: "approved", ready: true })]] });
  open();
  const card = await screen.findByLabelText("Bo");
  expect(within(card).getByText("Locked")).toBeInTheDocument();
  expect(within(card).queryByRole("button")).toBeNull();
});

test("a role with no character picks one from the library", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /projects/9/assets": [200, [asset({ ref: "slot:3", library_item_id: null, name: "", role: "Coach", sheet_status: "missing" })]],
    "GET /library/character": [200, [item({ id: 8, name: "Dana", sheet_status: "approved" })]],
    "PUT /projects/9/assets/slots/3": [200, []],
  });
  open();
  await userEvent.selectOptions(await screen.findByLabelText("Use a Cast & places character"), "8");
  await userEvent.click(screen.getByRole("button", { name: "Use this character" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "PUT /projects/9/assets/slots/3")).toBe(true));
});

const frame = { id: 1, clip_id: "c1", shot_id: "1.1", prompt: "p", reference_ids: [], problems: [], kept: [], file_id: 40, approved: true, stale: false, earlier: [], change: null };
const clip = (o: object) => ({ id: 3, clip_id: "c1", seconds: 8, prompt: "Bo sniffs the salmon", references: [], problems: [], kept: [], file_id: null, takes: [], picked_take_id: null, approved: false, stale: false, take_credits: 24, inserts: [], ...o });
const toClips = { ...base, "GET /projects/9/assets": [200, []] as [number, unknown], "GET /projects/9/storyboard": [200, [frame]] as [number, unknown] };

test("?step=make opens Clips: the clip list, and the picked clip's takes with its still under them", async () => {
  setViewport(1440);
  fakeServer({ ...toClips, "GET /projects/9/storyboard": [200, [{ ...frame, earlier: [] }]], "GET /projects/9/clips": [200, [{ ...done }]] });
  open("?step=make");
  expect(await screen.findByRole("tab", { name: "Clips 1", selected: true })).toBeInTheDocument(); // v6: its count on the tab
  expect(screen.queryByRole("heading", { name: "Clips", level: 2 })).toBeNull(); // v5: the list is the heading
  expect(within(screen.getByRole("list", { name: "Clip list" })).getByRole("button", { name: /^Clip 1 · 8 s/ })).toHaveAttribute("aria-current", "true");
  const card = await screen.findByLabelText("Clip c1");
  expect(within(card).getByLabelText("Frame c1")).toBeInTheDocument(); // its still, with the still's own presses
  expect(screen.queryByRole("tab", { name: /Stills/ })).toBeNull(); // no separate Stills | Clips any more
});

test("the picked clip's approved still is a small thumbnail beside its prompt, shown in full, with one note box; the thumbnail opens the still's own presses (QA-11)", async () => {
  setViewport(1440);
  fakeServer({ ...toClips, "GET /projects/9/clips": [200, [done]] });
  open("?step=clips");
  const card = await clipCard("c1");
  expect(within(card).getByLabelText("Prompt for clip c1")).toHaveTextContent("Bo sniffs the salmon"); // the words, not only Edit prompt
  expect(within(card).getByLabelText("Note for the next take c1")).toBeInTheDocument();
  expect(within(card).getAllByRole("textbox")).toHaveLength(1); // no second "Change this…" for the still
  expect(within(card).getByLabelText("Frame c1")).toHaveClass("w-16");
  await userEvent.click(within(card).getByRole("button", { name: "Still for clip c1: approve, redo or change it" }));
  const sheet = screen.getByRole("dialog", { name: "Still for clip 1" });
  expect(within(sheet).getByRole("button", { name: "Undo approve" })).toBeInTheDocument();
  expect(within(sheet).getByRole("button", { name: /Make another/ })).toBeInTheDocument();
  expect(within(sheet).getByLabelText("Change this… still c1")).toBeInTheDocument();
});

test("v5: one press makes the next take, at its exact price; a note typed for the next take makes it the note's, priced up to", async () => {
  setViewport(1440);
  fakeServer({ ...toClips, "GET /projects/9/clips": [200, [clip({ prompt_ok: true, takes: [take(1, 1)], picked_take_id: 1, file_id: 51 })]], "GET /projects/9/clips/3/change": [200, { credits: 27 }] });
  open("?step=clips");
  const card = await clipCard("c1");
  const make = within(card).getByRole("button", { name: "Make another take · 24 credits" });
  expect(make).toHaveTextContent(/^Make · 24 credits$/); // the tile already says Another take
  expect(within(card).queryAllByRole("button", { name: /Change it/ })).toHaveLength(0); // no second press beside the note
  await userEvent.type(within(card).getByLabelText("Note for the next take c1"), "Slower");
  expect(within(card).getByRole("button", { name: "Change it and make a new take · up to 27 credits" })).toHaveTextContent(/^Make · up to 27 credits$/);
});

test("a Review link's ?to= picks its clip once: a press on another clip in the list wins while ?to= stays (QA-11)", async () => {
  setViewport(1440);
  // The takes wait for the stills, so there is no "Clip c2" card to find and ?to= stays in the address for a while.
  fakeServer({ ...toClips, "GET /projects/9/storyboard": [200, [{ ...frame, approved: false }, { ...frame, id: 2, clip_id: "c2", approved: false }]] });
  open("?step=storyboard&to=Clip%20c2");
  const list = await screen.findByRole("list", { name: "Clip list" });
  expect(await within(list).findByRole("button", { name: /^Clip 2(\D|$)/ })).toHaveAttribute("aria-current", "true");
  await userEvent.click(within(list).getByRole("button", { name: /^Clip 1(\D|$)/ }));
  expect(within(list).getByRole("button", { name: /^Clip 1(\D|$)/ })).toHaveAttribute("aria-current", "true");
  expect(await screen.findByLabelText("Frame c1")).toBeInTheDocument();
  expect(screen.queryByLabelText("Frame c2")).toBeNull();
});

test("before the stills are approved, the takes wait and say why; the still is there to approve", async () => {
  setViewport(1440);
  fakeServer({ ...toClips, "GET /projects/9/storyboard": [200, [{ ...frame, earlier: [], approved: false }]] });
  open("?step=clips");
  expect(await screen.findByRole("tab", { name: /^Clips/, selected: true })).toBeInTheDocument();
  expect(await screen.findByLabelText("Frame c1")).toBeInTheDocument();
  expect(screen.getByText("Takes: Approve every still first (1 left)")).toBeInTheDocument(); // stills, as on Make the stills (QA-11)
  expect(screen.queryByLabelText("Clip c1")).toBeNull();
});

test("a clip's prompt is marked Prompt OK on the server, by its own button or by Make clip, which then makes the take", async () => {
  setViewport(390);
  const calls = fakeServer({ ...toClips, "GET /projects/9/clips": [200, [clip({ prompt_ok: false })]], "POST /projects/9/clips/3/prompt-ok": [200, clip({ prompt_ok: true })], "POST /projects/9/clips/3/generate": [201, { id: 21, kind: "video", status: "queued", credits: 24, project_id: 9 }] });
  open("?step=clips");
  expect(await screen.findByText("Bo sniffs the salmon")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Prompt OK for c1" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/clips/3/prompt-ok")).toBe(true));
});

test("Make clip on a prompt not yet marked Prompt OK marks it and makes the take in one press", async () => {
  setViewport(390);
  const calls = fakeServer({ ...toClips, "GET /projects/9/clips": [200, [clip({ prompt_ok: false })]], "POST /projects/9/clips/3/prompt-ok": [200, clip({ prompt_ok: true })], "POST /projects/9/clips/3/generate": [201, { id: 21, kind: "video", status: "queued", credits: 24, project_id: 9 }] });
  open("?step=clips");
  const make = await screen.findByRole("button", { name: /^Make clip/ });
  expect(make).toBeEnabled();
  await userEvent.click(make);
  await vi.waitFor(() => expect(calls.map((c) => c.key)).toEqual(expect.arrayContaining(["POST /projects/9/clips/3/prompt-ok", "POST /projects/9/clips/3/generate"])));
});

test("a Make clip that can't be pressed says why in a plain line under it", async () => {
  setViewport(390);
  fakeServer({ ...toClips, "GET /projects/9/clips": [200, [clip({ prompt_ok: true, problems: [clipProblem] })]] });
  open("?step=clips");
  const make = await screen.findByRole("button", { name: /^Make clip/ });
  expect(make).toBeDisabled();
  expect(make).toHaveAccessibleDescription("Fix the problems above first.");
  expect(screen.getByText("Fix the problems above first.")).toBeVisible();
});

test("a prompt already marked Prompt OK keeps its badge, lets the take be made, and can be undone", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...toClips, "GET /projects/9/clips": [200, [clip({ prompt_ok: true })]], "DELETE /projects/9/clips/3/prompt-ok": [200, clip({ prompt_ok: false })] });
  open("?step=clips");
  expect(await screen.findByText("Prompt OK")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^Make clip/ })).toBeEnabled();
  await userEvent.click(screen.getByRole("button", { name: "Undo Prompt OK for c1" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /projects/9/clips/3/prompt-ok")).toBe(true));
});

test("a prompt shows pictures by name, never [Image1]", async () => {
  setViewport(1440);
  const references = [{ kind: "image", id: "frame:c1", role: "frame:c1" }, { kind: "image", id: "char:5", role: "Bo's look" }, { kind: "image", id: "screen:2", role: "screen:2" }];
  fakeServer({ ...toClips, "GET /projects/9/clips": [200, [clip({ prompt: "[Image1] is the first frame. [Image2] eats. [Image3] shows.", references })]] });
  open("?step=clips");
  const prompt = await screen.findByLabelText("Prompt for clip c1");
  expect(prompt).toHaveTextContent("Storyboard frame is the first frame. Bo's look eats. Picture 3 shows.");
  expect(prompt).not.toHaveTextContent("[Image");
});

test("a role with no character makes a look for this video only in one press, with the price inside the button", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /projects/9/assets": [200, [asset({ ref: "slot:3", slot_id: 3, library_item_id: null, name: "", role: "Coach", sheet_status: "missing" })]],
    "POST /projects/9/assets/slots/3/make-look": [200, []],
  });
  open();
  expect(screen.queryByLabelText("Use a Cast & places character")).toBeNull();
  await userEvent.click(await screen.findByRole("button", { name: "Make a look · 2 credits" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/assets/slots/3/make-look")).toBe(true));
  expect(calls.some((c) => c.key === "POST /library/character")).toBe(false); // never added to Cast & places
});

test("an approved picked character shows no buttons: it is shared with every video", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/assets": [200, [asset({ sheet_status: "approved", ready: true })]], "GET /library/character/5": [200, item({ sheet_status: "approved" })] });
  open();
  const card = await screen.findByLabelText("Bo");
  expect(within(card).getByText("Approved")).toBeInTheDocument();
  expect(within(card).queryByRole("button")).toBeNull();
  expect(within(card).queryByRole("link")).toBeNull();
});

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

test("the server's video still matches its takes, but a clip is unapproved: Downloads says Out of date and the real count (#761 QA-2)", async () => {
  setViewport(390);
  fakeServer({ ...toClips, "GET /projects/9/storyboard": [200, [{ ...frame, approved: false, stale: true }]], "GET /projects/9/clips": [200, [{ ...done, approved: false }]], "GET /projects/9/video": [200, { file_id: 60, take_ids: [2], out_of_date: false }] });
  open("?step=downloads");
  expect(await screen.findByRole("link", { name: "Download MP4" })).toHaveAttribute("href", expect.stringContaining("/files/60"));
  expect(screen.getByText("Out of date.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Make it again" })).toHaveAccessibleDescription("Approve every clip first (1 left)");
});

test("after a breakdown edit, Clips already made stays open (out of date), not sent back to Storyboard", async () => {
  setViewport(390);
  fakeServer({ ...toClips, "GET /projects/9/storyboard": [200, [{ ...frame, approved: false, stale: true }]], "GET /projects/9/clips": [200, [{ ...done, approved: false, stale: true }]], "GET /projects/9/video": [200, { file_id: 60, take_ids: [2], out_of_date: true }] });
  open("?step=clips");
  expect(await screen.findByLabelText("Clip c1")).toBeInTheDocument();
  expect(screen.getByRole("list", { name: "Clip list" })).toBeInTheDocument();
});

test("the Cut tab puts the clips together by itself the first time, for free", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...toClips, "GET /projects/9/clips": [200, [done]], "POST /projects/9/video": [201, { file_id: 60, take_ids: [2], out_of_date: false }] });
  open("?step=downloads");
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /projects/9/video")).toHaveLength(1));
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

test("a filled slot can be swapped for another character", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /projects/9/assets": [200, [asset({ slot_id: 3, description: "A tired coach" })]],
    "GET /library/character": [200, [item({ id: 5, name: "Bo" }), item({ id: 8, name: "Dana", sheet_status: "approved" })]],
    "PUT /projects/9/assets/slots/3": [200, []],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Use a different character" }));
  expect(screen.getByRole("option", { name: "Dana" })).toBeInTheDocument();
  expect(screen.queryByRole("option", { name: /^Bo/ })).toBeNull(); // not the one it already has
  await userEvent.selectOptions(screen.getByLabelText("Use a Cast & places character"), "8");
  await userEvent.click(screen.getByRole("button", { name: "Use this character" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /projects/9/assets/slots/3")?.body).toEqual({ library_item_id: 8 }));
});

test("Assets shows where each one is used, the role's description, and the products and app screens the shots show", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /projects/9/assets": [
      200,
      [
        asset({ slot_id: 3, description: "A tired coach in a grey hoodie", shots: 3 }),
        { kind: "product", ref: "screen:4", role: "", library_item_id: null, name: "Peanut butter bag", locked: false, sheet_status: "approved", ready: true, slot_id: null, description: "", shots: 1, file_id: 90 },
        { kind: "screen", ref: "screen:7", role: "", library_item_id: null, name: "fomo Home", locked: false, sheet_status: "approved", ready: true, slot_id: null, description: "", shots: 2, file_id: 91 },
      ],
    ],
  });
  open();
  const cast = await screen.findByLabelText("Bo");
  expect(within(cast).getByText("A tired coach in a grey hoodie")).toBeInTheDocument();
  expect(within(cast).getByText("In 3 shots")).toBeInTheDocument();
  const products = screen.getByLabelText("Products");
  expect(within(products).getByText("Peanut butter bag")).toBeInTheDocument();
  expect(within(products).getByText("In 1 shot")).toBeInTheDocument();
  const screens = screen.getByLabelText("App screens");
  expect(within(screens).getByText("fomo Home")).toBeInTheDocument();
  expect(within(screens).queryByRole("button")).toBeNull(); // nothing to approve
});

const still = (o: object = {}) => ({ ...frame, approved: false, earlier: [], change: null, ...o });

test("Change this… sits under every still with its price; a note is sent as it is typed and clears once sent", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /projects/9/assets": [200, []],
    "GET /projects/9/storyboard": [200, [still()]],
    "GET /projects/9/storyboard/frames/1/change": [200, { credits: 4 }],
    "POST /projects/9/storyboard/frames/1/change": [201, { id: 8, kind: "image", status: "queued", credits: 4 }],
  });
  open("?step=storyboard");
  const box = await screen.findByLabelText("Change this… still c1");
  expect(screen.getByRole("button", { name: /^Change it/ })).toBeDisabled();
  expect(screen.getByText("Say what should change")).toBeInTheDocument();
  await userEvent.type(box, "Bo should look surprised");
  await userEvent.click(await screen.findByRole("button", { name: "Change it · up to 4 credits" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/storyboard/frames/1/change")?.body).toEqual({ note: "Bo should look surprised" }));
  await vi.waitFor(() => expect(box).toHaveValue(""));
});

test("a note that changes what's said is refused in the server's words, kept in the box, with where to change the words", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /projects/9/assets": [200, []],
    "GET /projects/9/storyboard": [200, [still()]],
    "GET /projects/9/storyboard/frames/1/change": [200, { credits: 4 }],
    "POST /projects/9/storyboard/frames/1/change": [422, { detail: "The note changes what's said. The spoken lines stay exactly as written." }],
  });
  open("?step=storyboard");
  const box = await screen.findByLabelText("Change this… still c1");
  await userEvent.type(box, "Make Bo say hello");
  await userEvent.click(await screen.findByRole("button", { name: "Change it · up to 4 credits" }));
  expect(await screen.findByText(/The note changes what's said\. The spoken lines stay exactly as written\. To change the words, edit the script\./)).toBeInTheDocument();
  expect(box).toHaveValue("Make Bo say hello");
});

test("while a change is made the still says so and the box is read-only; when it lands, what the note changed shows with Before and After", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /projects/9/assets": [200, []],
    "GET /projects/9/storyboard": [200, [still({ change: { note: "surprised", status: "changing" } })]],
    "GET /projects/9/storyboard/frames/1/change": [200, { credits: 4 }],
  });
  open("?step=storyboard");
  expect(await screen.findByText("Making the change…")).toBeInTheDocument();
  expect(screen.getByLabelText("Change this… still c1")).toHaveAttribute("readonly");
  expect(screen.getByRole("button", { name: "Changing…" })).toHaveAttribute("aria-busy", "true");
});

test("what the note changed shows only the changed words, struck and bold, with Before: and After:", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /projects/9/assets": [200, []],
    "GET /projects/9/storyboard": [200, [still({ change: { note: "surprised", status: "done", before: "Bo looks sad and drops his ears at the bowl in the kitchen", after: "Bo looks surprised with ears up at the bowl in the kitchen" } })]],
    "GET /projects/9/storyboard/frames/1/change": [200, { credits: 4 }],
  });
  open("?step=storyboard");
  const changed = await screen.findByLabelText("What your note changed");
  expect(within(changed).getByText("Before:")).toBeInTheDocument();
  expect(within(changed).getByText("After:")).toBeInTheDocument();
  expect(changed.querySelector("del")).toHaveTextContent("sad");
  expect(changed.querySelector("strong")).toHaveTextContent("surprised");
  expect(within(changed).getByRole("button", { name: "Show the whole prompt" })).toBeInTheDocument();
});

test("on the video page, Undo of a redone frame waits for the new still, then picks the earlier one back (#749 LW3, the server's order in #808)", async () => {
  setViewport(390);
  const at = (frame: object) => ({ ...base, "GET /projects/9/assets": [200, []] as [number, unknown], "GET /projects/9/storyboard": [200, [frame]] as [number, unknown], "GET /projects/9/storyboard/frames/1/change": [200, { credits: 4 }] as [number, unknown], "POST /projects/9/storyboard/frames/1/pick": [200, {}] as [number, unknown] });
  const redo = { note: "Redo this frame", job_id: 51, was_file_id: 40, before: "p", after: "p2" };
  // 1. The prompt is being written again.
  fakeServer(at(still({ stale: true, redo_credits: 4, change: { ...redo, status: "changing" } })));
  open("?step=storyboard");
  expect(await screen.findByText("Making the change…")).toBeInTheDocument();
  // 2. Written, its still drawing: still "changing", so no Undo yet.
  fakeServer(at(still({ prompt: "p2", drawing: true, change: { ...redo, status: "changing", made_job_id: 52 } })));
  expect(await screen.findByText("Drawing…", {}, { timeout: 9000 })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Undo" })).toBeNull();
  // 3. The new still lands, the earlier one kept: Undo stays on the card (not only a toast).
  fakeServer(at(still({ prompt: "p2", file_id: 41, earlier: [{ file_id: 40, prompt: "p" }], change: { ...redo, status: "done", made_job_id: 52 } })));
  expect(await screen.findByText("Redone from the new breakdown. The earlier still is kept.", {}, { timeout: 9000 })).toBeInTheDocument();
  // 4. Undo picks the earlier still; once it is back, there is nothing to undo.
  const calls = fakeServer(at(still({ prompt: "p", file_id: 40, earlier: [{ file_id: 41, prompt: "p2" }], change: { ...redo, status: "done", made_job_id: 52 } })));
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/storyboard/frames/1/pick")?.body).toMatchObject({ file_id: 40 }));
  await vi.waitFor(() => expect(screen.queryByText(/Redone from the new breakdown/)).toBeNull());
}, 30000);

test("a redo keeps reading through one stray failed read between its rewrite and its still, and ends with Undo (#803, QA-2's 2 in 12)", async () => {
  setViewport(390);
  const now = new Date().toISOString();
  const at = (frame: object, jobs: object[] = []) => ({ ...base, "GET /projects/9/assets": [200, []] as [number, unknown], "GET /projects/9/storyboard": [200, [frame]] as [number, unknown], "GET /projects/9/storyboard/frames/1/change": [200, { credits: 4 }] as [number, unknown], "GET /jobs": [200, jobs] as [number, unknown], "POST /projects/9/storyboard/frames/1/redo": [201, { id: 51, kind: "write-claude", status: "queued", credits: 4, project_id: 9, created_at: now }] as [number, unknown] });
  const redo = { note: "Redo this frame", job_id: 51, was_file_id: 40, before: "p", after: "p2" };
  fakeServer(at(still({ stale: true, redo_credits: 4 })));
  open("?step=storyboard");
  const press = await screen.findByRole("button", { name: /Redo this frame/ });
  vi.spyOn(window, "confirm").mockReturnValue(true);
  // The server answers the press's read in the gap between the rewrite and its still: "failed", nothing drawing.
  fakeServer(at(still({ prompt: "p2", change: { ...redo, status: "failed", error: "That change didn't finish, so nothing was charged. Try again." } }), [{ id: 51, kind: "write-claude", status: "succeeded", project_id: 9, credits: 4, created_at: now, finished_at: now }]));
  await userEvent.click(press);
  expect(await screen.findByText(/That change didn't finish/)).toBeInTheDocument();
  // The next read has the still on its way, then landed: the page kept reading, so it ends with Undo.
  fakeServer(at(still({ prompt: "p2", drawing: true, change: { ...redo, status: "changing", made_job_id: 52 } })));
  expect(await screen.findByText("Drawing…", {}, { timeout: 9000 })).toBeInTheDocument();
  fakeServer(at(still({ prompt: "p2", file_id: 41, earlier: [{ file_id: 40, prompt: "p" }], change: { ...redo, status: "done", made_job_id: 52 } })));
  expect(await screen.findByText("Redone from the new breakdown. The earlier still is kept.", {}, { timeout: 9000 })).toBeInTheDocument();
  expect(screen.queryByText(/That change didn't finish/)).toBeNull();
}, 30000);

test("a note that left the prompt as it was says so, and nothing is made", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /projects/9/assets": [200, []],
    "GET /projects/9/storyboard": [200, [still({ change: { note: "x", status: "unchanged", unchanged: true } })]],
    "GET /projects/9/storyboard/frames/1/change": [200, { credits: 4 }],
  });
  open("?step=storyboard");
  expect(await screen.findByText("Your note didn't change the prompt. Try saying it another way.")).toBeInTheDocument();
});

test("Undo after a clip change goes back to the take that was picked when Change it was pressed, not just the second-newest", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...toClips,
    "GET /projects/9/clips": [200, []],
    "GET /projects/9/clips/3/change": [200, { credits: 27 }],
    "POST /projects/9/clips/3/change": [201, { id: 8, kind: "clip_take", status: "queued", credits: 27 }],
    "POST /projects/9/clips/3/takes/1/pick": [200, {}],
  });
  const inner = (fetch as unknown as { getMockImplementation: () => (r: Request | string, i?: RequestInit) => Promise<Response> }).getMockImplementation()!;
  let seenChanging = 0;
  let phase = 0; // 0: takes 1 and 2, take 1 picked. 1: changing. 2: take 3 made and picked.
  const t3 = take(3, 3);
  const body = () =>
    phase === 0
      ? clip({ prompt_ok: true, takes: [take(1, 1), take(2, 2)], picked_take_id: 1, file_id: 51 })
      : phase === 1
        ? clip({ prompt_ok: true, takes: [take(1, 1), take(2, 2)], picked_take_id: 1, file_id: 51, change: { note: "Slower", status: "changing" } })
        : clip({ prompt_ok: true, takes: [take(1, 1), take(2, 2), t3], picked_take_id: 3, file_id: 53, change: { note: "Slower", status: "done", before: "a b", after: "a c" } });
  vi.stubGlobal("fetch", vi.fn(async (input: Request | string, init?: RequestInit) => {
    const req = input instanceof Request ? input : new Request(new URL(input, "http://x"), init);
    const path = new URL(req.url).pathname;
    if (req.method === "GET" && path.endsWith("/projects/9/clips")) {
      if (phase === 1 && ++seenChanging > 1) phase = 2; // the first read after the press shows it changing, the poll after that shows it done
      return new Response(JSON.stringify([body()]), { status: 200, headers: { "content-type": "application/json" } });
    }
    if (req.method === "POST" && path.endsWith("/clips/3/change")) phase = 1;
    return inner(req.clone(), init);
  }));
  open("?step=clips");
  await userEvent.type(await screen.findByLabelText("Note for the next take c1"), "Slower");
  await userEvent.click(await screen.findByRole("button", { name: "Change it and make a new take · up to 27 credits" }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }, { timeout: 9000 }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/clips/3/takes/1/pick")).toBe(true));
}, 20000);

test("a take that failed before the prompt was changed no longer reads as failing: a quiet line, and what to press next", async () => {
  setViewport(390);
  fakeServer({
    ...toClips,
    "GET /projects/9/clips": [200, [clip({ prompt_ok: false, change: { note: "Slower", job_id: 31, status: "done", before: "a b", after: "a c" } })]],
    "GET /projects/9/clips/3/change": [200, { credits: 3 }],
    "GET /jobs": [200, [{ id: 30, kind: "video", step: "clip_take", status: "failed", error: "The service couldn't finish this. Try again.", credits: 19, project_id: 9, project_clip_id: 3, created_at: "2026-10-28T10:00:00Z" }]],
  });
  open("?step=clips");
  const card = await screen.findByLabelText("Clip c1");
  expect(await within(card).findByText("The last take, before your change, failed.")).toBeInTheDocument();
  expect(within(card).queryByText(/couldn't finish this/)).toBeNull();
  expect(within(card).queryByText("Failed · credits returned")).toBeNull();
  expect(within(card).getByText(/Prompt updated\. Read it, then press Make clip/)).toBeInTheDocument();
  await userEvent.type(within(card).getByLabelText("Note for the next take c1"), "Slower"); // a note makes the tile's press the note's
  expect(within(card).getByRole("button", { name: "Change the prompt · up to 3 credits" })).toBeInTheDocument(); // no take yet: only the prompt
});

test("after Reword it to pass (a free fix in code), the refused take reads as before the change", async () => {
  setViewport(390);
  fakeServer({
    ...toClips,
    "GET /projects/9/clips": [200, [clip({ prompt_ok: false, change: { note: "Fix this clip's prompt", job_id: 30, status: "done", before: "a b", after: "a c", unchanged: false } })]],
    "GET /projects/9/clips/3/change": [200, { credits: 3 }],
    "GET /jobs": [200, [{ id: 30, kind: "video", step: "clip_take", status: "failed", error: "The video model refused this prompt. Change the wording, then make it again.", credits: 19, project_id: 9, project_clip_id: 3, created_at: "2026-10-28T10:00:00Z" }]],
  });
  open("?step=clips");
  const card = await screen.findByLabelText("Clip c1");
  expect(await within(card).findByText("The last take, before your change, failed.")).toBeInTheDocument();
  expect(within(card).queryByText(/Change the wording, then make it again/)).toBeNull();
  expect(within(card).queryByText("Failed · credits returned")).toBeNull();
});

test("when the newest take failed but an earlier take is picked, the clip stays Ready with a quiet line, not Failed (#749 G7)", async () => {
  setViewport(390);
  fakeServer({
    ...toClips,
    "GET /projects/9/clips": [200, [clip({ prompt_ok: true, takes: [take(1, 1)], picked_take_id: 1, file_id: 51 })]],
    "GET /projects/9/clips/3/change": [200, { credits: 22 }],
    "GET /jobs": [200, [{ id: 30, kind: "video", step: "clip_take", status: "failed", error: "The service couldn't finish this. Try again.", credits: 19, project_id: 9, project_clip_id: 3, created_at: "2026-10-28T10:00:00Z" }]],
  });
  open("?step=clips");
  const card = await screen.findByLabelText("Clip c1");
  const line = await within(card).findByText(/The newest take didn't work; Take 1 is still picked\./);
  expect(line.closest("p")).toHaveClass("text-muted");
  expect(within(card).queryByText("Didn't finish")).toBeNull();
  expect(within(card).getByRole("button", { name: "Make another take · 24 credits" })).toBeEnabled(); // tried again at its exact price: no dead end
  await userEvent.type(within(card).getByLabelText("Note for the next take c1"), "Slower");
  expect(within(card).getByRole("button", { name: "Change it and make a new take · up to 22 credits" })).toBeEnabled();
});

test("when the newest take failed and no take is picked, the clip still reads Failed and points to the other takes", async () => {
  setViewport(1440);
  fakeServer({
    ...toClips,
    "GET /projects/9/clips": [200, [clip({ prompt_ok: true, takes: [take(1, 1)], picked_take_id: null })]],
    "GET /projects/9/clips/3/change": [200, { credits: 22 }],
    "GET /jobs": [200, [{ id: 30, kind: "video", step: "clip_take", status: "failed", error: "The service couldn't finish this. Try again.", credits: 19, project_id: 9, project_clip_id: 3, created_at: "2026-10-28T10:00:00Z" }]],
  });
  open("?step=clips");
  const card = await screen.findByLabelText("Clip c1");
  expect((await within(card).findByText(/The last try didn't finish; your other takes are below\./)).closest("p")).toHaveClass("text-danger");
  expect(within(screen.getByRole("list", { name: "Clip list" })).getByRole("button", { name: /^Clip 1 / })).toHaveTextContent("Didn't finish");
});

test("once a clip has a take, Change it shows the full price (rewrite and take), not the rewrite-only price read before", async () => {
  setViewport(390);
  fakeServer({ ...toClips, "POST /projects/9/clips/3/generate": [201, { id: 21, kind: "video", status: "queued", credits: 19, project_id: 9 }] });
  const inner = (fetch as unknown as { getMockImplementation: () => (r: Request | string, i?: RequestInit) => Promise<Response> }).getMockImplementation()!;
  let made = false; // the clip's first take, once Make clip is pressed
  const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
  vi.stubGlobal("fetch", vi.fn(async (input: Request | string, init?: RequestInit) => {
    const req = input instanceof Request ? input : new Request(new URL(input, "http://x"), init);
    const path = new URL(req.url).pathname;
    if (req.method === "GET" && path.endsWith("/projects/9/clips")) return json([made ? clip({ prompt_ok: true, takes: [take(1, 1)], picked_take_id: 1, file_id: 51 }) : clip({ prompt_ok: true })]);
    if (req.method === "GET" && path.endsWith("/clips/3/change")) return json({ credits: made ? 22 : 3 });
    if (req.method === "GET" && path === "/api/jobs" && made) return json([{ id: 21, kind: "video", step: "clip_take", status: "running", credits: 19, project_id: 9, project_clip_id: 3, created_at: new Date().toISOString() }]); // keeps the clips polled
    if (req.method === "POST" && path.endsWith("/clips/3/generate")) made = true;
    return inner(req.clone(), init);
  }));
  open("?step=clips");
  await userEvent.type(await screen.findByLabelText("Note for the next take c1"), "Slower");
  expect(await screen.findByRole("button", { name: "Change the prompt · up to 3 credits" })).toBeInTheDocument();
  await userEvent.clear(screen.getByLabelText("Note for the next take c1")); // an empty note: the tile makes the take as it is
  await userEvent.click(screen.getByRole("button", { name: /^Make clip/ }));
  await userEvent.type(await screen.findByLabelText("Note for the next take c1"), "Slower");
  expect(await screen.findByRole("button", { name: "Change it and make a new take · up to 22 credits" }, { timeout: 9000 })).toBeInTheDocument();
}, 15000);

test("a clip change that didn't finish says the server's words, keeps the note in the box, and Try again sends it again", async () => {
  setViewport(390);
  const calls = fakeServer({
    ...toClips,
    "GET /projects/9/clips": [200, [clip({ prompt_ok: true, takes: [take(1, 1)], picked_take_id: 1, file_id: 51, change: { note: "Slower, warmer light", job_id: 876, status: "failed", error: "That change didn't finish. Nothing was charged." } })]],
    "GET /projects/9/clips/3/change": [200, { credits: 27 }],
    "POST /projects/9/clips/3/change": [201, { id: 9, kind: "write-claude", status: "queued", credits: 27 }],
  });
  open("?step=clips");
  expect(await screen.findByText("That change didn't finish. Nothing was charged.")).toBeInTheDocument();
  expect(screen.getByLabelText("Note for the next take c1")).toHaveValue("Slower, warmer light");
  expect(screen.queryByText(/Ask the owner/)).toBeNull();
  await userEvent.click(await screen.findByRole("button", { name: "Try again · up to 27 credits" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/clips/3/change")?.body).toEqual({ note: "Slower, warmer light" }));
});

test("Changing… stops when its rewrite job has failed, even while the clip still says changing", async () => {
  setViewport(1440);
  fakeServer({
    ...toClips,
    "GET /projects/9/clips": [200, [clip({ prompt_ok: true, takes: [take(1, 1)], picked_take_id: 1, file_id: 51, change: { note: "Slower", job_id: 876, status: "changing" } })]],
    "GET /projects/9/clips/3/change": [200, { credits: 27 }],
    "GET /jobs/876": [200, { id: 876, kind: "write-claude", project_id: 9, credits: 6, status: "failed", output: null, error: "Failed", created_at: "2026-10-28T10:00:00Z", finished_at: "2026-10-28T10:01:00Z" }],
  });
  open("?step=clips");
  expect(await screen.findByText("That change didn't finish.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Changing…" })).toBeNull();
  expect(screen.getByLabelText("Note for the next take c1")).not.toHaveAttribute("readonly");
  expect(screen.getByRole("button", { name: "Try again · up to 27 credits" })).toBeEnabled();
});

const own = (o: object = {}) => asset({ ref: "slot:3", slot_id: 3, library_item_id: 12, own_look_id: 12, only_here: "video", role: "Coach", name: "Coach", sheet_status: "needs_approval", ...o });

test("a look for this video only says so, is approved here with Undo, and is redrawn from a plain note at its price", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /projects/9/assets": [200, [own()]],
    "GET /library/character/12": [200, item({ id: 12, name: "Coach" })],
    "POST /library/character/12/sheet/approve": [200, {}],
    "DELETE /library/character/12/sheet/approve": [204, null],
    "POST /library/character/12/sheet": [201, { id: 4, kind: "image", status: "queued", credits: 1.5 }],
  });
  open();
  const card = await screen.findByLabelText("Coach");
  expect(within(card).getByText("This video only")).toBeInTheDocument();
  expect(within(card).queryByRole("link")).toBeNull(); // no trip to Cast & places
  expect(within(card).getByRole("button", { name: /Change it/ })).toBeDisabled();
  expect(within(card).getByText("Say what should change")).toBeInTheDocument();
  await userEvent.type(within(card).getByLabelText("Change this…"), "Warmer light");
  await userEvent.click(within(card).getByRole("button", { name: "Change it · 2 credits" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /library/character/12/sheet")?.body).toEqual({ model_id: "nano-banana-pro", change: "Warmer light" }));
  await userEvent.click(within(card).getByRole("button", { name: "Approve" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /library/character/12/sheet/approve")).toBe(true));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /library/character/12/sheet/approve")).toBe(true));
});

test("a made but unapproved look for this video shows its sheet with Needs your approval and Approve", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/assets": [200, [own({ sheet_file_id: 71 })]], "GET /library/character/12": [200, item({ id: 12, name: "Coach", sheet_file_id: null, sheet_status: "drawing" })] });
  open();
  const card = await screen.findByLabelText("Coach");
  // The picture follows the asset row, never an older copy of the look (Reed's Iron Paws card).
  expect(within(card).getByRole("img", { name: "Look of Coach" })).toHaveAttribute("src", expect.stringContaining("71"));
  expect(within(card).queryByText("No look yet")).toBeNull();
  expect(within(card).getByText("Needs your approval")).toBeInTheDocument();
  expect(within(card).getByRole("button", { name: "Approve" })).toBeInTheDocument();
});

test("a look still being made says Making the look…, with no approval badge and no Approve", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/assets": [200, [own({ sheet_status: "drawing", sheet_file_id: null })]], "GET /library/character/12": [200, item({ id: 12, name: "Coach", sheet_file_id: null, sheet_status: "drawing" })] });
  open();
  const card = await screen.findByLabelText("Coach");
  expect(within(card).getByText("Making the look…")).toBeInTheDocument();
  expect(within(card).queryByText("Needs your approval")).toBeNull();
  expect(within(card).queryByText("No look yet")).toBeNull();
  expect(within(card).queryByRole("button", { name: "Approve" })).toBeNull();
});

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

test("someone who can't change the script's role sees why in plain words, with no button for it", async () => {
  setViewport(1440);
  const fit = { seen: "The approved look is a French bulldog.", name: "", description: "A stocky French bulldog", notes: "", update_look: false, update_script: false, note: "The script's role still describes the earlier look; this video follows the look." };
  fakeServer({
    ...base,
    "GET /projects/9/assets": [200, [own({ role: "Biscuit", sheet_status: "approved", ready: true, sheet_file_id: 71, text_fit: fit })]],
    "GET /library/character/12": [200, item({ id: 12, name: "Biscuit", sheet_status: "approved" })],
  });
  open();
  const note = await screen.findByRole("note", { name: "Role words for Biscuit" });
  expect(within(note).getByText(/this video follows the look/)).toBeInTheDocument();
  expect(within(note).queryByRole("button")).toBeNull();
});

test("a look approved before the words were checked offers the check at its price", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /projects/9/assets": [200, [own({ role: "Biscuit", sheet_status: "approved", ready: true, sheet_file_id: 71, text_check_credits: 1 })]],
    "GET /library/character/12": [200, item({ id: 12, name: "Biscuit", sheet_status: "approved" })],
    "POST /projects/9/assets/slots/3/check-text": [200, []],
  });
  open();
  const card = await screen.findByLabelText("Biscuit");
  expect(within(card).queryByRole("note", { name: /Role words/ })).toBeNull();
  await userEvent.click(within(card).getByRole("button", { name: /^Check the words against the look · up to 1 credit/ }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/assets/slots/3/check-text")).toBe(true));
});

test("when the role has gone back to a Cast & places character, the video's own look is kept and offered again", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /projects/9/assets": [200, [asset({ ref: "slot:3", slot_id: 3, library_item_id: 5, own_look_id: 12, only_here: "video", role: "Coach", name: "Bo" })]],
    "PUT /projects/9/assets/slots/3": [200, []],
  });
  open();
  const card = await screen.findByLabelText("Coach");
  expect(within(card).getByText(/Not used/)).toBeInTheDocument();
  await userEvent.click(within(card).getByRole("button", { name: "Use its own look again" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /projects/9/assets/slots/3")?.body).toEqual({ library_item_id: 12 }));
});

test("Delete this look removes a kept own look from its menu, and Undo brings it back", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /projects/9/assets": [200, [asset({ ref: "slot:3", slot_id: 3, library_item_id: 5, own_look_id: 12, only_here: "video", role: "Coach", name: "Bo" })]],
    "DELETE /library/character/12": [204, null],
    "POST /library/character/12/unarchive": [200, {}],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "More for Coach" }));
  await userEvent.click(await screen.findByRole("menuitem", { name: "Delete this look" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /library/character/12")).toBe(true));
  expect(await screen.findByText("Deleted Coach's look.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /library/character/12/unarchive")).toBe(true));
});

test("a look a role still uses has no Delete this look: it is offered only once the role is swapped (Not used)", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/assets": [200, [own()]], "GET /library/character/12": [200, item({ id: 12, name: "Coach" })] });
  open();
  const card = await screen.findByLabelText("Coach");
  expect(within(card).getByText("This video only")).toBeInTheDocument();
  // Its only menu item is the disabled Merge into… (it is the video's one role); no Delete this look.
  await userEvent.click(within(card).getByRole("button", { name: /^More for/ }));
  expect(screen.queryByRole("menuitem", { name: "Delete this look" })).toBeNull();
});

test("a Cast & places character has no Delete this look", async () => {
  setViewport(1440);
  fakeServer(base);
  open();
  const card = await screen.findByLabelText("Bo");
  expect(within(card).queryByRole("button", { name: /^More for/ })).toBeNull();
});

test("a problem line never shows a raw id: the character's name stands in, the clip says Clip c1, and a missing look links to Assets", async () => {
  setViewport(1440);
  fakeServer({
    ...toClips,
    "GET /library/character": [200, [{ id: 5, name: "Bo", image_file_ids: [], brand_ids: [1] }]],
    "GET /projects/9/clips": [200, [clip({ prompt_ok: true, problems: ["c1: char:5 is in the clip but its sheet isn't attached", "Advice: c1: the Keep line doesn't name char:5; give their look"] })]],
  });
  open("?step=clips");
  const list = await screen.findByLabelText("Problems for c1");
  expect(list).toHaveTextContent("Clip c1: Bo is in the clip but its sheet isn't attached");
  expect(list).not.toHaveTextContent(/char:|slot:/);
  expect(within(list).getByRole("link", { name: "Approve a look in Cast" })).toHaveAttribute("href", "/b/1/videos/9?step=cast");
  const advice = screen.getByLabelText("Advice for c1");
  expect(advice).not.toHaveTextContent(/char:/);
  await userEvent.click(within(advice).getByText(/Advice \(/)); // open it
  const keepLabels = within(advice).getAllByRole("button").map((b) => b.getAttribute("aria-label") ?? "");
  expect(keepLabels.some((l) => l.startsWith("Keep anyway: "))).toBe(true);
  expect(keepLabels.join(" ")).not.toMatch(/char:|slot:/); // the screen reader hears names too
});

test("a take made from an older Cast & places look says Out of date, stays approved, and offers Make another take or Keep anyway (N6)", async () => {
  setViewport(390);
  const older = "Advice: Its take was made from an older look of Bo. Make another take to show it.";
  const calls = fakeServer({
    ...toClips,
    "GET /projects/9/clips": [200, [clip({ prompt_ok: true, approved: true, take_stale: true, takes: [take(1, 1)], picked_take_id: 1, file_id: 51, problems: [older] })]],
    "POST /projects/9/clips/3/keep": [200, {}],
  });
  open("?step=clips");
  const card = await screen.findByLabelText("Clip c1");
  expect(within(card).getByText("Out of date")).toBeInTheDocument();
  expect(within(card).getByRole("button", { name: "Undo approval" })).toBeInTheDocument(); // a sheet edit never unapproves
  expect(within(card).getByRole("button", { name: /^Make another take/ })).toBeEnabled();
  const advice = within(card).getByLabelText("Advice for c1");
  await userEvent.click(within(advice).getByText(/Advice \(/));
  expect(advice).toHaveTextContent("Its take was made from an older look of Bo");
  await userEvent.click(within(advice).getAllByRole("button").find((b) => (b.getAttribute("aria-label") ?? "").startsWith("Keep anyway: "))!);
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/clips/3/keep")?.body).toMatchObject({ problem: older }));
});

test("Downloads agrees with the lists: a take from an older look marks the finished video Out of date, and Make it again waits for a new take or Keep anyway (N6)", async () => {
  setViewport(390);
  fakeServer({ ...toClips, "GET /projects/9/clips": [200, [{ ...done, take_stale: true }]], "GET /projects/9/video": [200, { file_id: 60, take_ids: [2], out_of_date: false }] });
  open("?step=downloads");
  expect(await screen.findByRole("link", { name: "Download MP4" })).toHaveAttribute("href", expect.stringContaining("/files/60"));
  expect(screen.getByText("Out of date.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Make it again" })).toHaveAccessibleDescription("Make another take on Clips, or keep the older look (1 left)");
  expect(screen.getByText("A clip's take shows an older look from Cast & places. This MP4 still downloads. Making it again is free.")).toBeInTheDocument();
  expect(screen.queryByText(/Clips changed since/)).toBeNull();
});

test("a take from the current look shows no Out of date", async () => {
  setViewport(390);
  fakeServer({ ...toClips, "GET /projects/9/clips": [200, [clip({ prompt_ok: true, approved: true, take_stale: false, takes: [take(1, 1)], picked_take_id: 1, file_id: 51 })]] });
  open("?step=clips");
  const card = await screen.findByLabelText("Clip c1");
  expect(within(card).queryByText("Out of date")).toBeNull();
});

test("a frame's problem reads as a name too", async () => {
  setViewport(1440);
  fakeServer({
    ...toClips,
    "GET /library/character": [200, [{ id: 5, name: "Bo", image_file_ids: [], brand_ids: [1] }]],
    "GET /projects/9/storyboard": [200, [{ ...frame, approved: false, earlier: [], change: null, file_id: null, problems: ["c1: char:5 has no approved sheet"] }]],
  });
  open("?step=storyboard");
  const list = await screen.findByLabelText("Problems for c1");
  await vi.waitFor(() => expect(list).toHaveTextContent("Clip c1: Bo has no approved sheet"));
  expect(list).not.toHaveTextContent(/char:/);
});

test("an Assets role card leads with the role's facts, a guess marked", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/assets": [200, [asset({ ref: "slot:3", slot_id: 3, library_item_id: null, name: "", role: "Coach", description: "A tired coach.", sheet_status: "missing", facts: { age_range: { value: "Mid-40s", inferred: true }, gender: { value: "woman", inferred: false }, occupation: { value: "primary-school teacher", inferred: false } } })]],
    "GET /projects/9/assets/missing-looks": [200, { slot_ids: [], roles: [], credits: 0, reason: null }],
  });
  open();
  const card = await screen.findByLabelText("Coach");
  expect(within(card).getByText((_, el) => el?.tagName === "P" && el.textContent === "Mid-40s (a guess) · woman · primary-school teacher")).toBeInTheDocument();
});

const missing = (o: object = {}) => ({ slot_ids: [3, 4], roles: ["Nate", "Mia"], credits: 8.4, usual_credits: 4, reason: null, ...o });

test("missing looks: the price first with a countdown and Not now; Not now is recorded on the server and nothing is made", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /projects/9/assets/missing-looks": [200, missing()],
    "POST /projects/9/assets/missing-looks/decline": [204, null],
    "POST /projects/9/assets/make-missing": [200, []],
  });
  open();
  expect(await screen.findByText("Making looks for Nate and Mia · up to 9 credits (usually 4)")).toBeInTheDocument();
  expect(screen.getByText(/Starting in \d s/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Not now" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/assets/missing-looks/decline")).toBe(true));
  expect(screen.queryByText(/Making looks for/)).toBeNull();
  await new Promise((r) => setTimeout(r, 1500));
  expect(calls.some((c) => c.key === "POST /projects/9/assets/make-missing")).toBe(false);
});

test("missing looks that fit are made after the countdown, and the note then says what was made", async () => {
  setViewport(1440);
  const routes: Record<string, [number, unknown]> = { ...base, "POST /projects/9/assets/make-missing": [200, []] };
  // Before the press the server lists the missing roles; afterwards it says what was really made and spent.
  Object.defineProperty(routes, "GET /projects/9/assets/missing-looks", {
    enumerable: true,
    get: () => [200, calls.some((c) => c.key === "POST /projects/9/assets/make-missing") ? missing({ slot_ids: [], roles: [], made: { looks: 3, credits_used: 7, drawing: false } }) : missing()],
  });
  const calls = fakeServer(routes);
  open();
  await screen.findByText(/Starting in \d s/);
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/assets/make-missing")).toBe(true), { timeout: 9000 });
  expect(await screen.findByText("Made 3 looks · 7 credits. Check each one, then approve.")).toBeInTheDocument();
  expect(calls.filter((c) => c.key === "POST /projects/9/assets/make-missing")).toHaveLength(1); // once
}, 20000);

test("missing looks that don't fit are not made: the server's reason shows and there is no countdown", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /projects/9/assets/missing-looks": [200, missing({ reason: "Making a look (8 credits) would go over this video's budget." })] });
  open();
  expect(await screen.findByText("Making a look (8 credits) would go over this video's budget.")).toBeInTheDocument();
  expect(screen.queryByText(/Starting in/)).toBeNull();
  expect(screen.queryByRole("button", { name: "Not now" })).toBeNull();
  expect(calls.some((c) => c.key === "POST /projects/9/assets/make-missing")).toBe(false);
});

test("a refused start shows the server's reason", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/assets/missing-looks": [200, missing({ slot_ids: [3], roles: ["Nate"] })], "POST /projects/9/assets/make-missing": [409, { detail: "Making a look (8 credits) would go over this video's budget." }] });
  open();
  expect(await screen.findByText("Making a look (8 credits) would go over this video's budget.", {}, { timeout: 9000 })).toBeInTheDocument();
}, 20000);

test("Make a look shows the most it can cost, with the usual price under it, and the limit is checked against the most", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /projects/9/assets": [200, [asset({ ref: "slot:3", slot_id: 3, library_item_id: null, name: "", role: "Coach", sheet_status: "missing", look_credits: 3.6, look_usual_credits: 2 })]],
    "GET /projects/9/assets/missing-looks": [200, { slot_ids: [], roles: [], credits: 0, reason: null }],
  });
  open();
  await vi.waitFor(() => expect(screen.getByRole("button", { name: "Make a look · up to 4 credits" })).toBeInTheDocument());
  expect(screen.getByText("Usually 2. Anything not used comes back.")).toBeInTheDocument();
});

test("Change it on a look's sheet shows up to N credits with the usual price under it", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /projects/9/assets": [200, [own()]],
    "GET /library/character/12": [200, item({ id: 12, name: "Coach", change_credits: 5, sheet_credits: 4, sheet_usual_credits: 2 })],
    "GET /projects/9/assets/missing-looks": [200, { slot_ids: [], roles: [], credits: 0, reason: null }],
  });
  open();
  const card = await screen.findByLabelText("Coach");
  await userEvent.type(within(card).getByLabelText("Change this…"), "Warmer");
  expect(await within(card).findByRole("button", { name: "Change it · up to 5 credits" })).toBeEnabled();
  expect(within(card).getByText("Usually 2. Anything not used comes back.")).toBeInTheDocument();
});

test("a look that reads wrong says what it reads as; Fix it with a note puts the problem in the Change this… box, ready to send", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /projects/9/assets": [200, [own({ look_fit: { seen: "a teenage boy in a hoodie", problem: "Coach should be a woman in her 40s" }, look_credits: 4, look_usual_credits: 2 })]],
    "GET /library/character/12": [200, item({ id: 12, name: "Coach", change_credits: 4, sheet_usual_credits: 2 })],
    "GET /projects/9/assets/missing-looks": [200, { slot_ids: [], roles: [], credits: 0, usual_credits: 0, reason: null }],
    "POST /library/character/12/sheet": [201, { id: 4, kind: "image", status: "queued", credits: 4 }],
  });
  open();
  const card = await screen.findByLabelText("Coach");
  expect(within(card).getByText("This look reads as a teenage boy in a hoodie, but Coach should be a woman in her 40s.")).toBeInTheDocument();
  await userEvent.click(within(card).getByRole("button", { name: "Fix it with a note" }));
  expect(within(card).getByLabelText("Change this…")).toHaveValue("Coach should be a woman in her 40s");
  await userEvent.click(await within(card).findByRole("button", { name: /^Change it · up to 4 credits/ }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /library/character/12/sheet")?.body).toEqual({ model_id: "nano-banana-pro", change: "Coach should be a woman in her 40s" }));
});

test("while the made looks are still being drawn the note does not state a cost yet", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/assets/missing-looks": [200, missing({ slot_ids: [], roles: [], made: { looks: 1, credits_used: 2, drawing: true } })] });
  open();
  expect(await screen.findByText("Making 1 look…")).toBeInTheDocument();
  expect(screen.queryByText(/Check each one/)).toBeNull();
});

test("once every look is approved the made note stops asking on later visits", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /projects/9/assets": [200, [asset({ sheet_status: "approved", ready: true })]],
    "GET /projects/9/assets/missing-looks": [200, missing({ slot_ids: [], roles: [], made: { looks: 3, credits_used: 7, drawing: false } })],
  });
  open();
  await screen.findByText("Bo");
  expect(screen.queryByText(/Check each one/)).toBeNull();
});

test("a look with nothing wrong shows no look-check note", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/assets": [200, [own({ look_fit: null })]], "GET /library/character/12": [200, item({ id: 12, name: "Coach" })] });
  open();
  await screen.findByLabelText("Coach");
  expect(screen.queryByText(/This look reads as/)).toBeNull();
});

const waiting = (id: number, o: object = {}) => ({ ...frame, id, clip_id: `c${id}`, approved: false, earlier: [], change: null, ...o });

test("Approve all is not offered when every frame is approved or has no still", async () => {
  setViewport(1440);
  fakeServer({ ...toClips, "GET /projects/9/storyboard": [200, [{ ...frame, earlier: [], change: null }, waiting(2, { file_id: null })]] });
  open("?step=storyboard");
  await pickClip("c2");
  await screen.findByLabelText("Frame c2");
  expect(screen.queryByRole("button", { name: /^Approve (all|\d)/ })).toBeNull();
});

test("clips made before the storyboard went out of date stay open, with a banner (audit M14)", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...toClips, "GET /projects/9/storyboard": [200, [{ ...frame, stale: true, earlier: [], change: null }]], "GET /projects/9/clips": [200, [clip({ prompt_ok: true })]] });
  open("?step=clips");
  expect(await screen.findByText("The plan changed after these were made. Redo the stills first.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^Make the takes/ })).toBeNull(); // v6: the director makes the takes
  expect(screen.getByLabelText("Frame c1")).toBeInTheDocument(); // the still to redo is on the same tab, under the takes
  expect(screen.getByRole("button", { name: /^Redo stills/ })).toBeInTheDocument();
  expect(calls.some((c) => c.key.startsWith("POST /projects/9/clips"))).toBe(false);
});

test("a storyboard made before the shots changed stays open, and its stills wait for new shots in Plan", async () => {
  setViewport(1440);
  fakeServer({ ...toClips, "GET /projects/9/breakdown": [200, { ...breakdown, stale: true }], "GET /projects/9/storyboard": [200, [{ ...frame, approved: false, earlier: [], change: null }, { ...frame, id: 2, clip_id: "c2", approved: false, file_id: null, still_credits: 4, earlier: [], change: null }]] });
  open("?step=storyboard");
  expect(await screen.findByText("The plan changed after these were made. Make new shots in Plan first.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Open Plan" })).toBeInTheDocument();
});


const staleClips = [clip({ id: 3, clip_id: "c1", stale: true, takes: [{ id: 5 }], picked_take_id: 5 }), clip({ id: 4, clip_id: "c2", stale: true })];
const staleRoutes = {
  ...toClips,
  "GET /projects/9/clips": [200, staleClips] as [number, unknown],
  "GET /projects/9/clips/prompts/price": [200, { clip_ids: ["c1", "c2"], credits: 6 }] as [number, unknown],
  "GET /projects/9/clips/prompts/price?clip_id=c1": [200, { clip_ids: ["c1"], credits: 3 }] as [number, unknown],
  "POST /projects/9/clips/prompts": [201, { id: 7, kind: "write-claude", step: "clip_prompts", status: "queued", credits: 6, project_id: 9 }] as [number, unknown],
};

test("a stale clip has its own priced rewrite in place of Change this…", async () => {
  setViewport(1440);
  const calls = fakeServer(staleRoutes);
  open("?step=clips");
  const card = await screen.findByLabelText("Clip c1");
  expect(within(card).queryByLabelText("Note for the next take c1")).toBeNull();
  await userEvent.click(await within(card).findByRole("button", { name: "Rewrite this clip's prompt · up to 3 credits" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/clips/prompts")?.body).toEqual({ clip_id: "c1" }));
});

const noMissing: [number, unknown] = [200, { slot_ids: [], roles: [], credits: 0, usual_credits: 0, reason: null }];

test("Approve all on Assets is not offered for a library character, which is approved in Cast & places", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/assets": [200, [asset({})]], "GET /projects/9/assets/missing-looks": noMissing });
  open();
  await screen.findByLabelText("Bo");
  expect(screen.queryByRole("button", { name: /^Approve (all|\d)/ })).toBeNull();
});

test("a link to a locked step lands on the step that blocks it, not always on Breakdown", async () => {
  setViewport(1440);
  // Breakdown and Assets are done, but the storyboard frames are out of date: Clips is locked, and Storyboard is what blocks it.
  fakeServer({ ...toClips, "GET /projects/9/storyboard": [200, [{ ...frame, stale: true, earlier: [], change: null }]], "GET /projects/9/clips": [200, []] });
  open("?step=clips");
  expect(await screen.findByLabelText("Frame c1")).toBeInTheDocument();
});

test("a storyboard already made stays open while a look in the cast isn't ready, and its paid presses wait for Cast (audit M14)", async () => {
  setViewport(1440);
  fakeServer({ ...toClips, "GET /projects/9/storyboard": [200, [{ ...frame, earlier: [], change: null }]], "GET /projects/9/assets": [200, [asset({})]] });
  open("?step=storyboard");
  expect(await screen.findByLabelText("Frame c1")).toBeInTheDocument(); // not sent to Cast
  expect(screen.getByText("Waiting on the cast")).toBeInTheDocument();
  expect(screen.getAllByText("A look in the cast isn't ready. Make or approve it in Cast first.").length).toBeGreaterThan(0); // the banner, and the reason under the bar's press
  await userEvent.click(screen.getByRole("button", { name: "Open Cast" }));
  expect(await screen.findByLabelText("Bo")).toBeInTheDocument();
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
  expect(await screen.findByText("Fix the 2 problems in Plan first")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Open Plan" })).toBeInTheDocument();
});

const gone = asset({ ref: "slot:3", slot_id: 3, library_item_id: 77, name: "", role: "Nate", sheet_status: "none", library_deleted: true, look_credits: 4, look_usual_credits: 2 });
const deletedRoutes = {
  ...base,
  "GET /projects/9/assets": [200, [gone]] as [number, unknown],
  "GET /library/character/77": [404, { detail: "none" }] as [number, unknown],
  "GET /library/character": [200, [{ id: 5, name: "Bo", sheet_status: "approved", image_file_ids: [], brand_ids: [1] }]] as [number, unknown],
  "GET /projects/9/assets/missing-looks": noMissing,
};

test("a role whose Cast & places character was deleted says so and offers two fixes: Make a look, or Pick another for free", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...deletedRoutes, "POST /projects/9/assets/slots/3/make-look": [200, []] });
  open();
  const card = await screen.findByLabelText("Nate");
  expect(within(card).getByText("Character deleted")).toBeInTheDocument();
  expect(within(card).getByText("The character this role used was deleted from Cast & places.")).toBeInTheDocument();
  expect(within(card).queryByRole("button", { name: "Use a different character" })).toBeNull();
  expect(within(card).getByText("Free")).toBeInTheDocument(); // Pick another costs nothing
  await userEvent.click(within(card).getByRole("button", { name: /^Make a look · up to 4 credits/ }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/assets/slots/3/make-look")).toBe(true));
});

test("Pick another opens the Cast & places picker for the deleted role", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...deletedRoutes, "PUT /projects/9/assets/slots/3": [200, []] });
  open();
  const card = await screen.findByLabelText("Nate");
  expect(within(card).queryByLabelText("Use a Cast & places character")).toBeNull(); // closed until Pick another is pressed
  await userEvent.click(within(card).getByRole("button", { name: "Pick another" }));
  await userEvent.selectOptions(within(card).getByLabelText("Use a Cast & places character"), "5");
  await userEvent.click(within(card).getByRole("button", { name: "Use this character" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "PUT /projects/9/assets/slots/3")).toBe(true));
});

test("when the server clears the deleted character's id (library_item_id null), Pick another still opens the picker only when pressed", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...deletedRoutes, "GET /projects/9/assets": [200, [{ ...gone, library_item_id: null }]], "PUT /projects/9/assets/slots/3": [200, []] });
  open();
  const card = await screen.findByLabelText("Nate");
  expect(within(card).getByText("Character deleted")).toBeInTheDocument();
  expect(within(card).queryByLabelText("Use a Cast & places character")).toBeNull(); // closed until Pick another is pressed
  await userEvent.click(within(card).getByRole("button", { name: "Pick another" }));
  await userEvent.selectOptions(within(card).getByLabelText("Use a Cast & places character"), "5");
  await userEvent.click(within(card).getByRole("button", { name: "Use this character" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "PUT /projects/9/assets/slots/3")).toBe(true));
});

test("a role that is not deleted has no Character deleted badge or Pick another", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/assets": [200, [own({})]], "GET /projects/9/assets/missing-looks": noMissing });
  open();
  const card = await screen.findByLabelText("Coach");
  expect(within(card).queryByText("Character deleted")).toBeNull();
  expect(within(card).queryByRole("button", { name: "Pick another" })).toBeNull();
});

test("Pick another is disabled, with the reason, when Cast & places has no other characters", async () => {
  setViewport(1440);
  fakeServer({ ...deletedRoutes, "GET /library/character": [200, []] });
  open();
  const card = await screen.findByLabelText("Nate");
  const pick = within(card).getByRole("button", { name: "Pick another" });
  expect(pick).toBeDisabled();
  expect(pick).toHaveAccessibleDescription("Cast & places has no other characters yet.");
  expect(within(card).queryByText("Free")).toBeNull();
});

test("on the video page too, a shot with no script lines shows no Show line button and does not break Breakdown", async () => {
  setViewport(1440);
  const wordless = { ...breakdown, breakdown: { ...breakdown.breakdown, scenes: [{ id: 1, heading: "KITCHEN", look: "", shots: [{ id: "1.1", script_lines: [], speaker: null, line: null, action: "Bo looks up.", reaction: null, camera: "Wide", seconds: 2, character_ids: [], place_id: null, moment: null, screen_ids: [] }] }], clips: [{ id: "c1", shot_ids: ["1.1"], seconds: 2, seam: "end" }] } };
  fakeServer({ ...toClips, "GET /projects/9/breakdown": [200, wordless] });
  open("?step=breakdown");
  const silent = await screen.findByLabelText("Shot 1.1");
  expect(within(silent).queryByRole("button", { name: /in the script$/ })).toBeNull();
});

const clipProblem = "c1: the prompt has no [Image1] for the first frame";
const fixRoutes = {
  ...toClips,
  "GET /projects/9/clips/prompts/price?clip_id=c1": [200, { clip_ids: ["c1"], credits: 3 }] as [number, unknown],
};

test("a prompt the video model refused offers Reword it to pass · free, the same free fix", async () => {
  setViewport(390);
  const calls = fakeServer({
    ...fixRoutes,
    "GET /projects/9/clips": [200, [clip({ prompt_ok: false, problems: ["c1: The video model refused this prompt: it read it as violent. Reword it to pass."] })]],
    "POST /projects/9/clips/3/fix": [200, { fixed: true, before: "a", after: "b", reason: "", clip: clip({}) }],
  });
  open("?step=clips");
  const card = await screen.findByLabelText("Clip c1");
  await userEvent.click(await within(card).findByRole("button", { name: "Reword it to pass · free" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/clips/3/fix")).toBe(true));
});

test("a clip with a blocking problem has a free Fix this clip's prompt; it shows what changed, with Undo, and never makes a take", async () => {
  setViewport(1440);
  const routes: Record<string, [number, unknown]> = {
    ...fixRoutes,
    "POST /projects/9/clips/3/fix": [200, { fixed: true, before: "Bo sniffs", after: "[Image1] Bo sniffs", reason: "", clip: clip({}) }],
    "PUT /projects/9/clips/3": [200, clip({})],
  };
  Object.defineProperty(routes, "GET /projects/9/clips", {
    enumerable: true,
    get: () => [200, [calls.some((c) => c.key === "POST /projects/9/clips/3/fix") && !calls.some((c) => c.key === "PUT /projects/9/clips/3")
      ? clip({ prompt: "[Image1] Bo sniffs", prompt_ok: false, change: { note: "Fix this clip's prompt", status: "done", before: "Bo sniffs", after: "[Image1] Bo sniffs", unchanged: false } })
      : clip({ prompt: "Bo sniffs", prompt_ok: true, problems: [clipProblem] })]],
  });
  const calls = fakeServer(routes);
  open("?step=clips");
  const card = await screen.findByLabelText("Clip c1");
  expect(within(card).getByText("Free")).toBeInTheDocument();
  await userEvent.click(within(card).getByRole("button", { name: "Fix this clip's prompt" }));
  expect(await screen.findByText("Fixed clip c1's prompt.")).toBeInTheDocument(); // the toast, with Undo
  const note = await within(card).findByRole("note", { name: "Prompt fixed" });
  expect(note).toHaveTextContent("After: [Image1] Bo sniffs");
  expect(calls.some((c) => c.key.includes("/takes") || c.key.endsWith("/generate"))).toBe(false); // nothing was made
  await userEvent.click(within(note).getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /projects/9/clips/3")?.body).toMatchObject({ prompt: "Bo sniffs" }));
});

test("once the free rewrite is used, the clip says so and offers the priced Rewrite and Change this…, not the Fix again", async () => {
  setViewport(1440);
  fakeServer({ ...fixRoutes, "GET /projects/9/clips": [200, [clip({ prompt_ok: true, problems: [clipProblem], free_fix_used: true })]] });
  open("?step=clips");
  const card = await screen.findByLabelText("Clip c1");
  expect(within(card).queryByRole("button", { name: "Fix this clip's prompt" })).toBeNull();
  expect(within(card).getByRole("status")).toHaveTextContent("We couldn't fix this one automatically.");
  expect(within(card).getByRole("status")).not.toHaveTextContent("Try saying");
  expect(await within(card).findByRole("button", { name: "Rewrite this clip's prompt · up to 3 credits" })).toBeInTheDocument();
  expect(within(card).getByLabelText("Note for the next take c1")).toBeInTheDocument();
});

test("when the server can't fix it, the card says why in the server's words", async () => {
  setViewport(1440);
  fakeServer({
    ...fixRoutes,
    "GET /projects/9/clips": [200, [clip({ prompt_ok: true, problems: [clipProblem] })]],
    "POST /projects/9/clips/3/fix": [409, { detail: "We couldn't fix this one automatically." }],
  });
  open("?step=clips");
  const card = await screen.findByLabelText("Clip c1");
  await userEvent.click(within(card).getByRole("button", { name: "Fix this clip's prompt" }));
  expect(await within(card).findByRole("status")).toHaveTextContent("We couldn't fix this one automatically.");
});

test("a clip that is out of date keeps its own Rewrite and has no Fix this clip's prompt", async () => {
  setViewport(1440);
  fakeServer({ ...fixRoutes, "GET /projects/9/clips": [200, [clip({ stale: true, problems: [clipProblem] })]] });
  open("?step=clips");
  const card = await screen.findByLabelText("Clip c1");
  expect(await within(card).findByRole("button", { name: /^Rewrite this clip's prompt/ })).toBeInTheDocument();
  expect(within(card).queryByRole("button", { name: "Fix this clip's prompt" })).toBeNull();
});

/** Hold one request until `release` is called, answering with `status`; everything else goes to the fake server. */
function holdRequest(key: string) {
  const real = globalThis.fetch;
  let release: (status: number, body?: unknown) => void = () => {};
  const waiting = new Promise<Response>((resolve) => {
    release = (status, body = {}) => resolve(new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } }));
  });
  vi.stubGlobal("fetch", (input: Request | string, init?: RequestInit) => {
    const req = input instanceof Request ? input : new Request(new URL(input, "http://x"), init);
    return `${req.method} ${new URL(req.url).pathname.replace(/^\/api/, "")}` === key ? waiting : real(input, init);
  });
  return release;
}

test("pressing a prompt's Prompt OK shows it at once (the badge, Undo, the take button on), before the server answers; a refusal puts it back", async () => {
  setViewport(1440);
  fakeServer({ ...toClips, "GET /projects/9/clips": [200, [clip({ prompt_ok: false })]] });
  const release = holdRequest("POST /projects/9/clips/3/prompt-ok");
  open("?step=clips");
  await userEvent.click(await screen.findByRole("button", { name: "Prompt OK for c1" }));
  expect(await screen.findByRole("button", { name: "Undo Prompt OK for c1" })).toBeInTheDocument();
  expect(screen.getByText("Prompt OK")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^Make clip/ })).toBeEnabled();
  release(409, { detail: "Not now." });
  expect(await screen.findByRole("button", { name: "Prompt OK for c1" })).toBeInTheDocument();
});

test("after Change this… on a clip with no take that must be read again, the line says Prompt OK first, then Make clip", async () => {
  setViewport(1440);
  const change = { note: "Slower", status: "done", before: "a b", after: "a c" };
  fakeServer({ ...toClips, "GET /projects/9/clips": [200, [clip({ prompt_ok: false, change })]] });
  open("?step=clips");
  expect(await screen.findByText("Prompt updated. Read it, then press Make clip.")).toBeInTheDocument();
});

test("no 'Prompt updated' line once a take exists", async () => {
  setViewport(1440);
  const change = { note: "Slower", status: "done", before: "a b", after: "a c" };
  fakeServer({ ...toClips, "GET /projects/9/clips": [200, [clip({ prompt_ok: true, takes: [{ id: 1, number: 1, file_id: 51 }], picked_take_id: 1, file_id: 51, change })]] });
  open("?step=clips");
  await screen.findByLabelText("Clip c1");
  expect(screen.queryByText(/Prompt updated/)).toBeNull();
});

test("the header's money follows the video's jobs: when one finishes, it's read again", async () => {
  setViewport(1440);
  let done = false;
  const routes = { ...toClips } as Record<string, [number, unknown]>;
  const head = (credits: number) => ({ title: "Bo tries salmon · B", status: { kind: "working", words: "Working", made: 0, total: 0 }, spent: { credits, usd: null }, up_to: { credits: 99, usd: null }, budget: { credits: 24, usd: null }, folder: null, format: "", style: "House", seconds: 30, song: false });
  Object.defineProperty(routes, "GET /projects/9/idea", { enumerable: true, get: () => [200, head(done ? 13 : 3)] });
  Object.defineProperty(routes, "GET /jobs", { enumerable: true, get: () => [200, [{ id: 1, kind: "image", status: done ? "succeeded" : "running", project_id: 9, step: "frame", created_at: new Date().toISOString() }]] });
  fakeServer(routes);
  open("?step=clips");
  expect(await screen.findByText(/^3 credits used/)).toBeInTheDocument();
  done = true; // the job finishes; the job list polls while it runs
  expect(await screen.findByText(/^13 credits used/, {}, { timeout: 8000 })).toBeInTheDocument();
}, 20000);

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

test("a look from the library says it comes from Cast & places, so the Cast step and the library never read as one", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/assets": [200, [asset({ ready: true, locked: true, sheet_status: "approved" })]] });
  open("?step=assets");
  expect(await screen.findByRole("tab", { name: "Cast 1", selected: true })).toBeInTheDocument();
  expect(await screen.findByText("From Cast & places")).toBeInTheDocument();
});

test("switching the look re-reads the cast, so a role with no sheet in the new look holds Storyboard's redraw (Flow-QA on #926)", async () => {
  setViewport(1440);
  const looks = [{ id: "house", name: "House", blurb: "", on: true, sample_still_id: null }, { id: "pixar", name: "Disney Pixar", blurb: "", on: true, sample_still_id: null }];
  const settings = { look: "house", video_model: null, image_model: null, aspect_ratio: "9:16", product_variants: {}, language: "en", video_models: [], image_models: [], shapes: ["9:16"], flavours: {} };
  const routes: Record<string, [number, unknown]> = {
    ...toClips,
    "GET /projects/9/storyboard": [200, [{ ...frame, earlier: [], change: null }]],
    "GET /looks": [200, looks],
    "GET /projects/9/settings": [200, settings],
    "POST /projects/9/settings/preview": [200, { to_finish_credits: 30, was_credits: 30, stills_out_of_date: 1, clips_out_of_date: 0, sung_to_broll: 0, over_budget: false, reason: null, roles_needing_look: ["Bo"] }],
    "POST /projects/9/settings": [200, { settings: { ...settings, look: "pixar" }, was: { look: "house" } }],
  };
  fakeServer(routes);
  open("?step=storyboard");
  expect(await screen.findByLabelText("Frame c1")).toBeInTheDocument();
  expect(screen.queryByText("Waiting on the cast")).toBeNull();
  await userEvent.click(screen.getByRole("tab", { name: "Plan" })); // the video's settings sit at the top of Plan (S-gaps-05 V1)
  await userEvent.click(await screen.findByRole("button", { name: /Style House/ }));
  await userEvent.click((await screen.findAllByRole("button", { name: "Use this style" }))[0]);
  const ask = await screen.findByRole("alertdialog", { name: "Switch to Disney Pixar?" });
  routes["GET /projects/9/assets"] = [200, [asset({ locked: true })]]; // Bo has no sheet in Disney Pixar yet
  await userEvent.click(await within(ask).findByRole("button", { name: "Switch" }));
  await userEvent.click(await screen.findByRole("tab", { name: /^Clips/ }));
  expect(await screen.findByText("Waiting on the cast")).toBeInTheDocument();
});

test("a link to the Cut with no storyboard yet says the cut comes later; Clips offers the stills (A15)", async () => {
  setViewport(390);
  fakeServer({ ...toClips, "GET /projects/9/storyboard": [200, []], "GET /projects/9/clips": [200, []] });
  open("?step=downloads");
  expect(await screen.findByText("The cut plays here when it’s ready")).toBeInTheDocument();
  cleanup();
  fakeServer({ ...toClips, "GET /projects/9/storyboard": [200, []], "GET /projects/9/clips": [200, []] });
  open("?step=clips");
  expect(await screen.findByText("No frames yet.")).toBeInTheDocument();
});

test("a video not made from a script version has no Director tab: it opens on its steps", async () => {
  setViewport(1440);
  fakeServer(base);
  open("");
  expect(await screen.findByRole("tab", { name: "Plan", selected: true })).toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "Director" })).toBeNull();
});

test("the clip list: each clip's still, length, script line and status; a row opens that clip on the right", async () => {
  setViewport(1440);
  const shot = (id: string, o: object) => ({ id, script_lines: [], speaker: null, line: null, action: null, reaction: null, camera: "Wide", seconds: 4, character_ids: [], place_id: null, moment: null, screen_ids: [], ...o });
  const plan = { ...breakdown, breakdown: { ...breakdown.breakdown, scenes: [{ id: 1, heading: "KITCHEN", look: "", shots: [shot("1.1", { speaker: "Bo", line: "Is that… salmon?" }), shot("1.2", { action: "Bo sniffs the bag" }), shot("1.3", { action: "Bo spins" })] }], clips: [{ id: "c1", shot_ids: ["1.1"], seconds: 8, seam: "end" }, { id: "c2", shot_ids: ["1.2"], seconds: 4, seam: "end" }, { id: "c3", shot_ids: ["1.3"], seconds: 4, seam: "end" }] } };
  const frames = ["c1", "c2", "c3"].map((c, i) => ({ ...frame, id: i + 1, clip_id: c }));
  const rows = [done, clip({ id: 4, clip_id: "c2", seconds: 4, file_id: 52, takes: [take(3, 1), take(4, 2)], picked_take_id: 4 }), clip({ id: 5, clip_id: "c3", seconds: 4 })];
  fakeServer({ ...toClips, "GET /projects/9/breakdown": [200, plan], "GET /projects/9/storyboard": [200, frames], "GET /projects/9/clips": [200, rows] });
  open("?step=clips");
  const list = await screen.findByRole("list", { name: "Clip list" });
  const row = (n: number) => within(list).getByRole("button", { name: new RegExp(`^Clip ${n} `) });
  await vi.waitFor(() => expect(row(1)).toHaveTextContent("Clip 1 · 8 sApprovedBO: Is that… salmon?"));
  expect(row(2)).toHaveTextContent("Check take 2");
  expect(within(row(2)).getByText("(Bo sniffs the bag)")).toHaveClass("font-script");
  expect(row(3)).toHaveTextContent("No take yet");
  expect(row(2)).toHaveAttribute("aria-current", "true"); // it opens on the first clip that needs you
  const card = await screen.findByLabelText("Clip c2");
  expect(within(card).getByRole("button", { name: "Approve take 2" })).toBeInTheDocument();
  expect(within(within(card).getByLabelText("Take 1")).getByRole("button", { name: "Use take 1" })).toBeInTheDocument(); // the other take, side by side
  expect(within(card).getByRole("button", { name: /^Make another take/ })).toBeInTheDocument();
  await userEvent.click(row(3));
  expect(await screen.findByLabelText("Clip c3")).toBeInTheDocument();
  expect(screen.queryByLabelText("Clip c2")).toBeNull();
});
