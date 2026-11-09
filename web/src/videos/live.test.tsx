import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { FakeSource, fakeStream, tell } from "../test/live";
import { FALLBACK, useLive } from "./live";

beforeEach(fakeStream);
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

/** Video 7's page: its stream and three of its reads, each counting how often it's asked. */
function page() {
  const asked: Record<string, number> = { "run-progress": 0, asks: 0, storyboard: 0 };
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>;
  const read = (key: string) => ({ queryKey: [key, 7], queryFn: () => ++asked[key] });
  renderHook(
    () => {
      useLive(7);
      useQuery(read("run-progress"));
      useQuery(read("asks"));
      useQuery(read("storyboard"));
    },
    { wrapper },
  );
  return asked;
}

test("a change the server tells is read again at once, only the part that changed; a finished job reads the page", async () => {
  const asked = page();
  await waitFor(() => expect(asked).toEqual({ "run-progress": 1, asks: 1, storyboard: 1 }));
  const [source] = FakeSource.all;
  expect(source.url).toBe("/api/projects/7/live");
  act(() => source.onopen!()); // opening never reads again what the page has just read
  tell("cards");
  await waitFor(() => expect(asked.asks).toBe(2));
  tell("made");
  await waitFor(() => expect(asked).toEqual({ "run-progress": 2, asks: 3, storyboard: 2 }));
});

test("when the stream drops, the page reads every 30 s and opens it again; back, it reads what it missed and stops", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const asked = page();
  await waitFor(() => expect(asked.storyboard).toBe(1));
  act(() => FakeSource.all[0].onerror!());
  expect(FakeSource.all[0].closed).toBe(true);
  await act(() => vi.advanceTimersByTimeAsync(FALLBACK));
  await waitFor(() => expect(asked.storyboard).toBe(2)); // the slow fallback
  expect(FakeSource.all.length).toBeGreaterThan(1); // and it tried again (after 1 s)
  act(() => FakeSource.all.at(-1)!.onopen!());
  await waitFor(() => expect(asked.storyboard).toBe(3)); // back: what it missed
  await act(() => vi.advanceTimersByTimeAsync(FALLBACK));
  expect(asked.storyboard).toBe(3); // and no more polling
});
