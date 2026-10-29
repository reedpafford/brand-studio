import { expect, test, type Page } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

const WORDS = "Bo would never touch his bowl. Then we found Iron Paws. Now he licks it clean.";

/** New script → Narrated, words saved, the narration made on the free stand-in and used, then Cast opens (flows S1, N1). */
async function walk(page: Page, brand: string) {
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brandId = await emptyBrand(page, brand);
  await page.goto(`/b/${brandId}/scripts`);
  await page.getByRole("button", { name: "New script" }).click();
  await page.getByRole("menuitem", { name: /Narrated/ }).click();

  await page.getByLabel("Paste or write your script").fill(WORDS);
  await page.getByRole("button", { name: "Save script" }).click();
  await expect(page.getByText("Nothing changed yet")).toBeVisible(); // saved: nothing left to save
  await page.getByRole("button", { name: "Next: Narration" }).click();

  await expect(page.getByText("One voice reads the whole script. Voice: Sarah.")).toBeVisible();
  await page.getByRole("button", { name: /Make the narration · \d+ credits?/ }).click();
  await expect(page.getByRole("button", { name: "Play Narration 1" })).toBeVisible({ timeout: 30_000 });
  // The first narration is the one used on its own; Make another keeps it until a new one is used.
  await expect(page.getByRole("listitem").filter({ hasText: "Narration 1" }).getByText("In use")).toBeVisible();
  await expect(page.getByText(/Pauses trimmed: \d:\d\d → \d:\d\d|Kept the pauses/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Next: Cast" })).toBeEnabled();
  await page.getByRole("button", { name: "Next: Cast" }).click();
}

test("a narrated script: words saved, the narration made on the stand-in and used, Cast opens (desktop)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await walk(page, "Narrated Shop");
});

test("the same narrated walk at 390: no sideways scroll", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await walk(page, "Narrated Shop Phone");
  await expect(page.getByRole("button", { name: /Step 3 of 5 · Cast/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
