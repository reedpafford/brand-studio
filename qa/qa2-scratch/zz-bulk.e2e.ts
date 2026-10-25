import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";
// QA-2 scratch: Bulk create at 390 and 1440. Write all is never pressed.
for (const [w, h] of [[390, 844], [1440, 900]] as const) {
  test(`bulk create at ${w}`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    await signIn(page, "reed@example.com");
    await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
    const brand = await emptyBrand(page, `Bulk Co ${w}`);
    await page.goto(`/b/${brand}/scripts`);
    await page.getByRole("button", { name: "Bulk create" }).click();
    const d = page.getByRole("dialog");
    await expect(d).toBeVisible();
    const audit = () => page.evaluate((phone) => {
      const dlg = document.querySelector('[role="dialog"]')!;
      const small = [...dlg.querySelectorAll<HTMLElement>("a,button,input:not(.sr-only),select,textarea")]
        .filter((el) => { const box = (el.tagName === "INPUT" && el.closest("label")) ? el.closest("label")!.getBoundingClientRect() : el.getBoundingClientRect(); return box.height > 0 && box.height < (phone ? 43.5 : 35.5); })
        .map((el) => `${el.tagName}[${Math.round(el.getBoundingClientRect().height)}] ${(el.getAttribute("aria-label") || el.textContent || "").trim().slice(0, 30)}`);
      const r = dlg.getBoundingClientRect();
      return { sideways: document.documentElement.scrollWidth - document.documentElement.clientWidth, small, fits: r.left >= 0 && r.right <= innerWidth + 1 };
    }, w < 640);
    expect(await audit()).toEqual({ sideways: 0, small: [], fits: true });
    await d.getByLabel("Title 1").fill("Bulk one");
    await d.getByLabel("What it's for 1").fill("A test.");
    const buttons = await d.getByRole("button").allTextContents();
    console.log(`${w} buttons: ${buttons.map((b) => b.trim()).filter(Boolean).join(" | ")}`);
    await page.screenshot({ path: `test-results/qa2-bulk-${w}.png`, fullPage: true });
  });
}
