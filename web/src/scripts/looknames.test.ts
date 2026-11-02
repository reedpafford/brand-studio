import { expect, test } from "vitest";
import { lookName, styleOf, type Look } from "./Looks";

const l = (id: string, name: string, lanes: { id: string; name: string }[] = []) => ({ id, name, lanes, blurb: "", on: true }) as unknown as Look;
const looks = [l("house", "House"), l("paper", "Paper", [{ id: "paper-flat", name: "Paper · Flat Paper" }]), l("skeleton", "Skeleton")];

test("a look's name: a style's own, a lane's from its card (#1139), a lane's style and words as a fallback; never a raw id", () => {
  expect(lookName(looks, "paper")).toBe("Paper");
  expect(lookName(looks, "paper-flat")).toBe("Paper · Flat Paper");
  expect(lookName(looks, "skeleton-xray")).toBe("Skeleton · Xray");
  expect(lookName(looks, null)).toBe("House");
  expect(lookName(null, "claymation-goofy")).toBe("Claymation Goofy");
});

test("a lane's style is the card it sits in, marked In use in the picker", () => {
  expect(styleOf(looks, "paper-flat")).toBe("paper");
  expect(styleOf(looks, "skeleton-cute")).toBe("skeleton");
  expect(styleOf(looks, "paper")).toBe("paper");
});
