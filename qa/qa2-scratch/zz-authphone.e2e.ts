import { expect, test } from "@playwright/test";
// QA-2 scratch: sign-in and setup pages at 390: no sideways scroll, every control at least 44px, the eye toggles.
test.use({ viewport: { width: 390, height: 844 } });
for (const url of ["/login", "/setup", "/invite/made-up"]) {
  test(`auth page ${url} at 390`, async ({ page }) => {
    await page.goto(url);
    await page.waitForLoadState("networkidle");
    const r = await page.evaluate(() => {
      const de = document.documentElement;
      const small = [...document.querySelectorAll<HTMLElement>("a,button,input:not(.sr-only),select,textarea")]
        .filter((el) => { const b = el.getBoundingClientRect(); return b.height > 0 && b.height < 43.5; })
        .map((el) => `${el.tagName}[${Math.round(el.getBoundingClientRect().height)}] ${(el.getAttribute("aria-label") || el.textContent || "").trim().slice(0, 30)}`);
      return { sideways: de.scrollWidth - de.clientWidth, small };
    });
    expect(r).toEqual({ sideways: 0, small: [] });
  });
}
test("the password eye shows and hides the password", async ({ page }) => {
  await page.goto("/login");
  const pw = page.getByLabel("Password", { exact: true });
  await pw.fill("secret words");
  await expect(pw).toHaveAttribute("type", "password");
  await page.getByRole("button", { name: /Show password/ }).click();
  await expect(pw).toHaveAttribute("type", "text");
  await page.getByRole("button", { name: /Hide password/ }).click();
  await expect(pw).toHaveAttribute("type", "password");
});
