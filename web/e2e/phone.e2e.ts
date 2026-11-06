import { expect, test } from "@playwright/test";
import { onBrand, openAccountMenu, signIn } from "./helpers";

test.use({ viewport: { width: 390, height: 844 } });

test("on a phone, the four tabs (v6 P-01) reach every brand section and there is no sideways scroll", async ({ page }) => {
  await signIn(page, "reed@example.com");
  const tabs = page.getByRole("navigation", { name: "Tabs" });
  await expect(tabs).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Main" })).toHaveCount(0);
  await onBrand(page, "fomo"); // the sign-in redirect has landed
  await expect(tabs.getByRole("link")).toHaveCount(4);

  await tabs.getByRole("link", { name: "Videos" }).click();
  await expect(page).toHaveURL(/\/b\/\d+\/videos$/);
  await expect(page.getByRole("link", { name: /Unsorted/ })).toBeVisible(); // P-01: the brand's folders
  await page.getByRole("main").getByRole("link", { name: "New video" }).click();
  await expect(page.getByRole("heading", { name: "New video", exact: true })).toBeVisible();
  await page.goBack();

  await tabs.getByRole("link", { name: "Library" }).click();
  await page.getByRole("link", { name: "Cast & places" }).click();
  await expect(page.getByRole("navigation", { name: "Library" })).toBeVisible(); // P-13
  await tabs.getByRole("link", { name: "Library" }).click();
  await page.getByRole("link", { name: "Brand kit" }).click();
  await expect(page.getByLabel("Tone and rules")).toBeVisible(); // the library's Brand kit (P-13)
  await tabs.getByRole("link", { name: "Library" }).click();
  await page.getByRole("link", { name: "Scripts" }).click();
  await expect(page.getByRole("heading", { name: "Scripts", exact: true })).toBeVisible();
  const widths = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
  expect(widths.scroll).toBeLessThanOrEqual(widths.window);
});

test("on a phone, Needs you is a tab, and More has Team, Settings, the account and Sign out (S-gaps-04 R3)", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  const tabs = page.getByRole("navigation", { name: "Tabs" });
  await tabs.getByRole("link", { name: /^Needs you/ }).click();
  await expect(page.getByRole("heading", { name: "Needs you", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

  await tabs.getByRole("link", { name: "More" }).click();
  await page.getByRole("link", { name: "Team" }).click();
  await expect(page.getByRole("heading", { name: "Team" })).toBeVisible();
  await tabs.getByRole("link", { name: "More" }).click();
  await page.getByRole("link", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "Settings", exact: true })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Studio" })).toHaveAttribute("aria-selected", "true"); // v5: Studio is the first tab
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("on a phone, the brand menu opens as a sheet and switches brand", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await page.getByRole("button", { name: /^Brand: / }).click();
  await expect(page.getByRole("dialog", { name: "Brands" })).toBeVisible();
  await page.getByRole("menuitemradio", { name: "Iron Paws" }).click();
  await expect(page.getByRole("button", { name: "Brand: Iron Paws" })).toBeVisible();
});

test("on a phone, the app is light only and the account menu offers no theme (rule 33)", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await openAccountMenu(page);
  await expect(page.getByRole("menuitemradio", { name: "Dark" })).toHaveCount(0);
  await expect(page.getByRole("group", { name: "Theme" })).toHaveCount(0);
  const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(bg).not.toBe("rgb(14, 15, 17)"); // never the old dark background
});

test("on a phone, Escape closes the account menu and Sign out (in More) ends the session", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await openAccountMenu(page);
  await expect(page.getByRole("menuitem", { name: "Sign out" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("menuitem", { name: "Sign out" })).toHaveCount(0);

  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);
});

test("on a phone, New script → Dialogue opens with the box focused and no sideways scroll; backing out saves nothing", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  await page.getByRole("navigation", { name: "Tabs" }).getByRole("link", { name: "Library" }).click();
  await page.getByRole("link", { name: "Scripts" }).click();
  await expect(page.getByRole("heading", { name: "Scripts", exact: true })).toBeVisible();
  await page.waitForLoadState("networkidle"); // count once the rows have loaded, not before (an earlier test's Untitled script)
  const untitled = await page.getByRole("link", { name: "Untitled script" }).count();
  await page.getByRole("button", { name: "New script" }).first().click();
  await page.getByRole("menuitem", { name: /Dialogue/ }).click();
  await expect(page.getByLabel("Write or paste the script")).toBeFocused();
  const widths = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
  expect(widths.scroll).toBeLessThanOrEqual(widths.window);
  await page.goBack();
  await expect(page.getByRole("heading", { name: "Scripts", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Untitled script" })).toHaveCount(untitled);
});
