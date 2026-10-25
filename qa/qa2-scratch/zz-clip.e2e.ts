import { expect, test } from "@playwright/test";
import { onBrand, signIn } from "./helpers";

// QA-2 scratch: at desktop sizes, with the brand-piece picker open on fomo, the Generate bar never covers a field.
for (const [w, h] of [[1280, 720], [1280, 900], [1024, 640]] as const) {
  test(`Generate does not cover fields at ${w}x${h}`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    await signIn(page, "reed@example.com");
    await onBrand(page, "fomo");
    await page.getByRole("link", { name: "Quick clip" }).first().click();
    await page.getByRole("button", { name: "Add brand piece" }).click().catch(() => {});
    const gen = page.getByRole("region", { name: "Clip settings" }).getByRole("button", { name: /^(Generate|Ask Reed)/ });
    await expect(gen).toBeVisible();
    const covered = await page.evaluate(async () => {
      const panel = document.querySelector('[aria-label="Clip settings"]')!;
      const btn = [...panel.querySelectorAll("button")].find((b) => /^(Generate|Ask Reed)/.test(b.textContent ?? ""))!;
      const bar = btn.parentElement!;
      const scrollers = [document.scrollingElement as HTMLElement, panel.firstElementChild as HTMLElement];
      const hits = new Set<string>();
      for (const sc of scrollers) {
        for (let y = 0; y <= sc.scrollHeight; y += 30) {
          sc.scrollTop = y;
          await new Promise((r) => requestAnimationFrame(r));
          for (const el of panel.querySelectorAll("input:not(.sr-only),select,textarea,button,summary")) {
            if (bar.contains(el)) continue;
            const r = el.getBoundingClientRect();
            if (r.height === 0 || r.bottom < 0 || r.top > innerHeight) continue;
            const x = r.left + r.width / 2, cy = r.top + r.height / 2;
            if (cy < 0 || cy > innerHeight) continue;
            const inner = scrollers[1], ir = inner.getBoundingClientRect();
            if (inner.scrollHeight > inner.clientHeight + 1 && (cy < ir.top || cy > ir.bottom)) continue; // clipped by the panel's own scroll, not covered
            const top = document.elementFromPoint(x, cy);
            if (top && bar.contains(top)) hits.add(`${el.tagName}:${(el.textContent || (el as HTMLInputElement).name || "").trim().slice(0, 20)}`);
          }
        }
        sc.scrollTop = 0;
      }
      return [...hits];
    });
    await page.screenshot({ path: `test-results/qa2-clip-${w}x${h}.png` });
    expect(covered).toEqual([]);
    await expect(gen).toBeInViewport();
  });
}
