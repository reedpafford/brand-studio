import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

// Next-Lead's polish rows 11, 13 and 22 at 390: nothing wraps onto two lines, and every price chip has its space.
test("at 390: New script, the video's title and its settings chips each stay on one line, with no sideways scroll", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: /^Brand: / }).first()).toBeVisible();
  const brandId = await emptyBrand(page, "Polish Co");
  const oneLine = async (name: RegExp) => expect((await page.getByRole("button", { name }).first().boundingBox())!.height).toBeLessThanOrEqual(48);

  await page.goto(`/b/${brandId}/scripts`);
  await oneLine(/^New script$/);

  const id = (await (await page.request.post("/api/projects", { data: { brand_id: brandId, name: "Mia finally tries the salmon dip", planned_seconds: 20 } })).json()).id;
  await page.goto(`/b/${brandId}/videos/${id}?tab=plan`);
  const title = (await page.getByRole("heading", { level: 1 }).boundingBox())!;
  expect(title.width).toBeGreaterThan(200); // P-04: the title has the top bar's row to itself
  expect(title.height).toBeLessThanOrEqual(28);

  await page.getByRole("button", { name: /^Settings: / }).click();
  const chip = page.getByRole("dialog", { name: "Video settings" }).getByRole("button", { name: /^Video model / });
  await expect(chip).toHaveText(/^Video model\s*Auto/); // S-gaps-05 V1: the label, then the choice; its price is in the picker
  expect((await chip.boundingBox())!.height).toBeLessThanOrEqual(48);
  const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
  expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
});
