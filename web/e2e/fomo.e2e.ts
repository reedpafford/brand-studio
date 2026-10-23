import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

// fomo is set up with its real screens, logo and style board when the studio is first set up.
test("fomo comes with its real screens, logo and style board", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("heading", { name: "fomo" })).toBeVisible();

  await page.getByRole("link", { name: "Screens" }).click();
  await expect(page.getByRole("heading", { name: "Brand screens (4)" })).toBeVisible();
  await expect(page.getByRole("img", { name: "Token chart up" })).toBeVisible();
  await expect(page.getByText("★ Always used for: trading, win")).toBeVisible();

  await page.getByRole("link", { name: "Kit" }).click();
  await expect(page.getByRole("img", { name: "Logo" })).toBeVisible();
  await expect(page.getByRole("img", { name: "Style board" })).toBeVisible();
});
