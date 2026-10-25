import { expect, test } from "@playwright/test";
import { onBrand, signIn } from "./helpers";

// QA-2 scratch (sticky-footer rule): every control can be seen uncovered at some scroll position,
// nothing is covered at the page end, and Generate is always in the window.
for (const [w, h] of [[1280, 720], [1440, 900], [1024, 640]] as const) {
  test(`sticky Generate at ${w}x${h}`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    await signIn(page, "reed@example.com");
    await onBrand(page, "fomo");
    await page.getByRole("link", { name: "Quick clip" }).first().click();
    await page.getByRole("button", { name: "Add brand piece" }).click().catch(() => {});
    await expect(page.getByRole("region", { name: "Clip settings" }).getByRole("button", { name: /^(Generate|Ask Reed)/ })).toBeVisible();
    const res = await page.evaluate(async () => {
      const panel = document.querySelector('[aria-label="Clip settings"]')!;
      const btn = [...panel.querySelectorAll("button")].find((b) => /^(Generate|Ask Reed)/.test(b.textContent ?? ""))!;
      const bar = btn.parentElement!;
      const sc = document.scrollingElement as HTMLElement;
      const controls = [...panel.querySelectorAll("input:not(.sr-only),select,textarea,button,summary")].filter((el) => !bar.contains(el) && el.getBoundingClientRect().height > 0);
      const seen = new Set<Element>();
      let barOut = 0, coveredAtEnd: string[] = [];
      const name = (el: Element) => `${el.tagName}:${(el.textContent || "").trim().slice(0, 20)}`;
      const max = sc.scrollHeight - sc.clientHeight;
      for (let y = 0; y <= max + 30; y += 20) {
        sc.scrollTop = Math.min(y, max);
        await new Promise((r) => requestAnimationFrame(r));
        const b = btn.getBoundingClientRect();
        if (b.top < 0 || b.bottom > innerHeight) barOut++;
        const end = sc.scrollTop >= max - 1;
        for (const el of controls) {
          const r = el.getBoundingClientRect();
          const x = r.left + r.width / 2, cy = r.top + r.height / 2;
          if (cy < 0 || cy > innerHeight) continue;
          const top = document.elementFromPoint(x, cy);
          const under = !!top && bar.contains(top);
          if (!under) seen.add(el);
          else if (end) coveredAtEnd.push(name(el));
        }
      }
      return { never: controls.filter((c) => !seen.has(c)).map(name), coveredAtEnd: [...new Set(coveredAtEnd)], barOut };
    });
    expect(res).toEqual({ never: [], coveredAtEnd: [], barOut: 0 });
  });
}
