import { expect, test } from "vitest";
import { lookName, pickable, styleOf, type Look } from "./Looks";

const l = (id: string, name: string, parent?: string) => ({ id, name, parent, blurb: "", on: true }) as unknown as Look;
const looks = [l("house", "House"), l("paper", "Paper"), l("paper-flat", "Paper · Flat Paper", "paper"), l("skeleton", "Skeleton")];

test("a look's name: its own, a lane's server name, a lane's style and words as a fallback; never a raw id", () => {
  expect(lookName(looks, "paper")).toBe("Paper");
  expect(lookName(looks, "paper-flat")).toBe("Paper · Flat Paper");
  expect(lookName(looks, "skeleton-xray")).toBe("Skeleton · Xray");
  expect(lookName(looks, null)).toBe("House");
  expect(lookName(null, "claymation-goofy")).toBe("Claymation Goofy");
});

test("pickers offer the styles only; a lane's style is the one In use", () => {
  expect(pickable(looks).map((x) => x.id)).toEqual(["house", "paper", "skeleton"]);
  expect(styleOf(looks, "paper-flat")).toBe("paper");
  expect(styleOf(looks, "skeleton-cute")).toBe("skeleton");
  expect(styleOf(looks, "paper")).toBe("paper");
});
