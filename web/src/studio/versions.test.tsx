import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { renderApp } from "../test/render";
import { fakeServer } from "../test/server";
import { round2, threeHooks, threeHooksPlan, threeHooksRound, type Routes } from "../test/studioVideo";
import { setViewport } from "../test/viewport";

// Hooks as versions on a video's page in the new look: a script with three openings is one video with three versions,
// each opening in front of the same body (test/studioVideo.ts: clips 1, 2 and 3 are the openings' own, 4 to 9 the
// body). What the page reads for a version, what it shows, and exactly what each press sends.
async function open(routes: Routes, address = "") {
  const calls = fakeServer(routes);
  renderApp(`/s/b/1/videos/366${address}`);
  await screen.findByRole("heading", { name: "Three men at Target" });
  await chat().findByRole("textbox", { name: "Tell the director what to change" });
  return calls;
}
/** Everything the page has sent that isn't a read: its method, path and query, and its body. */
const sent = (calls: ReturnType<typeof fakeServer>) => calls.filter((c) => !c.key.startsWith("GET ")).map((c) => (c.body === undefined ? [c.key + new URL(c.url).search] : [c.key + new URL(c.url).search, c.body]));
/** The cut's reads, each with its query. */
const cuts = (calls: ReturnType<typeof fakeServer>) => [...new Set(calls.filter((c) => c.key.startsWith("GET /projects/366/cut")).map((c) => c.key + new URL(c.url).search))];
const page = () => within(screen.getByRole("main"));
const chat = () => within(screen.getByRole("region", { name: "The director" }));
const film = () => within(screen.getByRole("region", { name: "The video" }));
const caption = () => within(film().getByRole("group", { name: "The picked clip" }));
const timeline = () => within(film().getByRole("group", { name: "Clips, in order, each as wide as it is long" }));
const pieces = () => timeline().getAllByRole("button").map((b) => b.getAttribute("aria-label"));
const hook = (n: number) => within(film().getByRole("group", { name: "Version" })).getByRole("button", { name: `Hook ${n}` });
const read = <T,>(routes: Routes, path: string) => routes[`GET /projects/366${path}`][1] as T;
const BODY = ["Clip 4, 7 s", "Time card: TWENTY MINUTES EARLIER", "Clip 5, 7 s", "Clip 6, 6 s", "Clip 7, 8 s", "Clip 8, 8 s", "Clip 9, 8 s"];

beforeEach(() => {
  localStorage.clear();
  setViewport(1440);
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {}); // jsdom plays nothing
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

test("a switch by the views picks the version: its own cut is read with ?opening=, its film, its timeline and its hook's caption show, and nothing is sent", async () => {
  const calls = await open(threeHooks());
  const versions = within(await film().findByRole("group", { name: "Version" })).getAllByRole("button");
  expect(versions.map((b) => `${b.textContent}: ${b.title} ${b.getAttribute("aria-pressed")}`)).toEqual(["Hook 1: The lot, seconds after true", "Hook 2: He got the plate false", "Hook 3: Eggs on the asphalt false"]);
  expect(film().getByLabelText("The cut")).toHaveAttribute("src", "/api/files/90");
  expect(pieces()).toEqual(["Clip 1, 8 s", ...BODY]);
  expect(page().getByRole("button", { name: "$4.61 · 54 s · 3 versions" })).toBeInTheDocument();
  expect(cuts(calls)).toEqual(["GET /projects/366/cut", "GET /projects/366/cut/versions"]); // the first version's cut is the cut itself

  await userEvent.click(hook(2));
  await waitFor(() => expect(film().getByLabelText("The cut")).toHaveAttribute("src", "/api/files/92"));
  expect(hook(2)).toHaveAttribute("aria-pressed", "true");
  expect(pieces()).toEqual(["Clip 2, 4 s", ...BODY]);
  expect(caption().getByText("Clip 2 of 9 · Hook 2 · 4 s")).toBeInTheDocument();
  expect(page().getByRole("button", { name: "$4.61 · 50 s · 3 versions" })).toBeInTheDocument();
  await userEvent.click(timeline().getByRole("button", { name: "Clip 4, 7 s" }));
  expect(caption().getByText("Clip 4 of 9 · 7 s")).toBeInTheDocument(); // a clip of the body: no hook's name
  expect(cuts(calls)).toContain("GET /projects/366/cut?opening=2");
  expect(sent(calls)).toEqual([]);
});

test("the version in the address (?v=3) is the one on screen after a reload; one with no cut yet says so and plays its clips, with no Download", async () => {
  const calls = await open(threeHooks([90, 92, null]), "?v=3");
  expect(await film().findByText("Hook 3 has no cut yet.")).toBeInTheDocument();
  expect(film().getByText("No cut yet.")).toBeInTheDocument(); // where the film's time would be
  expect(hook(3)).toHaveAttribute("aria-pressed", "true");
  expect(film().queryByLabelText("The cut")).toBeNull();
  expect(film().getByLabelText("Clip 3")).toHaveAttribute("src", "/api/files/203"); // its own take plays
  expect(pieces()).toEqual(["Clip 3, 4 s", ...BODY]);
  expect(page().queryByRole("link", { name: "Download" })).toBeNull();
  expect(film().getByRole("button", { name: "Make the cuts free" })).toBeEnabled(); // the way on, if its cut never arrives
  expect(cuts(calls)).toContain("GET /projects/366/cut?opening=3");
  expect(sent(calls)).toEqual([]);
});

test("when versions are out of date the one press is Make the cuts, free: the same bare request, which makes every one of them", async () => {
  const routes = threeHooks([90, 92, 93], [1, 2, 3]);
  const calls = await open({ ...routes, "POST /projects/366/cut": [200, read(routes, "/cut")] }, "?v=2");
  expect(await film().findByText("Hook 1, Hook 2 and Hook 3 need a new cut.")).toBeInTheDocument();
  expect(film().queryByRole("button", { name: "Undo all" })).toBeNull(); // no edit is waiting: nothing to undo
  await userEvent.dblClick(film().getByRole("button", { name: "Make the cuts free" }));
  expect(sent(calls)).toEqual([["POST /projects/366/cut"]]);
});

test("Download is the version on screen, a further one named as the server names its file; the menu lists each version's", async () => {
  await open(threeHooks(), "?v=2");
  const download = await page().findByRole("link", { name: "Download" });
  expect(download).toHaveAttribute("href", "/api/files/92");
  expect(download).toHaveAttribute("download", "Three men at Target (version 2).mp4");
  await userEvent.click(page().getByRole("button", { name: "More" }));
  const links = within(screen.getByRole("menu", { name: "More for Three men at Target" })).getAllByRole("menuitem", { name: /^Download hook/ });
  expect(links.map((a) => `${a.textContent?.trim()}: ${a.getAttribute("href")} as ${a.getAttribute("download")}`)).toEqual([
    "Download hook 1 (MP4): /api/files/90 as three-men-at-target.mp4",
    "Download hook 2 (MP4): /api/files/92 as Three men at Target (version 2).mp4",
    "Download hook 3 (MP4): /api/files/93 as Three men at Target (version 3).mp4",
  ]);
});

test("in a further version, its hook's own clip can be made again or noted but not trimmed or switched to another take; a clip of the body is trimmed in the first version's seconds", async () => {
  const routes = threeHooks();
  const second = (c: { clip_id: string; takes: object[] }) => (c.clip_id === "c2" ? { ...c, takes: [...c.takes, { id: 122, number: 2, file_id: 222, created_at: "2026-11-13T09:30:00", verdict: "", mutes: [] }] } : c);
  const calls = await open({ ...routes, "GET /projects/366/clips": [200, read<{ clip_id: string; takes: object[] }[]>(routes, "/clips").map(second)], "POST /projects/366/clips/502/generate": [200, {}], "POST /projects/366/cut/edits": [200, read(routes, "/cut")] }, "?v=2");
  await film().findByLabelText("The cut");
  await userEvent.click(timeline().getByRole("button", { name: "Clip 2, 4 s" }));
  await userEvent.click(caption().getByRole("button", { name: "Edit clip" }));
  expect(caption().getByText("Hook 2’s own clip can be made again or changed with a note, but not trimmed or switched to another take yet.")).toBeInTheDocument();
  expect(caption().queryByRole("slider")).toBeNull();
  await userEvent.click(caption().getByRole("button", { name: "Watch take 2" }));
  expect(caption().queryByRole("button", { name: "Use this take" })).toBeNull();
  await userEvent.dblClick(caption().getByRole("button", { name: "Another take up to $0.50" }));
  await userEvent.click(caption().getByRole("button", { name: "Tell the director…" }));
  expect(chat().getByRole("textbox", { name: "Tell the director what to change" })).toHaveValue("Clip 2: ");

  await userEvent.click(timeline().getByRole("button", { name: "Clip 4, 7 s" })); // 0:04 to 0:11 of this version, 0:08 to 0:15 of the first
  await userEvent.click(caption().getByRole("button", { name: "Edit clip" }));
  caption().getByRole("slider", { name: "End of the clip" }).focus();
  await userEvent.keyboard("{ArrowLeft}{ArrowLeft}{ArrowLeft}{ArrowLeft}{ArrowLeft}{Enter}");
  await waitFor(() => expect(sent(calls)).toEqual([["POST /projects/366/clips/502/generate", { note: "" }], ["POST /projects/366/cut/edits", { snap: true, kind: "trim", piece: "c4", end: 14.5 }]]));
});

test("the start card says it is one video with a version for each hook, at one price, and marks each clip with its hook or as in all of them", async () => {
  await open(threeHooksPlan);
  const card = within(await chat().findByRole("region", { name: "The plan and the cast" }));
  expect(card.getByText("The plan is on the right: 9 clips for one video with 3 versions, each hook over the same body, at one price for all.")).toBeInTheDocument();
  const making = within(card.getByRole("list", { name: "What it will make" })).getAllByRole("listitem").map((li) => li.textContent);
  expect(making.slice(0, 4)).toEqual(["The lot, seconds afterClip 1 · 8 s · Hook 1$0.53", "He got the plateClip 2 · 4 s · Hook 2$0.26", "Eggs on the asphaltClip 3 · 4 s · Hook 3$0.26", "She’s okayClip 4 · 7 s · all 3 versions$0.46"]);
});

test("a round's card says which versions each changed clip is in: its own hook's only, or all of them", async () => {
  await open(threeHooksRound);
  const card = within(await chat().findByRole("region", { name: "Round 2" }));
  expect(within(card.getByRole("list", { name: "What it will make" })).getAllByRole("listitem").map((li) => li.textContent)).toEqual(["He got the plateClip 2 · 4 s · Hook 2 only$0.46", "Nobody’s buyingClip 9 · 8 s · in all 3 versions$0.53"]);
});

test("Plan lists each hook's clips first, then the body's scenes, which say they are in every version; a row of another hook puts its version on screen", async () => {
  const calls = await open(threeHooks());
  await userEvent.click(film().getByRole("button", { name: "Plan" }));
  expect(film().getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual(["Hook 11 clip · 8 s", "Hook 21 clip · 4 s", "Hook 31 clip · 4 s", "The lot, after1 clip · 7 s · body, in all 3 versions", "The store, twenty minutes earlier5 clips · 37 s · body, in all 3 versions"]);
  await userEvent.click(within(film().getByRole("region", { name: "Hook 3" })).getByRole("button", { name: /^3/ }));
  await waitFor(() => expect(hook(3)).toHaveAttribute("aria-pressed", "true"));
  await waitFor(() => expect(timeline().getByRole("button", { name: "Clip 3, 4 s" })).toHaveAttribute("aria-pressed", "true"));
  expect(cuts(calls)).toContain("GET /projects/366/cut?opening=3");
  expect(sent(calls)).toEqual([]);
});

test("an ordinary video has no switch, no word about versions or hooks on its cards, its plan or its clips, and one Download MP4 in its menu", async () => {
  const calls = await open(round2);
  await chat().findByRole("region", { name: "Round 2" });
  expect(film().queryByRole("group", { name: "Version" })).toBeNull();
  await userEvent.click(film().getByRole("button", { name: "Plan" }));
  expect(screen.getByRole("main")).not.toHaveTextContent(/version|hook \d/i);
  await userEvent.click(page().getByRole("button", { name: "More" }));
  expect(within(screen.getByRole("menu", { name: "More for Three men at Target" })).getAllByRole("menuitem", { name: /^Download/ }).map((a) => a.textContent?.trim())).toEqual(["Download MP4", "Download every clip (.zip)"]);
  expect(cuts(calls)).toEqual(["GET /projects/366/cut", "GET /projects/366/cut/versions"]);
});
