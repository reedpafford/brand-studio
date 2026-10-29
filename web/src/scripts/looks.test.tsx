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
const LYRICS = "[Verse]\nBo would never touch his bowl\n[Chorus]\nNow he licks it clean";
const version = (o: object = {}) => ({ slot: 0, status: "draft", title: "Bowl song", seconds: 0, project_id: null, text: LYRICS, words: 10, target_seconds: null, premise: "", changes: [], problems: [], has_breakdown: false, approved_at: null, style_line: "pop, female lead, upbeat", singer: "", spoken_end_line: "", song_directions: [], ...o });
const song = (o: object = {}, v: object = {}) => ({
  id: 7, brand_id: 1, kind: "song", title: "Bowl song", description: "", reference_id: null, published: false, status: "draft", created_by_id: 1, created_by_name: "Reed", created_at: "2026-10-28T10:00:00Z", versions_left: 0,
  notes: "", reference_replace: "", cast: [], versions: [version(v)], ...o,
});
const base: Record<string, [number, unknown]> = { "GET /auth/me": [200, owner], "GET /brands": [200, brands], "GET /references": [200, []], "GET /projects": [200, []], "GET /jobs": [200, []] };

function open(path: string) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const editor = { ...owner, id: 2, email: "sam@b.co", name: "Sam", role: "editor" };
const looks = [
  { id: "house", name: "House", blurb: "Our current look", on: true, sample_still_id: 90 },
  { id: "pixar", name: "Disney Pixar", blurb: "Soft 3D feature-film look", on: true, sample_still_id: 91 },
  { id: "clay", name: "Claymation", blurb: "Hand-made clay", on: false, sample_still_id: null },
];
const story = (o: object = {}) => song({ kind: "story", look: "house", ...o }, { style_line: "" });

test("a draft's header reads its format and Look: House; the picker shows each look's sample and line, and Use this look saves with Undo", async () => {
  setViewport(1440);
  const calls = fakeServer({ ...base, "GET /looks": [200, looks], "GET /scripts/7": [200, story()], "PATCH /scripts/7": [200, story({ look: "pixar" })] });
  open("/b/1/scripts/7");
  expect(await screen.findByText("Dialogue")).toBeInTheDocument();
  await userEvent.click(await screen.findByRole("button", { name: "Look: House" }));
  const picker = await screen.findByRole("dialog", { name: "Look" });
  expect(within(picker).getByAltText("Disney Pixar sample")).toHaveAttribute("src", "/api/files/91");
  expect(within(picker).getByText("Soft 3D feature-film look")).toBeInTheDocument();
  expect(within(picker).getByText("In use")).toBeInTheDocument();
  await userEvent.click(within(picker).getAllByRole("button", { name: "Use this look" })[0]);
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /scripts/7")?.body).toEqual({ look: "pixar" }));
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(calls.filter((c) => c.key === "PATCH /scripts/7").at(-1)?.body).toEqual({ look: "house" }));
});

test("an editor sees an Off look greyed, Not switched on yet; the owner may try it", async () => {
  setViewport(390);
  fakeServer({ ...base, "GET /auth/me": [200, editor], "GET /looks": [200, looks], "GET /scripts/7": [200, story({ created_by_id: 2 })] });
  open("/b/1/scripts/7");
  await userEvent.click(await screen.findByRole("button", { name: "Look: House" }));
  const picker = await screen.findByRole("dialog", { name: "Look" });
  const buttons = within(picker).getAllByRole("button", { name: "Use this look" });
  expect(buttons.at(-1)).toBeDisabled();
  expect(within(picker).getByText("Not switched on yet")).toBeInTheDocument();
  expect(within(picker).getByRole("button", { name: "Close" })).toBeInTheDocument();
});

test("the owner sees Off for editors: only you can use it", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /looks": [200, looks], "GET /scripts/7": [200, story()] });
  open("/b/1/scripts/7");
  await userEvent.click(await screen.findByRole("button", { name: "Look: House" }));
  const picker = await screen.findByRole("dialog", { name: "Look" });
  expect(within(picker).getByText("Off for editors: only you can use it.")).toBeInTheDocument();
  expect(within(picker).getAllByRole("button", { name: "Use this look" }).at(-1)).toBeEnabled();
});

test("a refused change (an Off look for an editor) says why in the server's words", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /looks": [200, looks.map((l) => ({ ...l, on: true }))], "GET /scripts/7": [200, story()], "PATCH /scripts/7": [409, { detail: "Claymation isn't switched on for editors yet." }] });
  open("/b/1/scripts/7");
  await userEvent.click(await screen.findByRole("button", { name: "Look: House" }));
  const picker = await screen.findByRole("dialog", { name: "Look" });
  await userEvent.click(within(picker).getAllByRole("button", { name: "Use this look" }).at(-1)!);
  expect(await within(picker).findByText("Claymation isn't switched on for editors yet.")).toBeInTheDocument();
});

test("a published script shows its look read only; a song shows the Song chip", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /looks": [200, looks], "GET /scripts/7": [200, song({ published: true, status: "published", look: "pixar" })], "GET /scripts/7/drafts/0/songs": [200, { songs_on: true, estimate_credits: 1, video_estimate_credits: 40, keep_lines: null, takes: [] }] });
  open("/b/1/scripts/7");
  expect(await screen.findByText("Look: Disney Pixar")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Look:/ })).toBeNull();
  expect(screen.getByText("Song", { selector: "span" })).toBeInTheDocument();
});

test("before the server offers looks, there's no Look control", async () => {
  setViewport(1440);
  fakeServer({ ...base, "GET /scripts/7": [200, story()] });
  open("/b/1/scripts/7");
  expect(await screen.findByText("Dialogue")).toBeInTheDocument();
  await vi.waitFor(() => expect(screen.queryByRole("button", { name: /Look:/ })).toBeNull());
});

const change = (o: object = {}) => ({ roles: ["Mom", "Bo"], to_finish_credits: 12, was_credits: 0, over_budget: false, reason: "", ...o });

test("once roles would need a new look, the change asks first with what it takes to finish; Change saves it", async () => {
  setViewport(390);
  const calls = fakeServer({ ...base, "GET /looks": [200, looks], "GET /scripts/7": [200, story()], "GET /scripts/7/look-change": [200, change()], "PATCH /scripts/7": [200, story({ look: "pixar" })] });
  open("/b/1/scripts/7");
  await userEvent.click(await screen.findByRole("button", { name: "Look: House" }));
  const picker = await screen.findByRole("dialog", { name: "Look" });
  await userEvent.click(within(picker).getAllByRole("button", { name: "Use this look" })[0]);
  const ask = await screen.findByRole("alertdialog", { name: "Change to Disney Pixar?" });
  expect(ask).toHaveTextContent("2 roles need a new look (Mom, Bo). To finish: about 12 credits (was 0).");
  expect(calls.some((c) => c.key === "PATCH /scripts/7")).toBe(false);
  await userEvent.click(within(ask).getByRole("button", { name: "Change" }));
  await vi.waitFor(() => expect(calls.find((c) => c.key === "PATCH /scripts/7")?.body).toEqual({ look: "pixar" }));
  expect(await screen.findByRole("button", { name: "Undo" })).toBeInTheDocument();
});

test("an editor over the week sees why Change is held back, and Not yet keeps the current look", async () => {
  setViewport(1440);
  const reason = "Making those looks would go over this week's credits. It resets on Monday.";
  const calls = fakeServer({ ...base, "GET /auth/me": [200, editor], "GET /looks": [200, looks], "GET /scripts/7": [200, story()], "GET /scripts/7/look-change": [200, change({ over_budget: true, reason })], "PATCH /scripts/7": [200, story({ look: "pixar" })] });
  open("/b/1/scripts/7");
  await userEvent.click(await screen.findByRole("button", { name: "Look: House" }));
  const picker = await screen.findByRole("dialog", { name: "Look" });
  await userEvent.click(within(picker).getAllByRole("button", { name: "Use this look" })[0]);
  const ask = await screen.findByRole("alertdialog", { name: "Change to Disney Pixar?" });
  expect(within(ask).getByRole("button", { name: "Change" })).toBeDisabled();
  expect(ask).toHaveTextContent(reason);
  await userEvent.click(within(ask).getByRole("button", { name: "Not yet" }));
  expect(screen.queryByRole("alertdialog")).toBeNull();
  expect(calls.some((c) => c.key === "PATCH /scripts/7")).toBe(false);
});
