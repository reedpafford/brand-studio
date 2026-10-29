import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

// Last in the run (it adds many brands): a long brand list scrolls inside its menu, so New brand is always reachable.
test("with many brands the brand menu scrolls and New brand can still be pressed", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1440, height: 700 });
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  for (let i = 0; i < 25; i++) await emptyBrand(page, `Many Brands ${String(i).padStart(2, "0")}`);
  await page.reload();
  await page.getByRole("button", { name: /^Brand: / }).click();
  await page.getByRole("menuitem", { name: "New brand" }).click();
  await expect(page.getByLabel("Brand name")).toBeVisible();
});
