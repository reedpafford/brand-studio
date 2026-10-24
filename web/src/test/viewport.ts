import { vi } from "vitest";

/** Makes window.matchMedia answer min-width / max-width queries for a pretend screen width (jsdom has none). */
export function setViewport(width: number) {
  vi.stubGlobal("matchMedia", (query: string) => {
    const min = /min-width:\s*(\d+)px/.exec(query)?.[1];
    const max = /max-width:\s*(\d+)px/.exec(query)?.[1];
    const matches = (min === undefined || width >= Number(min)) && (max === undefined || width <= Number(max));
    return { matches, media: query, addEventListener: () => {}, removeEventListener: () => {}, addListener: () => {}, removeListener: () => {}, onchange: null, dispatchEvent: () => false };
  });
}
