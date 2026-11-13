import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { editor } from "../test/people";
import { renderApp } from "../test/render";
import { fakeServer } from "../test/server";
import { HIS_NOTE, KIE_EMPTY, LEFT_OUT, archived, beingMade, broke, castChanged, castQuestion, delivered, earlier, edited, needsService, optionsQuestion, planUpdating, planWaiting, question, round2, stopped, voiceQuestion, twoQuestions, type Routes } from "../test/studioVideo";
import { setViewport } from "../test/viewport";

// One video in the new look (/s/b/1/videos/366): every press it has, and exactly what each sends. Each request is one
// the current site's page sends for the same press, through the same hook (the PR lists them side by side). A press
// sends once: pressed twice in a row, there is still one request. Opening the page sends nothing (video.test.tsx).
const OK: [number, unknown] = [200, {}];
async function open(routes: Routes) {
  const calls = fakeServer(routes);
  renderApp("/s/b/1/videos/366");
  await screen.findByRole("heading", { name: "Three men at Target" });
  await chat().findByRole("textbox", { name: "Tell the director what to change" });
  return calls;
}
/** Everything the page has sent that isn't a read: its method and path, and its body. */
const sent = (calls: ReturnType<typeof fakeServer>) => calls.filter((c) => !c.key.startsWith("GET ")).map((c) => (c.body === undefined ? [c.key] : [c.key, c.body]));
const page = () => within(screen.getByRole("main"));
const chat = () => within(screen.getByRole("region", { name: "The director" }));
const film = () => within(screen.getByRole("region", { name: "The video" }));
const caption = () => within(film().getByRole("group", { name: "The picked clip" }));
const clip = (name: RegExp) => userEvent.click(within(film().getByRole("group", { name: "Clips, in order, each as wide as it is long" })).getByRole("button", { name }));
const box = () => chat().getByRole("textbox", { name: "Tell the director what to change" });
const press = (within_: ReturnType<typeof within>, name: string | RegExp) => userEvent.dblClick(within_.getByRole("button", { name })); // twice: one request
const read = <T,>(routes: Routes, path: string) => routes[`GET /projects/366${path}`][1] as T;

beforeEach(() => {
  localStorage.clear();
  setViewport(1440);
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {}); // jsdom plays nothing
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

test("Approve and film answers the start card with make_it, once, from the card or from the header's same press; the look check's words are on the card before it", async () => {
  const calls = await open({ ...planWaiting, "POST /asks/7/answer": OK });
  const card = within(await chat().findByRole("region", { name: "The plan and the cast" }));
  expect(card.getByRole("note")).toHaveTextContent("The man in gray. This look reads as a man in his twenties, but the script says he is in his forties.Approve and film uses these looks as they are.");
  expect(page().getAllByRole("button", { name: "Approve and film about $4.87" })).toHaveLength(2); // the card's, and the header's
  await press(card, "Approve and film about $4.87");
  expect(sent(calls)).toEqual([["POST /asks/7/answer", { how: "make_it" }]]);
});

/** Holds the server's answer to one request until the returned function is called: a press while its request is in flight. */
function hold(key: string) {
  const answer = globalThis.fetch;
  let release = () => {};
  const gate = new Promise<void>((r) => (release = r));
  vi.stubGlobal("fetch", async (input: Request, init?: RequestInit) => {
    if (`${input.method} ${new URL(input.url).pathname.replace(/^\/api/, "")}` === key) await gate;
    return answer(input, init);
  });
  return release;
}

test("while its request is in flight a press is off, on the card and in the header, so it can't be sent twice", async () => {
  const calls = await open({ ...planWaiting, "POST /asks/7/answer": OK });
  const release = hold("POST /asks/7/answer");
  const [inHeader, onCard] = page().getAllByRole("button", { name: "Approve and film about $4.87" });
  await userEvent.click(onCard);
  await waitFor(() => expect(inHeader).toBeDisabled());
  expect(onCard).toBeDisabled();
  await userEvent.click(inHeader);
  release();
  await waitFor(() => expect(onCard).toBeEnabled());
  expect(sent(calls)).toEqual([["POST /asks/7/answer", { how: "make_it" }]]);
});

test("while the plan is being updated for a note there is no press, on the card or in the header, and the card says so", async () => {
  await open(planUpdating);
  const card = within(await chat().findByRole("region", { name: "The plan and the cast" }));
  expect(card.getByText("Updating the plan for your note…")).toBeInTheDocument();
  expect(card.getByText("The plan is being updated for your note. The press comes back with the new price.")).toBeInTheDocument();
  expect(page().queryByRole("button", { name: /Approve and film/ })).toBeNull();
});

test("a start card the server refuses says why in the server's words", async () => {
  await open({ ...planWaiting, "POST /asks/7/answer": [409, { detail: "The plan is being updated. Try again in a moment." }] });
  await press(await card("The plan and the cast"), "Approve and film about $4.87");
  expect(await chat().findByRole("alert")).toHaveTextContent("The plan is being updated. Try again in a moment.");
});

test.each([
  ["the look check objects: the press is Approve anyway, with the check's words", castChanged, "Approve anyway", true],
  ["nothing flagged: Approve cast and places", { ...castChanged, "GET /projects/366/cast": [200, { ...read<{ items: { look_fit?: unknown }[] }>(castChanged, "/cast"), items: read<{ items: object[] }>(castChanged, "/cast").items.map((i) => ({ ...i, look_fit: null })) }] } as Routes, "Approve cast and places", false],
])("the cast's own OK sends back each item's signature as read; %s", async (_case, routes, name, anyway) => {
  const calls = await open({ ...routes, "POST /projects/366/cast/approve": [200, read(routes, "/cast")] });
  const card = within(await chat().findByRole("region", { name: "Cast and places waiting for your OK" }));
  expect(card.getByRole("heading", { name: "The man in gray changed" })).toBeInTheDocument();
  if (anyway) expect(card.getByRole("note")).toHaveTextContent("The man in gray. This look reads as a man in his twenties, but the script says he is in his forties.");
  else expect(card.queryByRole("note")).toBeNull();
  expect(page().getAllByRole("button", { name })).toHaveLength(2);
  expect(page().getByRole("button", { name: "Stop" })).toBeInTheDocument(); // the run is still going: Stop stays in reach
  await press(card, name);
  expect(sent(calls)).toEqual([["POST /projects/366/cast/approve", { seen: { "char:11": "s", "char:12": "s2", "char:13": "s", "slot:4": "s", "place:21": "s", "place:22": "s" }, anyway }]]);
});

test("captions and time cards are two switches, on the start card and on the Cut view, each a cut edit", async () => {
  const cut = read<object>(delivered, "/cut");
  const calls = await open({ ...planWaiting, "POST /projects/366/cut/edits": [200, cut] });
  await userEvent.click(within(await chat().findByRole("region", { name: "The plan and the cast" })).getByRole("switch", { name: "Captions" }));
  await userEvent.click(film().getByRole("button", { name: "Cut" }));
  await userEvent.click(await film().findByRole("switch", { name: "Time cards" }));
  expect(sent(calls)).toEqual([
    ["POST /projects/366/cut/edits", { snap: false, kind: "captions", on: false }],
    ["POST /projects/366/cut/edits", { snap: false, kind: "cards", on: false }],
  ]);
});

const card = async (name: string) => within(await chat().findByRole("region", { name }));
const STORY = { ...read<object[]>(question, "/asks")[0], kind: "story", question: "Which way in?", saved: [], can: ["choice"], pick: "A", choices: [{ key: "A", title: "The lot first", why: "Starts on the outcome.", do: "", made: "", said: "", cannot: "", then: "" }, { key: "B", title: "The store first", why: "In order.", do: "", made: "", said: "", cannot: "", then: "" }] };
const WHO = "Who plays the woman with the stroller?";
test.each<[string, Routes, string, (c: ReturnType<typeof within>) => Promise<unknown>, unknown[][]]>([
  ["someone saved, picked by name", castQuestion, WHO, async (c) => (await userEvent.click(c.getByRole("button", { name: "Dana" })), press(c, "Use Dana")), [["POST /asks/8/answer", { how: "saved", option: "char:31" }]]],
  ["drawing options, at its price", castQuestion, WHO, (c) => press(c, "Draw 3 looks Up to $0.10 · for this video only"), [["POST /asks/8/generate", {}]]],
  ["a reply in words", castQuestion, WHO, async (c) => (await userEvent.click(c.getByRole("button", { name: /Tell me in words/ })), await userEvent.type(c.getByRole("textbox", { name: "Your answer" }), " A tired mother, forties "), press(c, "Send the answer")), [["POST /asks/8/answer", { how: "reply", text: "A tired mother, forties" }]]],
  ["an option it drew", optionsQuestion, WHO, (c) => press(c, "Use option 1"), [["POST /asks/8/answer", { how: "option", option: 0 }]]],
  ["more like one of them", optionsQuestion, WHO, async (c) => (await userEvent.click(c.getByRole("button", { name: "Option 2" })), press(c, "More like 2 up to $0.10")), [["POST /asks/8/generate", { like: 1 }]]],
  ["options with something changed", optionsQuestion, WHO, async (c) => (await userEvent.click(c.getByRole("button", { name: "Change something…" })), await userEvent.type(c.getByRole("textbox", { name: "What should change" }), "older"), press(c, "Make 3 more up to $0.10")), [["POST /asks/8/generate", { change: "older" }]]],
  ["a voice from its audition", voiceQuestion, "Which voice is the presenter?", (c) => press(c, "Use Warm"), [["POST /asks/10/answer", { how: "voice", option: "v1" }]]],
  ["a voice described", voiceQuestion, "Which voice is the presenter?", async (c) => (await userEvent.click(c.getByRole("button", { name: /Describe it/ })), await userEvent.type(c.getByRole("textbox", { name: "What the voice sounds like" }), "Late 40s, tired"), press(c, "Save and use it")), [["POST /asks/10/answer", { how: "describe", text: "Late 40s, tired", name: "" }]]],
  ["the voices read again when none of them read", { ...voiceQuestion, "GET /projects/366/asks": [200, read<object[]>(voiceQuestion, "/asks").map((a) => ({ ...a, audition_failed: true }))] }, "Which voice is the presenter?", (c) => press(c, "Read them again"), [["POST /asks/10/answer", { how: "again" }]]],
  ["a story's choice", { ...question, "GET /projects/366/asks": [200, [STORY]] }, "Which way in?", (c) => press(c, "Go with B"), [["POST /asks/8/answer", { how: "choice", choice: "B" }]]],
])("a question is answered with %s", async (_how, routes, name, answer, expected) => {
  const calls = await open({ ...routes, "POST /asks/8/answer": OK, "POST /asks/8/generate": OK, "POST /asks/10/answer": OK });
  await answer(await card(name));
  expect(sent(calls)).toEqual(expected);
});

test("an upload on a question goes through the current site's own steps: uploading, the file, then the answer", async () => {
  const calls = await open({ ...castQuestion, "POST /asks/8/uploading": OK, "POST /files": [200, { id: 55 }], "POST /asks/8/answer": OK });
  const c = await card(WHO);
  await userEvent.upload(c.getByLabelText("Upload a photo, a still or a clip"), new File(["x"], "her.jpg", { type: "image/jpeg" }));
  await waitFor(() => expect(sent(calls)).toEqual([["POST /asks/8/uploading", { on: true }], ["POST /files"], ["POST /asks/8/answer", { how: "upload", file_id: 55 }]]));
});

test("with several questions open, a line above the message box says how many are waiting and which", async () => {
  await open(twoQuestions);
  expect(chat().getByText("2 waiting · The woman with the stroller · The presenter’s voice")).toBeInTheDocument();
});

test("a note: Enter sends it once with its files, Shift+Enter is a new line, and the box says what the state calls for", async () => {
  const calls = await open({ ...beingMade, "POST /files": [200, { id: 55 }], "POST /projects/366/director/messages": [200, read(beingMade, "/director")] });
  expect(box()).toHaveAttribute("placeholder", "Tell the director what to change");
  await userEvent.upload(chat().getByLabelText("Pictures or clips for this video"), Array.from({ length: 7 }, (_, i) => new File(["x"], `lot-${i}.jpg`, { type: "image/jpeg" })));
  await waitFor(() => expect(chat().getAllByRole("button", { name: /^Take off/ })).toHaveLength(6)); // six at most
  expect(chat().getByRole("button", { name: "Add pictures or clips for this video" })).toBeDisabled();
  await userEvent.type(box(), "More people in the lot{Shift>}{Enter}{/Shift}and one cart rolling{Enter}{Enter}");
  expect(sent(calls).filter(([key]) => key !== "POST /files")).toEqual([["POST /projects/366/director/messages", { text: "More people in the lot\nand one cart rolling", files: [55, 55, 55, 55, 55, 55] }]]);
  await waitFor(() => expect(box()).toHaveValue(""));
});

test("a refused note is never sent again by itself: the server's words show and his words come back into the box", async () => {
  const calls = await open({ ...delivered, "POST /projects/366/director/messages": [429, { detail: "That’s 30 notes on this run. Wait for it to finish." }] });
  expect(box()).toHaveAttribute("placeholder", "Say what to change: “warmer light in scene 2”, “swap the B-roll at 0:14”…");
  await userEvent.type(box(), "Warmer light in the store{Enter}");
  expect(await chat().findByText("That’s 30 notes on this run. Wait for it to finish.")).toBeInTheDocument();
  expect(box()).toHaveValue("Warmer light in the store");
  expect(sent(calls)).toEqual([["POST /projects/366/director/messages", { text: "Warmer light in the store" }]]);
});

test("a note after delivery comes back as a round: only the clips it changes, each by name with its price, and Make round 2", async () => {
  const calls = await open({ ...round2, "POST /asks/9/answer": OK });
  expect(chat().getByText(HIS_NOTE)).toBeInTheDocument();
  const c = await card("Round 2");
  expect(c.getByRole("heading", { name: "Round 2: 2 clips change" })).toBeInTheDocument();
  expect(within(c.getByRole("list", { name: "What it will make" })).getAllByRole("listitem").map((li) => li.textContent)).toEqual(["She’s okayClip 4 · 7 s$0.46", "Nobody’s buyingClip 9 · 8 s$0.53"]);
  expect(c.queryByRole("list", { name: "The cast and places" })).toBeNull();
  expect(page().getAllByRole("button", { name: "Make round 2 about $0.99" })).toHaveLength(2);
  await press(c, "Make round 2 about $0.99");
  expect(sent(calls)).toEqual([["POST /asks/9/answer", { how: "make_it" }]]);
  await userEvent.click(c.getByRole("button", { name: "Change this plan…" }));
  expect(box()).toHaveFocus();
});

test.each([
  ["a video made from a send stops through it", beingMade, "POST /freestyles/9/stop"],
  ["a video with no send stops its director", { ...beingMade, "GET /projects/366": [200, { ...read<object>(beingMade, ""), freestyle_id: null }] } as Routes, "POST /projects/366/director/stop"],
])("Stop asks first in a small confirmation; only its own Stop sends anything; %s", async (_case, routes, route) => {
  const calls = await open({ ...routes, [route]: [200, route.includes("freestyles") ? { ...(routes["GET /freestyles/9"][1] as object), status: "stopped" } : read(routes, "/director")] });
  await userEvent.click(page().getByRole("button", { name: "Stop" }));
  const ask = within(screen.getByRole("dialog", { name: "Stop the director?" }));
  expect(ask.getByText("It makes no more moves. What it already started still finishes, and nothing is undone.")).toBeInTheDocument();
  await userEvent.click(ask.getByRole("button", { name: "Keep going" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(sent(calls)).toEqual([]);
  await userEvent.click(page().getByRole("button", { name: "Stop" }));
  await press(within(screen.getByRole("dialog", { name: "Stop the director?" })), "Stop");
  await waitFor(() => expect(sent(calls)).toEqual([[route]]));
});

test("stopped: who stopped it and when, what is kept, Carry on with the rest of the run's price, and Start the plan again", async () => {
  const calls = await open({ ...stopped, "POST /projects/366/director/carry-on": [200, read(stopped, "/director")], "POST /projects/366/director/plan-again": [200, read(stopped, "/director")] });
  expect(chat().getByText(/^Reed stopped the director at \d\d:26\. Nothing more is being spent\.$/)).toBeInTheDocument();
  expect(chat().getByText("Stopped. The 4 finished clips are kept. Tell me what to change, or carry on where I left off.")).toBeInTheDocument();
  expect(page().queryByRole("button", { name: "Stop" })).toBeNull();
  await press(chat(), "Carry on · up to $2.41 more");
  await press(chat(), "Start the plan again");
  expect(sent(calls)).toEqual([["POST /projects/366/director/carry-on"], ["POST /projects/366/director/plan-again"]]);
});

test("a run that can't start now says why in the server's words, and its presses are off", async () => {
  const why = "Another video is using the picture service. This one can start when it finishes.";
  await open({ ...stopped, "GET /projects/366/director": [200, { ...read<object>(stopped, "/director"), start_blocked: why }] });
  expect(chat().getByText(why)).toBeInTheDocument();
  expect(chat().getByRole("button", { name: "Carry on · up to $2.41 more" })).toBeDisabled();
  expect(chat().getByRole("button", { name: "Start the plan again" })).toBeDisabled();
});

test("a provider account that is empty: the server's words say what to do, and Carry on with its price", async () => {
  const calls = await open({ ...needsService, "POST /projects/366/director/carry-on": [200, read(needsService, "/director")] });
  const c = await card("KIE is out of credits");
  expect(c.getByText("The director needs you")).toBeInTheDocument();
  expect(c.getByText(KIE_EMPTY)).toBeInTheDocument();
  await press(c, "Carry on up to $2.41");
  expect(sent(calls)).toEqual([["POST /projects/366/director/carry-on"]]);
});

test("a step that failed twice: try that clip again as the current site does, or carry on without it", async () => {
  const calls = await open({ ...broke, "POST /projects/366/clips/505/generate": OK, "POST /projects/366/director/carry-on": [200, read(broke, "/director")] });
  const c = await card("Clip 5 couldn’t be made");
  expect(c.getByText("The service couldn't finish this twice running. Nothing was charged.")).toBeInTheDocument();
  await press(c, "Try again up to $0.70");
  await press(c, "Carry on without it");
  expect(sent(calls)).toEqual([["POST /projects/366/clips/505/generate"], ["POST /projects/366/director/carry-on"]]);
});

test("a run that ended with nothing to carry on from its card offers Carry on at the director's price and Make it again", async () => {
  const run = { ...read<object>(stopped, "/director"), carry_on: "$2.41", run_expected_usd: 4.87 };
  const calls = await open({ ...stopped, "GET /projects/366/director/progress": [200, null], "GET /projects/366/director": [200, run], "POST /projects/366/director": [200, run], "POST /projects/366/director/carry-on": [200, run] });
  await press(chat(), "Carry on up to $2.41");
  await press(chat(), "Make it again about $4.87");
  expect(sent(calls)).toEqual([["POST /projects/366/director/carry-on"], ["POST /projects/366/director"]]);
});

test("Another take is a plain take at its price; a take the director flagged is remade with the director's own note", async () => {
  const calls = await open({ ...edited, "POST /projects/366/clips/503/generate": OK, "POST /projects/366/clips/504/generate": OK });
  await clip(/^Clip 3,/);
  await press(caption(), "Another take up to $0.50");
  await clip(/^Clip 4,/);
  expect(caption().getByText("The cart kid says “I got it” once more than the script.")).toBeInTheDocument();
  await press(caption(), "Remake it up to $0.50");
  expect(sent(calls)).toEqual([
    ["POST /projects/366/clips/503/generate", { note: "" }],
    ["POST /projects/366/clips/504/generate", { note: "Say the line once, as written." }],
  ]);
});

test("a take the server refuses says why in the server's words", async () => {
  await open({ ...delivered, "POST /projects/366/clips/504/generate": [409, { detail: "Fix this clip's problems first." }] });
  await clip(/^Clip 4,/);
  await press(caption(), "Another take up to $0.50");
  expect(await caption().findByRole("alert")).toHaveTextContent("Fix this clip's problems first.");
});

test("a clip left out of the cut says why and offers a note to the director about it, never the same take again", async () => {
  const calls = await open(delivered);
  await clip(/^Clip 2,/);
  expect(caption().getByText(LEFT_OUT)).toBeInTheDocument();
  expect(caption().queryByRole("button", { name: /take|again/i })).toBeNull();
  await userEvent.click(caption().getByRole("button", { name: "Tell the director how to change it" }));
  expect(box()).toHaveValue("Clip 2: ");
  expect(box()).toHaveFocus();
  expect(sent(calls)).toEqual([]);
});

test("Edit clip: a take is watched, then used, and the cut is made again straight after, as the current site does", async () => {
  const calls = await open({ ...edited, "POST /projects/366/clips/504/takes/124/use": OK, "POST /projects/366/cut": [200, read(edited, "/cut")] });
  await clip(/^Clip 4,/);
  await userEvent.click(caption().getByRole("button", { name: "Edit clip" }));
  expect(caption().getByRole("button", { name: "Watch take 1" })).toHaveTextContent("Take 1In the cut");
  expect(caption().queryByRole("button", { name: "Use this take" })).toBeNull();
  await userEvent.click(caption().getByRole("button", { name: "Watch take 2" }));
  expect(film().getByLabelText("Clip 4")).toHaveAttribute("src", "/api/files/224"); // it plays where the film was
  await press(caption(), "Use this take");
  await waitFor(() => expect(sent(calls)).toEqual([["POST /projects/366/clips/504/takes/124/use"], ["POST /projects/366/cut"]]));
});

test("trim moves one edge of the piece, in the cut's own seconds, with snap on, when the handle is let go", async () => {
  const calls = await open({ ...edited, "POST /projects/366/cut/edits": [200, read(edited, "/cut")] });
  await clip(/^Clip 4,/); // its piece is 0:12 to 0:19 of the cut
  await userEvent.click(caption().getByRole("button", { name: "Edit clip" }));
  const end = caption().getByRole("slider", { name: "End of the clip" });
  expect(end).toHaveAttribute("aria-valuetext", "7 s");
  end.focus();
  await userEvent.keyboard("{ArrowLeft}{ArrowLeft}{ArrowLeft}{ArrowLeft}{ArrowLeft}");
  expect(caption().getByText("0 s to 6.5 s of the take")).toBeInTheDocument();
  expect(sent(calls)).toEqual([]); // nothing until it is let go
  await userEvent.keyboard("{Enter}");
  expect(sent(calls)).toEqual([["POST /projects/366/cut/edits", { snap: true, kind: "trim", piece: "c4", end: 18.5 }]]);
});

test("sound effects are added at their price or taken off, with the current site's requests", async () => {
  const calls = await open({ ...edited, "POST /projects/366/clips/504/sound": OK, "DELETE /projects/366/clips/503/sound": OK });
  await clip(/^Clip 4,/);
  await userEvent.click(caption().getByRole("button", { name: "Edit clip" }));
  await press(caption(), "Add sound effects up to $0.05");
  await waitFor(() => expect(sent(calls)).toEqual([["POST /projects/366/clips/504/sound", { asked: "" }]]));
  await clip(/^Clip 3,/);
  await userEvent.click(caption().getByRole("button", { name: "Edit clip" }));
  await press(caption(), "Remove the sound effects");
  await waitFor(() => expect(sent(calls)[1]).toEqual(["DELETE /projects/366/clips/503/sound"]));
});

test("Tell the director… starts a note about that clip in the message box and sends nothing", async () => {
  const calls = await open(delivered);
  await clip(/^Clip 4,/);
  await userEvent.click(caption().getByRole("button", { name: "Edit clip" }));
  await userEvent.click(caption().getByRole("button", { name: "Tell the director…" }));
  expect(box()).toHaveValue("Clip 4: ");
  expect(box()).toHaveFocus();
  expect(sent(calls)).toEqual([]);
});

test("changes waiting for the next cut: the cut's own count, Undo all, and Make the cut, free", async () => {
  const calls = await open({ ...edited, "POST /projects/366/cut/undo-all": [200, read(edited, "/cut")], "POST /projects/366/cut": [200, read(edited, "/cut")] });
  expect(await film().findByText("2 changes not in the cut yet.")).toBeInTheDocument();
  await press(film(), "Undo all");
  await press(film(), "Make the cut free");
  expect(sent(calls)).toEqual([["POST /projects/366/cut/undo-all"], ["POST /projects/366/cut"]]);
});

test("the music: quieter by the slider's own decibels when it is let go, off, and back on", async () => {
  const cut = read<{ timeline: { music: object } }>(edited, "/cut");
  const off = { ...cut, timeline: { ...cut.timeline, music: { ...cut.timeline.music, removed: true } } };
  const calls = await open({ ...edited, "POST /projects/366/cut/edits": [200, off] });
  await userEvent.click(film().getByRole("button", { name: "Music" }));
  const slider = within(screen.getByRole("dialog", { name: "Music" })).getByRole("slider", { name: "Quieter under the voice, in decibels" });
  fireEvent.change(slider, { target: { value: "14" } });
  expect(screen.getByText("A lot (−14 dB)")).toBeInTheDocument();
  expect(sent(calls)).toEqual([]);
  fireEvent.pointerUp(slider);
  await waitFor(() => expect(sent(calls)).toEqual([["POST /projects/366/cut/edits", { snap: false, kind: "music", quieter_db: 14 }]]));
  await press(film(), "Music off Put it back"); // the server's answer: the music is off now
  await waitFor(() => expect(sent(calls)[1]).toEqual(["POST /projects/366/cut/edits", { snap: false, kind: "music", removed: false }]));
});

test("turning the music off is one cut edit", async () => {
  const calls = await open({ ...edited, "POST /projects/366/cut/edits": [200, read(edited, "/cut")] });
  await userEvent.click(film().getByRole("button", { name: "Music" }));
  await press(within(screen.getByRole("dialog", { name: "Music" })), "Turn the music off");
  expect(sent(calls)).toEqual([["POST /projects/366/cut/edits", { snap: false, kind: "music", removed: true }]]);
});

test("a finished video whose cast changed afterwards keeps Download in the header: the cast's OK is the chat card's only", async () => {
  const cast = read<{ items: object[] }>(castChanged, "/cast");
  await open({ ...delivered, "GET /projects/366/cast": [200, { ...cast, asked: false, items: cast.items.map((i) => ({ ...i, look_fit: null })) }] });
  expect(page().getByRole("link", { name: "Download" })).toHaveAttribute("href", "/api/files/90");
  expect(page().getAllByRole("button", { name: "Approve cast and places" })).toHaveLength(1);
  expect(within(chat().getByRole("region", { name: "Cast and places waiting for your OK" })).getByRole("button", { name: "Approve cast and places" })).toBeEnabled();
});

test("a piece with no picture of its own shows the first frame of its take", async () => {
  const cut = read<{ timeline: { pieces: object[] } }>(delivered, "/cut");
  await open({ ...delivered, "GET /projects/366/cut": [200, { ...cut, timeline: { ...cut.timeline, pieces: cut.timeline.pieces.map((x) => ({ ...x, poster_file_id: null })) } }] });
  const first = within(film().getByRole("group", { name: "Clips, in order, each as wide as it is long" })).getAllByRole("button")[0];
  expect(first.querySelector("video")).toHaveAttribute("src", expect.stringMatching(/^\/api\/files\/\d+#t=0\.1$/));
  expect(first.querySelector("img")).toBeNull();
});

const menu = async () => (await userEvent.click(page().getByRole("button", { name: "More" })), within(screen.getByRole("menu", { name: "More for Three men at Target" })));
test("delivered: Download in the header, and the menu's items; What it cost opens So far; the downloads are plain links", async () => {
  await open(delivered);
  expect(page().getByRole("link", { name: "Download" })).toHaveAttribute("href", "/api/files/90");
  expect(page().getByRole("link", { name: "Download" })).toHaveAttribute("download", "three-men-at-target.mp4");
  const m = await menu();
  expect(m.getAllByRole("menuitem").map((i) => i.textContent?.trim())).toEqual(["What it cost…", "Rename…", "Move to folder…", "Make variations…", "Download MP4", "Download every clip (.zip)", "Archive"]);
  expect(m.getByRole("menuitem", { name: "Download every clip (.zip)" })).toHaveAttribute("href", "/api/projects/366/clips.zip");
  await userEvent.click(m.getByRole("menuitem", { name: "What it cost…" }));
  expect(await within(screen.getByRole("dialog", { name: "So far" })).findByText("Total")).toBeInTheDocument();
});

test("Rename saves the send's title, with Undo in the toast", async () => {
  const calls = await open({ ...delivered, "PATCH /freestyles/9": OK });
  await userEvent.click((await menu()).getByRole("menuitem", { name: "Rename…" }));
  const name = within(screen.getByRole("dialog", { name: "Rename this video" })).getByRole("textbox", { name: "Name" });
  await userEvent.clear(name);
  await userEvent.type(name, "Three men, no carts{Enter}");
  expect(await screen.findByText("Renamed to “Three men, no carts”.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Undo" }));
  await waitFor(() => expect(sent(calls)).toEqual([["PATCH /freestyles/9", { title: "Three men, no carts" }], ["PATCH /freestyles/9", { title: "Three men at Target" }]]));
});

test("Move to folder lists the brand's folders in the menu and files the video in the one picked", async () => {
  const tree = { folders: [{ id: 3, parent_id: null, name: "Target ads", count: 2, can_manage: true, ideas: [], more: 0, folders: [] }], unsorted: { id: null, parent_id: null, name: "Unsorted", count: 1, can_manage: false, ideas: [], more: 0, folders: [] } };
  const calls = await open({ ...delivered, "GET /brands/1/tree": [200, tree], "POST /folders/file": OK });
  const m = await menu();
  await userEvent.click(m.getByRole("menuitem", { name: "Move to folder…" }));
  expect(m.getByRole("menuitemradio", { name: "Unsorted" })).toHaveAttribute("aria-checked", "true");
  await userEvent.click(m.getByRole("menuitemradio", { name: "Target ads" }));
  await waitFor(() => expect(sent(calls)).toEqual([["POST /folders/file", { kind: "video", ids: [366], folder_id: 3 }]]));
});

test("Make variations asks for what the current dialog asks: how many, which part, and a note", async () => {
  const calls = await open({ ...delivered, "GET /projects/366/variations": [200, { state: "none", videos: [], blocked: "" }], "POST /projects/366/variations": [200, { state: "writing", videos: [], blocked: "" }] });
  await userEvent.click((await menu()).getByRole("menuitem", { name: "Make variations…" }));
  const d = within(screen.getByRole("dialog", { name: "Make variations" }));
  await userEvent.click(d.getByRole("button", { name: "2" }));
  await userEvent.click(d.getByRole("button", { name: "The ending" }));
  await userEvent.type(d.getByRole("textbox", { name: "Note, if you have one" }), "End on the empty lot");
  await waitFor(() => expect(d.getByRole("button", { name: "Make variations" })).toBeEnabled());
  await press(d, "Make variations");
  expect(sent(calls)).toEqual([["POST /projects/366/variations", { count: 2, part: "ending", note: "End on the empty lot" }]]);
});

test("Archive asks first, then archives; its toast's Undo restores", async () => {
  const calls = await open({ ...delivered, "POST /projects/366/archive": OK, "POST /projects/366/restore": OK });
  await userEvent.click((await menu()).getByRole("menuitem", { name: "Archive" }));
  expect(sent(calls)).toEqual([]);
  const d = within(screen.getByRole("dialog", { name: "Archive “Three men at Target”?" }));
  expect(d.getByText(/^It leaves the lists\. Its clips and downloads are kept, and you can restore it\./)).toBeInTheDocument();
  await press(d, "Archive");
  await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
  await waitFor(() => expect(sent(calls)).toEqual([["POST /projects/366/archive"], ["POST /projects/366/restore"]]));
});

test("an archived video says so, its box is closed, nothing in it can be pressed but Restore", async () => {
  const calls = await open({ ...archived, "POST /projects/366/restore": OK });
  expect(box()).toBeDisabled();
  expect(box()).toHaveAttribute("placeholder", "It’s archived. Restore it to keep working.");
  expect((await menu()).getAllByRole("menuitem").map((i) => i.textContent?.trim())).toEqual(["What it cost…", "Download MP4", "Download every clip (.zip)"]);
  await userEvent.keyboard("{Escape}");
  await press(chat(), "Restore");
  await waitFor(() => expect(sent(calls)).toEqual([["POST /projects/366/restore"]]));
});

// The paid presses, pressed twice in the same tick: before the page can draw the first as in flight, so only the
// lock (./useLock; the message box's own in videos/runActions.ts) stands between two clicks and two charges.
const twice = async (el: HTMLElement, again: HTMLElement = el) => {
  fireEvent.click(el);
  fireEvent.click(again);
  await act(() => new Promise((r) => setTimeout(r, 40)));
};
const editing = async (n: RegExp) => (await clip(n), await userEvent.click(caption().getByRole("button", { name: "Edit clip" })));
const RUN = { ...read<object>(stopped, "/director"), carry_on: "$2.41", run_expected_usd: 4.87 };
const ENDED: Routes = { ...stopped, "GET /projects/366/director/progress": [200, null], "GET /projects/366/director": [200, RUN] };
const FAILED_DRAW: Routes = { ...castQuestion, "GET /projects/366/asks": [200, read<object[]>(castQuestion, "/asks").map((a) => ({ ...a, state: "failed" }))] };
const PAID: Routes = { "POST /asks/7/answer": OK, "POST /asks/9/answer": OK, "POST /asks/8/generate": OK, "POST /projects/366/clips/503/generate": OK, "POST /projects/366/clips/504/generate": OK, "POST /projects/366/clips/505/generate": OK, "POST /projects/366/clips/504/sound": OK, "POST /projects/366/director": [200, RUN], "POST /projects/366/director/carry-on": [200, RUN], "POST /projects/366/director/plan-again": [200, RUN], "POST /projects/366/variations": [200, { state: "writing", videos: [], blocked: "" }], "GET /projects/366/variations": [200, { state: "none", videos: [], blocked: "" }] };
test.each<[string, Routes, () => Promise<HTMLElement>, unknown[]]>([
  ["Approve and film", planWaiting, async () => (await card("The plan and the cast")).getByRole("button", { name: "Approve and film about $4.87" }), ["POST /asks/7/answer", { how: "make_it" }]],
  ["Make round 2", round2, async () => (await card("Round 2")).getByRole("button", { name: "Make round 2 about $0.99" }), ["POST /asks/9/answer", { how: "make_it" }]],
  ["Draw options", castQuestion, async () => (await card(WHO)).getByRole("button", { name: /^Draw 3 looks/ }), ["POST /asks/8/generate", {}]],
  ["Try again, after a drawing that failed", FAILED_DRAW, async () => (await card(WHO)).getByRole("button", { name: /^Try again/ }), ["POST /asks/8/generate", {}]],
  ["More like one", optionsQuestion, async () => (await card(WHO)).getByRole("button", { name: "More like 1 up to $0.10" }), ["POST /asks/8/generate", { like: 0 }]],
  ["Change something", optionsQuestion, async () => {
    const c = await card(WHO);
    await userEvent.click(c.getByRole("button", { name: "Change something…" }));
    await userEvent.type(c.getByRole("textbox", { name: "What should change" }), "older");
    return c.getByRole("button", { name: "Make 3 more up to $0.10" });
  }, ["POST /asks/8/generate", { change: "older" }]],
  ["Another take", edited, async () => (await clip(/^Clip 3,/), caption().getByRole("button", { name: "Another take up to $0.50" })), ["POST /projects/366/clips/503/generate", { note: "" }]],
  ["Remake it", edited, async () => (await clip(/^Clip 4,/), caption().getByRole("button", { name: "Remake it up to $0.50" })), ["POST /projects/366/clips/504/generate", { note: "Say the line once, as written." }]],
  ["Try again, on a step that failed", broke, async () => (await card("Clip 5 couldn’t be made")).getByRole("button", { name: "Try again up to $0.70" }), ["POST /projects/366/clips/505/generate"]],
  ["Carry on, after a Stop", stopped, () => chat().findByRole("button", { name: "Carry on · up to $2.41 more" }), ["POST /projects/366/director/carry-on"]],
  ["Carry on, when it needs him", needsService, async () => (await card("KIE is out of credits")).getByRole("button", { name: "Carry on up to $2.41" }), ["POST /projects/366/director/carry-on"]],
  ["Start the plan again", stopped, () => chat().findByRole("button", { name: "Start the plan again" }), ["POST /projects/366/director/plan-again"]],
  ["Make it again", ENDED, () => chat().findByRole("button", { name: "Make it again about $4.87" }), ["POST /projects/366/director"]],
  ["Add sound effects", edited, async () => (await editing(/^Clip 4,/), caption().getByRole("button", { name: "Add sound effects up to $0.05" })), ["POST /projects/366/clips/504/sound", { asked: "" }]],
  ["Make variations", delivered, async () => {
    await userEvent.click((await menu()).getByRole("menuitem", { name: "Make variations…" }));
    const confirm = within(screen.getByRole("dialog", { name: "Make variations" })).getByRole("button", { name: "Make variations" });
    await waitFor(() => expect(confirm).toBeEnabled());
    return confirm;
  }, ["POST /projects/366/variations", { count: 3, part: "hook", note: "" }]],
])("%s, pressed twice in the same tick, is one request", async (_press, routes, find, expected) => {
  const calls = await open({ ...routes, ...PAID });
  await twice(await find());
  expect(sent(calls)).toEqual([expected]);
});

test("Approve and film pressed on the card and in the header in the same tick is one request", async () => {
  const calls = await open({ ...planWaiting, ...PAID });
  await card("The plan and the cast");
  const [inHeader, onCard] = page().getAllByRole("button", { name: "Approve and film about $4.87" });
  await twice(onCard, inHeader);
  expect(sent(calls)).toEqual([["POST /asks/7/answer", { how: "make_it" }]]);
});

test("a note sent twice before the box has been drawn empty is one note", async () => {
  const calls = await open({ ...delivered, "POST /projects/366/director/messages": [200, read(delivered, "/director")] });
  await userEvent.type(box(), "Warmer light in the store");
  act(() => {
    fireEvent.keyDown(box(), { key: "Enter" }); // both land before the page draws anything: the box's own lock
    fireEvent.keyDown(box(), { key: "Enter" });
  });
  await act(() => new Promise((r) => setTimeout(r, 40)));
  expect(sent(calls)).toEqual([["POST /projects/366/director/messages", { text: "Warmer light in the store" }]]);
});

test.each([
  ["a video the earlier director made", earlier],
  ["anyone but the owner", { ...delivered, "GET /auth/me": [200, editor] } as Routes],
])("%s opens the current site's page for it, not this one", async (_who, routes) => {
  fakeServer(routes);
  renderApp("/s/b/1/videos/366");
  expect(await screen.findByRole("list", { name: "Conversation with the director" })).toBeInTheDocument(); // the current page's chat
  expect(screen.queryByRole("region", { name: "The director" })).toBeNull();
});
