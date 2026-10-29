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
    const card = page.locator("div.rounded-lg", { has: page.getByRole("heading", { name: "Import from website" }) });

    await card.getByLabel("Paste the brand's website").fill("https://example.com/fail");
    await card.getByRole("button", { name: /^Read the site · about/ }).click();
    await expect(card.getByText("Couldn't read that site. Nothing was charged.")).toBeVisible();
    await card.getByRole("button", { name: "Try again" }).click();

    await card.getByLabel("Paste the brand's website").fill("https://example.com");
    await card.getByRole("button", { name: /^Read the site · about/ }).click();
    await expect(card.getByText(/Nothing is saved yet/)).toBeVisible({ timeout: 20_000 });
    await expect(card.getByRole("checkbox").first()).toBeChecked();
    const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
    const save = page.getByRole("button", { name: "Save the ticked ones" });
    expect((await save.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await save.click();
    await expect(page.getByText(/^Saved /)).toBeVisible();
    await page.getByRole("button", { name: "Undo" }).click();
    await expect(card.getByLabel("Paste the brand's website")).toBeVisible();
    await expect(page.getByText("$")).toHaveCount(0);
  });
}
