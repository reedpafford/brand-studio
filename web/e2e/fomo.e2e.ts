import { expect, test } from "@playwright/test";
import { onBrand, signIn } from "./helpers";

// fomo is set up with its real screens and logo when the studio is first set up: its app is a product holding them.
test("fomo comes with its real screens, as its app's pictures, and its logo", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  await page.goto(page.url().replace(/\/b\/(\d+).*/, "/b/$1/library/products"));
  await page.getByRole("link", { name: "fomo app" }).click();
  await page.getByRole("button", { name: "fomo app, Token chart up" }).click();
  await page.getByRole("button", { name: "Edit this screen" }).click();
  const editor = page.getByRole("dialog", { name: "Edit Token chart up" });
  const moments = editor.getByRole("group", { name: "Always use this screen for" });
  await expect(moments.getByRole("button", { name: "Remove trading", exact: true })).toBeVisible();
  await expect(moments.getByRole("button", { name: "Remove win", exact: true })).toBeVisible();
  await editor.getByRole("button", { name: "Close" }).click();

  await page.getByRole("link", { name: "Brand kit" }).click();
  await expect(page.getByRole("img", { name: "fomo logo" })).toBeVisible();
});
