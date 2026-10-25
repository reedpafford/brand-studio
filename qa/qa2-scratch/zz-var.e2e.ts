import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";
// QA-2 scratch: Variations at 390 and 1440: prices inside Write and Regenerate, nothing under 44px on phones, original words unchanged.
for (const [w, h] of [[390, 844], [1440, 900]] as const) {
  test(`variations at ${w}`, async ({ page }) => {
    test.setTimeout(120_000);
    await page.setViewportSize({ width: w, height: h });
    await signIn(page, "reed@example.com");
    await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
    const brand = await emptyBrand(page, `Var Co ${w}`);
    const words = "BO: Salmon again?\nMIA: Try it.";
    const made = await (await page.request.post("/api/scripts", { data: { brand_id: brand, title: "Var test", description: "QA", text: words } })).json();
    await page.goto(`/b/${brand}/scripts/${made.id}?step=variations`);
    await page.getByRole("radio", { name: "2", exact: true }).click();
    const write = page.getByRole("button", { name: /^Write 2 variations/ });
    await expect(write).toContainText(/· \d+ credits?/);
    console.log(`${w} write: ${(await write.textContent())?.trim()}`);
    const audit = () => page.evaluate((phone) => {
      const small = [...document.querySelectorAll<HTMLElement>("main a, main button, main input:not(.sr-only), main select, main textarea")]
        .filter((el) => { const box = (el.tagName === "INPUT" && el.closest("label")) ? el.closest("label")!.getBoundingClientRect() : el.getBoundingClientRect(); return box.height > 0 && box.height < (phone ? 43.5 : 35.5); })
        .map((el) => `${el.tagName}[${Math.round(el.getBoundingClientRect().height)}] ${(el.getAttribute("aria-label") || el.textContent || "").trim().slice(0, 30)}`);
      return { sideways: document.documentElement.scrollWidth - document.documentElement.clientWidth, small };
    }, w < 640);
    expect(await audit()).toEqual({ sideways: 0, small: [] });
    await write.click();
    const b = page.getByLabel("Version B", { exact: true });
    await expect(b).toBeVisible({ timeout: 60_000 });
    const regen = b.getByRole("button", { name: /^Regenerate/ });
    await expect(regen).toContainText(/· \d+ credits?/);
    console.log(`${w} regen: ${(await regen.textContent())?.trim()}`);
    expect(await audit()).toEqual({ sideways: 0, small: [] });
    await page.screenshot({ path: `test-results/qa2-var-${w}.png`, fullPage: true });
    const s = await (await page.request.get(`/api/scripts/${made.id}`)).json();
    const a = s.versions.find((v: { slot: number }) => v.slot === 0);
    expect(a.text).toBe(words); // the original's words never change
    console.log(`${w} original status after Write: ${a.status}`);
  });
}
