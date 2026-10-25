import { expect, test, type Page } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

// QA-2 scratch (not committed): the video frame's steps, locks, aliases, script panel and phone sheet.
async function pipeline(page: Page) {
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brands = (await (await page.request.get("/api/brands")).json()) as { id: number; name: string }[];
  const b = brands.find((x) => x.name === "Pipeline Co")!.id;
  const p = ((await (await page.request.get(`/api/projects?brand_id=${b}`)).json()) as { id: number; name: string }[]).find((x) => x.name === "Pipeline test")!.id;
  return `/b/${b}/projects/${p}`;
}

test("desktop: every step opens, the Script panel shows the script and closes on Escape", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  const base = await pipeline(page);
  for (const s of ["brief", "script", "shots", "storyboard", "clips", "final"]) {
    await page.goto(`${base}?stage=${s}`);
    await expect(page.locator('[aria-current="step"]')).toBeVisible();
    if (s !== "brief" && s !== "script") {
      const btn = page.getByRole("button", { name: "Script", exact: true });
      await btn.click();
      const panel = page.getByRole("dialog", { name: "Script" });
      await expect(panel.getByRole("list", { name: "Script text" })).toContainText("MAX: Where did the food go?");
      await page.keyboard.press("Escape");
      await expect(panel).toHaveCount(0);
      await expect(btn).toBeFocused();
    }
  }
});

test("old ?stage= names still work", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  const base = await pipeline(page);
  await page.goto(`${base}?stage=enhance`);
  await expect(page.locator('[aria-current="step"]')).toContainText("Script");
  await page.goto(`${base}?stage=breakdown`);
  await expect(page.locator('[aria-current="step"]')).toContainText("Shots");
});

test("a new video: later steps are locked with a reason, and a link to one lands on an open step", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brandId = await emptyBrand(page, "Lock Shop");
  const made = await (await page.request.post("/api/projects", { data: { brand_id: brandId, name: "Locks", planned_seconds: 20 } })).json();
  await page.goto(`/b/${brandId}/projects/${made.id}?stage=storyboard`);
  await expect(page.locator('[aria-current="step"]')).not.toContainText("Storyboard");
  const shots = page.getByRole("button", { name: /Shots/ }).first();
  await expect(shots).toHaveAttribute("aria-disabled", "true");
  const desc = await shots.getAttribute("aria-describedby");
  expect(desc).toBeTruthy();
  await expect(page.locator(`[id="${desc}"]`)).toContainText("Finish Script first");
  await shots.click({ force: true });
  await expect(page.locator('[aria-current="step"]')).not.toContainText("Shots");
});

test("phone: the step sheet lists six steps, Next sits in the action bar, the Script sheet opens, no sideways scroll", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const base = await pipeline(page);
  for (const s of ["brief", "script", "shots", "storyboard", "clips", "final"]) {
    await page.goto(`${base}?stage=${s}`);
    const picker = page.getByRole("button", { name: /^Step \d of 6/ });
    await expect(picker).toBeVisible();
    const [sw, cw] = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]);
    expect(sw, s).toBeLessThanOrEqual(cw);
  }
  await page.goto(`${base}?stage=shots`);
  await page.getByRole("button", { name: /^Step \d of 6/ }).click();
  const sheet = page.getByRole("dialog", { name: "Steps" });
  await expect(sheet.getByRole("listitem")).toHaveCount(6);
  await sheet.getByRole("button", { name: /Storyboard/ }).click();
  await expect(page.getByRole("button", { name: /^Step 4 of 6 · Storyboard/ })).toBeVisible();
  const next = page.getByRole("button", { name: /^Next: Clips/ });
  await expect(next).toBeVisible();
  const nb = (await next.boundingBox())!;
  expect(nb.height).toBeGreaterThanOrEqual(44);
  expect(nb.y).toBeGreaterThan(844 - 64 - 68 - 10); // in the action bar above the tabs
  await page.getByRole("button", { name: "Script", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Script" }).getByRole("list", { name: "Script text" })).toContainText("MAX:");
});
