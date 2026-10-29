import { expect, test, type Page } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

const LYRICS = "[Verse]\nBo would never touch his bowl\n[Chorus]\nNow he licks it clean, Iron Paws";

/** New script → Song, lyrics and style saved, two takes made on the free stand-in until one is Preferred, then Cast asks who sings. */
async function walk(page: Page, brand: string) {
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brandId = await emptyBrand(page, brand);
  await page.goto(`/b/${brandId}/scripts`);
  await page.getByRole("button", { name: "New script" }).click();
  await page.getByRole("menuitem", { name: /Song/ }).click();

  await page.getByLabel("Lyrics").fill(LYRICS);
  await page.getByLabel("Style").fill("pop, female lead, upbeat");
  await page.getByRole("button", { name: "Save lyrics" }).click();
  await expect(page.getByText("Sung word for word")).toBeVisible();
  await page.getByRole("button", { name: "Next: Takes" }).click();

  await page.getByRole("button", { name: /Make 2 takes · \d+ credits?/ }).click();
  await expect(page.getByText("Preferred", { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("button", { name: "Play Take 1" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Next: Cast" })).toBeEnabled();
  await page.getByRole("button", { name: "Next: Cast" }).click();
  await expect(page.getByRole("group", { name: "Who sings on camera?" })).toBeVisible();
  await page.getByRole("radio", { name: "Nobody on camera" }).check();
}

test("a song script: lyrics saved, 2 takes made on the stand-in, one Preferred, Cast opens (desktop)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await walk(page, "Song Shop");
});

test("the same song walk at 390: no sideways scroll, steps in one button", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await walk(page, "Song Shop Phone");
  await expect(page.getByRole("button", { name: /Step 3 of 5 · Cast/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test("a published song script: Make this version opens a video whose Breakdown has the song strip and Change song", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await walk(page, "Song Shop Video");
  await page.getByRole("button", { name: "Next: Plan" }).click();
  await page.getByRole("button", { name: "Next: Publish" }).click();
  await page.getByRole("button", { name: "Approve version A" }).click(); // every version is approved before publishing
  await page.getByRole("button", { name: /Publish 1 version/ }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Publish" }).click();
  await page.getByLabel(/Version A, ready to make/).click();
  await page.getByRole("button", { name: /Make this version/ }).click();
  await expect(page.getByRole("button", { name: "Change song" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/Song: Take \d · \d:\d\d/)).toBeVisible();
  await page.getByRole("button", { name: "Change song" }).click();
  await expect(page.getByRole("dialog", { name: "Change song" }).getByText("In this video", { exact: true })).toBeVisible();
});
