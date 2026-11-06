import { expect, test } from "vitest";
import { polled } from "./client";

// The real-run audit: a polled read turned any refusal into empty data, so one 502 during a deploy emptied the run card
// and stopped its polling. Now only "nothing here" (404) is empty; anything else throws and polling goes on.
const answer = (status: number, data?: unknown, error?: unknown) => Promise.resolve({ data, error, response: new Response(null, { status }) });

test("a polled read: its data, empty for a 404, and a server error throws so the last data stays", async () => {
  expect(await polled(answer(200, { status: "working" }), null)).toEqual({ status: "working" });
  expect(await polled(answer(404, undefined, { detail: "none" }), null)).toBeNull();
  expect(await polled(answer(404), [])).toEqual([]);
  await expect(polled(answer(502, undefined, { detail: "Bad gateway" }), null)).rejects.toThrow("Bad gateway");
});
