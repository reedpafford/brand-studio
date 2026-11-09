import { expect, test } from "vitest";
import { newQueryClient } from "./queryClient";

test("only the video page's own reads are shared for 3 s; every other screen asks again when it opens (QA on #1485)", () => {
  const client = newQueryClient();
  for (const key of [["project", 50], ["director", 50], ["project-clips", 50], ["breakdown", 50, 2]]) expect(client.getQueryDefaults(key).staleTime).toBe(3_000);
  for (const key of [["ideas", 1], ["brands"], ["jobs"], ["narration", 9], ["scripts"]]) expect(client.getQueryDefaults(key).staleTime).toBeUndefined();
});
