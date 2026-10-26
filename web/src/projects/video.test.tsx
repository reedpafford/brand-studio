import { render, screen, within } from "@testing-library/react";
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
  cast_ids: [], reference_file_id: null, estimate_credits: 30, budget_credits: 600, credits_used: 0, budget_pct: 0, product_variants: {},
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
  "GET /models": [200, [{ id: "nano-banana-pro", kind: "image", name: "Nano Banana Pro", credits_per_unit: { "2K": 1.5 } }]],
  "GET /credits/limits": [200, { weekly_quick_clip_credits: 145, per_video_max_credits: 729, editors_can_save_looks: false }],
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

test("the five steps, and Storyboard waits until every asset is approved", async () => {
  setViewport(1440);
  fakeServer(base);
  open();
  const steps = await screen.findByRole("list", { name: "Steps" });
  expect(within(steps).getAllByRole("button").map((b) => b.textContent?.replace(/^\d/, ""))).toEqual(["Breakdown", "Assets", "Storyboard", "Clips", "Downloads"]);
  expect(within(steps).getByRole("button", { name: "Storyboard" })).toHaveAccessibleDescription(/Approve every asset first \(1 left\)/);
  expect(screen.getByRole("button", { name: /Next: Storyboard/ })).toBeDisabled();
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
  expect(within(card).getByText("Locked by Reed")).toBeInTheDocument();
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

const frame = { id: 1, clip_id: "c1", shot_id: "1.1", prompt: "p", reference_ids: [], problems: [], kept: [], file_id: 40, approved: true, stale: false };
const clip = (o: object) => ({ id: 3, clip_id: "c1", seconds: 8, prompt: "Bo sniffs the salmon", references: [], problems: [], kept: [], file_id: null, takes: [], picked_take_id: null, approved: false, stale: false, take_credits: 24, inserts: [], ...o });
const toClips = { ...base, "GET /projects/9/assets": [200, []] as [number, unknown], "GET /projects/9/storyboard": [200, [frame]] as [number, unknown] };

test("a clip's prompt is read and marked Looks good (on the server) before its take can be made", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...toClips, "GET /projects/9/clips": [200, [clip({ prompt_ok: false })]], "POST /projects/9/clips/3/prompt-ok": [200, clip({ prompt_ok: true })] });
  open("?step=clips");
  expect(await screen.findByText("Bo sniffs the salmon")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^Make clip/ })).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "Prompt for c1 looks good" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/clips/3/prompt-ok")).toBe(true));
});

test("a prompt already marked Looks good keeps its badge, lets the take be made, and can be undone", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...toClips, "GET /projects/9/clips": [200, [clip({ prompt_ok: true })]], "DELETE /projects/9/clips/3/prompt-ok": [200, clip({ prompt_ok: false })] });
  open("?step=clips");
  expect(await screen.findByText("Looks good")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^Make clip/ })).toBeEnabled();
  await userEvent.click(screen.getByRole("button", { name: "Prompt for c1 undo looks good" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /projects/9/clips/3/prompt-ok")).toBe(true));
});

test("a prompt shows pictures by name, never [Image1]", async () => {
  setViewport(1440);
  const references = [{ kind: "image", id: "frame:c1", role: "frame:c1" }, { kind: "image", id: "char:5", role: "Bo's look" }, { kind: "image", id: "screen:2", role: "screen:2" }];
  fakeServer({ ...toClips, "GET /projects/9/clips": [200, [clip({ prompt: "[Image1] is the first frame. [Image2] eats. [Image3] shows.", references })]] });
  open("?step=clips");
  const prompt = await screen.findByLabelText("Prompt for clip c1");
  expect(prompt).toHaveTextContent("First frame is the first frame. Bo's look eats. Picture 3 shows.");
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

test("one-press Make storyboard is off for an editor when the writing plus the stills pass the budget, not only the writing", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /projects/9": [200, { ...project, credits_used: 590, budget_credits: 600 }],
    "GET /projects/9/assets": [200, []],
    "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 3 }, { kind: "image", unit: "image", credits_per_unit: 4 }]],
    "GET /projects/9/breakdown": [200, { ...breakdown, breakdown: { ...breakdown.breakdown, clips: [{ id: "c1" }, { id: "c2" }, { id: "c3" }] } }],
  });
  open("?step=storyboard");
  const make = await screen.findByRole("button", { name: "Make storyboard · 15 credits" });
  expect(make).toBeDisabled();
  expect(screen.getByText("That's more than this video's budget.")).toBeInTheDocument();
});

const take = (id: number, number: number) => ({ id, number, file_id: 50 + id, created_at: `2026-10-26T10:4${number}:00` });
const done = clip({ approved: true, file_id: 51, takes: [take(1, 1), take(2, 2)], picked_take_id: 2 });

test("Downloads: the zip, the picked take and the older take each download", async () => {
  setViewport(1440);
  fakeServer({ ...toClips, "GET /projects/9/clips": [200, [done]], "GET /projects/9/video": [200, { file_id: 60, take_ids: [2], out_of_date: false }] });
  open("?step=downloads");
  const zip = await screen.findByRole("link", { name: "Download all clips (.zip)" });
  expect(zip).toHaveAttribute("href", "/api/projects/9/clips.zip");
  expect(screen.getByRole("link", { name: "Download clip 1 (bo-tries-salmon-b-clip-1.mp4)" })).toHaveAttribute("href", expect.stringContaining("/files/52"));
  expect(screen.getByText("Older takes (1)")).toBeInTheDocument();
  expect(screen.getByText(/Take 1 · made \d{1,2}:41/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Download clip 1 take 1/ })).toBeInTheDocument();
});

test("Downloads puts the clips together by itself the first time, for free", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...toClips, "GET /projects/9/clips": [200, [done]], "POST /projects/9/video": [201, { file_id: 60, take_ids: [2], out_of_date: false }] });
  open("?step=downloads");
  expect(await screen.findByText("Putting your clips together…")).toBeInTheDocument();
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
  expect(await screen.findByRole("heading", { name: "Breakdown", level: 2 })).toBeInTheDocument();
  expect(screen.getByRole("list", { name: "Steps" })).toHaveTextContent("Downloads");
});

test("on a phone the zip button sits in the action bar", async () => {
  setViewport(390);
  fakeServer({ ...toClips, "GET /projects/9/clips": [200, [done]], "GET /projects/9/video": [200, { file_id: 60, take_ids: [2], out_of_date: false }] });
  open("?step=downloads");
  const zip = await screen.findByRole("link", { name: "Download all clips (.zip)" });
  expect(zip.closest(".border-t.text-center")).not.toBeNull();
  expect(screen.getByText("Made from: Clip 1 Take 2")).toBeInTheDocument();
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

test("on an editor's own script past the weekly allowance the storyboard is declined with the reason, never Ask Reed", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /projects/9": [200, { ...project, own_script: true, credits_used: 590, budget_credits: 600 }],
    "GET /projects/9/assets": [200, []],
    "GET /credits/me": [200, { quick_clip_credits_used: 140, quick_clip_credits_allowed: 145 }],
    "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 3 }, { kind: "image", unit: "image", credits_per_unit: 4 }]],
    "GET /projects/9/breakdown": [200, { ...breakdown, breakdown: { ...breakdown.breakdown, clips: [{ id: "c1" }, { id: "c2" }, { id: "c3" }] } }],
  });
  open("?step=storyboard");
  const button = await screen.findByRole("button", { name: "Make storyboard · 15 credits" });
  expect(button).toBeDisabled();
  expect(await screen.findByText(/more than this week's 145 free credits/)).toBeInTheDocument();
  expect(screen.queryByText(/Ask Reed/)).toBeNull();
});

test("on an editor's own script the header shows the week, not a budget", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9": [200, { ...project, own_script: true }], "GET /projects/9/assets": [200, []], "GET /credits/me": [200, { quick_clip_credits_used: 3, quick_clip_credits_allowed: 145 }] });
  open();
  expect(await screen.findByText("This week: 3 of 145 credits")).toBeInTheDocument();
  expect(screen.queryByText(/% ·|credits · \d+%/)).toBeNull();
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
  expect(screen.getByText("3 assets · 2 approved")).toBeInTheDocument();
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

test("Save to Cast & places needs an approved sheet first", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /auth/me": [200, { ...editor, role: "owner" }],
    "GET /projects/9/assets": [200, [own({ sheet_status: "needs_approval" })]],
    "GET /library/character/12": [200, item({ id: 12, name: "Coach" })],
  });
  open();
  const save = await within(await screen.findByLabelText("Coach")).findByRole("button", { name: "Save to Cast & places" });
  expect(save).toBeDisabled();
  expect(save).toHaveAccessibleDescription("Approve the sheet first");
});

test("an approved look is saved under a name; Undo removes the copy", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /auth/me": [200, { ...editor, role: "owner" }],
    "GET /projects/9/assets": [200, [own({ sheet_status: "approved", ready: true })]],
    "GET /library/character/12": [200, item({ id: 12, name: "Coach", sheet_status: "approved" })],
    "POST /projects/9/assets/slots/3/save-to-library": [201, { library_item_id: 30, assets: [] }],
    "DELETE /library/character/30": [204, null],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Save to Cast & places" }));
  const name = await screen.findByLabelText("Name");
  expect(name).toHaveValue("Coach");
  expect(screen.getByText("It becomes a normal character any script can use. This video keeps its look either way.")).toBeInTheDocument();
  await userEvent.clear(name);
  await userEvent.type(name, "Coach Dan");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/assets/slots/3/save-to-library")?.body).toEqual({ name: "Coach Dan" }));
  expect(await screen.findByText("Coach Dan saved to Cast & places.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /library/character/30")).toBe(true));
});

test("an editor doesn't see Save to Cast & places unless Team allows it", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/assets": [200, [own({ sheet_status: "approved", ready: true })]], "GET /library/character/12": [200, item({ id: 12, name: "Coach", sheet_status: "approved" })] });
  open();
  const card = await screen.findByLabelText("Coach");
  await within(card).findByRole("button", { name: /Change it/ });
  expect(within(card).queryByRole("button", { name: "Save to Cast & places" })).toBeNull();
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
