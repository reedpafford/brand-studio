import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

for (const width of [1440, 390]) {
  test(`at ${width}: Media opens from the brand's sections, says nothing is made yet, and filters (flows OR2)`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await signIn(page, "reed@example.com");
    await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
    const brandId = await emptyBrand(page, "Media Co");

    await page.goto(`/b/${brandId}/videos`);
    await page.getByRole("navigation", { name: width === 1440 ? "Main" : "Tabs" }).getByRole("link", { name: "Media" }).click();
    await expect(page).toHaveURL(new RegExp(`/b/${brandId}/media$`));
    await expect(page.getByRole("heading", { name: "Nothing made yet in Media Co." })).toBeVisible();
    await expect(page.getByRole("link", { name: "Make a quick clip" })).toHaveAttribute("href", `/b/${brandId}/clip`);

    if (width === 390) await page.getByRole("button", { name: "Filters" }).click();
    await page.getByLabel("Kind").selectOption("still");
    await expect(page).toHaveURL(/kind=still/);
    await expect(page.getByRole("heading", { name: "Nothing matches these filters." })).toBeVisible();
    if (width === 390) await page.keyboard.press("Escape");

    for (const press of [page.getByRole("link", { name: "Media" }).first(), page.getByRole("button", { name: /Filters|Clear filters/ }).first()]) {
      expect((await press.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    }
    const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
    await expect(page.getByText("$")).toHaveCount(0);
  });
}
