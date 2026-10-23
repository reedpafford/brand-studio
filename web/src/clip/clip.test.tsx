import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
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
  const base = { prompt: "Mia taps buy on the app", loading: false, tooMany: false, maxRefs: 4, credits: 10, left: 100, rendering: false };
  expect(blockedReason({ ...base, prompt: "short" })).toBe("Describe the clip (8+ characters)");
  expect(blockedReason({ ...base, rendering: true })).toBe("A clip is already rendering");
  expect(blockedReason({ ...base, left: 5 })).toBe("Not enough credits this week. Ask Reed.");
});

afterEach(() => vi.unstubAllGlobals());

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
  });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/b/1/clip"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  const prompt = await screen.findByLabelText(/Prompt/);
  expect(screen.getByRole("button", { name: /Generate · 8 credits/ })).toBeDisabled();
  expect(await screen.findByText("Describe the clip (8+ characters)")).toBeInTheDocument();
  expect(await screen.findByText("Your first fomo clip starts here.")).toBeInTheDocument();
  await userEvent.type(prompt, "Mia hits the buy moment");
  const chip = await screen.findByText("Buy BTC");
  expect(chip.closest("li")).toHaveTextContent("★");
  await userEvent.click(within(chip.closest("li")!).getByRole("button", { name: "Remove Buy BTC" }));
  expect(screen.queryByText("Buy BTC")).not.toBeInTheDocument();
  expect(screen.getByText("Generation isn't switched on yet.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "720p" }));
  expect(screen.getByRole("button", { name: /Generate · 20 credits/ })).toBeInTheDocument();
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
      { id: 1, kind: "video-480p", status: "succeeded", credits: 8, error: "", output: { file_ids: [77] } },
      { id: 2, kind: "video-480p", status: "failed", credits: 8, error: "The model could not make that clip.", output: null },
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
  expect(container.querySelector("video")).toHaveAttribute("src", "/api/files/77");
  expect(screen.getByText("Failed · credits returned")).toBeInTheDocument();
  expect(screen.getByText("The model could not make that clip.")).toBeInTheDocument();
});
