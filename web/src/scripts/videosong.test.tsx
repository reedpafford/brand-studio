import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { ToastProvider } from "../toast";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";
import { SongSetting, SongStrip } from "./VideoSong";

const editor = { id: 2, email: "sam@b.co", name: "Sam", role: "editor", workspace_id: 1 };
const take = (o: object = {}) => ({ id: 1, number: 1, status: "ready", failed_reason: null, retry_helps: true, file_id: 40, seconds: 31, made_at: "2026-10-28T10:42:00Z", preferred: true, out_of_date: false, peaks: [0.2, 0.8], advice: [], timing_guessed: false, refused_for: null, video_credits: 34, over_cap: false, fits_until: null, trim_to: null, in_video: false, ...o });
const songs = (takes: object[], o: object = {}) => ({ songs_on: true, estimate_credits: 1, takes, song_take_id: 1, ...o });
const project = (o: object = {}) => ({ id: 5, brand_id: 1, name: "Bowl song", own_script: false, credits_used: 10, budget_credits: 100, budget_pct: 10, ...o }) as never;

function show(p = project(), hasShots = true, hasClips = true) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <ToastProvider>
          <SongStrip project={p} hasShots={hasShots} hasClips={hasClips} />
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

test("the strip shows the video's song with Change song; Use this take asks first when shots exist, then has Undo", async () => {
  setViewport(1440);
  const calls = fakeServer({ "GET /auth/me": [200, editor], "GET /projects/5/songs": [200, songs([take(), take({ id: 2, number: 2, preferred: false, seconds: 28, video_credits: 33.73 })])], "PUT /projects/5/song": [200, { song_take_id: 2, was_song_take_id: 1 }] });
  show();
  expect(await screen.findByText("Song: Take 1 · 0:31")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Change song" }));
  const panel = await screen.findByRole("dialog", { name: "Change song" });
  expect(within(panel).getByText("In this video")).toBeInTheDocument();
  expect(within(panel).getByText("0:28 · a video of about 34 credits")).toBeInTheDocument();
  await userEvent.click(within(panel).getByRole("button", { name: "Use this take" }));
  const ask = screen.getByRole("alertdialog", { name: "Use take 2?" });
  expect(ask).toHaveTextContent("Clips already made for take 1 go out of date.");
  await userEvent.click(within(ask).getByRole("button", { name: "Use it" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /projects/5/song")?.body).toEqual({ take_id: 2 }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "PUT /projects/5/song").at(-1)?.body).toEqual({ take_id: 1 }));
});

test("an editor over the video's budget can't make 2 more and is told why; the takes there stay usable", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, editor], "GET /projects/5/songs": [200, songs([take(), take({ id: 2, number: 2, preferred: false })])] });
  show(project({ credits_used: 99.5, budget_credits: 100 }));
  await userEvent.click(await screen.findByRole("button", { name: "Change song" }));
  const panel = await screen.findByRole("dialog", { name: "Change song" });
  expect(within(panel).getByRole("button", { name: /Make 2 more takes/ })).toBeDisabled();
  expect(within(panel).getByText("That's more than this video's budget.")).toBeInTheDocument();
  expect(within(panel).getByRole("button", { name: "Use this take" })).toBeEnabled();
});

test("a take too long for this video can't be used until 'Use the first 0:55' trims it", async () => {
  setViewport(1440);
  const calls = fakeServer({ "GET /auth/me": [200, editor], "GET /projects/5/songs": [200, songs([take(), take({ id: 2, number: 2, preferred: false, seconds: 72, over_cap: true, fits_until: 55 })])], "POST /songs/2/trim": [200, take({ id: 2, number: 2, trim_to: 55 })] });
  show(project(), false);
  await userEvent.click(await screen.findByRole("button", { name: "Change song" }));
  const panel = await screen.findByRole("dialog", { name: "Change song" });
  expect(within(panel).getByRole("button", { name: "Use this take" })).toBeDisabled();
  expect(within(panel).getByText("Too long for this video.")).toBeInTheDocument();
  await userEvent.click(within(panel).getByRole("button", { name: /Use the first 0:55 · free/ }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /songs/2/trim")).toBe(true));
});

test("at 390 Change song opens as a sheet with Close", async () => {
  setViewport(390);
  fakeServer({ "GET /auth/me": [200, editor], "GET /projects/5/songs": [200, songs([take()])] });
  show();
  await userEvent.click(await screen.findByRole("button", { name: "Change song" }));
  const sheet = await screen.findByRole("dialog", { name: "Change song" });
  expect(within(sheet).getByRole("button", { name: "Close" })).toBeInTheDocument();
});

test("a take this video made says so and can be deleted with Undo; the one in use can't", async () => {
  setViewport(1440);
  const calls = fakeServer({ "GET /auth/me": [200, editor], "GET /projects/5/songs": [200, songs([take(), take({ id: 3, number: 1, preferred: false, in_video: true })])], "DELETE /songs/3": [204, null], "POST /songs/3/restore": [200, take({ id: 3, number: 1, in_video: true })] });
  show();
  await userEvent.click(await screen.findByRole("button", { name: "Change song" }));
  const panel = await screen.findByRole("dialog", { name: "Change song" });
  expect(within(panel).getByText("Made in this video")).toBeInTheDocument();
  expect(within(panel).getAllByRole("button", { name: "Delete take" })).toHaveLength(1);
  await userEvent.click(within(panel).getByRole("button", { name: "Delete take" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "DELETE /songs/3")).toBe(true));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /songs/3/restore")).toBe(true));
});

test("a refusal inside a video says the lyrics are final and the way on is another take or Try again", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, editor], "GET /projects/5/songs": [200, songs([take(), take({ id: 2, number: 2, preferred: false, status: "failed", file_id: null, seconds: null, refused_for: "words", failed_reason: "Suno won't sing these words. Change those words, then press Try again." })])] });
  show();
  await userEvent.click(await screen.findByRole("button", { name: "Change song" }));
  const panel = await screen.findByRole("dialog", { name: "Change song" });
  expect(within(panel).getByText("The lyrics are final in a video: try again, or use another take.")).toBeInTheDocument();
  expect(within(panel).getByRole("button", { name: /Try again/ })).toBeInTheDocument();
});

test("both takes this video made can be deleted, unless the video uses one", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, editor], "GET /projects/5/songs": [200, songs([take(), take({ id: 3, number: 1, preferred: false, in_video: true }), take({ id: 4, number: 2, preferred: false, in_video: true })])] });
  show();
  await userEvent.click(await screen.findByRole("button", { name: "Change song" }));
  const panel = await screen.findByRole("dialog", { name: "Change song" });
  expect(within(panel).getAllByRole("button", { name: "Delete take" })).toHaveLength(2);
});

test("with shots but no clips yet, Use this take asks without warning about clips", async () => {
  setViewport(1440);
  fakeServer({ "GET /auth/me": [200, editor], "GET /projects/5/songs": [200, songs([take(), take({ id: 2, number: 2, preferred: false })])] });
  show(project(), true, false);
  await userEvent.click(await screen.findByRole("button", { name: "Change song" }));
  const panel = await screen.findByRole("dialog", { name: "Change song" });
  await userEvent.click(within(panel).getByRole("button", { name: "Use this take" }));
  const ask = screen.getByRole("alertdialog", { name: "Use take 2?" });
  expect(ask).toHaveTextContent("their times move to take 2 (free).");
  expect(ask).not.toHaveTextContent("Clips already made");
});

test("SongSetting, for the Video settings row, names the song and opens Change song", async () => {
  setViewport(390);
  fakeServer({ "GET /auth/me": [200, editor], "GET /projects/5/songs": [200, songs([take()])] });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <ToastProvider>
          <SongSetting project={project()} />
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  await userEvent.click(await screen.findByRole("button", { name: "Song: Take 1 · 0:31" }));
  expect(await screen.findByRole("dialog", { name: "Change song" })).toBeInTheDocument();
});
