import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

// Reed couldn't see the samples: a portrait still was cropped into a wide box. The card now shows it whole,
// and tapping it opens the full still and the 5 s clip (made here by the free stand-ins).
for (const [width, look] of [[1440, "Zack D"], [390, "Skeleton"]] as const) {
  test(`at ${width}: a ${look} sample shows whole on its card, and opens full size with its clip playing`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await signIn(page, "reed@example.com");
    await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
    await page.goto("/looks");
    const card = page.getByRole("listitem", { name: look });
    const make = card.getByRole("button", { name: /^Make a sample/ });
    const thumb = card.getByAltText(`${look} sample`);
    await expect(make.or(thumb)).toBeVisible();
    if (await make.isVisible()) await make.click(); // a retry finds it made already
    await expect(thumb).toBeVisible({ timeout: 30_000 });
    expect(await thumb.evaluate((img) => getComputedStyle(img).objectFit)).toBe("contain"); // never cropped
    const open = card.getByRole("button", { name: `Open the ${look} sample` });
    const [img, box] = [(await thumb.boundingBox())!, (await open.boundingBox())!];
    expect(img.y + img.height).toBeLessThanOrEqual(box.y + box.height + 1); // the whole picture sits inside its box
    expect(img.x + img.width).toBeLessThanOrEqual(box.x + box.width + 1);
    expect((await open.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await expect(card.getByText("▶ 5 s clip")).toBeVisible({ timeout: 30_000 }); // the clip has landed
    await open.click();
    const viewer = page.getByRole("dialog", { name: `${look} sample` });
    await expect(viewer.getByAltText(`${look} sample, full size`)).toBeVisible();
    const clip = viewer.getByLabel(`${look} sample clip`);
    await expect(clip).toHaveAttribute("controls", "");
    await expect(viewer.getByRole("button", { name: /Switch on for editors|Switch off/ })).toBeVisible();
    const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
    await expect(page.getByText("$")).toHaveCount(0);
  });
}
