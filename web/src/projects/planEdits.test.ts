import { expect, test } from "vitest";
import { joinNext, moveLine, splitAt, toPut, toggleStar, type PlanScene } from "./planEdits";

const line = (n: number) => ({ n, text: `line ${n}`, action: `see ${n}`, star: false });
const plan: PlanScene[] = [
  { id: "a", part: "Problem", place: "Kitchen", time: "Day", cast_ids: ["c1"], lines: [line(1), line(2)] },
  { id: "b", part: "Payoff", place: "Park", time: "Day", cast_ids: ["c2"], lines: [line(3)] },
];
const order = (s: PlanScene[]) => s.map((x) => x.lines.map((l) => l.n));

test("lines move only across their scene's edge, so every line stays once and in order; an emptied scene goes", () => {
  expect(order(moveLine(plan, 0, 1, 1))).toEqual([[1], [2, 3]]);
  expect(order(moveLine(plan, 1, 0, -1))).toEqual([[1, 2, 3]]);
  expect(moveLine(plan, 0, 0, 1)).toBe(plan); // not the last line: refused
  expect(moveLine(plan, 0, 0, -1)).toBe(plan); // no scene before
});

test("split starts a scene at a line, join folds the next one in with both casts", () => {
  expect(order(splitAt(plan, 0, 1))).toEqual([[1], [2], [3]]);
  expect(splitAt(plan, 0, 0)).toBe(plan);
  const joined = joinNext(plan, 0);
  expect(order(joined)).toEqual([[1, 2, 3]]);
  expect(joined[0].cast_ids).toEqual(["c1", "c2"]);
  expect(plan[0].lines).toHaveLength(2); // the original is untouched
});

test("★ toggles and drops its product; the PUT body carries no words or ids", () => {
  const starred = toggleStar(plan, 1, 0);
  expect(starred[1].lines[0].star).toBe(true);
  const body = toPut(starred);
  expect(body.scenes[1]).toEqual({ part: "Payoff", place: "Park", time: "Day", cast_ids: ["c2"], lines: [{ n: 3, action: "see 3", star: true }] });
  expect(JSON.stringify(body)).not.toContain("line 3");
});
