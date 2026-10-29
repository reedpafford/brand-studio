/** Prices are whole credits, rounded up: 67.5 shows as 68. Zero is "free". */
export const wholeCredits = (n: number) => Math.ceil(n - 1e-9);
/** A price with decimals (a rate, an "about"), rounded up at `places`: 2.44 at one place shows as 2.5, never below the charge. */
export const roundUp = (n: number, places: number) => Math.ceil(n * 10 ** places - 1e-9) / 10 ** places;
export const creditsLabel = (n: number) => (wholeCredits(n) === 0 ? "free" : `${wholeCredits(n)} credit${wholeCredits(n) === 1 ? "" : "s"}`);
