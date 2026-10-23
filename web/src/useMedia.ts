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
