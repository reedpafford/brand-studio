import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

// QA-2 scratch: a never-say phrase typed but not added is kept when Save is pressed (real browser).
test("with another edit, a typed never-say phrase is saved by Save", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const id = await emptyBrand(page, "Never Say Co");
  await page.goto(`/b/${id}/brand`);
  await page.getByLabel("How we sound").fill("Plain and calm.");
  await page.getByLabel("Add to never say").fill("moon soon");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("button", { name: "Remove moon soon" })).toBeVisible();
  await expect.poll(async () => (await (await page.request.get(`/api/brands/${id}`)).json()).never_say).toContain("moon soon");
  await page.reload();
  await expect(page.getByRole("button", { name: "Remove moon soon" })).toBeVisible();
});

test("with only a typed phrase, Tab adds it and Save then saves it", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const id = await emptyBrand(page, "Never Say Two");
  await page.goto(`/b/${id}/brand`);
  const save = page.getByRole("button", { name: "Save changes" });
  await page.getByLabel("Add to never say").fill("to the moon");
  const disabledWhileTyping = await save.isDisabled();
  console.log("Save disabled while only typing:", disabledWhileTyping);
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Remove to the moon" })).toBeVisible();
  await expect(save).toBeEnabled();
  await save.click();
  await expect.poll(async () => (await (await page.request.get(`/api/brands/${id}`)).json()).never_say).toContain("to the moon");
});
