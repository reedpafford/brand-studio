import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

test.use({ viewport: { width: 390, height: 844 } });

test("QA-2 scratch: a long unbroken script line causes no sideways scroll at 390", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brandId = await emptyBrand(page, "Narrow Shop");
  const made = await page.request.post("/api/projects", { data: { brand_id: brandId, name: "Narrow", planned_seconds: 20 } });
  const id = (await made.json()).id;
  const text = "SCENE 1 - KITCHEN\nMAX: " + "https://example.com/" + "a".repeat(200) + "\n[Brand screen] " + "b".repeat(150);
  await page.goto(`/b/${brandId}/projects/${id}`);
  const tab = page.getByRole("button", { name: "Script", exact: true });
  if (await tab.count()) await tab.first().click();
  await page.getByLabel("Your script").fill(text);
  await page.getByRole("button", { name: "Save script" }).click();
  await expect(page.getByRole("list", { name: "Script text" })).toContainText("MAX:");
  const [sw, cw] = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]);
  await page.screenshot({ path: "test-results/qa2-narrow-390.png", fullPage: true });
  expect(sw).toBeLessThanOrEqual(cw);
});
