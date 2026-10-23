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
  cast_ids: [4], reference_file_id: null, estimate_credits: 30, budget_credits: 60, credits_used: 0, budget_pct: 0,
};
const script = { version: 5, source: "paste", words: 9, created_by_id: 2, created_at: "2026-10-23T10:00:00Z", text: "Mia scrolls her phone.\nMIA: Wait… it dipped?" };
const shot = (o: object) => ({
  id: "1.1", script_lines: [1], speaker: null, line: null, action: "Mia scrolls her phone, coffee in hand.", reaction: null, camera: "Wide, slow push-in",
  seconds: 3, character_ids: ["char:4"], place_id: "place:2", moment: null, screen_ids: [], ...o,
});
const breakdown = (o: object = {}) => ({
  id: 1, script_version: 5, source: "claude", stale: false, problems: [],
  breakdown: {
    hook: "Mia's coffee freezes mid-air as the chart drops.",
    scenes: [{ id: 1, heading: "INT. KITCHEN — MORNING", look: "Cold blue light.", shots: [shot({}), shot({ id: "1.2", script_lines: [2], speaker: "Mia", line: "Wait… it dipped?", reaction: "eyes snap wide", seconds: 2, moment: "loss", screen_ids: ["screen:3"] })] }],
    clips: [{ id: "c1", shot_ids: ["1.1", "1.2"], seconds: 5, seam: "end" }],
  },
  ...o,
});
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, editor],
  "GET /brands": [200, [{ id: 1, name: "fomo", colours: [] }]],
  "GET /projects/9": [200, project],
  "GET /projects/9/script": [200, script],
  "GET /projects/9/script/suggestions": [200, []],
  "GET /projects/9/script/notes": [200, []],
  "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 6 }]],
  "GET /jobs": [200, []],
  "GET /library/character": [200, [{ id: 4, name: "Mia", image_file_ids: [] }]],
  "GET /library/place": [200, [{ id: 2, name: "Kitchen", image_file_ids: [] }]],
  "GET /library/prop": [200, []],
  "GET /brands/1/screens": [200, [{ id: 3, name: "Chart down", file_id: 9, tags: [], default_for: ["loss"], brand_id: 1 }]],
};

function open() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/b/1/projects/9?stage=breakdown"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

test("with no breakdown it offers to make one and shows the cost", async () => {
  const calls = fakeServer({ ...base, "GET /projects/9/breakdown": [404, { detail: "This project has no breakdown yet." }], "POST /projects/9/breakdown": [201, { id: 8, kind: "write-claude", status: "queued", credits: 6, project_id: 9 }] });
  open();
  expect(await screen.findByText("No breakdown yet.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Make breakdown · 6 credits" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/breakdown")).toBe(true));
  expect(await screen.findByText("Breaking down your script…")).toBeInTheDocument();
});

test("the breakdown shows scenes, clips and shots with names, the spoken line and the star screens", async () => {
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown()] });
  open();
  expect(await screen.findByText(/Hook: “Mia's coffee freezes mid-air as the chart drops\.”/)).toBeInTheDocument();
  expect(screen.getByText("1 scene · 2 shots · 1 clip · 5 s (planned 30 s)")).toBeInTheDocument();
  const clip = screen.getByLabelText("Clip c1");
  expect(within(clip).getByText("Clip c1 · 5 s")).toBeInTheDocument();
  expect(within(clip).getByText("end")).toBeInTheDocument();
  const second = within(clip).getByLabelText("Shot 1.2");
  expect(within(second).getByText("MIA: “Wait… it dipped?”")).toBeInTheDocument();
  expect(within(second).getByText("Reaction: eyes snap wide")).toBeInTheDocument();
  expect(within(second).getByText("★ Chart down")).toBeInTheDocument();
  expect(within(clip).getAllByText("● Mia")).toHaveLength(2);
  expect(within(clip).getAllByText("⌂ Kitchen")).toHaveLength(2);
});

test("problems are listed in plain words and stop Next, with the reason", async () => {
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown({ problems: ["Shot 1.2 is a loss moment but shows no fomo screen.", "Clip c1 is 17 s; the model allows 4–15 s."] })] });
  open();
  const box = await screen.findByLabelText("Problems");
  expect(within(box).getByText("Shot 1.2 is a loss moment but shows no fomo screen.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Next: Storyboard →" })).toBeDisabled();
  expect(screen.getByText("Fix the 2 problems first.")).toBeInTheDocument();
});

test("a breakdown made for an older script is flagged and offers a new one", async () => {
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown({ script_version: 3, stale: true })] });
  open();
  expect(await screen.findByText("Made for script v3. The script is now v5.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Make a new breakdown · 6 credits" })).toBeInTheDocument();
  expect(screen.getByText("Make a new breakdown first.")).toBeInTheDocument();
});

test("Redo asks first when the breakdown was edited, and a failed run says nothing was charged", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown({ source: "edit" })] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Redo · 6 credits" }));
  expect(confirm).toHaveBeenCalledWith("Replace this breakdown? Your edits are kept in History.");
});

test("Breakdown stays locked until there is a script", async () => {
  fakeServer({ ...base, "GET /projects/9/script": [404, { detail: "no script" }], "GET /projects/9/breakdown": [409, { detail: "Add a script first." }] });
  open();
  const steps = await screen.findByRole("list", { name: "Stages" });
  expect(within(steps).getByRole("button", { name: /Breakdown/ })).toBeDisabled();
  expect(within(steps).getByRole("button", { name: /Breakdown/ })).toHaveAttribute("title", "Finish the script first");
});
