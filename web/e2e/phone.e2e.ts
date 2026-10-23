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

test("on a phone, the theme can be changed from More and is remembered", async ({ page }) => {
  await signIn(page, "reed@example.com");
  const tabs = page.getByRole("navigation", { name: "Tabs" });
  await tabs.getByRole("button", { name: "More" }).click();
  await page.getByRole("button", { name: "Theme: System" }).click();
  await expect(page.getByRole("button", { name: "Theme: Light" })).toBeVisible();
  await page.getByRole("button", { name: "Theme: Light" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

test("on a phone, Escape closes More and Sign out ends the session", async ({ page }) => {
  await signIn(page, "reed@example.com");
  const tabs = page.getByRole("navigation", { name: "Tabs" });
  await tabs.getByRole("button", { name: "More" }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "Sign out" })).toHaveCount(0);

  await tabs.getByRole("button", { name: "More" }).click();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);
});
