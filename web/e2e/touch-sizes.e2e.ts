import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

// From the 390 walk: Cast & places' tabs and New character were 40–42 px; the Brand page had no main landmark.
test("at 390: Cast & places' tabs and New character are 44 px presses, and the Brand page is a main landmark", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brandId = await emptyBrand(page, "Touch Co");
  await page.goto(`/b/${brandId}/library/characters`);
  for (const press of [page.getByRole("link", { name: "Characters", exact: true }), page.getByRole("link", { name: "Places", exact: true }), page.getByRole("link", { name: "Props", exact: true }), page.getByRole("button", { name: "New character" })]) {
    await expect(press).toBeVisible();
    expect((await press.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  }
  await page.goto(`/b/${brandId}/brand`);
  await expect(page.getByRole("main").getByRole("heading", { name: "Brand", level: 1 })).toBeVisible();
  const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
  expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
});
