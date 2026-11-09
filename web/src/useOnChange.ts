import { useEffect, useRef } from "react";

/** Runs `then` when `value` changes after it was first known: never for the first value read (undefined is "not read
 *  yet"), so opening a page never asks again for what it has just read. */
export function useOnChange<T>(value: T | undefined, then: () => void) {
  const seen = useRef(value);
  const latest = useRef(then);
  useEffect(() => {
    latest.current = then;
  });
  useEffect(() => {
    if (value === undefined || Object.is(seen.current, value)) return;
    const before = seen.current;
    seen.current = value;
    if (before !== undefined) latest.current();
  }, [value]);
}
