import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";

const editor = { id: 2, email: "e@b.co", name: "Eli", role: "editor", workspace_id: 1 };
const project = {
  id: 9, brand_id: 1, name: "Mia buys the dip", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "",
  cast_ids: [], reference_file_id: null, estimate_credits: 30, budget_credits: 600, credits_used: 0, budget_pct: 0,
};
const script = { version: 5, source: "paste", words: 9, created_by_id: 2, created_at: "2026-10-23T10:00:00Z", text: "Mia scrolls." };
const breakdown = { id: 1, script_version: 5, source: "claude", stale: false, problems: [], breakdown: { hook: "Hook.", scenes: [{ id: 1, heading: "KITCHEN", look: "", shots: [] }], clips: [] } };
const frames = [
  { id: 1, clip_id: "c1", shot_id: "1.1", prompt: "p", reference_ids: [], problems: [], file_id: 40, approved: true, stale: false },
  { id: 2, clip_id: "c2", shot_id: "2.1", prompt: "p", reference_ids: [], problems: [], file_id: 41, approved: true, stale: false },
];
const clip = (o: object) => ({ id: 1, clip_id: "c1", seconds: 8, prompt: "Mia taps buy", references: [], problems: [], file_id: null, takes: [], picked_take_id: null, approved: false, stale: false, ...o });
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
  "GET /jobs": [200, []],
  "GET /projects/9/video": [404, { detail: "none" }],
  "GET /library/character": [200, []],
  "GET /library/place": [200, []],
  "GET /library/prop": [200, []],
  "GET /brands/1/screens": [200, []],
};

function open(query = "?stage=clips") {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[`/b/1/projects/9${query}`]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

test("Clips stay locked until every storyboard frame is approved", async () => {
  fakeServer({ ...base, "GET /projects/9/storyboard": [200, [{ ...frames[0], approved: false }, frames[1]]] });
  open("?stage=script");
  const steps = await screen.findByRole("list", { name: "Stages" });
  expect(within(steps).getByRole("button", { name: /Clips/ })).toBeDisabled();
  expect(within(steps).getByRole("button", { name: /Clips/ })).toHaveAttribute("title", "Approve every storyboard frame first");
});

test("with no clips it offers to write the clip prompts, with the cost", async () => {
  const calls = fakeServer({ ...base, "GET /projects/9/clips": [200, []], "POST /projects/9/clips/prompts": [201, { id: 7, kind: "write-claude", step: "clip_prompts", status: "queued", credits: 6, project_id: 9 }] });
  open();
  expect(await screen.findByText("No clips yet.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Write clip prompts · 6 credits" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/clips/prompts")).toBe(true));
  expect(await screen.findByText("Writing your clip prompts…")).toBeInTheDocument();
});

test("clip cards show their status in words, with the frame as the poster and costs from the video rate", async () => {
  fakeServer({
    ...base,
    "GET /projects/9/clips": [200, [clip({}), clip({ id: 2, clip_id: "c2", seconds: 6, file_id: 70, takes: [{ id: 5, number: 1, file_id: 70 }], picked_take_id: 5 })]],
  });
  open();
  const first = await screen.findByLabelText("Clip c1");
  expect(within(first).getByText("Not made")).toBeInTheDocument();
  expect(within(first).getByAltText("Storyboard frame for clip c1")).toHaveAttribute("src", "/api/files/40");
  expect(within(first).getByRole("button", { name: "Make clip · 24 credits" })).toBeInTheDocument(); // 8 s × 3
  const second = screen.getByLabelText("Clip c2");
  expect(within(second).getByText("Ready")).toBeInTheDocument();
  expect(within(second).getByRole("button", { name: "Make another take · 18 credits" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Make missing · 24 credits" })).toBeInTheDocument();
});

test("Make clip queues a take and the card says Rendering with the time", async () => {
  const calls = fakeServer({
    ...base,
    "GET /projects/9/clips": [200, [clip({})]],
    "POST /projects/9/clips/1/generate": [201, { id: 21, kind: "video", step: "clip_take", status: "running", credits: 24, project_id: 9, created_at: new Date().toISOString() }],
    "GET /jobs": [200, [{ id: 21, kind: "video", step: "clip_take", status: "running", credits: 24, project_id: 9, created_at: new Date().toISOString() }]],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Make clip · 24 credits" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/clips/1/generate")).toBe(true));
  expect(await within(screen.getByLabelText("Clip c1")).findByText(/Rendering/)).toBeInTheDocument();
});

test("takes can be picked, and Looks good approves the picked one", async () => {
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
  await userEvent.click(within(card).getByRole("button", { name: "✓ Looks good" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/clips/1/approve")).toBe(true));
  expect(within(card).getByRole("link", { name: "Download" })).toHaveAttribute("download", "Mia buys the dip-c1-take2.mp4");
});

test("the video waits for every approval, says how many are left, then stitches for free", async () => {
  fakeServer({
    ...base,
    "GET /projects/9/clips": [200, [clip({ approved: true, file_id: 70, takes: [{ id: 5, number: 1, file_id: 70 }], picked_take_id: 5 }), clip({ id: 2, clip_id: "c2", seconds: 6 })]],
  });
  open();
  expect(await screen.findByText("1 of 2 clips approved. Approve every clip to make the video (1 left).")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Make the video" })).toBeDisabled();
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
  const calls2 = fakeServer({
    ...base,
    "GET /projects/9/clips": [200, [clip({ approved: true, file_id: 70, takes: [{ id: 5, number: 1, file_id: 70 }], picked_take_id: 5 })]],
    "POST /projects/9/video": [201, { file_id: 90, take_ids: [5], out_of_date: false }],
  });
  open();
  const make = await screen.findByRole("button", { name: "Make the video" });
  await vi.waitFor(() => expect(make).toBeEnabled());
  await userEvent.click(make);
  await vi.waitFor(() => expect(calls2.some((c) => c.key === "POST /projects/9/video")).toBe(true));
});

test("a finished video can be played and downloaded, and says when it is out of date", async () => {
  fakeServer({
    ...base,
    "GET /projects/9/clips": [200, [clip({ approved: true, file_id: 70, takes: [{ id: 5, number: 1, file_id: 70 }], picked_take_id: 5 })]],
    "GET /projects/9/video": [200, { file_id: 90, take_ids: [4], out_of_date: true }],
  });
  open();
  const box = await screen.findByLabelText("The video");
  expect(within(box).getByRole("link", { name: "Download MP4" })).toHaveAttribute("download", "Mia buys the dip.mp4");
  expect(within(box).getByText(/Out of date/)).toBeInTheDocument();
  expect(within(box).getByRole("button", { name: "Make the video again" })).toBeInTheDocument();
});

test("the storyboard's Next: Clips opens this step once every frame is approved", async () => {
  fakeServer({ ...base, "GET /projects/9/clips": [200, []] });
  open("?stage=storyboard");
  const next = await screen.findByRole("button", { name: "Next: Clips →" });
  await vi.waitFor(() => expect(next).toBeEnabled());
  await userEvent.click(next);
  expect(await screen.findByText("No clips yet.")).toBeInTheDocument();
});
