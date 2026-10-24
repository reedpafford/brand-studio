/** Prices are whole credits, rounded up: 67.5 shows as 68. Zero is "free". */
export const wholeCredits = (n: number) => Math.ceil(n - 1e-9);
export const creditsLabel = (n: number) => (wholeCredits(n) === 0 ? "free" : `${wholeCredits(n)} credit${wholeCredits(n) === 1 ? "" : "s"}`);
