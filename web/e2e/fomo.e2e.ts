import { expect, test } from "@playwright/test";
import { onBrand, signIn } from "./helpers";

// fomo is set up with its real screens and logo when the studio is first set up.
test("fomo comes with its real screens and logo", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");

  await page.getByRole("link", { name: "Brand", exact: true }).click();
  await page.getByRole("tab", { name: "App screens" }).click();
  await expect(page.getByRole("heading", { name: "Brand screens (5)" })).toBeVisible();
  await expect(page.getByRole("img", { name: "Token chart up" })).toBeVisible();
  await expect(page.getByText("★ Always used for: trading, win")).toBeVisible();

  await page.getByRole("tab", { name: "Look" }).click();
  await expect(page.getByRole("img", { name: "Logo" })).toBeVisible();
});
