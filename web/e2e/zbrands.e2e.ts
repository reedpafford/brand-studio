import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

// Runs last (after the owner exists). The brand's name sorts after "fomo", so no other test's first brand changes.
test("Reed archives a brand, it leaves the menu, and Restore on Usage brings it back", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const id = await emptyBrand(page, "Zulu Archive Co");
  await page.goto(`/b/${id}/brand`);
  await page.getByRole("button", { name: "More for Zulu Archive Co" }).click();
  await page.getByRole("menuitem", { name: "Archive brand" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Archive", exact: true }).click();
  await expect(page.getByText("Archived Zulu Archive Co.")).toBeVisible();
  await page.getByRole("button", { name: /^Brand: / }).click();
  await expect(page.getByRole("menuitemradio", { name: "Zulu Archive Co" })).toBeHidden();
  await page.keyboard.press("Escape");

  await page.goto("/usage?archived=1");
  await page.getByRole("button", { name: "Restore Zulu Archive Co" }).click();
  await expect(page.getByText("Brought back Zulu Archive Co.")).toBeVisible();
  await page.getByRole("button", { name: /^Brand: / }).click();
  await expect(page.getByRole("menuitemradio", { name: "Zulu Archive Co" })).toBeVisible();
});
