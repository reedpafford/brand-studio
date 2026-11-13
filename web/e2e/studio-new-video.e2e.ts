import { expect, test } from "@playwright/test";
import { onBrand, signIn } from "./helpers";

// New video in the new look (the redesign, stage 1; /s/b/N): the script box's tint must sit exactly under the typed
// text, which only a real browser can measure. It looks and never presses Make it, so no video is made.
const PART = [
  "[Dusk at a town pool. A whistle goes, twice, and the swimmers look up.]",
  "POOL GUARD (on the radio): Everybody out of the water, now, and stay behind the rope until I say!",
  "Hook 2 (the long one): If your pool has a gate, go and check the latch tonight, before anyone swims.",
  "Plate: The OPEN gate…",
  "",
  "It was the first hot Saturday of the year, and nobody had looked at the latch since the autumn.",
].join("\n");

for (const [width, height] of [[1440, 900], [390, 844]]) {
  test(`at ${width}, a long pasted script and its tint are the same size, the controls stay in reach, and nothing scrolls sideways`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await signIn(page, "reed@example.com");
    await onBrand(page, "fomo");
    await page.goto(`/s${new URL(page.url()).pathname}`);
    await page.getByRole("textbox", { name: "Your script" }).fill(Array(60).fill(PART).join("\n\n"));
    await expect(page.getByText(/^60 hooks · 2 voices · 121 spoken lines · about .+\. Your words are never changed\.$/)).toBeVisible();
    const sizes = await page.evaluate(() => {
      const text = document.querySelector<HTMLElement>(".sheet textarea")!;
      const ink = document.querySelector<HTMLElement>(".ink")!;
      const paper = document.querySelector<HTMLElement>(".paper")!;
      return { text: [text.clientWidth, text.scrollHeight], ink: [ink.clientWidth, ink.offsetHeight], paper: [paper.clientHeight, paper.scrollHeight], bar: document.querySelector(".bar")!.getBoundingClientRect().bottom, page: [document.documentElement.scrollWidth, document.documentElement.clientWidth] };
    });
    expect(sizes.ink).toEqual(sizes.text); // the two layers wrap alike, line for line
    expect(sizes.paper[1]).toBeGreaterThan(sizes.paper[0]); // the script scrolls inside its box
    if (width > 900) expect(sizes.bar).toBeLessThanOrEqual(height); // with the read-out and the controls pinned under it
    expect(sizes.page[0]).toBeLessThanOrEqual(sizes.page[1]);
  });
}
