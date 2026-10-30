import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";
import { editor } from "../test/people";

const project = {
  id: 9, brand_id: 1, name: "Mia buys the dip", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "",
  cast_ids: [], reference_file_id: null, estimate_credits: 30, budget_credits: 600, credits_used: 0, budget_pct: 0, created_by_id: 2,
};
const script = { version: 5, source: "paste", words: 9, created_by_id: 2, created_at: "2026-10-23T10:00:00Z", text: "Mia scrolls." };
const breakdown = { id: 1, script_version: 5, source: "claude", stale: false, problems: [], breakdown: { hook: "Hook.", scenes: [{ id: 1, heading: "KITCHEN", look: "", shots: [] }], clips: [] } };
const frames = [
  { id: 1, clip_id: "c1", shot_id: "1.1", prompt: "p", reference_ids: [], problems: [], file_id: 40, approved: true, stale: false },
  { id: 2, clip_id: "c2", shot_id: "2.1", prompt: "p", reference_ids: [], problems: [], file_id: 41, approved: true, stale: false },
];
const clip = (o: object) => ({ id: 1, clip_id: "c1", seconds: 8, prompt: "Mia taps buy", references: [], problems: [], file_id: null, takes: [], picked_take_id: null, approved: false, stale: false, take_credits: 24, inserts: [], ...o });
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, editor],
  "GET /brands": [200, [{ id: 1, name: "fomo", colours: [] }]],
  "GET /projects/9": [200, project],
  "GET /projects/9/script": [200, script],
  "GET /projects/9/breakdown": [200, breakdown],
  "GET /projects/9/storyboard": [200, frames],
  "GET /projects/9/script/suggestions": [200, []],
  "GET /projects/9/script/notes": [200, []],
  "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 6 }, { kind: "video", unit: "second", credits_per_unit: 3 }]],
  "GET /projects/9/clips/prompts/price": [200, { clip_ids: ["c1"], credits: 6 }], // a Claude call per few clips
  "GET /jobs": [200, []],
  "GET /projects/9/video": [404, { detail: "none" }],
  "GET /library/character": [200, []],
  "GET /library/place": [200, []],
  "GET /library/prop": [200, []],
  "GET /brands/1/screens": [200, []],
};

function open(query = "?stage=clips") {
  renderApp(`/b/1/projects/9${query}`);
}

afterEach(() => vi.unstubAllGlobals());

test("Clips stay locked until every storyboard frame is approved", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/storyboard": [200, [{ ...frames[0], approved: false }, frames[1]]] });
  open("?stage=script");
  const steps = await screen.findByRole("list", { name: "Steps" });
  const clips = within(steps).getByRole("button", { name: "Clips" });
  expect(clips).toHaveAttribute("aria-disabled", "true");
  expect(clips).toHaveAccessibleDescription(/Approve every storyboard frame first/);
});

test("with no clips it offers to write the clip prompts, with the cost", async () => {
  const calls = fakeServer({ ...base, "GET /projects/9/clips": [200, []], "POST /projects/9/clips/prompts": [201, { id: 7, kind: "write-claude", step: "clip_prompts", status: "queued", credits: 6, project_id: 9 }] });
  open();
  expect(await screen.findByText("No clips yet.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Write clip prompts · up to 6 credits" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/clips/prompts")).toBe(true));
  expect(await screen.findByText("Writing your clip prompts…")).toBeInTheDocument();
});

test("clip cards show their status in words, with the frame as the poster and costs from the server", async () => {
  fakeServer({
    ...base,
    "GET /projects/9/clips": [200, [clip({}), clip({ id: 2, clip_id: "c2", seconds: 6, file_id: 70, takes: [{ id: 5, number: 1, file_id: 70 }], picked_take_id: 5, take_credits: 18 })]],
  });
  open();
  const first = await screen.findByLabelText("Clip c1");
  expect(within(first).getByText("Not made")).toBeInTheDocument();
  expect(within(first).getByAltText("Storyboard frame for clip c1")).toHaveAttribute("src", "/api/files/40");
  expect(within(first).getByRole("button", { name: "Make clip · 24 credits" })).toBeInTheDocument(); // 8 s × 3
  const second = screen.getByLabelText("Clip c2");
  expect(within(second).getByText("Take 1 · ready to check")).toBeInTheDocument();
  expect(within(second).getByRole("button", { name: "Make another take · 18 credits" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Make missing · 24 credits" })).toBeInTheDocument();
});

test("Make clip queues a take", async () => {
  const calls = fakeServer({
    ...base,
    "GET /projects/9/clips": [200, [clip({})]],
    "POST /projects/9/clips/1/generate": [201, { id: 21, kind: "video", step: "clip_take", status: "running", credits: 24, project_id: 9, project_clip_id: 1, created_at: new Date().toISOString() }],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Make clip · 24 credits" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/clips/1/generate")).toBe(true));
});

test("advice on a clip is closed under Advice (1), and Keep anyway calls keep; Make clip stays open", async () => {
  const advice = "Advice: c1: shot 6: a quick cut names nobody";
  const calls = fakeServer({ ...base, "GET /projects/9/clips": [200, [clip({ problems: [advice] })]], "POST /projects/9/clips/1/keep": [200, clip({})] });
  open();
  const box = await screen.findByLabelText("Advice for c1");
  expect(box).not.toHaveAttribute("open");
  expect(within(box).getByText("Advice (1)")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Make clip · 24 credits" })).toBeEnabled();
  await userEvent.click(within(box).getByRole("button", { name: /Keep anyway/, hidden: true }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/clips/1/keep")?.body).toEqual({ problem: advice }));
});

test("after its free fix a clip's problem can be kept anyway: it then shows as Kept anyway, with Undo, and Make clip opens", async () => {
  const problem = "Shot 1.1's line isn't there once, word for word";
  const routes: Record<string, [number, unknown]> = { ...base, "GET /projects/9/clips": [200, [clip({ problems: [problem], free_fix_used: true })]], "POST /projects/9/clips/1/keep": [200, clip({})] };
  const calls = fakeServer(routes);
  open();
  expect(await screen.findByRole("button", { name: "Make clip · 24 credits" })).toBeDisabled();
  routes["GET /projects/9/clips"] = [200, [clip({ problems: [problem], kept: [problem], free_fix_used: true })]];
  await userEvent.click(screen.getByRole("button", { name: `Keep it anyway: ${problem}` }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/clips/1/keep")?.body).toEqual({ problem }));
  await vi.waitFor(() => expect(screen.getByRole("button", { name: "Make clip · 24 credits" })).toBeEnabled(), { timeout: 3000 });
  const box = screen.getByLabelText("Advice for c1");
  expect(within(box).getByText("Kept anyway")).toBeInTheDocument(); // never "Reed will see it"
  expect(within(box).getByRole("button", { name: `Undo keep: ${problem}`, hidden: true })).toBeInTheDocument();
});

test("a clip never written, its free fix used, points to the priced rewrite and can't be kept anyway", async () => {
  fakeServer({ ...base, "GET /projects/9/clips": [200, [clip({ prompt: "", problems: ["This clip's prompt wasn't written: the answer left it out."], free_fix_used: true })]] });
  open();
  expect(await screen.findByText("Rewrite this clip's prompt below writes it, at its price.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Rewrite this clip's prompt/ })).toBeInTheDocument(); // the way out, on this page too
  expect(screen.queryByRole("button", { name: /Keep it anyway/ })).toBeNull();
});

test("before its free fix a clip's problem has no Keep it anyway", async () => {
  fakeServer({ ...base, "GET /projects/9/clips": [200, [clip({ problems: ["Shot 1.1's line isn't there once, word for word"] })]] });
  open();
  expect(await screen.findByRole("button", { name: "Make clip · 24 credits" })).toBeDisabled();
  expect(screen.queryByRole("button", { name: /Keep it anyway/ })).not.toBeInTheDocument();
});

test("shot chips never show a raw id: an uncast slot shows its role with a hint", async () => {
  fakeServer({
    ...base,
    "GET /projects/9/assets": [200, [{ kind: "character", ref: "slot:28", role: "Nate", library_item_id: null, name: "", locked: false, sheet_status: "missing", ready: false }]],
    "GET /projects/9/storyboard": [200, [{ ...frames[0], reference_ids: ["slot:28", "frame:c1", "char:99"] }, frames[1]]],
  });
  open("?stage=storyboard");
  expect(await screen.findByText("Nate · cast at Assets")).toBeInTheDocument();
  expect(screen.getByText("First frame")).toBeInTheDocument();
  expect(screen.queryByText(/slot:|frame:|char:/)).toBeNull();
});

test("a take still rendering shows on its own clip after a reload, with the time", async () => {
  fakeServer({
    ...base,
    "GET /projects/9/clips": [200, [clip({}), clip({ id: 2, clip_id: "c2" })]],
    "GET /jobs": [200, [{ id: 21, kind: "video", step: "clip_take", status: "running", credits: 24, project_id: 9, project_clip_id: 2, created_at: new Date().toISOString() }]],
  });
  open();
  expect(await within(await screen.findByLabelText("Clip c2")).findByText(/Making…/)).toBeInTheDocument();
  expect(within(screen.getByLabelText("Clip c1")).getByText("Not made")).toBeInTheDocument();
});

test("a take that has waited a while to start says why, in plain words", async () => {
  fakeServer({
    ...base,
    "GET /projects/9/clips": [200, [clip({ id: 2, clip_id: "c2" })]],
    "GET /jobs": [200, [{ id: 21, kind: "video", step: "clip_take", status: "queued", credits: 24, project_id: 9, project_clip_id: 2, created_at: new Date().toISOString(), waiting: "This hasn't started yet: the service that makes it isn't taking work right now. It's charged only if it runs." }]],
  });
  open();
  expect(await within(await screen.findByLabelText("Clip c2")).findByText(/isn't taking work right now/)).toBeInTheDocument();
});

test('at 390 a waiting take says "Waiting to start · m:ss" from when it was asked', async () => {
  setViewport(390);
  fakeServer({
    ...base,
    "GET /projects/9/clips": [200, [clip({ id: 2, clip_id: "c2" })]],
    "GET /jobs": [200, [{ id: 21, kind: "video", step: "clip_take", status: "queued", credits: 24, project_id: 9, project_clip_id: 2, created_at: new Date(Date.now() - 125_000).toISOString() }]],
  });
  open();
  const card = await screen.findByLabelText("Clip c2");
  expect(await within(card).findByText((_, el) => el?.tagName === "SPAN" && /^Waiting to start · 2:0\d$/.test(el.textContent ?? ""))).toBeInTheDocument();
});

test("a take that is running counts Making… from when it started, not from when it was asked", async () => {
  setViewport(390);
  fakeServer({
    ...base,
    "GET /projects/9/clips": [200, [clip({ id: 2, clip_id: "c2" })]],
    "GET /jobs": [200, [{ id: 21, kind: "video", step: "clip_take", status: "running", credits: 24, project_id: 9, project_clip_id: 2, created_at: new Date(Date.now() - 600_000).toISOString(), started_at: new Date(Date.now() - 5_000).toISOString() }]],
  });
  open();
  const card = await screen.findByLabelText("Clip c2");
  expect(await within(card).findByText((_, el) => el?.tagName === "SPAN" && /^Making… 0:0\d$/.test(el.textContent ?? ""))).toBeInTheDocument();
});

test("takes can be picked, and Approve take approves the picked one", async () => {
  const calls = fakeServer({
    ...base,
    "GET /projects/9/clips": [200, [clip({ file_id: 71, takes: [{ id: 5, number: 1, file_id: 70 }, { id: 6, number: 2, file_id: 71 }], picked_take_id: 6 })]],
    "POST /projects/9/clips/1/takes/5/pick": [200, clip({})],
    "POST /projects/9/clips/1/approve": [200, clip({})],
  });
  open();
  const card = await screen.findByLabelText("Clip c1");
  expect(within(card).getByLabelText("Take 2")).toBeChecked();
  await userEvent.click(within(card).getByLabelText("Take 1"));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/clips/1/takes/5/pick")).toBe(true));
  await userEvent.click(within(card).getByRole("button", { name: "Approve take" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/clips/1/approve")).toBe(true));
  expect(within(card).getByRole("link", { name: "Download" })).toHaveAttribute("download", "Mia buys the dip-c1-take2.mp4");
});

test("the video waits for every approval, says how many are left, then stitches for free", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /projects/9/clips": [200, [clip({ approved: true, file_id: 70, takes: [{ id: 5, number: 1, file_id: 70 }], picked_take_id: 5 }), clip({ id: 2, clip_id: "c2", seconds: 6 })]],
  });
  open();
  const next = await screen.findByRole("button", { name: "Next: Final video" });
  expect(next).toBeDisabled();
  expect(next).toHaveAccessibleDescription("Approve every clip first (1 left)");
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
  const calls2 = fakeServer({
    ...base,
    "GET /projects/9/clips": [200, [clip({ approved: true, file_id: 70, takes: [{ id: 5, number: 1, file_id: 70 }], picked_take_id: 5 })]],
    "POST /projects/9/video": [201, { file_id: 90, take_ids: [5], out_of_date: false }],
  });
  open("?stage=final");
  const make = await screen.findByRole("button", { name: "Make the video" });
  await vi.waitFor(() => expect(make).toBeEnabled());
  await userEvent.click(make);
  await vi.waitFor(() => expect(calls2.some((c) => c.key === "POST /projects/9/video")).toBe(true));
});

test("a finished video is on the Final video step: it can be played and downloaded, and says when it is out of date", async () => {
  setViewport(1440);
  fakeServer({
    ...base,
    "GET /projects/9/clips": [200, [clip({ approved: true, file_id: 70, takes: [{ id: 5, number: 1, file_id: 70 }], picked_take_id: 5 })]],
    "GET /projects/9/video": [200, { file_id: 90, take_ids: [4], out_of_date: true }],
  });
  open("?stage=final");
  const box = await screen.findByLabelText("Final video");
  expect(within(box).getByRole("link", { name: "Download the older video" })).toHaveAttribute("download", "Mia buys the dip.mp4");
  expect(within(box).getByText("Out of date", { selector: "span" })).toBeInTheDocument();
  expect(within(box).getByRole("button", { name: "Make the video again" })).toBeInTheDocument();
});

test("the storyboard's Next: Clips opens this step once every frame is approved", async () => {
  fakeServer({ ...base, "GET /projects/9/clips": [200, []] });
  open("?stage=storyboard");
  const next = await screen.findByRole("button", { name: "Next: Clips" });
  await vi.waitFor(() => expect(next).toBeEnabled());
  await userEvent.click(next);
  expect(await screen.findByText("No clips yet.")).toBeInTheDocument();
});

test("an edited script makes the shots stale, which closes Clips again even with every frame approved", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, { ...breakdown, stale: true, script_version: 3 }], "GET /projects/9/clips": [200, []] });
  open("?stage=clips");
  expect(await screen.findByRole("heading", { name: "Shots" })).toBeInTheDocument(); // landed on the first unfinished step
  const steps = screen.getByRole("list", { name: "Steps" });
  const clips = within(steps).getByRole("button", { name: "Clips" });
  expect(clips).toHaveAttribute("aria-disabled", "true");
  expect(clips).toHaveAccessibleDescription("Make new shots first");
});

test("shots with problems also keep Clips closed, and without a script the reason is the script", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, { ...breakdown, problems: ["Shot 1.2 shows no fomo screen."] }] });
  open("?stage=script");
  const steps = await screen.findByRole("list", { name: "Steps" });
  expect(within(steps).getByRole("button", { name: "Clips" })).toHaveAccessibleDescription("Fix the 1 problem in Shots first");
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
  fakeServer({ ...base, "GET /projects/9/script": [404, { detail: "none" }], "GET /projects/9/breakdown": [409, { detail: "Add a script first." }] });
  open("?stage=script");
  const steps2 = await screen.findByRole("list", { name: "Steps" });
  expect(within(steps2).getByRole("button", { name: "Clips" })).toHaveAccessibleDescription("Finish Script first");
});

test("Needs a change sends what's wrong with the next take, and the price is the server's", async () => {
  const calls = fakeServer({
    ...base,
    "GET /projects/9/clips": [200, [clip({ file_id: 70, takes: [{ id: 5, number: 1, file_id: 70 }], picked_take_id: 5, take_credits: 30 })]],
    "POST /projects/9/clips/1/generate": [201, { id: 22, kind: "video", step: "clip_take", status: "queued", credits: 30, project_id: 9, project_clip_id: 1, created_at: new Date().toISOString() }],
  });
  open();
  const card = await screen.findByLabelText("Clip c1");
  expect(within(card).getByRole("button", { name: "Make another take · 30 credits" })).toBeInTheDocument();
  await userEvent.click(within(card).getByRole("button", { name: "Needs a change" }));
  await userEvent.type(within(card).getByLabelText("What's wrong?"), "Hand is too big");
  expect(within(card).queryByRole("button", { name: "Needs a change" })).not.toBeInTheDocument();
  await userEvent.click(within(card).getByRole("button", { name: "Redo · 30 credits" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/clips/1/generate")?.body).toEqual({ note: "Hand is too big" }));
});

test("Cancel closes the Needs a change form and brings the link back", async () => {
  fakeServer({
    ...base,
    "GET /projects/9/clips": [200, [clip({ file_id: 70, takes: [{ id: 5, number: 1, file_id: 70 }], picked_take_id: 5 })]],
  });
  open();
  const card = await screen.findByLabelText("Clip c1");
  await userEvent.click(within(card).getByRole("button", { name: "Needs a change" }));
  await userEvent.click(within(card).getByRole("button", { name: "Cancel" }));
  expect(within(card).queryByLabelText("What's wrong?")).not.toBeInTheDocument();
  expect(within(card).getByRole("button", { name: "Needs a change" })).toBeInTheDocument();
});

test("an approved clip can be un-approved", async () => {
  const calls = fakeServer({
    ...base,
    "GET /projects/9/clips": [200, [clip({ file_id: 70, takes: [{ id: 5, number: 1, file_id: 70 }], picked_take_id: 5, approved: true })]],
    "DELETE /projects/9/clips/1/approve": [200, clip({})],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Undo approval" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /projects/9/clips/1/approve")).toBe(true));
});

test("an insert has a Use the real image switch, off by default, that changes only the video", async () => {
  const insert = { shot_id: "1.2", asset_id: "screen:3", name: "Chart down", start: 2, end: 4, use_real_image: false };
  const calls = fakeServer({
    ...base,
    "GET /projects/9/clips": [200, [clip({ file_id: 70, takes: [{ id: 5, number: 1, file_id: 70 }], picked_take_id: 5, approved: true, inserts: [insert] }), clip({ id: 2, clip_id: "c2" })]],
    "PUT /projects/9/clips/1/inserts/1.2": [200, clip({ inserts: [{ ...insert, use_real_image: true }] })],
  });
  open();
  const card = await screen.findByLabelText("Clip c1");
  const sw = within(card).getByRole("switch", { name: /Use the real image · Chart down \(shot 1\.2\)/ });
  expect(sw).not.toBeChecked();
  expect(within(card).getByText("Free. Shows the real picture at that moment.")).toBeInTheDocument();
  expect(within(screen.getByLabelText("Clip c2")).queryByRole("switch")).not.toBeInTheDocument();
  await userEvent.click(sw);
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /projects/9/clips/1/inserts/1.2")?.body).toEqual({ use_real_image: true }));
  expect(within(card).getByText("Approved")).toBeInTheDocument(); // the approval stays
});

test("a clip whose shots use a character without an approved sheet is blocked, and Make missing skips it", async () => {
  const bd = { ...breakdown, breakdown: { ...breakdown.breakdown, scenes: [{ id: 1, heading: "K", look: "", shots: [{ id: "1.1", character_ids: ["char:4"], place_id: null }, { id: "2.1", character_ids: [], place_id: null }] }], clips: [{ id: "c1", shot_ids: ["1.1"] }, { id: "c2", shot_ids: ["2.1"] }] } };
  fakeServer({
    ...base,
    "GET /projects/9/breakdown": [200, bd],
    "GET /library/character": [200, [{ id: 4, name: "Mia", image_file_ids: [], sheet_status: "none" }]],
    "GET /projects/9/clips": [200, [clip({}), clip({ id: 2, clip_id: "c2" })]],
  });
  open();
  const first = await screen.findByLabelText("Clip c1");
  expect(await within(first).findByText(/Mia needs an approved sheet\./)).toBeInTheDocument();
  expect(within(first).getByRole("button", { name: /Make clip/ })).toBeDisabled();
  expect(within(screen.getByLabelText("Clip c2")).getByRole("button", { name: /Make clip/ })).toBeEnabled();
  expect(screen.getByText(/1 clip waits for a sheet \(Mia\)\./)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Make missing · 24 credits" })).toBeInTheDocument();
});

test("a take that finishes between two polls still shows up (the clips are fetched again)", async () => {
  const done = { id: 12, kind: "video", step: "clip_take", project_id: 9, project_clip_id: 1, status: "succeeded", credits: 24 };
  const routes = { ...base, "GET /projects/9/clips": [200, [clip({})]] as [number, unknown] };
  fakeServer(routes);
  const client = new QueryClient();
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/b/1/projects/9?stage=clips"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  await screen.findByLabelText("Clip c1");
  const calls = fakeServer({ ...routes, "GET /jobs": [200, [done]] }); // the job has finished by the next poll
  await client.invalidateQueries({ queryKey: ["jobs"] });
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "GET /projects/9/clips").length).toBeGreaterThanOrEqual(1));
});

test("a failed prompt run says so, nothing was charged, and the one Write button below tries again", async () => {
  const calls = fakeServer({
    ...base,
    "GET /projects/9/clips": [200, []],
    "GET /jobs": [200, [{ id: 31, kind: "write-claude", step: "clip_prompts", status: "failed", credits: 6, project_id: 9, created_at: new Date().toISOString(), error: "The answer ran out of room before it was finished. Nothing was charged; try again." }]],
    "POST /projects/9/clips/prompts": [201, { id: 32, kind: "write-claude", step: "clip_prompts", status: "queued", credits: 6, project_id: 9 }],
  });
  open();
  expect(await screen.findByText("The clip prompts didn't finish.")).toBeInTheDocument();
  expect(screen.getByText(/ran out of room before it was finished\. Nothing was charged/)).toBeInTheDocument(); // the cause
  expect(screen.queryByText("Writing your clip prompts…")).toBeNull();
  // One paid button, not two: the banner only says what happened.
  expect(screen.getAllByRole("button", { name: /credits/ })).toHaveLength(1);
  await userEvent.click(screen.getByRole("button", { name: "Write clip prompts · up to 6 credits" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/clips/prompts")).toBe(true));
});

test("a refused take says why, and after two refusals the card warns before the next paid take", async () => {
  const why = "The video model thinks this clip looks too much like someone else's character or video. Try another look for Mom, or use Change this… on the opening shot. Nothing was charged.";
  const warning = "The last two takes of this clip were refused: the video model thought they looked too much like someone else's character or video. Change the look or the opening shot first, or this take may be refused too.";
  fakeServer({
    ...base,
    "GET /projects/9/clips": [200, [clip({ take_warning: warning })]],
    "GET /jobs": [200, [{ id: 40, kind: "video", step: "clip_take", status: "failed", credits: 5, project_id: 9, project_clip_id: 1, created_at: new Date().toISOString(), error: why }]],
  });
  open();
  expect(await screen.findByText(why)).toBeInTheDocument();
  expect(screen.getByText(warning)).toBeInTheDocument();
});

test("pressing Approve take shows Approved with Undo approval at once, before the server answers", async () => {
  fakeServer({ ...base, "GET /projects/9/clips": [200, [clip({ file_id: 70, takes: [{ id: 5, number: 1, file_id: 70 }], picked_take_id: 5 })]] });
  const faked = globalThis.fetch;
  let release: (r: Response) => void = () => {};
  const waiting = new Promise<Response>((resolve) => (release = resolve));
  vi.stubGlobal("fetch", (input: Request | string, init?: RequestInit) => {
    const req = input instanceof Request ? input : new Request(new URL(input, "http://x"), init);
    return `${req.method} ${new URL(req.url).pathname}`.endsWith("POST /api/projects/9/clips/1/approve") ? waiting : faked(input, init);
  });
  open();
  const card = await screen.findByLabelText("Clip c1");
  await userEvent.click(within(card).getByRole("button", { name: "Approve take" }));
  expect(await within(card).findByRole("button", { name: "Undo approval" })).toBeInTheDocument();
  expect(within(card).getByText("Approved")).toBeInTheDocument();
  release(new Response(JSON.stringify({ detail: "Pick a take first." }), { status: 409, headers: { "content-type": "application/json" } }));
  expect(await within(card).findByRole("button", { name: "Approve take" })).toBeInTheDocument(); // refused: back as it was
});

test("a grey Make clip always says why, on the line under it", async () => {
  fakeServer({ ...base, "GET /projects/9/clips": [200, [clip({ problems: ["The prompt names no camera."] })]] });
  open();
  const card = await screen.findByLabelText("Clip c1");
  const make = within(card).getByRole("button", { name: "Make clip · 24 credits" });
  expect(make).toBeDisabled();
  expect(make).toHaveAccessibleDescription("Fix the problems above first.");
});

test("a failed newest take never turns a card with a good picked take red, and never says Ask the owner", async () => {
  fakeServer({
    ...base,
    "GET /projects/9/clips": [200, [clip({ file_id: 70, takes: [{ id: 5, number: 1, file_id: 70 }], picked_take_id: 5 })]],
    "GET /jobs": [200, [{ id: 40, kind: "video", step: "clip_take", status: "failed", credits: 5, project_id: 9, project_clip_id: 1, created_at: new Date().toISOString(), error: "The service couldn't finish this. Ask the owner for details." }]],
  });
  open();
  const card = await screen.findByLabelText("Clip c1");
  expect(within(card).getByText("Take 1 · ready to check")).toBeInTheDocument();
  expect(within(card).getByText("The service couldn't finish this. Credits returned; try again.")).toBeInTheDocument();
  expect(within(card).queryByText(/Ask the owner/)).toBeNull();
});
