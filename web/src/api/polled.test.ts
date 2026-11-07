import { expect, test, vi } from "vitest";
import { SIGNED_OUT, polled } from "./client";

// The real-run audit: a polled read turned any refusal into empty data, so one 502 during a deploy emptied the run card
// and stopped its polling. Now only "nothing here" (404) is empty; anything else throws and polling goes on.
const answer = (status: number, data?: unknown, error?: unknown) => Promise.resolve({ data, error, response: new Response(null, { status }) });

test("a polled read: its data, empty for a 404, and a server error throws so the last data stays", async () => {
  expect(await polled(answer(200, { status: "working" }), null)).toEqual({ status: "working" });
  expect(await polled(answer(404, undefined, { detail: "none" }), null)).toBeNull();
  expect(await polled(answer(404), [])).toEqual([]);
  await expect(polled(answer(502, undefined, { detail: "Bad gateway" }), null)).rejects.toThrow("Bad gateway");
});

test("a gone session (401) or a forbidden read (403) stops polling: empty, and a gone session brings up sign-in", async () => {
  const heard = vi.fn();
  window.addEventListener(SIGNED_OUT, heard);
  expect(await polled(answer(401, undefined, { detail: "Sign in." }), null)).toBeNull();
  expect(heard).toHaveBeenCalledTimes(1); // who's signed in is read again: the sign-in screen
  expect(await polled(answer(403, undefined, { detail: "Not yours." }), [])).toEqual([]);
  expect(heard).toHaveBeenCalledTimes(1); // still signed in: nothing to read here, and no polling on
  window.removeEventListener(SIGNED_OUT, heard);
});
