import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

// QA-2 scratch: click Team while the home page is still waiting for brands (slowed to 1.5 s).
test("Team clicked during the sign-in redirect", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.route("**/api/brands", async (r) => { await new Promise((x) => setTimeout(x, 1500)); await r.continue(); });
  await signIn(page, "reed@example.com");
  await page.getByRole("link", { name: "Team" }).click();
  await expect(page.getByRole("heading", { name: "Team" })).toBeVisible({ timeout: 3000 });
  await page.waitForTimeout(2500);
  await expect(page.getByRole("heading", { name: "Team" })).toBeVisible();
  console.log("URL after wait:", page.url());
});
