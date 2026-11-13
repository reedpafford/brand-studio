import { act, cleanup, fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { renderApp } from "../test/render";
import { fakeServer } from "../test/server";
import { archived, beingMade, delivered, narrated, round2, stopped, voiceRound, type Routes } from "../test/studioVideo";
import { setViewport } from "../test/viewport";

// "Narration voice" in a video's Cast view (/s/b/1/videos/366 › Cast): the voice a narrated video is read in, and
// swapping it. A swap is two requests the current site already sends: the video's voice setting (cast/Presenter.tsx's
// pick, and its Undo), then Carry on (videos/runActions.ts). Nothing else is ever sent from here, and each press sends
// once. The fixtures are test/studioVideo.ts's: Roger (the app's) is the voice in use, Kim (the brand's own) the other.
const SET = "POST /projects/366/settings";
const CARRY = "POST /projects/366/director/carry-on";
const KIM = { voice: "voice:7" };
const NOT_READ = "not read yet · the video still plays in Roger";
const answer = <T,>(routes: Routes, path: string) => routes[`GET /projects/366${path}`][1] as T;
/** The server's answers to the two requests: the setting with what it was, and the run. */
const ANSWERS: Routes = { [SET]: [200, { settings: answer(voiceRound, "/settings"), was: { voice: null } }], [CARRY]: [200, answer(voiceRound, "/director")] };
const film = () => within(screen.getByRole("region", { name: "The video" }));
const chat = () => within(screen.getByRole("region", { name: "The director" }));
const row = () => within(film().getByRole("region", { name: "Narration voice" }));
const presses = () => row().queryAllByRole("button").map((b) => b.getAttribute("aria-label") ?? b.textContent);
const sent = (calls: ReturnType<typeof fakeServer>) => calls.filter((c) => !c.key.startsWith("GET ")).map((c) => (c.body === undefined ? [c.key] : [c.key, c.body]));
/** The video's Cast view, on a server that answers `routes` (the same object: a test changes what it answers next). */
async function open(routes: Routes) {
  const calls = fakeServer(routes);
  renderApp("/s/b/1/videos/366");
  await screen.findByRole("heading", { name: "Three men at Target" });
  await userEvent.click(film().getByRole("button", { name: "Cast" }));
  await film().findByRole("heading", { name: "People" });
  if (answer<{ voice?: string | null } | undefined>({ "GET /projects/366/host": [200, undefined], ...routes }, "/host")?.voice) await film().findByRole("region", { name: "Narration voice" });
  return calls;
}
const menu = async () => (await userEvent.click(row().getByRole("button", { name: "Change the voice" })), within(screen.getByRole("menu", { name: "Narration voice" })));
/** Two clicks before the page has drawn anything for the first: only the lock stands between them and two requests. */
const twice = async (el: HTMLElement) => {
  act(() => {
    fireEvent.click(el);
    fireEvent.click(el);
  });
  await act(() => new Promise((r) => setTimeout(r, 40)));
};

beforeEach(() => {
  localStorage.clear();
  setViewport(1440);
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {}); // jsdom plays nothing
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

test("a narrated video names the voice it is read in, with its sample; Change the voice lists the brand's voices then the app's, each with its line and sample, the one in use ticked", async () => {
  const calls = await open(narrated(delivered));
  expect(row().getByText("Roger")).toBeInTheDocument();
  expect(row().getByRole("button", { name: "Play Roger’s sample" }).querySelector("audio")).toHaveAttribute("src", "/api/voices/samples/Roger.mp3");
  const m = await menu();
  expect(m.getByText("You see the price first. Nothing is read until you approve it.")).toBeInTheDocument();
  expect(m.getAllByRole("menuitemradio").map((i) => i.textContent)).toEqual(["KimWarm, fifties", "Dr. PickleDeep, fixed", "RogerRelaxed man", "SarahWarm narrator", "HopeNatural woman", "GeorgeOlder man, dry"]);
  expect(m.getAllByRole("menuitemradio", { checked: true }).map((i) => i.textContent)).toEqual(["RogerRelaxed man"]);
  expect(m.getByRole("button", { name: "Play Kim’s sample" }).querySelector("audio")).toHaveAttribute("src", "/api/files/60");
  expect(m.queryByRole("button", { name: "Play Dr. Pickle’s sample" })).toBeNull(); // it has none
  await userEvent.click(m.getByRole("menuitemradio", { name: /^Roger/ })); // the one in use: nothing to change
  expect(screen.queryByRole("menu")).toBeNull();
  expect(sent(calls)).toEqual([]);
});

test("picking a voice sets it on the video and then carries on: the start card comes up with its line over the press, and the row waits with Undo", async () => {
  const routes = { ...narrated(delivered), ...ANSWERS };
  const calls = await open(routes);
  const pick = (await menu()).getByRole("menuitemradio", { name: /^Kim/ });
  Object.assign(routes, voiceRound); // what the server says once both are in: Kim is set, and the run's card waits
  await userEvent.click(pick);
  const card = within(await chat().findByRole("region", { name: "Round 2" }));
  expect(sent(calls)).toEqual([[SET, KIM], [CARRY]]);
  const line = card.getByText("The narration is read again in the Kim voice.");
  expect(line.compareDocumentPosition(card.getByRole("button", { name: "Make round 2 up to $1.84" })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(document.querySelector(".stage-wrap")).toHaveAttribute("data-first", "chat"); // the chat side, as for any open card
  expect(row().getByText("Kim")).toBeInTheDocument();
  expect(row().getByText(NOT_READ)).toBeInTheDocument();
  expect(presses()).toEqual(["Play Kim’s sample", "Undo"]); // the card is the press
});

test("an app voice is set by its key", async () => {
  const calls = await open({ ...narrated(delivered), ...ANSWERS });
  await userEvent.click((await menu()).getByRole("menuitemradio", { name: /^Sarah/ }));
  await vi.waitFor(() => expect(sent(calls)).toEqual([[SET, { voice: "stock:Sarah" }], [CARRY]]));
});

test("a setting the server refuses says why in the server's words, and nothing else is sent", async () => {
  const calls = await open({ ...narrated(delivered), ...ANSWERS, [SET]: [409, { detail: "Kim is still being cloned. Pick it once it is ready." }] });
  await userEvent.click((await menu()).getByRole("menuitemradio", { name: /^Kim/ }));
  expect(await row().findByRole("alert")).toHaveTextContent("Kim is still being cloned. Pick it once it is ready.");
  expect(sent(calls)).toEqual([[SET, KIM]]);
  expect(row().getByText("Roger")).toBeInTheDocument();
  expect(row().getByRole("button", { name: "Change the voice" })).toBeEnabled();
});

test("Carry on refused after the voice is set: the server's words, and the row waits with Read it in Kim and Undo; Undo puts back what the setting was", async () => {
  const routes: Routes = { ...narrated(delivered), ...ANSWERS, [CARRY]: [409, { detail: "The director is already working on this video." }] };
  const calls = await open(routes);
  const pick = (await menu()).getByRole("menuitemradio", { name: /^Kim/ });
  Object.assign(routes, narrated(delivered, "voice:7")); // the setting is in; no run started
  await userEvent.click(pick);
  expect(await row().findByRole("alert")).toHaveTextContent("The director is already working on this video.");
  expect(row().getByText(NOT_READ)).toBeInTheDocument();
  expect(presses()).toEqual(["Play Kim’s sample", "Read it in Kim", "Undo"]);
  await userEvent.click(row().getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(sent(calls)).toEqual([[SET, KIM], [CARRY], [SET, { voice: null, undo: true }]]));
});

test("a voice set but not read yet: Read it in Kim is Carry on alone; Undo, after a reload, sets the voice the video is read in", async () => {
  const calls = await open({ ...narrated(delivered, "voice:7"), ...ANSWERS });
  expect(row().getByText("Kim")).toBeInTheDocument();
  expect(presses()).toEqual(["Play Kim’s sample", "Read it in Kim", "Undo"]);
  await userEvent.click(row().getByRole("button", { name: "Read it in Kim" }));
  await vi.waitFor(() => expect(sent(calls)).toEqual([[CARRY]]));
  await vi.waitFor(() => expect(row().getByRole("button", { name: "Undo" })).toBeEnabled());
  await userEvent.click(row().getByRole("button", { name: "Undo" }));
  await vi.waitFor(() => expect(sent(calls)).toEqual([[CARRY], [SET, { voice: "stock:Roger", undo: true }]]));
});

test.each<[string, Routes, () => Promise<HTMLElement>, unknown[][]]>([
  ["Picking a voice", narrated(delivered), async () => (await menu()).getByRole("menuitemradio", { name: /^Kim/ }), [[SET, KIM], [CARRY]]],
  ["Read it in Kim", narrated(delivered, "voice:7"), async () => row().getByRole("button", { name: "Read it in Kim" }), [[CARRY]]],
  ["Undo", narrated(delivered, "voice:7"), async () => row().getByRole("button", { name: "Undo" }), [[SET, { voice: "stock:Roger", undo: true }]]],
])("%s, pressed twice in the same tick, is one of each request", async (_press, routes, find, expected) => {
  const calls = await open({ ...routes, ...ANSWERS });
  await twice(await find());
  expect(sent(calls)).toEqual(expected);
});

test.each([
  ["being made", narrated(beingMade), "Roger", ["Play Roger’s sample"]],
  ["archived", narrated(archived), "Roger", ["Play Roger’s sample"]],
  ["being made, with a voice not read yet", narrated(beingMade, "voice:7"), "Kim", ["Play Kim’s sample"]],
  ["stopped, with a voice not read yet (Carry on is the chat's): Undo alone", narrated(stopped, "voice:7"), "Kim", ["Play Kim’s sample", "Undo"]],
  ["read in a voice the brand's list doesn't have: its key, no sample", narrated(archived, null, { voice: "Austin" }), "Austin", []],
])("the row is only to read on a video that is %s", async (_state, routes, name, expected) => {
  await open(routes);
  expect(row().getByText(name)).toBeInTheDocument();
  expect(presses()).toEqual(expected);
});

test("a video with no narration (Movie, Dialogue, a song) looks exactly as today, and reads neither the setting nor the voices", async () => {
  await open(delivered); // today: a server that says nothing of a voice
  const today = document.querySelector(".castview")!.innerHTML;
  cleanup();
  const calls = await open(narrated(delivered, null, { voice: null }));
  await vi.waitFor(() => expect(calls.map((c) => c.key)).toContain("GET /projects/366/host"));
  expect(film().queryByRole("region", { name: "Narration voice" })).toBeNull();
  expect(document.querySelector(".castview")!.innerHTML).toBe(today);
  expect(calls.map((c) => c.key).filter((k) => k.endsWith("/settings") || k.endsWith("/voices"))).toEqual([]);
});

test.each([
  ["narrated, delivered", narrated(delivered)],
  ["a voice set but not read yet", narrated(delivered, "voice:7")],
  ["the start card of a new voice", voiceRound],
  ["narrated, being made", narrated(beingMade)],
  ["narrated, stopped", narrated(stopped, "voice:7")],
  ["narrated, archived", narrated(archived)],
  ["a presenter video", narrated(delivered, null, { on: true, state: "ready", presenter_id: 11 })],
  ["no narration", narrated(delivered, null, { voice: null })],
])("%s: opening the Cast view, and the menu when there is one, only reads", async (_state, routes) => {
  const calls = await open(routes);
  for (const b of film().queryAllByRole("button", { name: "Change the voice" })) await userEvent.click(b);
  await vi.waitFor(() => expect(calls.map((c) => c.key)).toContain("GET /projects/366/host"));
  expect(calls.filter((c) => !c.key.startsWith("GET "))).toEqual([]);
});

test("the start card of a new voice says which voice the narration is read again in; a round with no new voice says nothing of it", async () => {
  await open(voiceRound);
  expect(await chat().findByText("The narration is read again in the Kim voice.")).toBeInTheDocument();
  cleanup();
  await open(narrated(round2));
  await chat().findByRole("region", { name: "Round 2" });
  expect(chat().queryByText(/The narration is read again/)).toBeNull();
});
