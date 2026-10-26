import { useEffect, useState } from "react";

/**
 * A paid run was just asked for and its job should show up in the jobs list within moments.
 * If it never does (the list lost it, or the connection dropped), the screen must not wait on it for ever:
 * `unseen` turns true after 45 s, and the pane stops saying "Writing…".
 */
export function usePressed() {
  const [at, setAt] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (at === null) return;
    const t = setInterval(() => setNow(Date.now()), 5000);
    return () => clearInterval(t);
  }, [at]);
  return {
    press: () => {
      const t = Date.now();
      setAt(t);
      setNow(t);
    },
    unseen: at !== null && now - at > 45_000,
  };
}
