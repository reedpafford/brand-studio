import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

// QA-2 scratch: the action bar on Videos at 390 and 768.
for (const [w, h] of [[390, 844], [768, 1024]] as const) {
  test(`action bar at ${w}`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    await signIn(page, "reed@example.com");
    await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
    const brands = (await (await page.request.get("/api/brands")).json()) as { id: number; name: string }[];
    await page.goto(`/b/${brands.find((b) => b.name === "Pipeline Co")!.id}/projects`);
    await expect(page.getByRole("heading", { name: "Videos", exact: true })).toBeVisible();
    await expect(page.getByRole("main").getByRole("listitem").first()).toBeVisible();
    const link = page.getByRole("link", { name: "New video" });
    await expect(link).toHaveCount(1);
    await expect(link).toBeVisible();
    const r = (await link.boundingBox())!;
    const tabs = (await page.getByRole("navigation", { name: "Tabs" }).boundingBox())!;
    expect(r.height).toBeGreaterThanOrEqual(44);
    expect(r.y + r.height).toBeLessThanOrEqual(tabs.y + 1); // sits above the tabs
    expect(r.width).toBeGreaterThan(w - 80); // full width less padding
    const [sw, cw] = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]);
    expect(sw).toBeLessThanOrEqual(cw);
    // the last card is not hidden under the bar when scrolled to the end
    await page.evaluate(() => window.scrollTo(0, 1e6));
    const last = page.getByRole("main").getByRole("listitem").last();
    if (await last.count()) {
      const lb = (await last.boundingBox())!;
      expect(lb.y + lb.height).toBeLessThanOrEqual(r.y + 2);
    }
    await page.screenshot({ path: `test-results/qa2-bar-${w}.png` });
  });
}
