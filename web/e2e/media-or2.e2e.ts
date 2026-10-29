import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

for (const width of [1440, 390]) {
  test(`at ${width}: Media opens from the rail (from Videos on a phone), says nothing is made yet, and filters (flows OR2)`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await signIn(page, "reed@example.com");
    await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
    const brandId = await emptyBrand(page, "Media Co");

    await page.goto(`/b/${brandId}/videos`);
    if (width === 1440) await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Media" }).click();
    else {
      await expect(page.getByRole("navigation", { name: "Tabs" }).getByRole("link")).toHaveCount(5); // Media isn't a phone tab
      await page.getByRole("main").getByRole("link", { name: "Media" }).click(); // it opens from the Videos header
    }
    await expect(page).toHaveURL(new RegExp(`/b/${brandId}/media$`));
    await expect(page.getByRole("heading", { name: "Nothing made yet in Media Co." })).toBeVisible();
    await expect(page.getByRole("link", { name: "Make a quick clip" })).toHaveAttribute("href", `/b/${brandId}/clip`);

    if (width === 390) await page.getByRole("button", { name: "Filters" }).click();
    await page.getByLabel("Kind").selectOption("still");
    await expect(page).toHaveURL(/kind=still/);
    await expect(page.getByRole("heading", { name: "Nothing matches these filters." })).toBeVisible();
    if (width === 390) await page.keyboard.press("Escape");

    for (const press of [width === 1440 ? page.getByRole("link", { name: "Media" }).first() : page.getByRole("main").getByRole("link", { name: "Videos" }), page.getByRole("button", { name: /Filters|Clear filters/ }).first()]) {
      expect((await press.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    }
    const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
    await expect(page.getByText("$")).toHaveCount(0);
  });
}

test("at 390 a deleted video's badge wraps a long unbroken maker name inside its tile (QA on #997)", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brandId = await emptyBrand(page, "Long Name Co");
  const name = "Bartholomewchristopheralexanderjonathanson"; // no break of its own
  const item = { key: "take:1", kind: "take", file_id: 1, content_type: "video/mp4", poster_file_id: null, made_at: "2026-10-28T10:00:00Z", made_by: null, project_id: 9, folder_id: null, video_name: "Bo tries salmon", script_id: null, open_step: "clips", from_deleted_video: true, deleted_video_by: { id: 99, name } };
  await page.route(`**/api/brands/${brandId}/media*`, (r) => r.fulfill({ json: { items: [item], next: null } }));
  await page.goto(`/b/${brandId}/media`);
  const tile = page.getByRole("list", { name: "Media" }).getByRole("listitem");
  const badge = tile.getByText(`From ${name}'s deleted video`);
  await expect(badge).toBeVisible();
  const [b, t] = [(await badge.boundingBox())!, (await tile.boundingBox())!];
  expect(b.x + b.width).toBeLessThanOrEqual(t.x + t.width);
  const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
  expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
});
