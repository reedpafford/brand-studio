import { expect, test } from "vitest";
import { hookCount, parse, readOut, roleName, roles } from "./script";

// Made-up scripts in the formats Reed writes them in (the Palace Guard scripts doc).
const DIALOGUE = [
  "Intention: A scene at the pool, told as it happens",
  "",
  "Script:",
  "Cast: Mara (a lifeguard, 20s) · Ben (her brother)",
  "",
  "V1 - ACTION START",
  "",
  "[Noon at a town pool. A whistle goes.]",
  "POOL GUARD (on the radio): Everybody out! Now!",
  "[Ben drops his towel and runs.]",
  "BEN: I saw it! By the deep end!",
  "MARA (V.O.): I knew that gate was open. [She looks back.]",
  "MARA: Stay behind me.",
].join("\n");
const HOOKS = [
  "Why?: Parents share a warning they have not heard before.",
  "A second line of the note, with no label.",
  "Inspo (for the b-roll): https://example.com/reel/1",
  "",
  "Hook 1: A gate left open nearly cost a family everything.",
  "Plate: The OPEN gate…",
  "Hook 2 (proven winner): If your pool has a gate, check it tonight.",
  "",
  "Body:",
  "",
  "It was the first hot Saturday of the year.",
  "https://example.com/the-latch",
  "Nobody had looked at the latch since the autumn.",
].join("\n");
// Each opening under a heading of its own, several lines long.
const HEADED = ["Hook 1", "[A gate swings in the wind.]", "MARA: They nearly took her.", "", "HOOK 2 (the long one)", "BEN: I saw the van.", "BEN: It was white.", "", "Body", "MARA: She is okay."].join("\n");
const SONG = ["Mood 1: Slow country", "", "Script/lyrics:", "", "She left the gate on the latch that day.", "", "CHORUS (plays twice)", "Check it, check it twice."].join("\n");

const kinds = (text: string) => parse(text).map((p) => p.kind ?? "");

test("a line that starts with a NAME is spoken, with its speaker; [brackets] and what is above Script: are notes", () => {
  expect(kinds(DIALOGUE)).toEqual(["note", "", "note", "note", "", "note", "", "note", "said", "note", "said", "said", "said"]);
  const read = parse(DIALOGUE);
  expect(read[8]).toEqual({ line: "POOL GUARD (on the radio): Everybody out! Now!", kind: "said", label: "POOL GUARD (on the radio)", by: "POOL GUARD", words: "Everybody out! Now!" });
  expect(read[7].beat).toBe(true); // a line of what is going on: four seconds of the rough length
  expect(read[5].beat).toBe(false); // a heading
});

test("hooks are spoken wherever they sit; Why, Inspo, Plate, links and headings are notes; plain paragraphs are spoken", () => {
  expect(kinds(HOOKS)).toEqual(["note", "said", "note", "", "hook", "note", "hook", "", "note", "", "said", "note", "said"]);
  expect(parse(HOOKS)[6]).toMatchObject({ label: "Hook 2 (proven winner)", words: "If your pool has a gate, check it tonight." });
});

test("Script/lyrics: marks where the words start, and a heading in capitals is a note", () => {
  expect(kinds(SONG)).toEqual(["note", "", "note", "", "said", "", "note", "said"]);
});

test("the openings are counted as the script writes them: a heading line with the opening under it, or the opening on the line", () => {
  expect(hookCount(HEADED)).toBe(2);
  expect(hookCount(HOOKS)).toBe(2);
  expect(hookCount(DIALOGUE)).toBe(0);
  expect(hookCount("Hook them early, the coach said.")).toBe(0); // a spoken sentence, not an opening
  expect(readOut(HEADED)).toMatch(/^2 hooks · /);
});

test("the roles are the named speakers, each once, as written; shown with capitals on each word", () => {
  expect(roles(DIALOGUE)).toEqual(["POOL GUARD", "BEN", "MARA"]);
  expect(roles(HOOKS)).toEqual([]);
  expect(roleName("POOL GUARD")).toBe("Pool Guard");
});

test("the read-out counts voices, spoken lines and a rough length, and says how to write one while the box is empty", () => {
  expect(readOut("")).toBe("Put what’s going on in [brackets]. Lines that start with a name are spoken.");
  expect(readOut(DIALOGUE)).toBe("3 voices · 4 spoken lines · about 20 s. Your words are never changed.");
  expect(readOut(HOOKS)).toBe("2 hooks · 1 voice · 4 spoken lines · about 15 s. Your words are never changed.");
  expect(readOut("[A gate swings in the wind.]")).toBe("Nothing is spoken · about 5 s. Your words are never changed.");
  expect(readOut(Array(120).fill("MARA: One two three four five six seven eight nine ten.").join("\n"))).toBe("1 voice · 120 spoken lines · about 11 min. Your words are never changed.");
});
