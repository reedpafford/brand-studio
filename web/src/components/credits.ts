/** Prices are whole credits, rounded up: 67.5 shows as 68. Zero is "free". */
export const wholeCredits = (n: number) => Math.ceil(n - 1e-9);
/** A price with decimals (a rate, an "about"), rounded up at `places`: 2.44 at one place shows as 2.5, never below the charge. */
export const roundUp = (n: number, places: number) => Math.ceil(n * 10 ** places - 1e-9) / 10 ** places;
export const creditsLabel = (n: number) => (wholeCredits(n) === 0 ? "free" : `${wholeCredits(n)} credit${wholeCredits(n) === 1 ? "" : "s"}`);

/** How a paid press charges (rule 32). "estimate": held at its most and charged what it used (a Claude call, a look
 *  with its check), so it reads "up to N". "fixed": exactly what it says (a still, a take, a quick clip, a song). */
export type Charge = "estimate" | "fixed";
/** A press's price as its button says it: whole credits, rounded up, "up to" when the charge can be lower. */
export const pressLabel = (n: number, charge: Charge) => `${charge === "estimate" && wholeCredits(n) > 0 ? "up to " : ""}${creditsLabel(n)}`;
/** A rate or a total away from a press: one decimal, rounded up, so it's never below the charge ("0.4 credits"). */
export const creditsText = (n: number) => `${roundUp(n, 1)} credit${roundUp(n, 1) === 1 ? "" : "s"}`;
