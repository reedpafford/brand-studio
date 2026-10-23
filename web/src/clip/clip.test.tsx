import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { elapsed } from "./History";
import { blockedReason, clipCredits, fit, mentionsMoment, type Model } from "./logic";

const seedance = {
  id: "seedance-2.5", name: "Seedance 2.5", kind: "video", default: true, duration: { min: 4, max: 30 },
  resolutions: ["480p", "720p"], aspect_ratios: ["9:16", "1:1", "16:9"], max_reference_images: 4,
  credits_per_unit: { "480p": 1, "720p": 2.5 },
} as unknown as Model;
const older = { ...seedance, id: "seedance-2.0", name: "Seedance 2.0", default: false, duration: { min: 4, max: 15 }, resolutions: ["480p"], aspect_ratios: ["9:16"] } as unknown as Model;
const editor = { id: 2, email: "e@b.co", name: "Eli", role: "editor", workspace_id: 1 };
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
  expect(blockedReason({ ...base, prompt: "short" })).toBe("Describe the clip (8+ characters)");
  expect(blockedReason({ ...base, rendering: true })).toBe("A clip is already rendering");
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
  "GET /library/character": [200, [{ id: 4, name: "Mia", image_file_ids: [] }]],
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
  const prompt = await screen.findByLabelText(/Prompt/);
  expect(screen.getByRole("button", { name: /Generate · 8 credits/ })).toBeDisabled();
  expect(await screen.findByText("Describe the clip (8+ characters)")).toBeInTheDocument();
  expect(await screen.findByText("Your first fomo clip starts here.")).toBeInTheDocument();
  await userEvent.type(prompt, "Mia hits the buy moment");
  const chip = await screen.findByText("Buy BTC");
  expect(chip.closest("li")).toHaveTextContent("★");
  expect(screen.getByText(/was added because your prompt mentions buy-moment/)).toBeInTheDocument();
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
  expect(await screen.findByText("Ready")).toBeInTheDocument();
  expect(screen.getByText("Mia taps Buy…")).toBeInTheDocument();
  expect(screen.getByText("8s · 480p · 9:16")).toBeInTheDocument();
  expect(container.querySelector("video")).toHaveAttribute("src", "/api/files/77");
  expect(screen.getByText("Failed · credits returned")).toBeInTheDocument();
  expect(screen.getByText("The model could not make that clip.")).toBeInTheDocument();
});

test("Generate sends the brand pieces to the server and says the clip is queued", async () => {
  const calls = fakeServer({ ...studio, "POST /clips": [201, { id: 5, kind: "video", status: "queued", credits: 9 }] });
  open();
  await userEvent.type(await screen.findByLabelText(/Prompt/), "Mia hits the buy moment today");
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

test("when the clip would need Reed's approval, say so before the click", async () => {
  fakeServer({ ...studio, "POST /clips/estimate": [200, { ...estimateOk, needs_owner_approval: true, reason: "This goes past your weekly quick-clip allowance, so Reed will need to approve it." }] });
  open();
  await userEvent.type(await screen.findByLabelText(/Prompt/), "A long calm shot of the city");
  expect(await screen.findByText(/Reed will need to approve it/)).toBeInTheDocument();
});

test("a refusal from the server is shown as the reason Generate is off", async () => {
  fakeServer({ ...studio, "POST /clips/estimate": [422, { detail: "Seedance 2.5 makes clips from 4 to 30 seconds." }] });
  open();
  await userEvent.type(await screen.findByLabelText(/Prompt/), "A long calm shot of the city");
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
  await userEvent.type(await screen.findByLabelText(/Prompt/), "Mia hits the buy moment today");
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
  await userEvent.click(await screen.findByRole("button", { name: "Try again" }));
  expect(await screen.findByDisplayValue("Mia taps buy on the app")).toBeInTheDocument();
  expect(await screen.findByText("Mia")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "16:9" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "720p" })).toHaveAttribute("aria-pressed", "true");
  expect(calls.some((c) => c.key === "POST /clips")).toBe(false);
});

test("over the weekly allowance the button asks Reed instead of blocking, and the toast says so", async () => {
  const calls = fakeServer({
    ...studio,
    "GET /credits/me": [200, { quick_clip_credits_used: 145, quick_clip_credits_allowed: 150 }],
    "POST /clips/estimate": [200, { ...estimateOk, credits: 68, needs_owner_approval: true, reason: "This goes past your weekly quick-clip allowance, so Reed will need to approve it." }],
    "POST /clips": [201, { id: 7, kind: "video", status: "needs_owner_approval", credits: 68 }],
  });
  open();
  await userEvent.type(await screen.findByLabelText(/Prompt/), "A long calm shot of the city");
  const ask = await screen.findByRole("button", { name: "Ask Reed to approve · 68 credits" });
  await vi.waitFor(() => expect(ask).toBeEnabled());
  await userEvent.click(ask);
  expect(await screen.findByText("Sent to Reed for approval. It will show in History.")).toBeInTheDocument();
  expect(calls.some((c) => c.key === "POST /clips")).toBe(true);
});

test("the button stays on while you keep typing, and a second press needs a change first", async () => {
  const calls = fakeServer({ ...studio, "POST /clips": [201, { id: 8, kind: "video", status: "queued", credits: 9 }] });
  open();
  const prompt = await screen.findByLabelText(/Prompt/);
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
  await userEvent.type(await screen.findByLabelText(/Prompt/), "A long calm shot of the city");
  const generate = await screen.findByRole("button", { name: /Generate · 9 credits/ });
  await vi.waitFor(() => expect(generate).toBeEnabled());
  await userEvent.click(generate);
  expect(await screen.findByRole("alert")).toHaveTextContent("Generation is switched off on this server.");
});
