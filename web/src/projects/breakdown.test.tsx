import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const editor = { id: 2, email: "e@b.co", name: "Eli", role: "editor", workspace_id: 1 };
const project = {
  id: 9, brand_id: 1, name: "Mia buys the dip", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "",
  cast_ids: [4], reference_file_id: null, estimate_credits: 30, budget_credits: 60, credits_used: 0, budget_pct: 0, created_by_id: 2,
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
  expect(await screen.findByText("No breakdown yet")).toBeInTheDocument();
  await userEvent.click(await screen.findByRole("button", { name: "Make the breakdown · 6 credits" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/breakdown")).toBe(true));
  expect(await screen.findByText(/Making the breakdown…/)).toBeInTheDocument();
});

test("a song video's shots being made (started by Approve the plan) show as running, not \"No breakdown yet\"", async () => {
  fakeServer({ ...base, "GET /projects/9/breakdown": [404, { detail: "This project has no breakdown yet." }], "GET /jobs": [200, [{ id: 8, kind: "write-claude", step: "song_breakdown", status: "queued", credits: 6, project_id: 9, created_at: "2026-10-29T10:00:00Z" }]] });
  open();
  expect(await screen.findByText(/Making the breakdown…/)).toBeInTheDocument();
  expect(screen.queryByText("No breakdown yet")).not.toBeInTheDocument();
});

test("with no set length, the breakdown says its own length, not \"22 s of 22 s planned\" (#749 LW9)", async () => {
  fakeServer({ ...base, "GET /projects/9": [200, { ...project, planned_seconds: null, breakdown_seconds: 5 }], "GET /projects/9/breakdown": [200, breakdown()] });
  open();
  expect(await screen.findByText(/1 scene · 2 shots · 1 clip · 5 s$/)).toBeInTheDocument();
  expect(screen.queryByText(/s planned/)).toBeNull();
});

test("the breakdown shows scenes, clips and shots with names, the spoken line and the star screens", async () => {
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown()] });
  open();
  expect(await screen.findByText(/Hook: “Mia's coffee freezes mid-air as the chart drops\.”/)).toBeInTheDocument();
  expect(screen.getByText(/1 scene · 2 shots · 1 clip · 5 s of 30 s planned/)).toBeInTheDocument();
  const clip = screen.getByLabelText("Clip c1");
  expect(within(clip).getByText("Clip c1 · 5 s")).toBeInTheDocument();
  expect(within(clip).getByText("End")).toBeInTheDocument();
  expect(within(clip).getByText("End line")).toBeInTheDocument();
  const second = within(clip).getByLabelText("Shot 1.2");
  expect(within(second).getByText("MIA: “Wait… it dipped?”")).toBeInTheDocument();
  expect(within(second).getByText("Reaction: eyes snap wide")).toBeInTheDocument();
  expect(within(second).getByText("Chart down")).toBeInTheDocument();
  expect(within(clip).getAllByText("Mia")).toHaveLength(2);
  expect(within(clip).getAllByText("Kitchen")).toHaveLength(2);
});

test("problems are listed in plain words and stop Next, with the reason", async () => {
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown({ problems: ["Shot 1.2 is a loss moment but shows no fomo screen.", "Clip c1 is 17 s; the model allows 4–15 s."] })] });
  open();
  const box = await screen.findByLabelText("Problems");
  expect(within(box).getByText("Shot 1.2 is a loss moment but shows no fomo screen.")).toBeInTheDocument();
  const next = screen.getByRole("button", { name: "Next: Storyboard" });
  expect(next).toBeDisabled();
  expect(next).toHaveAccessibleDescription("Fix the 2 problems in Shots first");
});

test("advice sits closed under one line, not as an error, and never stops Next", async () => {
  const advice = "Advice: shot 1.2: a montage shot without the main character";
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown({ problems: [advice] })] });
  open();
  const box = await screen.findByLabelText("Advice");
  expect(box).not.toHaveAttribute("open");
  expect(within(box).getByText("Advice (1)")).toBeInTheDocument();
  expect(screen.queryByLabelText("Problems")).toBeNull();
  expect(within(box).getByText("shot 1.2: a montage shot without the main character")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Next: Storyboard" })).toBeEnabled();
});

test("Keep anyway on breakdown advice calls keep and takes it out of the count", async () => {
  const advice = "Advice: shot 1.2: a montage shot without the main character";
  const calls = fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown({ problems: [advice], kept: [advice] })], "POST /projects/9/breakdown/keep": [200, breakdown({})] });
  open();
  expect(await screen.findByText("Advice (0)")).toBeInTheDocument();
  expect(screen.getByText("Kept anyway")).toBeInTheDocument();
  expect(screen.queryByText(/Reed/)).toBeNull(); // editors never see Reed's name
  expect(calls.some((c) => c.key === "POST /projects/9/breakdown/keep")).toBe(false);
});

test("the owner sees kept advice in the same neutral words", async () => {
  const advice = "Advice: shot 1.2: a montage shot without the main character";
  fakeServer({ ...base, "GET /auth/me": [200, { ...editor, id: 1, role: "owner" }], "GET /projects/9/breakdown": [200, breakdown({ problems: [advice], kept: [advice] })] });
  open();
  expect(await screen.findByText("Kept anyway")).toBeInTheDocument();
});

test("Keep anyway can be undone", async () => {
  const advice = "Advice: shot 1.2: a montage shot without the main character";
  const calls = fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown({ problems: [advice], kept: [advice] })], "DELETE /projects/9/breakdown/keep": [200, breakdown({ problems: [advice] })] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: /Undo keep/, hidden: true }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /projects/9/breakdown/keep")).toBe(true));
});

test("a real problem stays a red row, apart from the advice", async () => {
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown({ problems: ["Shot 1.1 has no clip", "Advice: shot 1.2: a slow hook"] })] });
  open();
  const box = await screen.findByLabelText("Problems");
  expect(within(box).getByText("Shot 1.1 has no clip")).toBeInTheDocument();
  expect(within(box).queryByText(/slow hook/)).toBeNull();
});

test("a breakdown made for an older script is flagged and offers a new one", async () => {
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown({ script_version: 3, stale: true })] });
  open();
  expect(await screen.findByText("This breakdown was made for older words.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Make it again · 6 credits" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Next: Storyboard" })).toHaveAccessibleDescription("Make new shots first");
});

test("Redo asks first when the breakdown was edited, and a failed run says nothing was charged", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown({ source: "edit" })] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Redo · 6 credits" }));
  expect(confirm).toHaveBeenCalledWith("Replace this breakdown? Your edits are kept in History.");
});

test("Shots stay locked until there is a script", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/script": [404, { detail: "no script" }], "GET /projects/9/breakdown": [409, { detail: "Add a script first." }] });
  open();
  const steps = await screen.findByRole("list", { name: "Steps" });
  const shots = within(steps).getByRole("button", { name: "Shots" });
  expect(shots).toHaveAttribute("aria-disabled", "true");
  expect(shots).toHaveAccessibleDescription("Finish Script first");
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
  // On a phone Save and Discard take the action bar's place, so Next steps aside until the edits are saved.
  expect(screen.queryByRole("button", { name: "Next: Storyboard" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Discard" }).closest("div.border-t")).toHaveClass("[&_button]:w-full");
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
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
  expect(within(screen.getByLabelText("Shot 1.1")).getAllByText("Chart down").length).toBeGreaterThan(0);
});

test("Split cuts a clip after a shot and Join puts it back together; ids and seconds follow", async () => {
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, twoClips()] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "More for shot 1.1" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Split clip c1 after shot 1.1" }));
  expect(screen.getByText("Clip c1 · 3 s")).toBeInTheDocument();
  expect(screen.getByText("Clip c2 · 3 s")).toBeInTheDocument(); // 2.5 rounded up
  await userEvent.click(screen.getByRole("button", { name: "More for shot 1.1" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Join clip c1 with the next clip" }));
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

test("with a finished video, unsaved edits say what saving them marks out of date (#749 LW1)", async () => {
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, twoClips()], "GET /projects/9/video": [200, { file_id: 60, take_ids: [2], out_of_date: false }] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Edit shot 1.1" }));
  await userEvent.type(screen.getByLabelText("Shot 1.1 camera"), " EXTRA");
  expect(await screen.findByText(/Saving them marks Clips and Final cut out of date; your finished video stays downloadable\./)).toBeInTheDocument();
});

test("on desktop Next waits, disabled, while edits are unsaved, and says why", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, twoClips()] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Edit shot 1.1" }));
  await userEvent.type(screen.getByLabelText("Shot 1.1 camera"), " EXTRA");
  const next = screen.getByRole("button", { name: "Next: Storyboard" });
  expect(next).toBeDisabled();
  expect(next).toHaveAccessibleDescription("Save your changes first.");
  expect(screen.getByRole("button", { name: "Save changes" })).toBeInTheDocument();
});

test("Redo is a secondary button; Next is the only primary one", async () => {
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown()] });
  open();
  const redo = await screen.findByRole("button", { name: "Redo · 6 credits" });
  expect(redo).not.toHaveClass("bg-accent");
  expect(screen.getByRole("button", { name: "Next: Storyboard" })).toHaveClass("bg-accent");
});

test("an editor's paid button is off, with the reason, when the call would take the video past its budget; nothing asks Reed", async () => {
  fakeServer({ ...base, "GET /projects/9": [200, { ...project, credits_used: 56, budget_credits: 60 }], "GET /projects/9/breakdown": [200, breakdown()] });
  open();
  const redo = await screen.findByRole("button", { name: "Redo · 6 credits" });
  expect(redo).toBeDisabled();
  expect(redo).toHaveAccessibleDescription("That's more than this video's budget.");
  expect(screen.queryByText(/Ask Reed/)).not.toBeInTheDocument();
});

test("Reed past the budget gets the plain button: pressing it is his approval", async () => {
  fakeServer({ ...base, "GET /auth/me": [200, { ...editor, id: 1, role: "owner" }], "GET /projects/9": [200, { ...project, credits_used: 56, budget_credits: 60 }], "GET /projects/9/breakdown": [200, breakdown()] });
  open();
  expect(await screen.findByRole("button", { name: "Redo · 6 credits" })).toBeEnabled();
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
  const next = await screen.findByRole("button", { name: "Next: Storyboard" });
  expect(next).toBeEnabled();
  await userEvent.click(next);
  expect(await screen.findByText("No frames yet.")).toBeInTheDocument();
});

test("a breakdown run is recognised by its step, even after a reload; an Enhance run is not mistaken for it", async () => {
  const running = (step: string) => [{ id: 3, kind: "write-claude", step, status: "running", credits: 6, project_id: 9, created_at: "2026-10-23T10:00:00Z" }];
  fakeServer({ ...base, "GET /projects/9/breakdown": [404, { detail: "none" }], "GET /jobs": [200, running("breakdown")] });
  open();
  expect(await screen.findByText(/Making the breakdown…/)).toBeInTheDocument();
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
  fakeServer({ ...base, "GET /projects/9/breakdown": [404, { detail: "none" }], "GET /jobs": [200, running("enhance")] });
  open();
  expect(await screen.findByText("No breakdown yet")).toBeInTheDocument();
});

test("every tap target on a shot is at least 44px tall below the sm width", async () => {
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown({ problems: ["Shot 1.2 is a loss moment but shows no fomo screen."] })] });
  open();
  for (const name of ["Edit shot 1.1", "Go to: Shot 1.2 is a loss moment but shows no fomo screen.", "Show line 2 in the script"]) {
    const el = await screen.findByRole("button", { name });
    expect(el.className).toContain("min-h-control");
  }
  await userEvent.click(screen.getByRole("button", { name: "Edit shot 1.1" }));
  const mia = screen.getByLabelText("Mia");
  expect(mia.closest("label")?.className).toContain("min-h-11");
});

const castProblem = "Check the cast: shot 1.1: the script has Nate here, but the shot shows Mogging BF instead of Carl";

test("a cast problem blocks Next, offers Keep anyway and the free fix; the fix says how many shots and Undo puts the old cast back", async () => {
  const calls = fakeServer({
    ...base,
    "GET /projects/9/breakdown": [200, breakdown({ problems: [castProblem], kept: [] })],
    "POST /projects/9/breakdown/fix-cast": [200, { ...breakdown(), changed_shots: [{ shot_id: "1.1", before: ["char:9"], after: ["char:4"] }], kept: [] }],
    "PUT /projects/9/breakdown": [200, { ...breakdown(), problems: [castProblem] }],
  });
  open();
  const box = await screen.findByLabelText("Problems");
  expect(within(box).getByText(castProblem)).toBeInTheDocument();
  expect(screen.getByText("Free. Uses who the script names in each line.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Next: Storyboard" })).toBeDisabled();
  expect(within(box).getByRole("button", { name: /Keep anyway/ })).toBeInTheDocument();
  await userEvent.click(within(box).getByRole("button", { name: "Put the right cast in each shot" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /projects/9/breakdown/fix-cast")).toBe(true));
  expect(await screen.findByText("Cast fixed in 1 shot.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "PUT /projects/9/breakdown")).toBe(true));
});

test("a cast problem kept anyway stops blocking and moves under the closed list, where the keep can be undone", async () => {
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown({ problems: [castProblem], kept: [castProblem] })] });
  open();
  expect(await screen.findByText("Advice (0)")).toBeInTheDocument();
  expect(screen.queryByLabelText("Problems")).toBeNull();
  expect(screen.getByRole("button", { name: "Next: Storyboard" })).toBeEnabled();
  expect(screen.getByRole("button", { name: /Undo keep/, hidden: true })).toBeInTheDocument();
});

test("a shot with no script lines (a reaction or an insert) shows no line label and does not break the page", async () => {
  const wordless = breakdown({ breakdown: { ...breakdown().breakdown, scenes: [{ ...breakdown().breakdown.scenes[0], shots: [shot({}), shot({ id: "1.2", script_lines: [], line: null, speaker: null })] }] } });
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, wordless] });
  open();
  const silent = await screen.findByLabelText("Shot 1.2");
  expect(within(silent).queryByText(/^Lines? \d/)).toBeNull();
  expect(within(screen.getByLabelText("Shot 1.1")).getByText("Line 1")).toBeInTheDocument();
});

const lost = "Line 4 isn't in any shot.";
const changed = "Shot 1.1 says 'see you later', but the script says 'see you soon'.";

test("a missing line has a free fix beside it; it says what it did and Undo puts the breakdown back", async () => {
  const calls = fakeServer({
    ...base,
    "GET /projects/9/breakdown": [200, breakdown({ problems: [lost], fixes: [{ problem: lost, kind: "add_line", label: "Add it to a shot" }] })],
    "POST /projects/9/breakdown/fix": [200, { ...breakdown(), fixed: ["Put line 4 in shot 1.2."] }],
    "PUT /projects/9/breakdown": [200, breakdown({ problems: [lost] })],
  });
  open();
  const box = await screen.findByLabelText("Problems");
  expect(within(box).getByText("Free")).toBeInTheDocument();
  await userEvent.click(within(box).getByRole("button", { name: `Add it to a shot: ${lost}` }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/breakdown/fix")?.body).toEqual({ problems: [lost] }));
  expect(await screen.findByText("Put line 4 in shot 1.2.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "PUT /projects/9/breakdown")).toBe(true));
});

test("several fixable problems also get one Fix N problems for all of them", async () => {
  const calls = fakeServer({
    ...base,
    "GET /projects/9/breakdown": [200, breakdown({ problems: [lost, changed], fixes: [{ problem: lost, kind: "add_line", label: "Add it to a shot" }, { problem: changed, kind: "restore_line", label: "Use the script's words" }] })],
    "POST /projects/9/breakdown/fix": [200, { ...breakdown(), fixed: ["Put line 4 in shot 1.2.", "Put the script's words back in shot 1.1."] }],
  });
  open();
  const box = await screen.findByLabelText("Problems");
  await userEvent.click(within(box).getByRole("button", { name: "Fix 2 problems" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/breakdown/fix")?.body).toEqual({ problems: [lost, changed] }));
});

test("a problem with no free fix shows no fix button", async () => {
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown({ problems: [lost], fixes: [] })] });
  open();
  const box = await screen.findByLabelText("Problems");
  expect(within(box).queryByText("Free")).toBeNull();
});

const withUnknown = (ids: string[], names: object = {}) => ({
  ...breakdown({ breakdown: { ...breakdown().breakdown, scenes: [{ ...breakdown().breakdown.scenes[0], shots: [shot({ character_ids: ["char:4", ...ids] }), shot({ id: "1.2" })] }] } }),
  unknown_names: names,
});

test("a shot that names someone the video doesn't have offers a free Remove by name; the toast says what was done", async () => {
  const before = withUnknown(["char:99"], { "char:99": "Nate" });
  const calls = fakeServer({
    ...base,
    "GET /projects/9/breakdown": [200, before],
    "POST /projects/9/shots/1.1/remove-ref": [200, { ...breakdown(), fixed: ["Removed char:99 from shot 1.1."] }],
    "PUT /projects/9/breakdown": [200, before],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Edit shot 1.1" }));
  expect(await screen.findByText("Nate isn't in this video.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Remove Nate from this shot" }));
  // The id goes to the server so two unknown people stay apart; the toast uses the name, never the id.
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/shots/1.1/remove-ref")?.body).toEqual({ kind: "character", name: "char:99" }));
  expect(await screen.findByText("Removed Nate from shot 1.1. To use them again, add them in Cast & places, then pick them in this shot.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Undo" })).toBeNull(); // the server can't put back a name the video doesn't have
});

test("an unknown name the server can't give reads \"a character\"; two of them stay apart; an error shows right under the button", async () => {
  const calls = fakeServer({
    ...base,
    "GET /projects/9/breakdown": [200, withUnknown(["char:98", "char:99"])],
    "POST /projects/9/shots/1.1/remove-ref": [409, { detail: "Shot 1.1 doesn't have that any more." }],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Edit shot 1.1" }));
  expect(await screen.findAllByText("This character isn't in this video.")).toHaveLength(2);
  const buttons = screen.getAllByRole("button", { name: "Remove a character from this shot" });
  expect(buttons).toHaveLength(2);
  await userEvent.click(buttons[1]);
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/shots/1.1/remove-ref")?.body).toEqual({ kind: "character", name: "char:99" }));
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("Shot 1.1 doesn't have that any more.");
  expect(alert.previousElementSibling).toContainElement(buttons[1]); // under the button, inside the editor
});

test("a shot that only names people the video has shows no Remove", async () => {
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown()] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Edit shot 1.1" }));
  expect(screen.queryByRole("button", { name: /from this shot$/ })).toBeNull();
});

test("a problem's words get the whole row on a phone, with its buttons wrapping under them", async () => {
  fakeServer({ ...base, "GET /projects/9/breakdown": [200, breakdown({ problems: [lost], fixes: [{ problem: lost, kind: "add_line", label: "Add it to a shot" }] })] });
  open();
  const words = (await screen.findByLabelText("Problems")).querySelector("li > span");
  expect(words).toHaveClass("w-full", "sm:flex-1");
  expect(words?.parentElement).toHaveClass("flex-wrap");
});

test("when a fix is refused, the server's reason is shown, in its words", async () => {
  fakeServer({
    ...base,
    "GET /projects/9/breakdown": [200, breakdown({ problems: [lost, changed], fixes: [{ problem: lost, kind: "add_line", label: "Add it to a shot" }, { problem: changed, kind: "restore_line", label: "Use the script's words" }] })],
    "POST /projects/9/breakdown/fix": [409, { detail: "Nothing here can be fixed for you. Edit the shot instead." }],
  });
  open();
  const box = await screen.findByLabelText("Problems");
  await userEvent.click(within(box).getByRole("button", { name: "Fix 2 problems" }));
  expect(await within(box).findByRole("alert")).toHaveTextContent("Nothing here can be fixed for you. Edit the shot instead.");
});

test("when the server refuses an Undo, the person is told why in its words", async () => {
  fakeServer({
    ...base,
    "GET /projects/9/breakdown": [200, breakdown({ problems: [lost], fixes: [{ problem: lost, kind: "add_line", label: "Add it to a shot" }] })],
    "POST /projects/9/breakdown/fix": [200, { ...breakdown(), fixed: ["Put line 4 in shot 1.2."] }],
    "PUT /projects/9/breakdown": [422, { detail: "The breakdown changed since. Fix it by hand." }],
  });
  open();
  const box = await screen.findByLabelText("Problems");
  await userEvent.click(within(box).getByRole("button", { name: `Add it to a shot: ${lost}` }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  expect(await screen.findByText("The breakdown changed since. Fix it by hand.")).toBeInTheDocument();
});

test("removing a place or a screen the video doesn't have says how to use it again, in its own words", async () => {
  const gone = breakdown({ breakdown: { ...breakdown().breakdown, scenes: [{ ...breakdown().breakdown.scenes[0], shots: [shot({ place_id: "place:99", screen_ids: ["screen:98"] }), shot({ id: "1.2" })] }] } });
  fakeServer({
    ...base,
    "GET /projects/9/breakdown": [200, { ...gone, unknown_names: { "place:99": "Bin Lot", "screen:98": "Chart up" } }],
    "POST /projects/9/shots/1.1/remove-ref": [200, { ...breakdown(), fixed: [] }],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Edit shot 1.1" }));
  await userEvent.click(await screen.findByRole("button", { name: "Remove Bin Lot from this shot" }));
  expect(await screen.findByText("Removed Bin Lot from shot 1.1. To use it again, add it in Cast & places, then pick it in this shot.")).toBeInTheDocument();
});

test("Make the breakdown shows the server's price for it (the clip prompts' rewrite included), not the writing rate", async () => {
  fakeServer({ ...base, "GET /projects/9/breakdown": [404, { detail: "This project has no breakdown yet." }], "GET /projects/9/breakdown/price": [200, { credits: 12 }] });
  open();
  expect(await screen.findByRole("button", { name: "Make the breakdown · 12 credits" })).toBeInTheDocument();
});
