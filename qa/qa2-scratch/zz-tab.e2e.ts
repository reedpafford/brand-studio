import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";
// QA-2 scratch: the step picker is the sheet button below 1024 and the row from 1024.
for (const [w, sheet] of [[390, true], [768, true], [1023, true], [1024, false], [1280, false]] as const) {
  test(`step picker at ${w}`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: 900 });
    await signIn(page, "reed@example.com");
    await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
    const brands = (await (await page.request.get("/api/brands")).json()) as { id: number; name: string }[];
    const b = brands.find((x) => x.name === "Pipeline Co")!.id;
    const p = ((await (await page.request.get(`/api/projects?brand_id=${b}`)).json()) as { id: number }[])[0].id;
    await page.goto(`/b/${b}/projects/${p}?stage=script`);
    const btn = page.getByRole("button", { name: /^Step \d of 6/ });
    const row = page.getByRole("list", { name: "Steps" });
    if (sheet) {
      await expect(btn).toBeVisible();
      expect((await btn.boundingBox())!.height).toBeGreaterThanOrEqual(44);
      await expect(row).toHaveCount(0);
    } else {
      await expect(row).toBeVisible();
      await expect(btn).toHaveCount(0);
    }
    const [sw, cw] = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]);
    expect(sw).toBeLessThanOrEqual(cw);
  });
}
