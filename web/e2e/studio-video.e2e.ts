import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

// One video in the new look (the redesign, stage 2; /s/b/N/videos/ID), on the real server: what only a real browser
// can measure. It fits the window at a desk and on a phone, the divider drags within its limits and is remembered,
// and the page sends nothing but reads.
for (const [width, height] of [[1440, 900], [390, 844]]) {
  test(`at ${width}, a video opens in the new look, only reads, and nothing scrolls sideways; a desk's divider drags and is remembered`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await signIn(page, "reed@example.com");
    await expect(page.getByRole("button", { name: /^Brand: / }).first()).toBeVisible();
    const brandId = await emptyBrand(page, `Studio video ${width}`);
    const id = (await (await page.request.post("/api/projects", { data: { brand_id: brandId, name: "A video to read", planned_seconds: 20 } })).json()).id;
    const writes: string[] = [];
    page.on("request", (r) => r.method() !== "GET" && new URL(r.url()).pathname.startsWith("/api/") && writes.push(`${r.method()} ${r.url()}`));

    await page.goto(`/s/b/${brandId}/videos/${id}`);
    await expect(page.getByRole("heading", { name: "A video to read" })).toBeVisible();
    await expect(page.getByRole("link", { name: "open this video on the current site" })).toHaveAttribute("href", `/b/${brandId}/videos/${id}`);
    const film = page.getByRole("region", { name: "The video" });
    for (const view of ["Cut", "Cast", "Plan"]) await film.getByRole("button", { name: view }).click();
    await expect(film.getByText("The plan shows here first")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);

    const bar = page.getByRole("separator", { name: "Resize the chat and the film" });
    if (width > 900) {
      const chat = page.getByRole("region", { name: "The director" });
      const at = (await bar.boundingBox())!;
      const before = (await chat.boundingBox())!.width;
      await page.mouse.move(at.x + 4, at.y + 200);
      await page.mouse.down();
      await page.mouse.move(at.x + 4 - 150, at.y + 200, { steps: 5 });
      await page.mouse.up();
      expect(Math.abs((await chat.boundingBox())!.width - (before - 150))).toBeLessThanOrEqual(5); // it follows the pointer
      await page.mouse.move(at.x - 150 + 4, at.y + 200);
      await page.mouse.down();
      await page.mouse.move(0, at.y + 200, { steps: 5 }); // as far left as it goes: the chat keeps its least width
      await page.mouse.up();
      expect((await chat.boundingBox())!.width).toBe(320);
      await page.reload();
      await expect(page.getByRole("heading", { name: "A video to read" })).toBeVisible();
      expect((await chat.boundingBox())!.width).toBe(320);
      await bar.dblclick();
      expect((await chat.boundingBox())!.width).toBeGreaterThan(320);
    } else await expect(bar).toBeHidden(); // a phone stacks the two
    expect(writes).toEqual([]);
  });
}
