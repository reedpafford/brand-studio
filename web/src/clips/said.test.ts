import { expect, test } from "vitest";
import { scenesOf } from "./data";

test("Polish: a clip with several speakers says each line on its own line, never run together", () => {
  const shot = (id: string, speaker: string, line: string) => ({ id, speaker, line, action: "", seconds: 2 });
  const bd = { scenes: [{ id: 1, shots: [shot("1.1", "Maya", "I put twenty dollars in last week."), shot("1.2", "Jordan", "And now?")] }], clips: [{ id: "c1", shot_ids: ["1.1", "1.2"], seconds: 4 }] };
  const [scene] = scenesOf(bd as never, [], [], null);
  expect(scene.rows[0].said).toBe("Maya: “I put twenty dollars in last week.”\nJordan: “And now?”");
});
