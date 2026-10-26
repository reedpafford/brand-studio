import { expect, test } from "vitest";
import { changedSnippets } from "./ChangeBox";

const text = (parts: { text: string }[]) => parts.map((p) => p.text).join(" ");

test("only the changed words show, with about five around them, and at most three snippets", () => {
  const before = "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen";
  const after = "one two three four five six SEVEN eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen";
  const s = changedSnippets(before, after);
  expect(s).toHaveLength(1);
  expect(text(s[0].before)).toBe("two three four five six seven eight nine ten eleven twelve");
  expect(text(s[0].after)).toBe("two three four five six SEVEN eight nine ten eleven twelve");
});

test("far-apart changes are separate snippets, capped at three", () => {
  const w = (n: number) => Array.from({ length: n }, (_, i) => `w${i}`).join(" ");
  const before = [w(20), "a", w(20), "b", w(20), "c", w(20), "d", w(20)].join(" ");
  const after = [w(20), "A", w(20), "B", w(20), "C", w(20), "D", w(20)].join(" ");
  expect(changedSnippets(before, after)).toHaveLength(3);
});

test("no change gives no snippets", () => {
  expect(changedSnippets("same words", "same words")).toEqual([]);
});
