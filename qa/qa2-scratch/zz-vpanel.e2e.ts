import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";
// QA-2 scratch: the version panel at 390 and 1440 (opened, not pressed).
for (const [w, h] of [[390, 844], [1440, 900]] as const) {
  test(`version panel at ${w}`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    await signIn(page, "reed@example.com");
    await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
    const brand = await emptyBrand(page, `Panel Co ${w}`);
    const made = await (await page.request.post("/api/scripts", { data: { brand_id: brand, title: "Panel test", description: "QA", text: "BO: Salmon again?\nMIA: Try it." } })).json();
    await page.request.post(`/api/scripts/${made.id}/drafts/0/approve`);
    await page.request.post(`/api/scripts/${made.id}/publish`);
    await page.goto(`/b/${brand}/scripts`);
    await page.getByRole("link", { name: "Version A, ready to make" }).click();
    const panel = page.getByRole("dialog", { name: "Panel test · Version A" });
    await expect(panel).toContainText("Salmon again?");
    const make = panel.getByRole("button", { name: /Make this version/ });
    await expect(make).toBeVisible();
    console.log(`${w}: button label = "${(await make.textContent())?.trim()}"`);
    const r = await page.evaluate(() => {
      const d = document.querySelector('[role="dialog"]')!;
      const small = [...d.querySelectorAll<HTMLElement>("a,button,input,select,textarea")].filter((el) => { const b = el.getBoundingClientRect(); return b.height > 0 && b.height < 43.5; }).map((el) => `${el.tagName}[${Math.round(el.getBoundingClientRect().height)}] ${(el.getAttribute("aria-label") || el.textContent || "").trim().slice(0, 30)}`);
      const de = document.documentElement; const pr = d.getBoundingClientRect();
      return { sideways: de.scrollWidth - de.clientWidth, small, panelFits: pr.left >= 0 && pr.right <= innerWidth + 1 };
    });
    await page.screenshot({ path: `test-results/qa2-vpanel-${w}.png` });
    expect(r).toEqual({ sideways: 0, small: [], panelFits: true });
  });
}
