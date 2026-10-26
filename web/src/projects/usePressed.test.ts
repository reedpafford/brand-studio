import { act, renderHook } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { usePressed } from "./usePressed";

afterEach(() => vi.useRealTimers());

test("a run that was pressed but never shows in the list stops being waited on after 45 seconds", () => {
  vi.useFakeTimers();
  const { result } = renderHook(() => usePressed());
  expect(result.current.unseen).toBe(false); // nothing pressed
  act(() => result.current.press());
  act(() => vi.advanceTimersByTime(30_000));
  expect(result.current.unseen).toBe(false);
  act(() => vi.advanceTimersByTime(20_000));
  expect(result.current.unseen).toBe(true);
});
