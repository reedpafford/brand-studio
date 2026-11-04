import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

for (const width of [1440, 390]) {
  test(`at ${width}: an idea moves into a folder with Undo, the folder opens with it, and deleting the folder sends it back to Unsorted with Undo (v6 S1)`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await signIn(page, "reed@example.com");
    await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
    const brandId = await emptyBrand(page, "Projects Co"); // one brand for both widths; named to sort after fomo (a fresh sign-in opens the first brand)
    const run = `${width}-${Date.now() % 1e6}`; // a retry or a rerun shares the database: new names
    const video = `Filed video ${run}`;
    const name = `November launch ${run}`;
    const id = (await (await page.request.post("/api/projects", { data: { brand_id: brandId, name: video, planned_seconds: 20 } })).json()).id;
    const folder = (await (await page.request.post(`/api/brands/${brandId}/folders`, { data: { name } })).json()).id;

    if (width === 1440) {
      await page.goto(`/b/${brandId}/videos`); // no folder picked: Unsorted
      await page.getByRole("link", { name: new RegExp(video) }).hover();
      await page.getByRole("checkbox", { name: `Select ${video}` }).click();
      const bar = page.getByRole("region", { name: "Selected ideas" });
      await expect(bar).toContainText("1 selected");
      await bar.getByRole("button", { name: "Move to…" }).click();
      await page.getByRole("menu", { name: "Move 1 idea to" }).getByRole("menuitem", { name }).click();
      await expect(page.getByText(`Moved 1 idea to ${name}.`)).toBeVisible();
      await page.getByRole("button", { name: "Undo" }).click();
      await expect(page.getByRole("link", { name: new RegExp(video) })).toBeVisible(); // back in Unsorted
    }
    await page.request.post("/api/folders/file", { data: { kind: "video", ids: [id], folder_id: folder } });
    await page.goto(`/b/${brandId}/videos?folder=${folder}`);
    await expect(page.getByRole("link", { name: new RegExp(video) })).toBeVisible();
    if (width === 1440) {
      await page.getByRole("button", { name: `More for ${name}` }).click();
      await page.getByRole("menuitem", { name: "Delete folder…" }).click();
      const ask = page.getByRole("alertdialog", { name: `Delete ${name}?` });
      await expect(ask).toContainText("Its 1 idea moves to Unsorted.");
      await ask.getByRole("button", { name: "Delete folder" }).click();
      await expect(page.getByText(`Deleted “${name}”. Its 1 idea moved to Unsorted.`)).toBeVisible();
      await page.getByRole("button", { name: "Undo" }).click();
      await expect.poll(async () => (await (await page.request.get(`/api/brands/${brandId}/tree`)).json()).folders.some((f: { id: number }) => f.id === folder)).toBe(true);
    }
    const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
  });
}
