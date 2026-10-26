import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

// The new video page (Breakdown · Assets · Storyboard · Clips · Downloads) on the free stand-ins.
const SCRIPT = ["SCENE 1 - KITCHEN", "Max stares at the empty bowl.", "MAX: Where did the food go?", "MIA: Ask him."].join("\n");

for (const width of [1440, 390]) {
  test(`at ${width}: shots are made, Assets lets you go on, and nothing scrolls sideways`, async ({ page }) => {
    test.setTimeout(120_000);
    await page.setViewportSize({ width, height: 900 });
    await signIn(page, "reed@example.com");
    await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
    const brandId = await emptyBrand(page, `Video Co ${width}`);
    const made = await page.request.post("/api/projects", { data: { brand_id: brandId, name: "Video test", planned_seconds: 20 } });
    const id = (await made.json()).id;
    expect((await page.request.put(`/api/projects/${id}/script`, { data: { text: SCRIPT } })).ok()).toBeTruthy();

    await page.goto(`/b/${brandId}/videos/${id}`);
    await expect(page.getByRole("heading", { name: "Breakdown", level: 2 })).toBeVisible();
    await page.getByRole("button", { name: /Make shots/ }).click();
    await expect(page.getByRole("region", { name: "Scene 1" })).toBeVisible({ timeout: 30_000 });
    await page.getByRole("button", { name: "Next: Assets" }).click();
    await expect(page.getByRole("heading", { name: "Assets", level: 2 })).toBeVisible();
    const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
    await expect(page.getByRole("button", { name: "Next: Storyboard" })).toBeEnabled();
  });
}
