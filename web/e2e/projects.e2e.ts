import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

test("a brief becomes a project that is listed with its credit meter", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  // The earlier way to start a video stays on Scripts, under "Videos made before scripts"; the old list is Videos now.
  const brandId = await emptyBrand(page);
  await page.goto(`/b/${brandId}/projects`);
  await expect(page).toHaveURL(new RegExp(`/b/${brandId}/videos$`));
  await page.goto(`/b/${brandId}/scripts`);
  await page.getByRole("link", { name: "New video (the earlier way)" }).click();
  await page.getByLabel("Title").fill("Launch teaser");
  await page.getByLabel("What's it for?").fill("Announce the new drop.");
  await page.getByRole("button", { name: "1:1" }).click();
  await page.getByLabel("Planned length (seconds)").fill("20");
  await page.getByRole("button", { name: "Create project" }).click();

  await expect(page.getByRole("heading", { name: "Launch teaser" })).toBeVisible();
  await expect(page.getByText("Announce the new drop.")).toBeVisible();
  await expect(page.getByText("1:1")).toBeVisible();

  await page.getByRole("main").getByRole("link", { name: "Videos", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/b/${brandId}/videos$`));
  const card = page.getByRole("listitem").filter({ has: page.getByRole("link", { name: /Launch teaser/ }) });
  await expect(card).toContainText("(earlier way)");
  await expect(card).toContainText("credits");
  await expect(card).not.toContainText("$");
});
