import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

test("a brief becomes a project that is listed with its credit meter", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  await page.goto(`/b/${await emptyBrand(page)}`);
  await expect(page).toHaveURL(/\/projects$/);
  await expect(page.getByText("No videos for Night Owl yet.")).toBeVisible();

  await page.getByRole("link", { name: "New video" }).click();
  await page.getByLabel("Title").fill("Launch teaser");
  await page.getByLabel("What's it for?").fill("Announce the new drop.");
  await page.getByRole("button", { name: "1:1" }).click();
  await page.getByLabel("Planned length (seconds)").fill("20");
  await page.getByRole("button", { name: "Create project" }).click();

  await expect(page.getByRole("heading", { name: "Launch teaser" })).toBeVisible();
  await expect(page.getByText("Announce the new drop.")).toBeVisible();
  await expect(page.getByText("1:1")).toBeVisible();

  await page.getByRole("link", { name: "← Projects" }).click();
  const card = page.getByRole("link", { name: /Launch teaser/ });
  await expect(card).toContainText("20s · 1:1");
  await expect(card).toContainText("credits");
  await expect(card).not.toContainText("$");
});
