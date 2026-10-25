import { test } from "@playwright/test";
import { onBrand, signIn } from "./helpers";
test("shot", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  await page.getByRole("link", { name: "Quick clip" }).first().click();
  await page.getByRole("button", { name: "Add brand piece" }).click();
  await page.waitForTimeout(800);
  await page.screenshot({ path: "test-results/qa2-shot-top.png" });
  await page.evaluate(() => window.scrollTo(0, 99999));
  await page.waitForTimeout(300);
  await page.screenshot({ path: "test-results/qa2-shot-end.png" });
});
