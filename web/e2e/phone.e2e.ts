import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test.use({ viewport: { width: 390, height: 844 } });

test("on a phone, the bottom tabs and More reach every section", async ({ page }) => {
  await signIn(page, "reed@example.com");
  const tabs = page.getByRole("navigation", { name: "Tabs" });
  await expect(tabs).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Main" })).toBeHidden();

  await tabs.getByRole("link", { name: "Library" }).click();
  await expect(page.getByRole("heading", { name: "Library" })).toBeVisible();

  await tabs.getByRole("link", { name: "Clip" }).click();
  await expect(page.getByRole("heading", { name: /^Quick clip/ })).toBeVisible();

  await tabs.getByRole("button", { name: "More" }).click();
  await page.getByRole("link", { name: "Brand kit" }).click();
  await expect(page.getByRole("heading", { name: /^Brand kit/ })).toBeVisible();

  await tabs.getByRole("button", { name: "More" }).click();
  await page.getByRole("link", { name: "Team" }).click();
  await expect(page.getByRole("heading", { name: "Team" })).toBeVisible();
});
