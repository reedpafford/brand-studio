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
  "GET /models": [200, [{ id: "nano-banana-pro", kind: "image", name: "Nano Banana Pro", default: false, credits_per_unit: { "2K": 1.5 } }, { id: "nano-banana-2.1", kind: "image", name: "Nano Banana 2.1", default: true, credits_per_unit: { "1K": 3 } }]],
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
    "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 3 }, { kind: "image-nano-banana-2.1", unit: "image", credits_per_unit: 4 }]],
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
    "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 3 }, { kind: "image-nano-banana-2.1", unit: "image", credits_per_unit: 4 }]],
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
  const box = await screen.findByLabelText("Change this… c1");
  expect(screen.getByRole("button", { name: /^Change it/ })).toBeDisabled();
  expect(screen.getByText("Say what should change")).toBeInTheDocument();
  await userEvent.type(box, "Bo should look surprised");
  await userEvent.click(await screen.findByRole("button", { name: "Change it · 4 credits" }));
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
  const box = await screen.findByLabelText("Change this… c1");
  await userEvent.type(box, "Make Bo say hello");
  await userEvent.click(await screen.findByRole("button", { name: "Change it · 4 credits" }));
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
  expect(screen.getByLabelText("Change this… c1")).toHaveAttribute("readonly");
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

test("Change this… on a clip has the clip's price, and an editor past the budget is told why", async () => {
  setViewport(1440);
  fakeServer({
    ...toClips,
    "GET /projects/9": [200, { ...project, credits_used: 590, budget_credits: 600 }],
    "GET /projects/9/clips": [200, [clip({ prompt_ok: true, takes: [take(1, 1)], picked_take_id: 1, file_id: 51 })]],
    "GET /projects/9/clips/3/change": [200, { credits: 27 }],
  });
  open("?step=clips");
  await userEvent.type(await screen.findByLabelText("Change this… c1"), "Slower");
  const button = await screen.findByRole("button", { name: "Change it · 27 credits" });
  expect(button).toBeDisabled();
  expect(button).toHaveAccessibleDescription("That's more than this video's budget.");
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
  await userEvent.type(await screen.findByLabelText("Change this… c1"), "Slower");
  await userEvent.click(await screen.findByRole("button", { name: "Change it · 27 credits" }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }, { timeout: 9000 }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/clips/3/takes/1/pick")).toBe(true));
}, 20000);

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
  expect(within(card).queryByRole("button", { name: /^More for/ })).toBeNull();
});

test("a Cast & places character has no Delete this look", async () => {
  setViewport(1440);
  fakeServer(base);
  open();
  await screen.findByLabelText("Bo");
  expect(screen.queryByRole("button", { name: /^More for/ })).toBeNull();
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
  expect(within(list).getByRole("link", { name: "Approve a look in Assets" })).toHaveAttribute("href", "/b/1/videos/9?step=assets");
  const advice = screen.getByLabelText("Advice for c1");
  expect(advice).not.toHaveTextContent(/char:/);
  await userEvent.click(within(advice).getByText(/Advice \(/)); // open it
  const keepLabels = within(advice).getAllByRole("button").map((b) => b.getAttribute("aria-label") ?? "");
  expect(keepLabels.some((l) => l.startsWith("Keep anyway: "))).toBe(true);
  expect(keepLabels.join(" ")).not.toMatch(/char:|slot:/); // the screen reader hears names too
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

test("Approve all on the storyboard approves the frames that can be, says why the others weren't, and Undo takes back exactly those", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...toClips,
    "GET /projects/9/storyboard": [200, [waiting(1), waiting(2, { file_id: null })]],
    "POST /projects/9/storyboard/approve-all": [200, { approved: [1], skipped: [{ id: 2, reason: "no still yet" }] }],
    "POST /projects/9/storyboard/approve-all/undo": [200, []],
  });
  open("?step=storyboard");
  await userEvent.click(await screen.findByRole("button", { name: "Approve 1" })); // one of the two can be approved
  expect(await screen.findByText(/Approved 1\./)).toHaveTextContent("Approved 1. 1 not approved: Frame c2: no still yet");
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/storyboard/approve-all/undo")?.body).toEqual({ ids: [1] }));
  expect(screen.queryByText(/Approved 1\./)).toBeNull();
});

test("the Approve all result line goes away on the next action, but not when its own links are pressed", async () => {
  setViewport(1440);
  fakeServer({
    ...toClips,
    "GET /projects/9/storyboard": [200, [waiting(1), waiting(2, { file_id: null })]],
    "POST /projects/9/storyboard/approve-all": [200, { approved: [1], skipped: [{ id: 2, reason: "no still yet" }] }],
  });
  open("?step=storyboard");
  await userEvent.click(await screen.findByRole("button", { name: "Approve 1" }));
  await userEvent.click(await screen.findByRole("button", { name: "Frame c2" }));
  expect(screen.getByText(/Approved 1\./)).toBeInTheDocument();
  await userEvent.tab(); // moving by keyboard leaves it be
  expect(screen.getByText(/Approved 1\./)).toBeInTheDocument();
  await userEvent.click(document.body);
  await vi.waitFor(() => expect(screen.queryByText(/Approved 1\./)).toBeNull());
});

test("Approve all is not offered when every frame is approved or has no still", async () => {
  setViewport(1440);
  fakeServer({ ...toClips, "GET /projects/9/storyboard": [200, [{ ...frame, earlier: [], change: null }, waiting(2, { file_id: null })]] });
  open("?step=storyboard");
  await screen.findByLabelText("Frame c2");
  expect(screen.queryByRole("button", { name: /^Approve (all|\d)/ })).toBeNull();
});

test("Approve all on Clips approves the clips with a picked take", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...toClips,
    "GET /projects/9/clips": [200, [clip({ id: 3, clip_id: "c1", prompt_ok: true, takes: [{ id: 5 }], picked_take_id: 5 })]],
    "POST /projects/9/clips/approve-all": [200, { approved: [3], skipped: [] }],
  });
  open("?step=clips");
  await userEvent.click(await screen.findByRole("button", { name: "Approve all" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/clips/approve-all")).toBe(true));
  expect(await screen.findByText("Approved 1.")).toBeInTheDocument();
  expect(await screen.findByText("Approved 1 clip.")).toBeInTheDocument(); // the toast, with Undo
});

const staleClips = [clip({ id: 3, clip_id: "c1", stale: true, takes: [{ id: 5 }], picked_take_id: 5 }), clip({ id: 4, clip_id: "c2", stale: true })];
const staleRoutes = {
  ...toClips,
  "GET /projects/9/clips": [200, staleClips] as [number, unknown],
  "GET /projects/9/clips/prompts/price": [200, { clip_ids: ["c1", "c2"], credits: 6 }] as [number, unknown],
  "GET /projects/9/clips/prompts/price?clip_id=c1": [200, { clip_ids: ["c1"], credits: 3 }] as [number, unknown],
  "POST /projects/9/clips/prompts": [201, { id: 7, kind: "write-claude", step: "clip_prompts", status: "queued", credits: 6, project_id: 9 }] as [number, unknown],
};

test("clips made for an older breakdown offer one priced rewrite for all, and Make the takes waits for it", async () => {
  setViewport(1440);
  // A third clip is fine but has no take yet, so Make the takes is on screen beside the rewrite.
  const calls = fakeServer({ ...staleRoutes, "GET /projects/9/clips": [200, [...staleClips, clip({ id: 5, clip_id: "c3", prompt_ok: true })]] });
  open("?step=clips");
  expect(await screen.findByText("2 clips were made for an older breakdown. Rewrite their prompts so they match.")).toBeInTheDocument();
  expect(screen.getByText("Rewrite the clips made for an older breakdown first (2).")).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: /credits/ }).filter((b) => b.className.includes("bg-accent"))).toHaveLength(1); // one amber: the rewrite
  await userEvent.click(await screen.findByRole("button", { name: "Rewrite clip prompts · 6 credits" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/clips/prompts")).toBeDefined());
  expect(calls.find((c) => c.key === "POST /projects/9/clips/prompts")?.body).toBeUndefined(); // every stale clip
  expect(await screen.findByText("Rewriting clip prompts…")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^Rewrite/ })).toBeNull();
});

test("a stale clip has its own priced rewrite in place of Change this…", async () => {
  setViewport(1440);
  const calls = fakeServer(staleRoutes);
  open("?step=clips");
  const card = await screen.findByLabelText("Clip c1");
  expect(within(card).queryByLabelText("Change this…")).toBeNull();
  await userEvent.click(await within(card).findByRole("button", { name: "Rewrite this clip's prompt · 3 credits" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/clips/prompts")?.body).toEqual({ clip_id: "c1" }));
});

const noLook = asset({ ref: "slot:4", slot_id: 4, library_item_id: null, name: "", role: "Nate", sheet_status: "missing" });
const noMissing: [number, unknown] = [200, { slot_ids: [], roles: [], credits: 0, usual_credits: 0, reason: null }];

test("Approve all on Assets approves the looks made for this video, says which role was left, and Undo sends back exactly those", async () => {
  setViewport(1440);
  const calls = fakeServer({
    ...base,
    "GET /projects/9/assets": [200, [own({}), noLook]],
    "GET /projects/9/assets/missing-looks": noMissing,
    "POST /projects/9/assets/approve-all": [200, { approved: [12], skipped: [{ id: null, slot_id: 4, label: "Nate", reason: "no look yet" }] }],
    "POST /projects/9/assets/approve-all/undo": [200, []],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Approve 1" })); // one of the two roles has a sheet to approve
  expect(await screen.findByText(/Approved 1\./)).toHaveTextContent("Approved 1. 1 not approved: Nate: no look yet");
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/assets/approve-all/undo")?.body).toEqual({ ids: [12] }));
});

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

test("a link to a locked step lands on Assets while assets are left to approve", async () => {
  setViewport(1440);
  fakeServer({ ...toClips, "GET /projects/9/assets": [200, [asset({})]] });
  open("?step=storyboard");
  expect(await screen.findByLabelText("Bo")).toBeInTheDocument();
});

test("when Undo of Approve all fails, it says why", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /projects/9/assets": [200, [own({})]],
    "GET /projects/9/assets/missing-looks": noMissing,
    "POST /projects/9/assets/approve-all": [200, { approved: [12], skipped: [] }],
    "POST /projects/9/assets/approve-all/undo": [409, { detail: "That look changed since. Undo it on its card." }],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Approve all" }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  expect(await screen.findByText("That look changed since. Undo it on its card.")).toBeInTheDocument();
});

test("a locked step says Breakdown, the name this page uses, when problems in it are in the way", async () => {
  setViewport(1440);
  fakeServer({ ...toClips, "GET /projects/9/breakdown": [200, { ...breakdown, problems: ["c1: the shot has no action", "c2: the shot has no setting"] }] });
  open("?step=breakdown");
  const steps = await screen.findByRole("list", { name: "Steps" });
  expect(within(steps).getByRole("button", { name: "Assets" })).toHaveAccessibleDescription("Fix the 2 problems in Breakdown first");
});
