import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

for (const width of [1440, 390]) {
  test(`at ${width}: the Video settings row switches the video model and Undo puts it back, with no sideways scroll (flows VS1)`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await signIn(page, "reed@example.com");
    await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
    const brandId = await emptyBrand(page, `Settings Co ${width}`);
    const id = (await (await page.request.post("/api/projects", { data: { brand_id: brandId, name: "Settings test", planned_seconds: 20 } })).json()).id;
    const before = await (await page.request.get(`/api/projects/${id}/settings`)).json();
    await page.goto(`/b/${brandId}/videos/${id}`);
    if (width === 390) await page.getByRole("button", { name: /^Settings: / }).click();
    await page.getByRole("button", { name: /Video model: / }).click();
    const other = before.video_models.find((m: { default: boolean; over_cap: boolean }) => !m.default && !m.over_cap);
    await page.getByRole("button", { name: new RegExp(other.name) }).first().click();
    const ask = page.getByRole("alertdialog", { name: `Switch to ${other.name}?` });
    await expect(ask.getByText(/To finish: up to/)).toBeVisible();
    await ask.getByRole("button", { name: "Switch" }).click();
    await expect(ask).toBeHidden();
    expect((await (await page.request.get(`/api/projects/${id}/settings`)).json()).video_model).toBe(other.id);
    await page.getByRole("button", { name: "Undo" }).click();
    await expect.poll(async () => (await (await page.request.get(`/api/projects/${id}/settings`)).json()).video_model).toBe(before.video_model);
    const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
  });
}
