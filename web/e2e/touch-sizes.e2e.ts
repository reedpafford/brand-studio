import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

// From the 390 walk: Cast & places' tabs and New character were 40–42 px; the Brand page had no main landmark.
test("at 390: Cast & places' tabs and New character are 44 px presses, and the Brand page is a main landmark", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brandId = await emptyBrand(page, "Touch Co");
  await page.goto(`/b/${brandId}/library/characters`);
  for (const press of [page.getByRole("link", { name: /^Characters/ }), page.getByRole("link", { name: /^Places/ }), page.getByRole("link", { name: /^Props/ }), page.getByRole("button", { name: "New character" })]) {
    await expect(press).toBeVisible();
    expect((await press.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  }
  await page.goto(`/b/${brandId}/brand`);
  await expect(page.getByRole("main").getByRole("heading", { name: "Brand", level: 1 })).toBeVisible();
  const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
  expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
});

// QA sweep (1 Nov): every video page asked for /api/brands/0/screens before its brand loaded, a 404 each time.
test("a video page never asks for brand 0's screens", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brandId = await emptyBrand(page, "Zero Co");
  const id = (await (await page.request.post("/api/projects", { data: { brand_id: brandId, name: "Zero test", planned_seconds: 20 } })).json()).id;
  const zero: string[] = [];
  page.on("request", (r) => r.url().includes("/api/brands/0/") && zero.push(r.url()));
  await page.goto(`/b/${brandId}/videos/${id}`);
  await expect(page.getByRole("heading", { name: "Zero test", level: 1 })).toBeVisible();
  await page.waitForLoadState("networkidle");
  expect(zero).toEqual([]);
});

// QA-3 on #1153: at 390 a script row's title (its main link) was 24 px, and "Ready to make" wrapped over three lines.
test("at 390, a script row's title is a 44 px press and the stage tabs stay on one line", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brandId = await emptyBrand(page, "Rows Co");
  const title = `Row ${Date.now()}`;
  expect((await page.request.post("/api/scripts", { data: { brand_id: brandId, title, description: "", notes: "", reference_replace: "", text: "NATE: Hi." } })).ok()).toBe(true);
  await page.goto(`/b/${brandId}/scripts`);
  const link = page.getByRole("link", { name: title, exact: true });
  await expect(link).toBeVisible();
  expect((await link.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  const ready = page.getByRole("tab", { name: /^Ready to make/ });
  expect((await ready.boundingBox())!.height).toBeLessThanOrEqual(48); // one line, not three
});

test("at 390, a character page's Add outfit, Save and Archive character are 44 px presses (QA-3 on #1163)", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brandId = await emptyBrand(page, `Touch Cast ${test.info().retry}`);
  await page.goto(`/b/${brandId}/library/characters`);
  await page.getByRole("button", { name: "New character" }).click();
  await page.getByLabel("Name").fill("Pip");
  await page.getByRole("button", { name: "Create character" }).click();
  await page.getByRole("link", { name: "Pip" }).click();
  for (const press of [page.getByRole("button", { name: "Add outfit" }), page.getByRole("button", { name: "Save", exact: true }), page.getByRole("button", { name: "Archive character" })]) {
    await press.scrollIntoViewIfNeeded();
    expect((await press.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  }
});
