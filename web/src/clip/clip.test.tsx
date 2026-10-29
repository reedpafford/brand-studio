import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { BrandPieces } from "./BrandPieces";
import { elapsed } from "./History";
import { blockedReason, clipCredits, fit, mentionsMoment, type Model } from "./logic";
import { editor } from "../test/people";

const seedance = {
  id: "seedance-2.5", name: "Seedance 2.5", kind: "video", default: true, duration: { min: 4, max: 30 },
  resolutions: ["480p", "720p"], aspect_ratios: ["9:16", "1:1", "16:9"], max_reference_images: 4,
  credits_per_unit: { "480p": 1, "720p": 2.5 },
} as unknown as Model;
const older = { ...seedance, id: "seedance-2.0", name: "Seedance 2.0", default: false, duration: { min: 4, max: 15 }, resolutions: ["480p"], aspect_ratios: ["9:16"] } as unknown as Model;
const buy = { id: 3, name: "Buy BTC", file_id: 9, tags: [], default_for: ["buy-moment"], brand_id: 1 };

test("switching to a model with smaller limits says what changed", () => {
  const { settings, notes } = fit(older, { aspect: "16:9", duration: 25, resolution: "720p" });
  expect(settings).toEqual({ aspect: "9:16", duration: 15, resolution: "480p" });
  expect(notes[0]).toBe("Length set to 15s, the most Seedance 2.0 allows.");
});

test("cost is credits per second times length; moments match across spaces and dashes", () => {
  expect(clipCredits(seedance, { aspect: "9:16", duration: 8, resolution: "720p" })).toBe(20);
  expect(mentionsMoment("Mia taps to Buy Moment now", "buy-moment")).toBe(true);
  expect(mentionsMoment("Mia sells", "buy-moment")).toBe(false);
});

test("the first reason that applies wins", () => {
  const base = { prompt: "Mia taps buy on the app", loading: false, tooMany: false, maxRefs: 4, rendering: false };
  expect(blockedReason({ ...base, prompt: "short" })).toBe("Describe the clip (8 or more characters)");
  expect(blockedReason({ ...base, rendering: true })).toBe("A clip is already being made");
  expect(blockedReason({ ...base, noEstimate: true })).toBe("Working out the cost…");
  expect(blockedReason({ ...base, refused: "Nope." })).toBe("Nope.");
  expect(blockedReason(base)).toBeNull();
});

afterEach(() => vi.unstubAllGlobals());

const estimateOk = { credits: 9, needs_owner_approval: false, reason: "", auto_screen_ids: [], reference_images: 0, reference_videos: 0, reference_audios: 0 };
const studio: Record<string, [number, unknown]> = {
  "GET /auth/me": [200, editor],
  "GET /brands": [200, [{ id: 1, name: "fomo", colours: [] }]],
  "GET /models": [200, [seedance, older]],
  "GET /library/character": [200, [{ id: 4, name: "Mia", image_file_ids: [], sheet_status: "approved" }]],
  "GET /library/place": [200, []],
  "GET /library/prop": [200, []],
  "GET /brands/1/screens": [200, [buy]],
  "GET /credits/me": [200, { quick_clip_credits_used: 10, quick_clip_credits_allowed: 150 }],
  "GET /jobs": [200, []],
  "POST /clips/estimate": [200, estimateOk],
};
const open = () =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/b/1/clip"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );

test("a screen is added with a star when the prompt mentions its moment, and can be removed", async () => {
  fakeServer({
    "GET /auth/me": [200, editor],
    "GET /brands": [200, [{ id: 1, name: "fomo", colours: [] }]],
    "GET /models": [200, [seedance, older]],
    "GET /library/character": [200, []],
    "GET /library/place": [200, []],
    "GET /library/prop": [200, []],
    "GET /brands/1/screens": [200, [buy]],
    "GET /credits/me": [200, { quick_clip_credits_used: 10, quick_clip_credits_allowed: 150 }],
    "GET /jobs": [200, []],
    "POST /clips/estimate": [200, estimateOk],
  });
  open();
  const prompt = await screen.findByLabelText(/What happens/);
  expect(screen.getByRole("button", { name: /Generate · 8 credits/ })).toBeDisabled();
  expect(await screen.findByText("Describe the clip (8 or more characters)")).toBeInTheDocument();
  expect(await screen.findByText("Your first fomo clip starts here.")).toBeInTheDocument();
  await userEvent.type(prompt, "Mia hits the buy moment");
  const chip = await screen.findByText("Buy BTC");
  expect(screen.getByText(/added because you mentioned the buy moment/)).toBeInTheDocument();
  await userEvent.click(within(chip.closest("li")!).getByRole("button", { name: "Remove Buy BTC" }));
  expect(screen.queryByText("Buy BTC")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "720p" }));
  expect(await screen.findByRole("button", { name: /Generate · 9 credits/ })).toBeEnabled();
});

test("history shows a ready clip with its video, and a failed one in plain words", async () => {
  fakeServer({
    "GET /auth/me": [200, editor],
    "GET /brands": [200, [{ id: 1, name: "fomo", colours: [] }]],
    "GET /models": [200, [seedance]],
    "GET /library/character": [200, []],
    "GET /library/place": [200, []],
    "GET /library/prop": [200, []],
    "GET /brands/1/screens": [200, []],
    "GET /credits/me": [200, { quick_clip_credits_used: 0, quick_clip_credits_allowed: 150 }],
    "GET /jobs": [200, [
      { id: 1, kind: "video", status: "succeeded", credits: 8, error: "", output: { file_ids: [77] }, prompt_summary: "Mia taps Buy…", duration: 8, resolution: "480p", aspect_ratio: "9:16" },
      { id: 2, kind: "video", status: "failed", credits: 8, error: "The model could not make that clip.", output: null },
    ]],
  });
  const { container } = render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/b/1/clip"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(await screen.findByText("Ready", { selector: "span" })).toBeInTheDocument();
  expect(screen.getByText("Mia taps Buy…")).toBeInTheDocument();
  expect(screen.getByText(/8 s · 9:16 · 480p/)).toBeInTheDocument();
  expect(container.querySelector("video")).toHaveAttribute("src", "/api/files/77#t=0.1");
  expect(screen.getByRole("link", { name: "Download clip 1" })).toHaveAttribute("href", "/api/files/77");
  expect(screen.getByText("Didn't finish · credits returned")).toBeInTheDocument();
  expect(screen.getByText("The model could not make that clip.")).toBeInTheDocument();
});

test("Generate sends the brand pieces to the server and says the clip is queued", async () => {
  const calls = fakeServer({ ...studio, "POST /clips": [201, { id: 5, kind: "video", status: "queued", credits: 9 }] });
  open();
  await userEvent.type(await screen.findByLabelText(/What happens/), "Mia hits the buy moment today");
  await userEvent.click(await screen.findByRole("button", { name: "Add brand piece" }));
  await userEvent.click(await screen.findByText("Mia"));
  const generate = await screen.findByRole("button", { name: /Generate · 9 credits/ });
  await vi.waitFor(() => expect(generate).toBeEnabled());
  await userEvent.click(generate);
  expect(await screen.findByText("Clip queued. It will show in History.")).toBeInTheDocument();
  expect(calls.find((c) => c.key === "POST /clips")?.body).toMatchObject({
    brand_id: 1, model_id: "seedance-2.5", prompt: "Mia hits the buy moment today", aspect_ratio: "9:16",
    duration: 8, resolution: "480p", character_ids: [4], screen_ids: [3],
  });
});

test("past the weekly allowance Generate is disabled with the server's reason, and nothing offers to ask Reed", async () => {
  fakeServer({ ...studio, "POST /clips/estimate": [409, { detail: "That's more than this week's 150 credits (145 used). It resets on Monday." }] });
  open();
  await userEvent.type(await screen.findByLabelText(/What happens/), "A long calm shot of the city");
  expect(await screen.findByText("That's more than this week's 150 credits (145 used). It resets on Monday.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^Generate/ })).toBeDisabled();
  expect(screen.queryByText(/Ask Reed/)).toBeNull();
});

test("a refusal from the server is shown as the reason Generate is off", async () => {
  fakeServer({ ...studio, "POST /clips/estimate": [422, { detail: "Seedance 2.5 makes clips from 4 to 30 seconds." }] });
  open();
  await userEvent.type(await screen.findByLabelText(/What happens/), "A long calm shot of the city");
  expect(await screen.findByText("Seedance 2.5 makes clips from 4 to 30 seconds.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Generate/ })).toBeDisabled();
});

test("elapsed time reads as seconds, then minutes", () => {
  expect(elapsed(45_000)).toBe("45s");
  expect(elapsed(80_000)).toBe("1m 20s");
  expect(elapsed(-5_000)).toBe("0s");
});

test("removing a star screen is sent as skip_screen_ids, so the server doesn't add it back", async () => {
  const calls = fakeServer({ ...studio, "POST /clips": [201, { id: 6, kind: "video", status: "queued", credits: 9 }] });
  open();
  await userEvent.type(await screen.findByLabelText(/What happens/), "Mia hits the buy moment today");
  const chip = await screen.findByText("Buy BTC");
  await userEvent.click(within(chip.closest("li")!).getByRole("button", { name: "Remove Buy BTC" }));
  const generate = await screen.findByRole("button", { name: /Generate · 9 credits/ });
  await vi.waitFor(() => expect(generate).toBeEnabled());
  await userEvent.click(generate);
  await screen.findByText("Clip queued. It will show in History.");
  expect(calls.filter((c) => c.key === "POST /clips").at(-1)?.body).toMatchObject({ screen_ids: [], skip_screen_ids: [3] });
});

test("Try again on a failed clip brings back its prompt, settings and pieces without sending anything", async () => {
  const calls = fakeServer({
    ...studio,
    "GET /jobs": [200, [{ id: 2, kind: "video", status: "failed", credits: 8, error: "The model could not make that clip.", output: null, prompt_summary: "Mia…", duration: 12, resolution: "720p", aspect_ratio: "16:9" }]],
    "GET /clips/2/request": [200, {
      brand_id: 1, model_id: "seedance-2.5", prompt: "Mia taps buy on the app", aspect_ratio: "16:9", duration: 12, resolution: "720p",
      generate_audio: true, character_ids: [4], place_ids: [], prop_ids: [], screen_ids: [], skip_screen_ids: [], file_ids: [],
    }],
  });
  open();
  await userEvent.click(await screen.findByRole("button", { name: /^Try again/ }));
  expect(await screen.findByDisplayValue("Mia taps buy on the app")).toBeInTheDocument();
  expect(await screen.findByText("Mia")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "16:9" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "720p" })).toHaveAttribute("aria-pressed", "true");
  expect(calls.some((c) => c.key === "POST /clips")).toBe(false);
});

test("the button stays on while you keep typing, and a second press needs a change first", async () => {
  const calls = fakeServer({ ...studio, "POST /clips": [201, { id: 8, kind: "video", status: "queued", credits: 9 }] });
  open();
  const prompt = await screen.findByLabelText(/What happens/);
  await userEvent.type(prompt, "A calm shot of the city at dusk");
  const generate = await screen.findByRole("button", { name: /Generate · 9 credits/ });
  await vi.waitFor(() => expect(generate).toBeEnabled());
  await userEvent.type(prompt, " again");
  expect(generate).toBeEnabled(); // keeps the last estimate while the next one is worked out
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "POST /clips/estimate").length).toBeLessThan(10));
  await userEvent.click(generate);
  await screen.findByText("Clip queued. It will show in History.");
  expect(await screen.findByText("Sent. Change something to send another.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Generate/ })).toBeDisabled();
});

test("when generation is switched off on the server, its message is shown by the button", async () => {
  fakeServer({ ...studio, "POST /clips": [503, { detail: "Generation is switched off on this server." }] });
  open();
  await userEvent.type(await screen.findByLabelText(/What happens/), "A long calm shot of the city");
  const generate = await screen.findByRole("button", { name: /Generate · 9 credits/ });
  await vi.waitFor(() => expect(generate).toBeEnabled());
  await userEvent.click(generate);
  expect(await screen.findByRole("alert")).toHaveTextContent("Generation is switched off on this server.");
});

test("Improve prompt writes a prompt, Use this fills the box and Generate says it was improved, Undo improve puts the idea back", async () => {
  const calls = fakeServer({
    ...studio,
    "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 3 }]],
    "POST /clips/improve": [201, { id: 31, kind: "write-claude", step: "improve", status: "queued", credits: 3 }],
    "GET /clips/improve/31": [200, { status: "succeeded", prompt: "Shot 1: Mia taps buy, close-up.", problems: [], error: "" }],
    "POST /clips": [201, { id: 40 }],
  });
  open();
  const prompt = await screen.findByLabelText(/What happens/);
  expect(screen.getByRole("button", { name: "Improve prompt" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Improve prompt" })).toHaveAccessibleDescription("Describe the clip first (8 or more characters)"); // #749 LW12
  await userEvent.type(prompt, "Mia buys bitcoin");
  await userEvent.click(screen.getByRole("button", { name: "Improve prompt" }));
  const dialog = await screen.findByRole("dialog", { name: "Improve prompt" });
  await userEvent.click(within(dialog).getByRole("button", { name: "Funny" }));
  await userEvent.click(within(dialog).getByRole("button", { name: "3" }));
  await userEvent.click(await within(dialog).findByRole("button", { name: "Improve · 3 credits" }));
  expect(await within(dialog).findByLabelText("Improved prompt")).toHaveValue("Shot 1: Mia taps buy, close-up.");
  expect(calls.find((c) => c.key === "POST /clips/improve")?.body).toMatchObject({ direction: "Funny", shots: 3, prompt: "Mia buys bitcoin" });
  await userEvent.click(within(dialog).getByRole("button", { name: "Use this" }));
  expect(prompt).toHaveValue("Shot 1: Mia taps buy, close-up.");
  await userEvent.click(await screen.findByRole("button", { name: /Generate · 9 credits/ }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /clips")?.body).toMatchObject({ improved: true }));
  await userEvent.click(screen.getByRole("button", { name: "Undo improve" }));
  expect(prompt).toHaveValue("Mia buys bitcoin");
});

test("Improve's price is rounded up, never below the charge (an owner's rate of 2.4 reads 3 credits)", async () => {
  fakeServer({ ...studio, "GET /credits/rates": [200, [{ kind: "write-claude", unit: "call", credits_per_unit: 2.4 }]] });
  open();
  await userEvent.type(await screen.findByLabelText(/What happens/), "Mia buys bitcoin");
  await userEvent.click(screen.getByRole("button", { name: "Improve prompt" }));
  const dialog = await screen.findByRole("dialog", { name: "Improve prompt" });
  expect(await within(dialog).findByRole("button", { name: "Improve · 3 credits" })).toBeInTheDocument();
});

test("typing your own prompt after Improve sends improved: false again", async () => {
  const calls = fakeServer({
    ...studio,
    "POST /clips/improve": [201, { id: 31, kind: "write-claude", step: "improve", status: "queued", credits: 3 }],
    "GET /clips/improve/31": [200, { status: "succeeded", prompt: "Shot 1: Mia taps buy.", problems: [], error: "" }],
    "POST /clips": [201, { id: 40 }],
  });
  open();
  const prompt = await screen.findByLabelText(/What happens/);
  await userEvent.type(prompt, "Mia buys bitcoin");
  await userEvent.click(screen.getByRole("button", { name: "Improve prompt" }));
  const dialog = await screen.findByRole("dialog", { name: "Improve prompt" });
  await userEvent.click(within(dialog).getByRole("button", { name: /^Improve ·|^Improve$/ }));
  await userEvent.click(await within(dialog).findByRole("button", { name: "Use this" }));
  await userEvent.type(prompt, " now");
  await vi.waitFor(() => expect(screen.getByRole("button", { name: /Generate/ })).toBeEnabled());
  await userEvent.click(screen.getByRole("button", { name: /Generate/ }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /clips")?.body).toMatchObject({ improved: false }));
});

test("a failed Improve says so and a refused one shows the server's reason", async () => {
  fakeServer({
    ...studio,
    "POST /clips/improve": [422, { detail: "Add a brand piece first." }],
  });
  open();
  await userEvent.type(await screen.findByLabelText(/What happens/), "Mia buys bitcoin");
  await userEvent.click(screen.getByRole("button", { name: "Improve prompt" }));
  await userEvent.click(await within(await screen.findByRole("dialog", { name: "Improve prompt" })).findByRole("button", { name: /^Improve ·|^Improve$/ }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Add a brand piece first.");
});

test("a brand with no clips yet invites the first one, and Start describing goes to the prompt", async () => {
  fakeServer({ ...studio });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Start describing" }));
  expect(screen.getByLabelText(/What happens/)).toHaveFocus();
});

test("history can be filtered, newest first, and Generate sits in the action bar on a phone", async () => {
  fakeServer({
    ...studio,
    "GET /jobs": [200, [
      { id: 1, kind: "video", status: "succeeded", credits: 8, error: "", output: { file_ids: [77] }, prompt_summary: "Older clip", duration: 8, resolution: "480p", aspect_ratio: "9:16" },
      { id: 2, kind: "video", status: "failed", credits: 8, error: "Busy.", output: null, prompt_summary: "Newer clip" },
    ]],
  });
  open();
  const items = await screen.findAllByText(/(Older|Newer) clip/);
  expect(items.map((e) => e.textContent)).toEqual(["Newer clip", "Older clip"]);
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Show" }), "Ready");
  expect(screen.queryByText("Newer clip")).not.toBeInTheDocument();
  expect(screen.getByText("Older clip")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^Generate/ }).closest("div.border-t")).toHaveClass("[&_button]:w-full"); // in the phone action bar
});

test("History lists only clips made in Quick clip, not takes made inside a video", async () => {
  fakeServer({
    ...studio,
    "GET /jobs": [200, [
      { id: 1, kind: "video", status: "succeeded", credits: 8, error: "", output: { file_ids: [77] }, prompt_summary: "A quick one", project_id: null },
      { id: 2, kind: "video", status: "succeeded", credits: 8, error: "", output: { file_ids: [78] }, prompt_summary: "[Image1] is the first frame. A take in a video", project_id: 9 },
    ]],
  });
  open();
  expect(await screen.findByText("A quick one")).toBeInTheDocument();
  expect(screen.queryByText(/A take in a video/)).not.toBeInTheDocument();
});

test("Add brand piece opens a sheet on a phone", async () => {
  fakeServer({ ...studio });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Add brand piece" }));
  expect(await screen.findByRole("dialog", { name: "Add a brand piece" })).toBeInTheDocument();
});

test("Add brand piece stays inline from 1024", async () => {
  setViewport(1440);
  fakeServer({ ...studio });
  open();
  await userEvent.click(await screen.findByRole("button", { name: "Add brand piece" }));
  expect(screen.getByRole("tab", { name: "Characters" })).toBeInTheDocument();
  expect(screen.queryByRole("dialog", { name: "Add a brand piece" })).not.toBeInTheDocument();
});

test("at the most brand pieces a model takes, the picker says why the rest are grey (#749 LW12)", async () => {
  setViewport(1440);
  const mia = { key: "c1", type: "character" as const, id: 1, name: "Mia" };
  const bo = { key: "c2", type: "character" as const, id: 2, name: "Bo" };
  render(<BrandPieces all={[mia, bo]} chosen={[mia]} max={1} onAdd={() => {}} onRemove={() => {}} />);
  await userEvent.click(screen.getByRole("button", { name: "Add brand piece" }));
  expect(screen.getByRole("button", { name: "Bo" })).toBeDisabled();
  expect(screen.getByText("That's the most this model takes (1). Remove one to add another.")).toBeInTheDocument();
});
