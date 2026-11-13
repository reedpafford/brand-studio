import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

// The new look is where the owner lands (the redesign, stage 7). "Back to the current site" is remembered on this
// computer, and the current Settings' "Open the new look" undoes it. Nothing here makes or spends anything.
test("signing in opens the new look; Back to the current site is remembered, and its Settings come back", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page, "reed@example.com", undefined, "new");
  await expect(page.getByRole("heading", { level: 1, name: "New video" })).toBeVisible();
  await expect(page).toHaveURL(/\/s\/b\/\d+$/);

  await page.getByRole("link", { name: "Back to the current site" }).click();
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  await page.goto("/");
  await expect(page).toHaveURL(/^[^?]*\/b\/\d+$/);
  expect(new URL(page.url()).pathname.startsWith("/s/")).toBe(false); // remembered: "/" is the current site now

  await page.goto("/settings");
  await page.getByRole("button", { name: "Open the new look" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "New video" })).toBeVisible();
  await page.goto("/");
  await expect(page).toHaveURL(/\/s\/b\/\d+$/);
});
