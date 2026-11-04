import { expect, test } from "@playwright/test";
import { onBrand, signIn } from "./helpers";

// fomo is set up with its real screens and logo when the studio is first set up.
test("fomo comes with its real screens and logo", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");

  await page.getByRole("link", { name: "Brand kit", exact: true }).click();
  await page.getByRole("tab", { name: /^App screens/ }).click();
  await expect(page.getByRole("heading", { name: /^App screens/ })).toContainText("5");
  // fomo's real screens are always used for their moments: the tile says so, and the editor lists both.
  const tile = page.getByRole("button", { name: "Token chart up" });
  await expect(tile).toBeVisible();
  await expect(page.getByRole("listitem").filter({ has: tile })).toContainText("trading"); // under the tile (v5 F_BrandScreens)
  await tile.click();
  const editor = page.getByRole("dialog", { name: "Edit Token chart up" });
  const moments = editor.getByRole("group", { name: "Always use this screen for" });
  await expect(moments.getByRole("button", { name: "Remove trading", exact: true })).toBeVisible();
  await expect(moments.getByRole("button", { name: "Remove win", exact: true })).toBeVisible();
  await editor.getByRole("button", { name: "Close" }).click();

  await page.getByRole("tab", { name: "Look" }).click();
  await expect(page.getByRole("img", { name: "Logo" })).toBeVisible();
});
