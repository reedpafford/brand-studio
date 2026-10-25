import { useEffect, useState } from "react";

/** True while the screen matches a media query (e.g. a phone). Without matchMedia it is false. */
export function useMedia(query: string) {
  const [matches, setMatches] = useState(() => !!window.matchMedia?.(query).matches);
  useEffect(() => {
    const mq = window.matchMedia?.(query);
    if (!mq) return;
    const on = () => setMatches(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [query]);
  return matches;
}

/** The desktop layout (side rail, side panels) starts at 1024px; below it is the phone layout with bottom tabs. */
export const useRail = () => useMedia("(min-width: 1024px)");
