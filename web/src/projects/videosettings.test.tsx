import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { renderApp } from "../test/render";
import { editor } from "../test/people";

const project = {
  id: 9, brand_id: 1, name: "Bo tries salmon · B", planned_seconds: 30, status: "active", goal: "", platform: "TikTok", aspect_ratio: "9:16", format: "",
  cast_ids: [], reference_file_id: null, estimate_credits: 30, budget_credits: 600, credits_used: 0, budget_pct: 0, product_variants: {}, created_by_id: 2,
};
const settings = {
  look: "house", video_model: null, image_model: null, aspect_ratio: "9:16", product_variants: {}, language: "es",
  video_models: [
    { id: "seedance-2.5", name: "Seedance 2.5", credits_per_second: 1, lip_sync: true, default: true },
    { id: "seedance-2.0", name: "Seedance 2.0", credits_per_second: 0.6, lip_sync: false, default: false },
  ],
  image_models: [{ id: "nano-banana-pro", name: "Nano Banana Pro", credits_per_still: 1.2, default: true }],
  shapes: ["9:16", "1:1"],
  flavours: { bag: ["Chicken", "Peanut butter"] },
};
const looks = [
  { id: "house", name: "House", blurb: "", on: true, sample_still_id: null },
  { id: "disney-pixar", name: "Disney Pixar", blurb: "", on: true, sample_still_id: null },
  { id: "noir", name: "Noir", blurb: "", on: false, sample_still_id: null },
];
const preview = { to_finish_credits: 30, was_credits: 24, stills_out_of_date: 0, clips_out_of_date: 2, sung_to_broll: 3, over_budget: false, reason: null };
const base: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, editor],
  "GET /brands": [200, [{ id: 1, name: "Iron Paws", colours: [] }]],
  "GET /projects/9": [200, project],
  "GET /projects/9/script": [200, { version: 5, source: "paste", words: 9, created_by_id: 2, created_at: "2026-10-23T10:00:00Z", text: "Bo eats." }],
  "GET /projects/9/breakdown": [200, { id: 1, script_version: 5, source: "claude", stale: false, problems: [], breakdown: { hook: "Hook.", scenes: [], clips: [] } }],
  "GET /projects/9/storyboard": [200, []],
  "GET /projects/9/clips": [200, []],
  "GET /projects/9/video": [404, { detail: "none" }],
  "GET /projects/9/assets": [200, []],
  "GET /jobs": [200, []],
  "GET /looks": [200, looks],
  "GET /projects/9/settings": [200, settings],
  "POST /projects/9/settings/preview": [200, preview],
  "POST /projects/9/settings": [200, { settings, was: { video_model: null } }],
};

function open(query = "?step=plan") {
  renderApp(`/b/1/videos/9${query}`);
}
afterEach(() => vi.unstubAllGlobals());

test("the Video settings row shows each choice and its price, and the language read only from the script (flows VS1)", async () => {
  setViewport(1440);
  fakeServer(base);
  open();
  const row = await screen.findByRole("region", { name: "Video settings" });
  expect(within(row).getByRole("button", { name: /Shape 9:16/ })).toBeInTheDocument();
  expect(within(row).getByRole("button", { name: /Video model Auto/ })).toHaveAttribute("title", "1 credit a second"); // S-gaps-05 V1: the price in the picker
  expect(within(row).getByRole("button", { name: /Pictures Auto/ })).toHaveAttribute("title", "1.2 credits a still");
  expect(within(row).getByRole("button", { name: /Flavour Chicken/ })).toBeInTheDocument(); // the bag is on its default
  expect(within(row).getByRole("button", { name: /Style House/ })).toBeInTheDocument();
  expect(within(row).getByTitle("From the script")).toHaveTextContent("Language Spanish");
  expect(within(row).queryByRole("button", { name: /Language/ })).toBeNull(); // read only
  expect(document.body.textContent).not.toMatch(/\$/);
});

test("a video made from a script shows its style locked (a lock, no picker), with no picker, at 390 and desktop (Reed's walk item 7)", async () => {
  for (const width of [1440, 390]) {
    setViewport(width);
    fakeServer({ ...base, "GET /projects/9": [200, { ...project, look_locked: true }] });
    const { unmount } = renderApp("/b/1/videos/9?step=plan");
    if (width === 390) await userEvent.click(await screen.findByRole("button", { name: /^Settings: / }));
    const where = width === 390 ? await screen.findByRole("dialog", { name: "Video settings" }) : await screen.findByRole("region", { name: "Video settings" });
    expect(within(where).getByTitle("Style is set on the script")).toHaveTextContent("Style House");
    expect(within(where).queryByRole("button", { name: /Look:/ })).toBeNull();
    expect(within(where).getByRole("button", { name: /Shape 9:16/ })).toBeInTheDocument(); // the others still switch
    unmount();
  }
});

test("a picker lists choices with prices, says No lip-sync", async () => {
  setViewport(1440);
  fakeServer(base);
  open();
  await userEvent.click(await screen.findByRole("button", { name: /Video model Auto/ }));
  const seedance = await screen.findByRole("button", { name: /Seedance 2.0/ });
  expect(seedance).toHaveTextContent("0.6 credits a second");
  expect(within(seedance).getByText("No lip-sync")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Auto \(Seedance 2.5\)/ })).toHaveAttribute("aria-pressed", "true");
});

test("the look picks from the existing look picker, where an off look is greyed for an editor; the switch sends just the look", async () => {
  setViewport(1440);
  const calls = fakeServer(base);
  open();
  await userEvent.click(await screen.findByRole("button", { name: /Style House/ }));
  expect(await screen.findByRole("heading", { name: "Noir" })).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Use this style" }).filter((b) => b.hasAttribute("disabled"))).toHaveLength(1);
  await userEvent.click(screen.getAllByRole("button", { name: "Use this style" })[0]);
  await screen.findByRole("alertdialog", { name: "Switch to Disney Pixar?" });
  expect(calls.find((c) => c.key === "POST /projects/9/settings/preview")?.body).toEqual({ look: "disney-pixar" });
});

test("a flavour switch sends just that product's pick", async () => {
  setViewport(1440);
  const calls = fakeServer(base);
  open();
  await userEvent.click(await screen.findByRole("button", { name: /Flavour Chicken/ }));
  await userEvent.click(await screen.findByRole("button", { name: /Peanut butter/ }));
  await screen.findByRole("alertdialog", { name: "Switch to Peanut butter?" });
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/settings/preview")?.body).toEqual({ product_variants: { bag: "Peanut butter" } }));
});

test("picking previews the switch: Sung to B-roll, what goes out of date and the new total; Switch applies it, and Undo puts it back", async () => {
  setViewport(1440);
  const calls = fakeServer(base);
  open();
  await userEvent.click(await screen.findByRole("button", { name: /Video model Auto/ }));
  await userEvent.click(await screen.findByRole("button", { name: /Seedance 2.0/ }));
  const ask = await screen.findByRole("alertdialog", { name: "Switch to Seedance 2.0?" });
  expect(await within(ask).findByText("Seedance 2.0 can't lip-sync. Your 3 Sung shots become B-roll (picture only).")).toBeInTheDocument();
  expect(within(ask).getByText(/2 clips already made stay as they are and show Out of date/)).toBeInTheDocument();
  expect(within(ask).getByText("To finish: about 30 credits (planned; was 24).")).toBeInTheDocument();
  expect(calls.find((c) => c.key === "POST /projects/9/settings/preview")?.body).toEqual({ video_model: "seedance-2.0" });
  await userEvent.click(within(ask).getByRole("button", { name: "Switch" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/settings")?.body).toEqual({ video_model: "seedance-2.0" }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /projects/9/settings").map((c) => c.body)).toContainEqual({ video_model: null, undo: true })); // `was` with undo, so it's never refused over the limit
});

test("past the budget a switch still goes through (later presses wait for the owner); only the cap stops it", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "POST /projects/9/settings/preview": [200, { ...preview, over_budget: true, reason: "Waiting for the owner's OK: this goes past the video's budget." }] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: /Video model Auto/ }));
  await userEvent.click(await screen.findByRole("button", { name: /Seedance 2.0/ }));
  const ask = await screen.findByRole("alertdialog", { name: "Switch to Seedance 2.0?" });
  const go = await within(ask).findByRole("button", { name: "Switch" });
  await vi.waitFor(() => expect(go).toBeEnabled());
  expect(calls.some((c) => c.key === "POST /projects/9/settings")).toBe(false);
});

test("on a finished video the warning that the final cut stays downloadable comes first", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /projects/9/video": [200, { file_id: 60, take_ids: [2], out_of_date: false }], "GET /projects/9/clips": [200, [{ id: 3, clip_id: "c1", seconds: 8, prompt: "p", references: [], problems: [], kept: [], file_id: 61, takes: [{ id: 2 }], picked_take_id: 2, approved: true, stale: false, take_credits: 24, inserts: [] }]] });
  open("?step=plan");
  await userEvent.click(await screen.findByRole("button", { name: /Shape 9:16/ }));
  await userEvent.click(await screen.findByRole("button", { name: "1:1" }));
  const ask = await screen.findByRole("alertdialog", { name: "Change to 1:1?" });
  const first = (await within(ask).findAllByText(/./, { selector: "p" }))[0];
  expect(first).toHaveTextContent(/^This video is finished\. Changing the shape puts 2 clips out of date; your current final cut stays downloadable until you make a new one\.$/);
});

test("on a phone the row is one line that opens a sheet with the settings", async () => {
  setViewport(390);
  fakeServer(base);
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Settings: 9:16 · Chicken · House · Auto · Auto" }));
  const sheet = await screen.findByRole("dialog", { name: "Video settings" });
  expect(within(sheet).getByRole("button", { name: /Video model Auto/ })).toBeInTheDocument();
  expect(within(sheet).getByTitle("From the script")).toHaveTextContent("Language Spanish");
});

test("one credit to finish says credit", async () => {
  setViewport(1440);
  fakeServer({ ...base, "POST /projects/9/settings/preview": [200, { ...preview, to_finish_credits: 1, sung_to_broll: 0, clips_out_of_date: 0 }] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: /Video model Auto/ }));
  await userEvent.click(await screen.findByRole("button", { name: /Seedance 2.0/ }));
  expect(await screen.findByText("To finish: about 1 credit (planned; was 24).")).toBeInTheDocument();
});

test("a look switch names the roles that need a new look in it (ST1)", async () => {
  setViewport(1440);
  fakeServer({ ...base, "POST /projects/9/settings/preview": [200, { ...preview, roles_needing_look: ["Nate", "Mia"], sung_to_broll: 0 }] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: /Style House/ }));
  await userEvent.click((await screen.findAllByRole("button", { name: "Use this style" }))[0]);
  const ask = await screen.findByRole("alertdialog", { name: "Switch to Disney Pixar?" });
  expect(await within(ask).findByText("Nate and Mia need a new look, made in Cast.")).toBeInTheDocument();
});

// One look per style: a video can be on a lane of a style ("paper-flat"). Its name shows, never the raw id; the picker offers
// the styles (one card each, #1139), with the lane's style In use.
const paper = { id: "paper", name: "Paper", blurb: "", on: true, sample_still_id: null, lanes: [] };
test("at 390, a video on a lane shows the lane's own name; the picker lists styles only, with its style In use", async () => {
  setViewport(390);
  fakeServer({ ...base, "GET /looks": [200, [...looks, { ...paper, lanes: [{ id: "paper-flat", name: "Paper · Flat Paper" }, { id: "paper-origami", name: "Paper · Origami" }] }]], "GET /projects/9/settings": [200, { ...settings, look: "paper-flat" }] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Settings: 9:16 · Chicken · Paper · Flat Paper · Auto · Auto" })); // the phone's one row
  await userEvent.click(within(await screen.findByRole("dialog", { name: "Video settings" })).getByRole("button", { name: /Style Paper · Flat Paper/ }));
  expect(await screen.findByRole("heading", { name: "Paper" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: /Paper · / })).toBeNull(); // lanes aren't offered
  const card = screen.getByRole("heading", { name: "Paper" }).closest("li")!;
  expect(within(card).getByText("In use")).toBeInTheDocument();
  expect(document.body.textContent).not.toContain("paper-flat");
});

test("a lane the looks list doesn't carry yet reads as its style and its words, never the raw id", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /looks": [200, [...looks, paper]], "GET /projects/9/settings": [200, { ...settings, look: "paper-flat" }] });
  open();
  expect(await screen.findByRole("button", { name: /Style Paper · Flat/ })).toBeInTheDocument();
  expect(document.body.textContent).not.toContain("paper-flat");
});

test("a presenter's video has a Presenter chip after the B-roll model: Auto (the style's pick), talks, corner or acts in L3's words; a switch sends just that, and Undo puts it back (S-gaps-05 V1, L3)", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /projects/9/settings": [200, { ...settings, presenter: null, presenter_now: "talks" }], "POST /projects/9/settings": [200, { settings, was: { presenter: null } }] });
  open();
  const row = await screen.findByRole("region", { name: "Video settings" });
  const chips = within(row).getAllByRole("button").map((b) => b.textContent);
  expect(chips.indexOf("Presenter Talks to camera")).toBe(chips.findIndex((t) => /^Video model/.test(t ?? "")) + 1);
  await userEvent.click(within(row).getByRole("button", { name: "Presenter Talks to camera" }));
  const panel = await screen.findByRole("dialog", { name: "Presenter" });
  const ways = within(panel).getAllByRole("button", { pressed: false }).concat(within(panel).getAllByRole("button", { pressed: true }));
  expect(within(panel).getByRole("button", { name: /^Auto \(Talks to camera\)/ })).toHaveAttribute("aria-pressed", "true"); // the style's start
  expect(ways.map((b) => b.textContent)).toEqual(expect.arrayContaining(["Talks to camera· HeyGen from one still, with B-roll laid over parts", "In a corner over the B-roll· HeyGen, keyed over the B-roll", "Acts in the story· Omni: moves and acts in the scenes"]));
  await userEvent.click(within(panel).getByRole("button", { name: /^In a corner over the B-roll/ }));
  const ask = await screen.findByRole("alertdialog", { name: "Switch to In a corner over the B-roll?" });
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/settings/preview")?.body).toEqual({ presenter: "corner" }));
  await userEvent.click(within(ask).getByRole("button", { name: "Switch" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/settings")?.body).toEqual({ presenter: "corner" }));
  expect(await screen.findByText(/Presenter changed/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /projects/9/settings").map((c) => c.body)).toContainEqual({ presenter: null, undo: true }));
});

test("a video switched to its own way offers Auto back, which sends null", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /projects/9/settings": [200, { ...settings, presenter: "corner", presenter_now: "corner" }] });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Presenter In a corner" }));
  const panel = await screen.findByRole("dialog", { name: "Presenter" });
  expect(within(panel).getByRole("button", { name: /^In a corner over the B-roll/ })).toHaveAttribute("aria-pressed", "true");
  await userEvent.click(within(panel).getByRole("button", { name: /^Auto/ }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /projects/9/settings/preview")?.body).toEqual({ presenter: null }));
});

test("on a phone the settings line and its sheet carry the presenter", async () => {
  setViewport(390);
  fakeServer({ ...base, "GET /projects/9/settings": [200, { ...settings, presenter: null, presenter_now: "acts" }] });
  open();
  const line = await screen.findByRole("button", { name: /^Settings: / });
  expect(line).toHaveTextContent("Acts in the story");
  await userEvent.click(line);
  const sheet = await screen.findByRole("dialog", { name: "Video settings" });
  expect(within(sheet).getByRole("button", { name: "Presenter Acts in the story" })).toBeInTheDocument();
});

test("a video with no presenter has no Presenter chip", async () => {
  setViewport(1440);
  fakeServer(base);
  open();
  const row = await screen.findByRole("region", { name: "Video settings" });
  expect(within(row).queryByRole("button", { name: /^Presenter/ })).toBeNull();
});
