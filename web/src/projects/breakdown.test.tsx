import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
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

const twoClips = () =>
  breakdown({
    breakdown: {
      hook: "Hook line.",
      scenes: [{ id: 1, heading: "INT. KITCHEN — MORNING", look: "Cold blue light.", shots: [shot({}), shot({ id: "1.2", script_lines: [2], seconds: 2.5, moment: "loss", screen_ids: ["screen:3"] })] }],
      clips: [{ id: "c1", shot_ids: ["1.1", "1.2"], seconds: 6, seam: "end" }],
    },
  });

test("editing a shot changes only the draft; Save sends the whole breakdown and says what is left", async () => {
  const calls = fakeServer({ ...base, "GET /projects/9/breakdown": [200, twoClips()], "PUT /projects/9/breakdown": [200, { ...twoClips(), source: "edit", problems: ["Clip c1 is 17 s; the model allows 4–15 s."] }] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Edit shot 1.1" }));
  const action = screen.getByLabelText("Shot 1.1 action");
  await userEvent.clear(action);
  await userEvent.type(action, "Mia sips her coffee");
  await userEvent.clear(screen.getByLabelText("Shot 1.1 seconds"));
  await userEvent.type(screen.getByLabelText("Shot 1.1 seconds"), "5");
  expect(screen.getByText("Clip c1 · 8 s")).toBeInTheDocument(); // 5 + 2.5 rounded up
  expect(screen.getByRole("button", { name: "Next: Storyboard →" })).toBeDisabled();
  expect(screen.getByText("Save your changes first.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "PUT /projects/9/breakdown")).toBe(true));
  const body = calls.find((c) => c.key === "PUT /projects/9/breakdown")?.body as { scenes: { shots: { id: string; action: string; seconds: number }[] }[]; clips: { seconds: number }[] };
  expect(body.scenes[0].shots[0]).toMatchObject({ action: "Mia sips her coffee", seconds: 5 });
  expect(body.clips[0].seconds).toBe(8);
  expect(await screen.findByText("Saved. 1 problem left.")).toBeInTheDocument();
});

test("the spoken words can't be edited, and the editor says where to change them", async () => {
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown()] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Edit shot 1.2" }));
  expect(screen.getByText("To change the words, edit the script.")).toBeInTheDocument();
  expect(screen.queryByLabelText(/Shot 1.2 (line|speaker)/)).not.toBeInTheDocument();
});

test("picking a moment adds the screens that are always used for it", async () => {
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, twoClips()] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Edit shot 1.1" }));
  await userEvent.selectOptions(screen.getByLabelText("Shot 1.1 moment"), "loss");
  expect(within(screen.getByLabelText("Shot 1.1")).getAllByText("★ Chart down").length).toBeGreaterThan(0);
});

test("Split cuts a clip after a shot and Join puts it back together; ids and seconds follow", async () => {
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, twoClips()] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Split clip c1 after shot 1.1" }));
  expect(screen.getByText("Clip c1 · 3 s")).toBeInTheDocument();
  expect(screen.getByText("Clip c2 · 3 s")).toBeInTheDocument(); // 2.5 rounded up
  await userEvent.click(screen.getByRole("button", { name: "Join clip c1 with the next clip" }));
  expect(screen.getByText("Clip c1 · 6 s")).toBeInTheDocument();
  expect(screen.queryByText(/Clip c2/)).not.toBeInTheDocument();
});

test("Go to scrolls to the shot or clip a problem names and outlines it", async () => {
  const scrolled = vi.fn();
  Element.prototype.scrollIntoView = scrolled;
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown({ problems: ["Shot 1.2 is a loss moment but shows no fomo screen.", "Clip c1 is 17 s; the model allows 4–15 s."] })] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Go to: Shot 1.2 is a loss moment but shows no fomo screen." }));
  expect(scrolled).toHaveBeenCalled();
  expect(document.getElementById("shot-1.2")).toHaveClass("outline");
});

test("Discard throws the draft away", async () => {
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, twoClips()] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Edit shot 1.1" }));
  await userEvent.type(screen.getByLabelText("Shot 1.1 camera"), " EXTRA");
  await userEvent.click(screen.getByRole("button", { name: "Discard" }));
  expect(screen.queryByLabelText("Unsaved changes")).not.toBeInTheDocument();
  expect(screen.queryByText(/EXTRA/)).not.toBeInTheDocument();
});

test("Redo is a secondary button; Next is the only primary one", async () => {
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown()] });
  open();
  const redo = await screen.findByRole("button", { name: "Redo · 6 credits" });
  expect(redo).not.toHaveClass("bg-accent");
  expect(screen.getByRole("button", { name: "Next: Storyboard →" })).toHaveClass("bg-accent");
});

test("a paid button asks Reed when the call would take the project past its budget", async () => {
  fakeServer({ ...base, "GET /projects/9": [200, { ...project, credits_used: 56, budget_credits: 60 }], "GET /projects/9/breakdown": [200, breakdown()] });
  open();
  expect(await screen.findByRole("button", { name: "Ask Reed to approve · 6 credits" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Redo · 6 credits" })).not.toBeInTheDocument();
});

test("'lines 2 ◂' lights those lines in the script, and a script line lights its shot", async () => {
  const scrolled = vi.fn();
  Element.prototype.scrollIntoView = scrolled;
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown()] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Show line 2 in the script" }));
  const lines = screen.getByRole("list", { name: "Script text" });
  const second = within(lines).getAllByRole("listitem")[1];
  expect(second).toHaveAttribute("data-hl", "true");
  expect(within(lines).getAllByRole("listitem")[0]).not.toHaveAttribute("data-hl");
  // The other way: pick a script line, and the shot that covers it is lit.
  await userEvent.click(within(lines).getByRole("button", { name: "Show line 2 in the breakdown" }));
  expect(screen.getByLabelText("Shot 1.2")).toHaveClass("bg-accent-soft");
  expect(screen.getByLabelText("Shot 1.1")).not.toHaveClass("bg-accent-soft");
  expect(scrolled).toHaveBeenCalled();
});

describe("on a phone", () => {
  const original = window.matchMedia;
  beforeEach(() => {
    window.matchMedia = ((q: string) => ({ matches: q.includes("max-width: 639px"), addEventListener() {}, removeEventListener() {} })) as unknown as typeof window.matchMedia;
  });
  afterEach(() => {
    window.matchMedia = original;
  });

  test("problems collapse to one line that opens a sheet with Go to", async () => {
    fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown({ problems: ["Shot 1.2 is a loss moment but shows no fomo screen.", "Clip c1 is 17 s; the model allows 4–15 s."] })] });
    open();
    await userEvent.click(await screen.findByRole("button", { name: "Problems" }));
    const sheet = await screen.findByRole("dialog", { name: "Problems (2)" });
    expect(within(sheet).getByText("Clip c1 is 17 s; the model allows 4–15 s.")).toBeInTheDocument();
    await userEvent.click(within(sheet).getByRole("button", { name: "Go to: Shot 1.2 is a loss moment but shows no fomo screen." }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  test("Edit opens the shot in a sheet, and Split / Join live in a ⋯ menu", async () => {
    fakeServer({ ...base, "GET /projects/9/breakdown": [200, twoClips()] });
    open();
    await userEvent.click(await screen.findByRole("button", { name: "Edit shot 1.1" }));
    const sheet = await screen.findByRole("dialog", { name: "Shot 1.1" });
    await userEvent.type(within(sheet).getByLabelText("Shot 1.1 camera"), " EXTRA");
    await userEvent.click(within(sheet).getByRole("button", { name: "Done" }));
    expect(screen.getByText(/EXTRA/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "More for shot 1.1" }));
    await userEvent.click(screen.getByRole("menuitem", { name: "Split clip c1 after shot 1.1" }));
    expect(screen.getByText("Clip c2 · 3 s")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Join clip c1 with the next clip" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "More for shot 1.1" }));
    await userEvent.click(screen.getByRole("menuitem", { name: "Join clip c1 with the next clip" }));
    expect(screen.queryByText(/Clip c2/)).not.toBeInTheDocument();
  });
});

test("a clean breakdown opens the Storyboard step with Next", async () => {
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown()], "GET /projects/9/storyboard": [200, []] });
  open();
  const next = await screen.findByRole("button", { name: "Next: Storyboard →" });
  expect(next).toBeEnabled();
  await userEvent.click(next);
  expect(await screen.findByText("No frames yet.")).toBeInTheDocument();
});
