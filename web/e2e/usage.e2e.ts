import { expect, test } from "@playwright/test";
import { onBrand, signIn } from "./helpers";

// Runs after shell.e2e.ts; Reed is the owner. Nothing here costs anything.
test("Reed opens Usage: the totals, a row for every brand, and one brand's page", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Usage" }).click();
  await expect(page.getByRole("heading", { name: "Usage", exact: true, level: 1 })).toBeVisible();
  await expect(page.getByRole("group", { name: "Totals" })).toContainText("Cost per finished video");
  const fomo = page.getByRole("link", { name: /^fomo: \$[\d,.]+ spent, \d+ finished$/ });
  await expect(fomo).toBeVisible();
  await page.getByRole("radio", { name: "All time" }).click();
  await expect(page).toHaveURL(/period=all/);
  await fomo.click();
  await expect(page.getByRole("heading", { name: "fomo", level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: "Usage", exact: true }).first()).toBeVisible();
  await expect(page.getByRole("tab", { name: /^Videos/ })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: /^Scripts/ }).click();
  await expect(page).toHaveURL(/tab=scripts/);
});
