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

test("a still opens full size with the prompt Claude wrote", async () => {
  fakeServer({ ...base, "GET /projects/9/storyboard": [200, [frame({ file_id: 40 })]] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Open the still for clip c1" }));
  const box = await screen.findByRole("dialog", { name: "Clip c1 · shot 1.1" });
  expect(within(box).getByText("Mia in a cold blue kitchen")).toBeInTheDocument();
});

test("paid buttons ask Reed when the project is close to its budget", async () => {
  fakeServer({ ...base, "GET /projects/9": [200, { ...project, credits_used: 598, budget_credits: 600 }], "GET /projects/9/storyboard": [200, []] });
  open();
  expect(await screen.findByRole("button", { name: "Ask Reed to approve · 6 credits" })).toBeInTheDocument();
});

test("Storyboard stays locked until there is a breakdown", async () => {
  fakeServer({ ...base, "GET /projects/9/breakdown": [404, { detail: "none" }] });
  open("?stage=script");
  const steps = await screen.findByRole("list", { name: "Stages" });
  expect(within(steps).getByRole("button", { name: /Storyboard/ })).toBeDisabled();
  expect(within(steps).getByRole("button", { name: /Storyboard/ })).toHaveAttribute("title", "Make the breakdown first");
});

test("after a reload, runs are recognised by their step: frames being written, and stills being drawn", async () => {
  const going = (step: string, id: number) => ({ id, kind: step === "storyboard" ? "write-claude" : "image", step, status: "running", credits: 3, project_id: 9, created_at: "2026-10-23T10:00:00Z" });
  fakeServer({ ...base, "GET /projects/9/storyboard": [200, []], "GET /jobs": [200, [going("storyboard", 5)]] });
  open();
  expect(await screen.findByText("Writing your frames…")).toBeInTheDocument();
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
  fakeServer({ ...base, "GET /projects/9/storyboard": [200, [frame({}), frame({ id: 2, clip_id: "c2" })]], "GET /jobs": [200, [going("frame", 6), going("frame", 7)]] });
  open();
  expect(await screen.findByText("Drawing 2 stills…")).toBeInTheDocument();
});
