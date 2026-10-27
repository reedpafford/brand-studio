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
  id: 9, brand_id: 1, name: "Mia buys the dip", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "",
  cast_ids: [4], reference_file_id: null, estimate_credits: 30, budget_credits: 600, credits_used: 0, budget_pct: 0,
};
const script = { version: 5, source: "paste", words: 9, created_by_id: 2, created_at: "2026-10-23T10:00:00Z", text: "Mia scrolls her phone." };
const breakdown = { id: 1, script_version: 5, source: "claude", stale: false, problems: [], breakdown: { hook: "Hook.", scenes: [{ id: 1, heading: "KITCHEN", look: "", shots: [] }], clips: [] } };
const frame = (o: object) => ({ id: 1, clip_id: "c1", shot_id: "1.1", prompt: "Mia in a cold blue kitchen", reference_ids: ["char:4", "screen:3"], problems: [], file_id: null, stale: false, ...o });
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, editor],
  "GET /brands": [200, [{ id: 1, name: "fomo", colours: [] }]],
  "GET /projects/9": [200, project],
  "GET /projects/9/script": [200, script],
  "GET /projects/9/breakdown": [200, breakdown],
  "GET /projects/9/script/suggestions": [200, []],
  "GET /projects/9/script/notes": [200, []],
  "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 6 }, { kind: "image", unit: "image", credits_per_unit: 3 }]],
  "GET /jobs": [200, []],
  "GET /library/character": [200, [{ id: 4, name: "Mia", image_file_ids: [] }]],
  "GET /library/place": [200, []],
  "GET /library/prop": [200, []],
  "GET /brands/1/screens": [200, [{ id: 3, name: "Chart down", file_id: 9, tags: [], default_for: [], brand_id: 1 }]],
};

function open(query = "?stage=storyboard") {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[`/b/1/projects/9${query}`]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

test("with no frames it offers to write them and shows the cost", async () => {
  const calls = fakeServer({ ...base, "GET /projects/9/storyboard": [200, []], "POST /projects/9/storyboard": [201, { id: 7, kind: "write-claude", status: "queued", credits: 6, project_id: 9 }] });
  open();
  expect(await screen.findByText("No frames yet.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Make storyboard · 6 credits" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/storyboard")?.body).toEqual({ per_shot: false }));
  expect(await screen.findByText("Writing your frames…")).toBeInTheDocument();
});

test("frames show their still or a placeholder, their label, references with names, and problems", async () => {
  fakeServer({
    ...base,
    "GET /projects/9/storyboard": [200, [frame({ file_id: 40 }), frame({ id: 2, clip_id: "c2", shot_id: "2.1", problems: ["Chart down is not attached."], stale: true })]],
  });
  open();
  const first = await screen.findByLabelText("Frame c1");
  expect(within(first).getByAltText("Still for clip c1")).toHaveAttribute("src", "/api/files/40");
  expect(within(first).getByText("c1 · shot 1.1")).toBeInTheDocument();
  expect(within(first).getByText("● Mia")).toBeInTheDocument();
  expect(within(first).getByText("★ Chart down")).toBeInTheDocument();
  const second = screen.getByLabelText("Frame c2");
  expect(within(second).getByText("No still yet")).toBeInTheDocument();
  expect(within(second).getByText("Breakdown changed: redo this frame")).toBeInTheDocument();
  expect(within(second).getByText("Chart down is not attached.")).toBeInTheDocument();
  expect(within(second).getByRole("button", { name: /Make still/ })).toBeDisabled(); // problems first
});

test("Make still and Make all stills queue the image jobs and say Drawing…", async () => {
  const calls = fakeServer({
    ...base,
    "GET /projects/9/storyboard": [200, [frame({ file_id: 40 }), frame({ id: 2, clip_id: "c2" }), frame({ id: 3, clip_id: "c3" })]],
    "POST /projects/9/storyboard/frames/2/render": [201, { id: 11, kind: "image", status: "queued", credits: 3, project_id: 9 }],
    "POST /projects/9/storyboard/frames/3/render": [201, { id: 12, kind: "image", status: "queued", credits: 3, project_id: 9 }],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Make all stills · 6 credits" })); // two missing × 3
  await vi.waitFor(() => expect(calls.filter((c) => c.key.endsWith("/render"))).toHaveLength(2));
  expect(await within(screen.getByLabelText("Frame c2")).findByText("Drawing…")).toBeInTheDocument();
});

test("editing a frame's prompt saves it with its references", async () => {
  const calls = fakeServer({ ...base, "GET /projects/9/storyboard": [200, [frame({})]], "PUT /projects/9/storyboard/frames/1": [200, frame({})] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Edit the prompt for clip c1" }));
  const box = screen.getByLabelText("Prompt for clip c1");
  await userEvent.clear(box);
  await userEvent.type(box, "Warmer light");
  await userEvent.click(screen.getByRole("button", { name: "Save prompt" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /projects/9/storyboard/frames/1")?.body).toEqual({ prompt: "Warmer light", reference_ids: ["char:4", "screen:3"] }));
});

test("editing the prompt of a frame that has a still saves it and draws the still again, with the price on the button", async () => {
  const calls = fakeServer({
    ...base,
    "GET /projects/9/storyboard": [200, [frame({ file_id: 40 })]],
    "PUT /projects/9/storyboard/frames/1": [200, frame({ file_id: 40, prompt: "Warmer light" })],
    "POST /projects/9/storyboard/frames/1/render": [409, { detail: "This frame's still is already being made." }],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Edit the prompt for clip c1" }));
  await userEvent.type(screen.getByLabelText("Prompt for clip c1"), " at night");
  await userEvent.click(screen.getByRole("button", { name: "Save and redraw · 3 credits" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/storyboard/frames/1/render")).toBe(true));
  // A refusal says why on the frame itself.
  expect(await within(screen.getByLabelText("Frame c1")).findByText("This frame's still is already being made.")).toBeInTheDocument();
});

test("Save and redraw shows … until the price is known", async () => {
  fakeServer({ ...base, "GET /credits/rates": [500, { detail: "later" }], "GET /projects/9/storyboard": [200, [frame({ file_id: 40 })]] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Edit the prompt for clip c1" }));
  expect(screen.getByRole("button", { name: "Save and redraw · …" })).toBeInTheDocument();
});

test("a still being made for a frame (a Change it's) says Drawing… and the new still shows once it lands", async () => {
  const routes: Record<string, [number, unknown]> = { ...base, "GET /projects/9/storyboard": [200, [frame({ file_id: 40, drawing: true, change: { note: "night", status: "done", before: "a", after: "a night" } })]] };
  fakeServer(routes);
  open();
  const card = await screen.findByLabelText("Frame c1");
  expect(within(card).getByText("Drawing…")).toBeInTheDocument();
  routes["GET /projects/9/storyboard"] = [200, [frame({ file_id: 41, drawing: false, change: { note: "night", status: "done", before: "a", after: "a night" } })]];
  expect(await within(card).findByAltText("Still for clip c1", {}, { timeout: 5000 })).toHaveAttribute("src", "/api/files/41");
});

test("a still opens full size with the prompt Claude wrote", async () => {
  fakeServer({ ...base, "GET /projects/9/storyboard": [200, [frame({ file_id: 40 })]] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Open the still for clip c1" }));
  const box = await screen.findByRole("dialog", { name: "Clip c1 · shot 1.1" });
  expect(within(box).getByText("Mia in a cold blue kitchen")).toBeInTheDocument();
});

test("close to the budget an editor's paid button is off with the reason, and Reed's is the plain label", async () => {
  fakeServer({ ...base, "GET /projects/9": [200, { ...project, credits_used: 598, budget_credits: 600 }], "GET /projects/9/storyboard": [200, []] });
  open();
  const make = await screen.findByRole("button", { name: "Make storyboard · 6 credits" });
  expect(make).toBeDisabled();
  expect(screen.getByText("That's more than this video's budget.")).toBeInTheDocument();
  expect(screen.queryByText(/Ask Reed/)).toBeNull();
});

test("Reed near the budget can press the plain Make storyboard", async () => {
  fakeServer({ ...base, "GET /auth/me": [200, { ...editor, id: 1, role: "owner" }], "GET /projects/9": [200, { ...project, credits_used: 598, budget_credits: 600 }], "GET /projects/9/storyboard": [200, []] });
  open();
  expect(await screen.findByRole("button", { name: "Make storyboard · 6 credits" })).toBeEnabled();
});

test("Storyboard stays locked until there are shots", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/breakdown": [404, { detail: "none" }] });
  open("?stage=script");
  const steps = await screen.findByRole("list", { name: "Steps" });
  const storyboard = within(steps).getByRole("button", { name: "Storyboard" });
  expect(storyboard).toHaveAttribute("aria-disabled", "true");
  expect(storyboard).toHaveAccessibleDescription("Make the shots first");
});

test("after a reload, runs are recognised by their step and frame: frames being written, a still being drawn, one that failed", async () => {
  const job = (step: string, id: number, over: object = {}) => ({ id, kind: step === "storyboard" ? "write-claude" : "image", step, status: "running", credits: 3, project_id: 9, created_at: "2026-10-23T10:00:00Z", ...over });
  fakeServer({ ...base, "GET /projects/9/storyboard": [200, []], "GET /jobs": [200, [job("storyboard", 5)]] });
  open();
  expect(await screen.findByText("Writing your frames…")).toBeInTheDocument();
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
  fakeServer({
    ...base,
    "GET /projects/9/storyboard": [200, [frame({}), frame({ id: 2, clip_id: "c2" })]],
    "GET /jobs": [200, [job("frame", 6, { frame_id: 1 }), job("frame", 7, { frame_id: 2, status: "failed" })]],
  });
  open();
  expect(await within(await screen.findByLabelText("Frame c1")).findByText("Drawing…")).toBeInTheDocument();
  expect(within(screen.getByLabelText("Frame c2")).getByText("Didn't finish · credits returned")).toBeInTheDocument();
});

test("the storyboard stays locked while the shots have problems or are out of date, and a link to it lands on Shots", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, { ...breakdown, problems: ["Shot 1.2 is a loss moment but shows no fomo screen."] }] });
  open();
  expect(await screen.findByLabelText("Problems")).toBeInTheDocument(); // landed on the Shots step
  const steps = screen.getByRole("list", { name: "Steps" });
  const storyboard = within(steps).getByRole("button", { name: "Storyboard" });
  expect(storyboard).toHaveAttribute("aria-disabled", "true");
  expect(storyboard).toHaveAccessibleDescription("Fix the 1 problem in Shots first");
  expect(screen.getByRole("button", { name: "Next: Storyboard" })).toBeDisabled();
});

test("shots made for an older script also keep the storyboard locked", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, { ...breakdown, stale: true, script_version: 3 }] });
  open("?stage=shots");
  const steps = await screen.findByRole("list", { name: "Steps" });
  expect(within(steps).getByRole("button", { name: "Storyboard" })).toHaveAccessibleDescription("Make new shots first");
});

test("Redo storyboard says the stills already made will be dropped", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  fakeServer({ ...base, "GET /projects/9/storyboard": [200, [frame({ file_id: 40 }), frame({ id: 2, clip_id: "c2", file_id: 41 }), frame({ id: 3, clip_id: "c3" })]] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Redo storyboard · 6 credits" }));
  expect(confirm).toHaveBeenCalledWith("Replace these frames? The 2 stills you've made will be dropped.");
});

const withStill = (o: object = {}) => frame({ file_id: 40, ...o });

test("Approve marks a frame with a tick and a border; Undo approve takes it back; the header counts", async () => {
  const calls = fakeServer({
    ...base,
    "GET /projects/9/storyboard": [200, [withStill({ approved: true }), withStill({ id: 2, clip_id: "c2" })]],
    "POST /projects/9/storyboard/frames/2/approve": [200, withStill({ id: 2 })],
    "DELETE /projects/9/storyboard/frames/1/approve": [204, null],
  });
  open();
  expect(await screen.findByText(/2 frames · 1 approved/)).toBeInTheDocument();
  const first = screen.getByLabelText("Frame c1");
  expect(within(first).getByText("✓ Approved")).toBeInTheDocument();
  await userEvent.click(within(first).getByRole("button", { name: "Undo approve" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /projects/9/storyboard/frames/1/approve")).toBe(true));
  await userEvent.click(within(screen.getByLabelText("Frame c2")).getByRole("button", { name: "Approve" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/storyboard/frames/2/approve")).toBe(true));
});

test("a frame can't be approved while its breakdown has changed", async () => {
  fakeServer({ ...base, "GET /projects/9/storyboard": [200, [withStill({ stale: true })]] });
  open();
  expect(await within(await screen.findByLabelText("Frame c1")).findByRole("button", { name: "Approve" })).toBeDisabled();
});

test("Next: Clips waits until every frame is approved and says how many are left", async () => {
  fakeServer({ ...base, "GET /projects/9/storyboard": [200, [withStill({ approved: true }), withStill({ id: 2, clip_id: "c2" }), withStill({ id: 3, clip_id: "c3" })]] });
  open();
  const next = await screen.findByRole("button", { name: "Next: Clips" });
  expect(next).toBeDisabled();
  expect(next).toHaveAccessibleDescription("Approve every storyboard frame first (2 left)");
});

test("Redo asks what should change and sends it as the note for that render only", async () => {
  const calls = fakeServer({
    ...base,
    "GET /projects/9/storyboard": [200, [withStill({})]],
    "POST /projects/9/storyboard/frames/1/render": [201, { id: 11, kind: "image", step: "frame", frame_id: 1, status: "queued", credits: 3, project_id: 9 }],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Redo · 3 credits" }));
  await userEvent.type(screen.getByLabelText("What should change? (optional)"), "Warmer light");
  const redoButtons = screen.getAllByRole("button", { name: "Redo · 3 credits" }); // the opener, then the form's button
  await userEvent.click(redoButtons[1]);
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/storyboard/frames/1/render")?.body).toEqual({ note: "Warmer light" }));
});

test("an editor with room for one still but not all of them gets Make all stills off, with the reason shown", async () => {
  fakeServer({
    ...base,
    "GET /projects/9": [200, { ...project, credits_used: 597, budget_credits: 600 }],
    "GET /projects/9/storyboard": [200, [frame({ file_id: 40 }), frame({ id: 2, clip_id: "c2" }), frame({ id: 3, clip_id: "c3" })]],
  });
  open();
  const all = await screen.findByRole("button", { name: "Make all stills · 6 credits" });
  expect(all).toBeDisabled();
  expect(screen.getByText("That's more than this video's budget.")).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: /^Make still · 3 credits/ })[0]).toBeEnabled();
});

test("a frame whose character has no approved sheet says so, links to the character, and is skipped by Make all stills", async () => {
  const withMia = { ...breakdown, breakdown: { ...breakdown.breakdown, scenes: [{ id: 1, heading: "KITCHEN", look: "", shots: [{ id: "1.1", character_ids: ["char:4"], place_id: null }, { id: "2.1", character_ids: [], place_id: null }] }] } };
  fakeServer({
    ...base,
    "GET /projects/9/breakdown": [200, withMia],
    "GET /library/character": [200, [{ id: 4, name: "Mia", image_file_ids: [], sheet_status: "needs_approval" }]],
    "GET /projects/9/storyboard": [200, [frame({}), frame({ id: 2, clip_id: "c2", shot_id: "2.1", reference_ids: [] })]],
  });
  open();
  const first = await screen.findByLabelText("Frame c1");
  expect(await within(first).findByText(/Mia needs an approved sheet\./)).toBeInTheDocument();
  expect(within(first).getByRole("link", { name: "Open Mia" })).toHaveAttribute("href", expect.stringContaining("/b/1/library/characters/4?back=%2Fb%2F1%2Fprojects%2F9%3Fstage%3Dstoryboard"));
  expect(within(first).getByRole("button", { name: /Make still/ })).toBeDisabled();
  expect(within(screen.getByLabelText("Frame c2")).getByRole("button", { name: /Make still/ })).toBeEnabled();
  expect(screen.getByText(/1 frame waits for a sheet \(Mia\)\./)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Make all stills · 3 credits" })).toBeInTheDocument(); // only the frame that can be made
});

test("a failed frames run says so, nothing was charged, and the one Make button below asks again", async () => {
  const calls = fakeServer({
    ...base,
    "GET /projects/9/storyboard": [200, []],
    "GET /jobs": [200, [{ id: 31, kind: "write-claude", step: "storyboard", status: "failed", credits: 6, project_id: 9, created_at: new Date().toISOString() }]],
    "POST /projects/9/storyboard": [201, { id: 32, kind: "write-claude", step: "storyboard", status: "queued", credits: 6, project_id: 9 }],
  });
  open();
  expect(await screen.findByText("The frames didn't finish.")).toBeInTheDocument();
  expect(screen.queryByText("Writing your frames…")).toBeNull();
  expect(screen.getAllByRole("button", { name: /credits/ })).toHaveLength(1);
  await userEvent.click(screen.getByRole("button", { name: "Make storyboard · 6 credits" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/storyboard")).toBe(true));
});

test("after Redo storyboard the old frames are not shown while the new ones load, so none of them can be pressed", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  fakeServer({ ...base, "GET /projects/9/storyboard": [200, [frame({ id: 1, file_id: 40 })]], "POST /projects/9/storyboard": [201, { id: 7, kind: "write-claude", step: "storyboard", status: "queued", credits: 6, project_id: 9 }] });
  // The server replaces the frames when the run finishes; the new list is slow to arrive.
  const inner = (fetch as unknown as { getMockImplementation: () => (r: Request | string, i?: RequestInit) => Promise<Response> }).getMockImplementation();
  let release: () => void = () => {};
  const held = new Promise<void>((r) => (release = r));
  let asked = false;
  const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
  vi.stubGlobal("fetch", vi.fn(async (input: Request | string, init?: RequestInit) => {
    const req = input instanceof Request ? input : new Request(new URL(input, "http://x"), init);
    const path = new URL(req.url).pathname.replace(/^\/api/, "");
    if (req.method === "POST" && path === "/projects/9/storyboard") asked = true;
    if (asked && req.method === "GET" && path === "/jobs") return json([{ id: 7, kind: "write-claude", step: "storyboard", status: "succeeded", credits: 6, project_id: 9, created_at: new Date().toISOString() }]);
    if (asked && req.method === "GET" && path === "/projects/9/storyboard") {
      await held;
      return json([frame({ id: 5, file_id: 60 })]);
    }
    return inner!(req.clone(), init);
  }));
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Redo storyboard · 6 credits" }));
  // The run has finished but the new frames haven't come: the old ones are gone from the screen.
  expect(await screen.findByText("Writing your frames…")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^Redo · / })).toBeNull();
  release();
  expect(await screen.findByLabelText("Frame c1")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^Redo · / })).toBeInTheDocument();
});

test("stills that show the old cast say Out of date and Redraw N stills shows the price; a redrawn one says Redrawn", async () => {
  const calls = fakeServer({
    ...base,
    "GET /projects/9/storyboard": [200, [withStill({ still_stale: true }), withStill({ id: 2, clip_id: "c2", still_stale: true }), withStill({ id: 3, clip_id: "c3", redrawn: true })]],
    "POST /projects/9/storyboard/frames/1/render": [201, { id: 11, kind: "image", step: "frame", frame_id: 1, status: "queued", credits: 3, project_id: 9 }],
    "POST /projects/9/storyboard/frames/2/render": [201, { id: 12, kind: "image", step: "frame", frame_id: 2, status: "queued", credits: 3, project_id: 9 }],
  });
  open();
  expect(within(await screen.findByLabelText("Frame c1")).getByText("Out of date")).toBeInTheDocument();
  expect(within(screen.getByLabelText("Frame c3")).getByText("Redrawn")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Redraw 2 stills · 6 credits" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key.endsWith("/render")).length).toBe(2));
});

test("an editor past the video's budget is told why and can't redraw; the price shows first", async () => {
  fakeServer({
    ...base,
    "GET /projects/9": [200, { ...project, credits_used: 598, budget_credits: 600 }],
    "GET /projects/9/storyboard": [200, [withStill({ still_stale: true }), withStill({ id: 2, clip_id: "c2", still_stale: true })]],
  });
  open();
  const redraw = await screen.findByRole("button", { name: "Redraw 2 stills · 6 credits" });
  expect(redraw).toBeDisabled();
  expect(screen.getByText("That's more than this video's budget.")).toBeInTheDocument();
});
