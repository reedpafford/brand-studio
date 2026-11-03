import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "vitest";

/** Every .ts/.tsx under web/src except tests and generated files. */
function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === "test" ? [] : sources(path);
    return /\.tsx?$/.test(name) && !/\.test\.tsx?$/.test(name) && name !== "schema.d.ts" ? [path] : [];
  });
}

/** What the code says to a person: comments removed, so only strings and JSX text remain. */
const withoutComments = (code: string) =>
  code
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .split("\n")
    .map((l) => l.replace(/(^|\s)\/\/.*$/, "$1"))
    .join("\n");

test("no screen words type the owner's name; names come from data (Current rule 4)", () => {
  const found = sources(join(__dirname)).flatMap((file) =>
    withoutComments(readFileSync(file, "utf8"))
      .split("\n")
      .filter((l) => /\bReed\b/.test(l))
      .map((l) => `${file.replace(__dirname, "src")}: ${l.trim()}`),
  );
  expect(found).toEqual([]);
});

test("no screen words send anyone to the owner: no \"Ask the owner\", \"Ask Reed\" or \"Ask whoever…\" (Current rule 22)", () => {
  // A regex that hides the server's own "Ask the owner…" (`/ask the owner/i`) is not screen words.
  const found = sources(join(__dirname)).flatMap((file) =>
    withoutComments(readFileSync(file, "utf8"))
      .split("\n")
      .filter((l) => /(?<!\/)\bask (the owner|reed|whoever)\b/i.test(l))
      .map((l) => `${file.replace(__dirname, "src")}: ${l.trim()}`),
  );
  expect(found).toEqual([]);
});
