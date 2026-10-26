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

// scripts.e2e.ts started a version of "Bo tries salmon" (Make this version), so it is being made.
test("Reed opens In production from the rail and sees the version being made, with no sideways scroll on a phone", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: /^In production/ }).click();
  await expect(page.getByRole("heading", { name: "In production", level: 1 })).toBeVisible();
  const row = page.getByRole("link", { name: /^Bo tries salmon, version A, .*, at [A-Z][a-z]+/ });
  await expect(row).toBeVisible();
  await row.click();
  await expect(page).toHaveURL(/\/projects\/\d+/);
  await page.setViewportSize({ width: 390, height: 800 });
  await page.goto("/production");
  await expect(page.getByRole("link", { name: /^Bo tries salmon/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("Reed adds a brand from the brand menu and lands on its Look page", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  await page.getByRole("button", { name: /^Brand: / }).click();
  await page.getByRole("menuitem", { name: "New brand" }).click();
  await page.getByLabel("Brand name").fill("Zephyr Studio");
  await page.getByRole("button", { name: "Create brand" }).click();
  await expect(page.getByText("Zephyr Studio is ready. Add its logo and colours.")).toBeVisible();
  await expect(page).toHaveURL(/\/b\/\d+\/brand$/);
  await expect(page.getByRole("button", { name: "Brand: Zephyr Studio" })).toBeVisible();
});
