import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

// QA-2 scratch (not committed): the new shell's overlays at 390 and focus return on desktop.
test("at 390 the brand sheet sits over the tab bar, and Escape gives focus back", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signIn(page, "reed@example.com");
  const opener = page.getByRole("button", { name: /^Brand: / });
  await opener.click();
  const sheet = page.getByRole("dialog", { name: "Brands" });
  await expect(sheet).toBeVisible();
  // what is on top at the bottom middle of the screen (where the tab bar lives)
  const onTop = await page.evaluate(() => {
    const el = document.elementFromPoint(195, 844 - 20);
    return !!el?.closest('[role="dialog"]') || !!el?.closest('[aria-hidden]');
  });
  expect(onTop).toBe(true);
  const tabsCovered = await page.evaluate(() => {
    const tabs = document.querySelector('nav[aria-label="Tabs"]');
    const r = tabs!.getBoundingClientRect();
    const el = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    return !tabs!.contains(el);
  });
  expect(tabsCovered).toBe(true);
  await page.keyboard.press("Escape");
  await expect(sheet).toHaveCount(0);
  await expect(opener).toBeFocused();
  const [sw, cw] = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]);
  expect(sw).toBeLessThanOrEqual(cw);
});

test("on desktop, Escape on the account and brand menus gives focus back to their buttons", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await signIn(page, "reed@example.com");
  for (const name of ["Account menu", /^Brand: /] as const) {
    const b = page.getByRole("button", { name });
    await b.click();
    await expect(page.getByRole("menu")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("menu")).toHaveCount(0);
    await expect(b).toBeFocused();
  }
});

test("the switcher keeps the section", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await signIn(page, "reed@example.com");
  await page.getByRole("link", { name: "Cast & places" }).click();
  await expect(page).toHaveURL(/\/library/);
  await page.getByRole("button", { name: /^Brand: / }).click();
  await page.getByRole("menuitemradio", { name: "Iron Paws" }).click();
  await expect(page.getByRole("button", { name: "Brand: Iron Paws" })).toBeVisible();
  await expect(page).toHaveURL(/\/library/);
});
