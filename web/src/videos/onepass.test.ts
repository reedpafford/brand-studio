import { expect, test } from "vitest";
import { moneyOf } from "./VideoHead";

type Head = Parameters<typeof moneyOf>[0];
const money = (credits: number, usd: number | null) => ({ credits, usd });
const head = (kind: string, o: object = {}) => ({ title: "Eggs", status: { kind, words: "", reason: null, at: null, made: 0, total: 0 }, spent: money(0, 0), up_to: money(50, 5.14), budget: null, folder: null, format: "Dialogue", style: "Movie", seconds: 16, song: false, ...o }) as unknown as Head;

test("a video planned in one pass draws no stills: before anything is made its header says no clips yet", () => {
  expect(moneyOf(head("waiting"), false, false, true)[0]).toBe("No clips yet ·");
  expect(moneyOf(head("working"), false, false, true)[0]).toBe("Planning, no clips yet ·");
  expect(moneyOf(head("waiting"), false, false)[0]).toBe("No stills or clips yet ·"); // every other video, as before
});

test("once it has clips or a cut the header says what it cost, never that nothing is made", () => {
  const delivered = head("delivered", { spent: money(30.72, 3.16) });
  expect(moneyOf(delivered, false, true, true).join(" ")).toBe("$3.16 of up to $5.14");
  const uncapped = head("delivered", { spent: money(30.72, 0), actual: true, expected: money(5.4, 0.56) });
  expect(moneyOf(uncapped, false, true, true).join(" ")).toBe("This video so far $0.00 · next run about $0.56 (estimate)");
});
