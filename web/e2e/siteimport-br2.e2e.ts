import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

// The stand-in reads a practice page (never fetched): a logo, two colours, two products; "fail" in the address fails.
for (const width of [1440, 390]) {
  test(`at ${width}: the owner reads the brand's site, ticks what to keep, saves with Undo; a site that can't be read says so (flows BR2)`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await signIn(page, "reed@example.com");
    await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
    const brandId = await emptyBrand(page, `Site Co ${width}-${test.info().retry}`);
    await page.goto(`/b/${brandId}/brand`);
    await page.getByRole("button", { name: "Import from website" }).first().click(); // v5: opened from the top bar (or the setup list)
    const card = page.getByRole("region", { name: "Import from website" });

    await card.getByLabel("Paste the brand's website").fill("https://example.com/fail");
    await card.getByRole("button", { name: /^Read the site · up to/ }).click();
    await expect(card.getByText("Couldn't read that site. Nothing was charged.")).toBeVisible();

    // The address stays in the box; Read it again reads the corrected one.
    await card.getByLabel("Paste the brand's website").fill("https://example.com");
    await card.getByRole("button", { name: /^Read it again · up to/ }).click();
    await expect(card.getByText(/Nothing is saved yet/)).toBeVisible({ timeout: 20_000 });
    await expect(card.getByRole("checkbox").first()).toBeChecked();
    const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
    const save = page.getByRole("button", { name: /^Save \d+ picked$/ });
    expect((await save.boundingBox())!.height).toBeGreaterThanOrEqual(width === 1440 ? 24 : 44); // desktop: Linear-sized controls (Reed, 2 Nov)
    await save.click();
    await expect(page.getByText(/^Saved /)).toBeVisible();
    await page.getByRole("button", { name: "Undo" }).click();
    // The save closes the import; Undo puts the empty brand back, so its setup list offers Import from website again (F_BrandEmpty).
    await expect(page.getByRole("region", { name: /^Set up / }).getByRole("button", { name: "Import from website" })).toBeVisible();
    await expect(page.getByText("$")).toHaveCount(0);
  });
}
