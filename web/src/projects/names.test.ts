import { expect, test } from "vitest";
import { aboutMissingLook, plainWords, refName } from "./names";

const pieces = [{ key: "character-5", name: "Bo" }] as Parameters<typeof refName>[1];
const roles = new Map([["slot:3", "Coach"]]);
const nameOf = (id: string) => refName(id, pieces, roles);

test("raw ids become names: a character, a role not cast yet, the first frame, and the clip label", () => {
  expect(plainWords("c3: char:5 is in the clip but its sheet isn't attached", nameOf)).toBe("Clip c3: Bo is in the clip but its sheet isn't attached");
  expect(plainWords("c1: slot:3 needs a look", nameOf)).toBe("Clip c1: Coach needs a look");
  expect(plainWords("c1: frame:c1 isn't first", nameOf)).toBe("Clip c1: the first frame isn't first");
  expect(plainWords("c2: slot:9 and char:77", nameOf)).toBe("Clip c2: A role and Character");
  expect(plainWords("shot 1.2: the script has Nate here", nameOf)).toBe("shot 1.2: the script has Nate here");
});

test("a problem about a look that isn't approved is told apart from the others", () => {
  expect(aboutMissingLook("c1: Bo has no approved sheet")).toBe(true);
  expect(aboutMissingLook("c1: Bo is in the clip but its sheet isn't attached")).toBe(true);
  expect(aboutMissingLook("c1: 8 s is shorter than its shots")).toBe(false);
});
