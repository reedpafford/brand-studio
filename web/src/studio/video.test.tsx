import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { owner } from "../test/people";
import { renderApp } from "../test/render";
import { fakeServer } from "../test/server";
import { LEFT_OUT, beingMade, delivered, planWaiting, question, type Routes } from "../test/studioVideo";
import { setViewport } from "../test/viewport";

// One video in the new look (the redesign, stage 2; /s/b/1/videos/366), to read and watch. The fixtures are one video
// in four states (test/studioVideo.ts). Nothing on this page sends anything.
async function open(routes: Routes) {
  const calls = fakeServer(routes);
  renderApp("/s/b/1/videos/366");
  await screen.findByRole("heading", { name: "Three men at Target" });
  return calls;
}
const page = () => within(screen.getByRole("main"));
const chat = () => within(screen.getByRole("region", { name: "The director" }));
const film = () => within(screen.getByRole("region", { name: "The video" }));
const view = (name: string) => userEvent.click(film().getByRole("button", { name }));
const caption = () => film().getByRole("group", { name: "The picked clip" });
const timeline = () => within(film().getByRole("group", { name: "Clips, in order, each as wide as it is long" }));

beforeEach(() => {
  localStorage.clear();
  setViewport(1440);
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {}); // jsdom plays nothing
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

test.each([
  ["the plan waiting", planWaiting],
  ["being made", beingMade],
  ["delivered", delivered],
  ["a question waiting", question],
])("%s: the page only reads, through every view and the money", async (_state, routes) => {
  const calls = await open(routes);
  await chat().findByRole("button", { name: "Show all 9 lines" });
  for (const name of ["Cut", "Plan", "Cast"]) await view(name);
  await userEvent.click(page().getByRole("button", { name: /^\$/ }));
  expect(await within(screen.getByRole("dialog", { name: "So far" })).findByText("Total")).toBeInTheDocument();
  for (const read of ["", "/director", "/director/progress", "/idea", "/asks", "/clips", "/breakdown", "/cut", "/cast", "/assets"]) expect(calls.map((c) => c.key)).toContain(`GET /projects/366${read}`);
  expect(calls.filter((c) => !c.key.startsWith("GET "))).toEqual([]);
});

test("the header says where it is, the look and format, the server's status, and the money with the run's estimate; the money opens So far by part", async () => {
  await open(beingMade);
  expect(page().getByRole("link", { name: "Videos" })).toHaveAttribute("href", "/s/b/1/videos");
  expect(page().getByText("Movie · Dialogue")).toBeInTheDocument();
  expect(page().getByText("Working · 4 of 9")).toBeInTheDocument();
  await userEvent.click(page().getByRole("button", { name: "$2.46 so far · this run about $4.87" }));
  const parts = within(screen.getByRole("dialog", { name: "So far" }));
  await parts.findByText("Total");
  expect(parts.getAllByRole("term").map((t) => `${t.textContent}: ${t.nextElementSibling?.textContent}`)).toEqual(["Claude’s thinking: $0.61", "Looks: $0.30", "Takes: $1.55", "Total: $2.46", "Still to go: about $2.41"]);
});

test("the plan waiting: his script's opening lines, the treatment, and the start card to read (the plan, the cast, each clip's price), with one link to answer it on the current site", async () => {
  await open(planWaiting);
  expect(await chat().findByText("[Dusk in a Target parking lot. A siren is screaming and a white strobe flashes across the lot.]")).toBeInTheDocument();
  expect(chat().queryByText("Wait. Nobody's buying anything.")).toBeNull();
  await userEvent.click(chat().getByRole("button", { name: "Show all 9 lines" }));
  expect(chat().getByText("Wait. Nobody's buying anything.")).toBeInTheDocument();
  expect(chat().getAllByRole("term").map((t) => t.textContent)).toEqual(["Hook", "Story", "Why it holds"]);
  expect(chat().getByText("A siren, a white strobe, a van pulling away with its door open.")).toBeInTheDocument();

  const card = within(await chat().findByRole("region", { name: "Make it for about $4.87?" }));
  expect(card.getByText("Ready to start")).toBeInTheDocument();
  expect(card.getByText("Nothing is filmed until you say so.")).toBeInTheDocument();
  expect(card.getByText("The plan is on the right: 9 clips, about 60 s.")).toBeInTheDocument();
  const cast = within(card.getByRole("list", { name: "The cast and places" })).getAllByRole("listitem").map((li) => li.textContent);
  expect(cast).toEqual(["PaigeFrom your libraryVoice: Light and clear, a little dry", "The man in grayNew for this video", "The woman with the strollerNew for this videoVoice: Fast and breathless", "The cart kidNew for this video", "Target parking lotDrawn for this video", "Target aislesDrawn for this video"]);
  const making = within(card.getByRole("list", { name: "What it will make" })).getAllByRole("listitem").map((li) => li.textContent);
  expect(making.slice(0, 2)).toEqual(["Clip 18 s$0.53", "Clip 24 s$0.26"]); // each clip the run makes, and its price
  expect(making).toHaveLength(9);
  expect(card.getByRole("link", { name: "Answer this on the current site" })).toHaveAttribute("href", "/b/1/videos/366");
  expect(card.queryByRole("button")).toBeNull();

  expect(chat().queryByRole("list", { name: "The director’s steps" })).toBeNull(); // nothing runs until Make it
  expect(page().queryByRole("textbox")).toBeNull();
  expect(chat().getByRole("link", { name: "open this video on the current site" })).toHaveAttribute("href", "/b/1/videos/366");
  expect(film().getByRole("button", { name: "Plan" })).toHaveAttribute("aria-pressed", "true"); // nothing is filmed: the plan first
});

test("being made: the steps done, now and to come with the run's cost, a pinned progress line, his note and the reply in order, and the clips as they arrive", async () => {
  await open(beingMade);
  const steps = within(await chat().findByRole("list", { name: "The director’s steps" })).getAllByRole("listitem");
  expect(steps.map((li) => li.textContent?.split(":")[0])).toEqual(["Done", "Done", "Done", "Now", "To come"]);
  expect(steps[3]).toHaveTextContent("Now: Making takes: 4 of 9Clip 5 · scene 2 · 7 s · about 1 min");
  expect(chat().getByText("$2.46 on this run · about $4.87 (estimate)")).toBeInTheDocument();
  expect(chat().getByText("4 of 9 clips made").closest("[role=status]")).toHaveTextContent("4 of 9 clips madeabout 4 min left");
  expect(chat().getByText("Make it for about $4.87?").parentElement).toHaveTextContent("Answered by Reed"); // the start card, answered: a line
  const note = chat().getByText("Add shoppers in the store, going about their evening.");
  const reply = chat().getByText("Got it. Clip 6 isn’t filmed yet, so it is made that way. No extra cost.");
  expect(note.compareDocumentPosition(reply) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

  expect(film().getByRole("button", { name: "Cut" })).toHaveAttribute("aria-pressed", "true");
  expect(film().getByText("No cut yet. Clips show here as they are made.")).toBeInTheDocument();
  expect(timeline().getAllByRole("button").map((b) => b.getAttribute("aria-label")).slice(3, 6)).toEqual(["Clip 4, 7 s, not in the cut yet", "Clip 5, 7 s, being made now", "Clip 6, 6 s, planned"]);
  expect(timeline().getByRole("button", { name: "Clip 5, 7 s, being made now" })).toHaveAttribute("aria-pressed", "true");
  expect(caption()).toHaveTextContent("Clip 5of 9 · 7 s · being made nowPAIGEWeird. But whatever.");
  await userEvent.click(timeline().getByRole("button", { name: "Clip 1, 8 s, not in the cut yet" }));
  expect(film().getByLabelText("Clip 1")).toHaveAttribute("src", "/api/files/201"); // its own take plays
  expect(caption()).toHaveTextContent("Clip 1of 9 · 8 s · not in the cut yetSTROLLER MOMTwo men just tried to abduct a girl in the Target parking lot!");
});

test("while the plan is written, the director's thinking and the plan so far show as they come, and the progress line says what it is doing", async () => {
  const [, progress] = question["GET /projects/366/director/progress"] as [number, object];
  await open({ ...question, "GET /projects/366/asks": [200, []], "GET /projects/366/director/progress": [200, { ...progress, status: "working", title: "Writing the plan", tone: "now", scenes: [], clips: 0 }], "GET /projects/366/director/thinking": [200, { thinking: "The script opens after the attack, not before it.", written: ["Hook: a siren, a van leaving"] }] });
  expect(await chat().findByText("The script opens after the attack, not before it.")).toBeInTheDocument();
  expect(chat().getByRole("list", { name: "The plan so far" })).toHaveTextContent("Hook: a siren, a van leaving");
  expect(chat().getByText("Writing the plan").closest("[role=status]")).toBeInTheDocument();
});

test("delivered: the delivery note as the server words it, the cut on the player, and the timeline with a time card and the clip left out", async () => {
  await open(delivered);
  expect(await chat().findByText("A 55-second cut in eight clips, every line as written.")).toBeInTheDocument();
  expect(chat().getAllByRole("heading", { level: 4 }).map((h) => h.textContent)).toEqual(["What I made", "What I watched and redid", "What remains uncertain", "What I need from you"]);
  expect(chat().getByText("0:12").parentElement).toHaveTextContent("0:12 Her mouth moved on a line that is voice-over.");
  expect(chat().getByText(`Clip 2 couldn’t be made, so the cut is without it: ${LEFT_OUT}`)).toBeInTheDocument();
  expect(page().getByRole("button", { name: "$4.61 · 58 s" })).toBeInTheDocument();

  expect(film().getByLabelText("The cut")).toHaveAttribute("src", "/api/files/90");
  expect(film().getByText(/^Captions/)).toHaveTextContent("Captions on · Time cards on");
  expect(timeline().getAllByRole("button").map((b) => b.getAttribute("aria-label"))).toEqual(["Clip 1, 8 s", "Clip 2, 4 s, left out of the cut", "Clip 3, 4 s", "Clip 4, 7 s", "Time card: TWENTY MINUTES EARLIER", "Clip 5, 7 s", "Clip 6, 6 s", "Clip 7, 8 s", "Clip 8, 8 s", "Clip 9, 8 s"]);
  expect(film().getByText("0:00 / 0:58")).toBeInTheDocument();

  const card = timeline().getByRole("button", { name: "Time card: TWENTY MINUTES EARLIER" });
  expect(card).toHaveTextContent("TWENTY MINUTES EARLIER"); // a piece with its words, and no number
  await userEvent.click(card);
  expect(card).toHaveAttribute("aria-pressed", "true");
  expect(caption()).toHaveTextContent("Time cardbefore clip 5 · 2.6 sTWENTY MINUTES EARLIER");
  expect(film().getByText("0:19 / 0:58")).toBeInTheDocument(); // the film moved to it

  await userEvent.click(timeline().getByRole("button", { name: "Clip 2, 4 s, left out of the cut" }));
  expect(caption()).toHaveTextContent(`Clip 2of 9 · 4 sLeft out${LEFT_OUT}`);
  expect(film().getByText("Left out of the cut")).toBeInTheDocument(); // on the frame, where the film was
});

test("the playhead follows the film, and the picked clip follows the playhead", async () => {
  await open(delivered);
  const cut = await film().findByLabelText("The cut");
  Object.defineProperties(cut, { currentTime: { value: 30 }, paused: { value: false } });
  fireEvent.timeUpdate(cut);
  expect(film().getByText("0:30 / 0:58")).toBeInTheDocument();
  expect(timeline().getByRole("button", { name: "Clip 6, 6 s" })).toHaveAttribute("aria-pressed", "true");
  expect(caption()).toHaveTextContent("Clip 6of 9 · 6 sShe turns into the next aisle. Same sweatsuit, same boots. Handheld.");
});

test("Plan: the clips by scene, each with who speaks and the line or Picture only; the picked row opens to its shot", async () => {
  await open(delivered);
  await view("Plan");
  const lot = within(await film().findByRole("region", { name: "The lot, after" }));
  expect(lot.getByRole("heading")).toHaveTextContent("The lot, after4 clips · 23 s");
  expect(lot.getAllByRole("button").map((b) => b.textContent)).toEqual([
    "1She runs with the stroller, phone to her ear, the van pulling out behind herSTROLLER MOMTwo men just tried to abduct a girl in the Target parking lot!8 s",
    "2He runs after the van, phone held highLeft outCART KIDI got the plate! I got it!4 s",
    "3The alarm still screaming in her hand, eggs broken on the asphaltPicture only4 s",
    "4Paige frozen, the woman beside her, dusk behindSTROLLER MOMShe's okay. She's standing right here.7 s",
  ]);
  const row = within(film().getByRole("region", { name: "The store, twenty minutes earlier" })).getByRole("button", { name: /^7/ });
  expect(row).toHaveAttribute("aria-expanded", "false");
  await userEvent.click(row);
  expect(row).toHaveAttribute("aria-expanded", "true");
  expect(film().getByText("Paige at the freezer doors; the third man reflected in the glass. Handheld.")).toBeInTheDocument();
});

test("Cast: people, then places and the product; the picked one's tray says who they are, where from, their voice, the look check's advice and a look on its way", async () => {
  await open(delivered);
  await view("Cast");
  const tiles = await film().findAllByRole("button", { name: /library|this video|alarm/ });
  expect(tiles.map((b) => b.textContent)).toEqual(["PaigeFrom your library", "The man in grayNew for this video", "The woman with the strollerNew for this video", "The cart kidNew for this video", "Target parking lotDrawn for this video", "Target aislesDrawn for this video", "Protector alarm"]);
  expect(film().getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual(expect.arrayContaining(["People", "Places and product"]));
  const tray = () => film().getByRole("status");
  expect(tray()).toHaveTextContent("Paige18, tall, volleyball sweatshirt · From your library · in 7 clips");
  expect(within(tray()).getByRole("button", { name: "Play Paige’s voice sample" }).querySelector("audio")).toHaveAttribute("src", "/api/voices/11/sample");
  await userEvent.click(tiles[1]);
  expect(tray()).toHaveTextContent("Forties, gray sweatsuit, work boots · New for this video · in 4 clipsThis look reads as a man in his twenties, but the script says he is in his forties.");
  await userEvent.click(tiles[2]);
  expect(tray()).toHaveTextContent("Voice: Fast and breathless"); // no sample to hear: its name
  await userEvent.click(tiles[3]);
  expect(tray()).toHaveTextContent("New for this video · in 1 clipDrawing");
});

test("a question waiting: the card to read, with what it offers and the link to answer it on the current site", async () => {
  await open(question);
  expect(page().getByText("Needs you · Who plays the woman with the stroller?")).toBeInTheDocument();
  const card = within(await chat().findByRole("region", { name: "Who plays the woman with the stroller?" }));
  expect(card.getByText("The director needs you")).toBeInTheDocument();
  expect(card.getByText("She opens the hook and has two lines. Use someone saved in Palace Guard, or make someone new.")).toBeInTheDocument();
  expect(card.getByText("Saved in Palace Guard")).toBeInTheDocument();
  expect(card.getAllByRole("listitem").map((li) => li.textContent)).toEqual(["Dana", "The store manager"]);
  expect(card.getByRole("link", { name: "Answer this on the current site" })).toHaveAttribute("href", "/b/1/videos/366");
  expect(card.queryByRole("button")).toBeNull();
  expect(chat().getByText(/^Waiting:/).closest("li")).toHaveTextContent("Waiting: Cast and places1 question waiting");
});

test("the divider is remembered on this computer, moves with the arrow keys within its limits, and a double-click puts it back", async () => {
  localStorage.setItem("bs.split", "500");
  await open(delivered);
  const bar = page().getByRole("separator", { name: "Resize the chat and the film" });
  const wrap = bar.parentElement!;
  expect(wrap.style.getPropertyValue("--thread")).toBe("500px");
  bar.focus();
  await userEvent.keyboard("{ArrowLeft}");
  expect(localStorage.getItem("bs.split")).toBe("320"); // the chat's least (jsdom has no widths)
  expect(wrap.style.getPropertyValue("--thread")).toBe("320px");
  await userEvent.dblClick(bar);
  expect(localStorage.getItem("bs.split")).toBeNull();
  expect(wrap.style.getPropertyValue("--thread")).toBe("");
});

test("a video that isn't there says so, with the way back to the videos", async () => {
  fakeServer({ "GET /auth/me": [200, owner], "GET /brands": [200, [{ id: 1, name: "Palace Guard", colours: [] }]] });
  renderApp("/s/b/1/videos/999");
  expect(await screen.findByText("That video doesn’t exist.")).toBeInTheDocument();
  expect(page().getByRole("link", { name: "Back to the videos" })).toHaveAttribute("href", "/s/b/1/videos");
});
