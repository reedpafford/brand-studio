import { expect, test } from "@playwright/test";
import { onBrand, signIn } from "./helpers";

test.use({ viewport: { width: 390, height: 844 } });

test("on a phone, the five bottom tabs reach every brand section and there is no sideways scroll", async ({ page }) => {
  await signIn(page, "reed@example.com");
  const tabs = page.getByRole("navigation", { name: "Tabs" });
  await expect(tabs).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Main" })).toHaveCount(0);
  await onBrand(page, "fomo"); // the sign-in redirect has landed

  await tabs.getByRole("link", { name: "Videos" }).click();
  await expect(page.getByRole("heading", { name: "Videos", exact: true })).toBeVisible();

  await tabs.getByRole("link", { name: "Cast" }).click();
  await expect(page.getByRole("heading", { name: "Cast & places" })).toBeVisible();

  await tabs.getByRole("link", { name: "Quick clip" }).click();
  await expect(page.getByRole("heading", { name: "Quick clip", exact: true })).toBeVisible();

  await tabs.getByRole("link", { name: "Brand" }).click();
  await expect(page.getByRole("heading", { name: "Brand", exact: true })).toBeVisible();

  await tabs.getByRole("link", { name: "Scripts", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Scripts", exact: true })).toBeVisible();
  const widths = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
  expect(widths.scroll).toBeLessThanOrEqual(widths.window);
});

test("on a phone, with nothing waiting Reed sees no Approvals bell (the page still opens), and reaches Team from the account menu", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const waiting = (await (await page.request.get("/api/jobs?status=needs_owner_approval")).json()).length;
  if (waiting === 0) await expect(page.getByRole("link", { name: /^Approvals/ })).toHaveCount(0);
  else await expect(page.getByRole("link", { name: /^Approvals/ })).toBeVisible();
  await page.goto("/approvals");
  await expect(page.getByRole("heading", { name: /^Approvals/ })).toBeVisible();

  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("link", { name: "Team" }).click();
  await expect(page.getByRole("heading", { name: "Team" })).toBeVisible();
});

test("on a phone, the brand menu opens as a sheet and switches brand", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await page.getByRole("button", { name: /^Brand: / }).click();
  await expect(page.getByRole("dialog", { name: "Brands" })).toBeVisible();
  await page.getByRole("menuitemradio", { name: "Iron Paws" }).click();
  await expect(page.getByRole("button", { name: "Brand: Iron Paws" })).toBeVisible();
});

test("on a phone, the theme can be changed from the account menu and is remembered", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitemradio", { name: "Light" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByRole("menuitemradio", { name: "Match my device" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "system");

  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "system");
});

test("on a phone, Escape closes the account menu and Sign out ends the session", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await page.getByRole("button", { name: "Account menu" }).click();
  await expect(page.getByRole("menuitem", { name: "Sign out" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("menuitem", { name: "Sign out" })).toHaveCount(0);

  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);
});

test("on a phone, New script → Dialogue opens with the box focused and no sideways scroll; backing out saves nothing", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  await page.getByRole("navigation", { name: "Tabs" }).getByRole("link", { name: "Scripts", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Scripts", exact: true })).toBeVisible();
  const untitled = await page.getByRole("link", { name: "Untitled script" }).count();
  await page.getByRole("button", { name: "New script" }).first().click();
  await page.getByRole("menuitem", { name: /Dialogue/ }).click();
  await expect(page.getByLabel("Paste or write your script")).toBeFocused();
  const widths = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
  expect(widths.scroll).toBeLessThanOrEqual(widths.window);
  await page.goBack();
  await expect(page.getByRole("heading", { name: "Scripts", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Untitled script" })).toHaveCount(untitled);
});
