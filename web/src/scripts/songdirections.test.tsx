import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "../App";
import { fakeServer } from "../test/server";
import { setViewport } from "../test/viewport";

const owner = { id: 1, email: "reed@b.co", name: "Reed", role: "owner", workspace_id: 1 };
const brands = [{ id: 1, name: "Iron Paws", colours: [], end_line: "Get Iron Paws through the link in my bio." }];
const LYRICS = "[Verse]\nBo would never touch his bowl\n[Chorus]\nNow he licks it clean, Iron Paws";
const direction = (o: object = {}) => ({ id: 11, title: "Clean Bowl", concept: "A bouncy before-and-after.", lyrics: LYRICS, style_line: "indie pop, warm female lead, 104 BPM", visual_concept: "Bo sniffs, then licks the bowl clean.", recommended: true, left_out: [], unchecked_claims: [], ...o });
const version = (o: object = {}) => ({ slot: 0, status: "draft", title: "Bowl song", seconds: 0, project_id: null, text: "", words: 0, target_seconds: null, premise: "", changes: [], problems: [], has_breakdown: false, approved_at: null, style_line: "", singer: "", spoken_end_line: "", song_directions: [], directions_job: null, directions_estimate_credits: 3, directions_stop: null, claims_to_check: [], ...o });
const song = (v: object = {}) => ({
  id: 7, brand_id: 1, kind: "song", title: "Bowl song", description: "", reference_id: null, published: false, status: "draft", created_by_id: 1, created_by_name: "Reed", created_at: "2026-10-28T10:00:00Z", versions_left: 0,
  notes: "", reference_replace: "", cast: [], versions: [version(v)],
});
const base: Record<string, [number, unknown]> = { "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /references": [200, []], "GET /projects": [200, []], "GET /jobs": [200, []], "GET /scripts/7/drafts/0/songs": [200, { songs_on: true, estimate_credits: 1, video_estimate_credits: 40, keep_lines: null, takes: [] }] };

function open() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/b/1/scripts/7"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

test("empty lyrics: Write 2 song directions shows its price and sends the From a script and Sounds like boxes", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, song()], "POST /scripts/7/drafts/0/directions": [200, { id: 90 }] });
  open();
  await userEvent.type(await screen.findByLabelText("From a script (optional)"), "Bo hated his bowl.");
  await userEvent.type(screen.getByLabelText("Sounds like (optional)"), "a sunny acoustic song");
  await userEvent.click(screen.getByRole("button", { name: /Write 2 song directions for me · 3 credits/ }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "POST /scripts/7/drafts/0/directions")?.body).toEqual({ source: "Bo hated his bowl.", sounds_like: "a sunny acoustic song" }));
});

test("while writing: in words with a timer, and Cancel only before it starts", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, song({ directions_job: { id: 90, status: "queued", reason: null, started_at: new Date().toISOString() } })] });
  open();
  expect(await screen.findByText(/Waiting to start/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Write 2/ })).toBeNull();
});

test("two cards: Recommended, the length, Leaves out and Not checked; Use this one with empty boxes fills them, with Undo", async () => {
  setViewport(1440);
  const two = [direction({ left_out: ["the vet quote"], unchecked_claims: ["vet-approved in 7 days"] }), direction({ id: 12, title: "Lick It Clean", recommended: false, style_names: ["Jack Johnson"] })];
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, song({ song_directions: two })], "POST /scripts/7/drafts/0/directions/11/use": [200, { was_text: "", was_style_line: "" }], "PUT /scripts/7/drafts/0": [200, song()] });
  open();
  const cards = await screen.findByRole("region", { name: "Song directions" });
  expect(within(cards).getAllByText("Recommended")).toHaveLength(1);
  expect(within(cards).getAllByText(/13 sung words: a song of about 0:05–0:07/)).toHaveLength(2);
  expect(within(cards).getByText("Leaves out: the vet quote")).toBeInTheDocument();
  expect(within(cards).getByText('Not checked: "vet-approved in 7 days"')).toBeInTheDocument();
  expect(within(cards).getByText(/The style names "Jack Johnson"\. Suno won't take names/)).toBeInTheDocument();
  expect(within(cards).getByRole("button", { name: /Write 2 more · 3 credits/ })).toBeInTheDocument();
  await userEvent.click(within(cards).getAllByRole("button", { name: "Use this one" })[0]);
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/drafts/0/directions/11/use")).toBe(true));
  expect(await screen.findByText(/"Clean Bowl" is in\. The lyrics are yours now/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PUT /scripts/7/drafts/0")?.body).toMatchObject({ text: "", style_line: "" }));
});

test("Use this one over words already there asks to replace them first", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, song({ text: LYRICS, song_directions: [direction()] })], "POST /scripts/7/drafts/0/directions/11/use": [200, { was_text: LYRICS, was_style_line: "" }] });
  open();
  await userEvent.click(await screen.findByText("Directions · 1"));
  await userEvent.click(screen.getByRole("button", { name: "Use this one" }));
  const ask = screen.getByRole("alertdialog", { name: 'Replace your lyrics with "Clean Bowl"?' });
  expect(ask).toHaveTextContent("Your words are kept in Undo.");
  expect(calls.some((c) => c.key === "POST /scripts/7/drafts/0/directions/11/use")).toBe(false);
  await userEvent.click(within(ask).getByRole("button", { name: "Replace" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/drafts/0/directions/11/use")).toBe(true));
});

test("failed and refused say so, nothing charged, with Try again; nothing to go on names the reason and a way to the brand page", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, song({ directions_job: { id: 90, status: "refused", reason: "it won't promise a health result", started_at: "2026-10-29T03:00:00Z" } })] });
  open();
  expect(await screen.findByText(/Claude won't write this: it won't promise a health result/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Try again · 3 credits/ })).toBeEnabled();
});

test("nothing to go on: the press says why and links to the brand page", async () => {
  setViewport(390);
  fakeServer({ ...base, "GET /scripts/7": [200, song({ directions_stop: "Say what the brand sells on the brand page first" })] });
  open();
  expect(await screen.findByRole("button", { name: /Write 2 song directions for me/ })).toBeDisabled();
  expect(screen.getByText("Say what the brand sells on the brand page first")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open the brand page" })).toHaveAttribute("href", "/b/1/brand");
});

test("after a direction is used, its unchecked claims show under the lyrics until Keep it", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /scripts/7": [200, song({ text: LYRICS, claims_to_check: ["vet-approved in 7 days"] })], "POST /scripts/7/drafts/0/claims/keep": [200, {}] });
  open();
  expect(await screen.findByText(/Not checked against the brand's facts: "vet-approved in 7 days"/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Keep it" }));
  await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /scripts/7/drafts/0/claims/keep")).toBe(true));
});

test("before the server offers directions, the section isn't shown at all (no dead press)", async () => {
  setViewport(1440);
  const v = version();
  const old = Object.fromEntries(Object.entries(v).filter(([k]) => !["directions_job", "directions_estimate_credits", "directions_stop", "claims_to_check"].includes(k)));
  fakeServer({ ...base, "GET /scripts/7": [200, { ...song(), versions: [old] }] });
  open();
  expect(await screen.findByLabelText("Lyrics")).toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "Song directions" })).toBeNull();
});
