import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

// The new video page (Breakdown · Assets · Storyboard · Clips · Downloads) on the free stand-ins.
const SCRIPT = [
  "SCENE 1 - KITCHEN",
  "Max stares at the empty bowl.",
  "MAX: Where did the food go?",
  "MIA: Ask him.",
].join("\n");

for (const width of [1440, 390]) {
  test(`at ${width}: shots are made, Assets lets you go on, and nothing scrolls sideways`, async ({
    page,
  }) => {
    test.setTimeout(120_000);
    await page.setViewportSize({ width, height: 900 });
    await signIn(page, "reed@example.com");
    await expect(
      page.getByRole("button", { name: "Account menu" }),
    ).toBeVisible();
    const brandId = await emptyBrand(page, `Video Co ${width}`);
    const made = await page.request.post("/api/projects", {
      data: { brand_id: brandId, name: "Video test", planned_seconds: 20 },
    });
    const id = (await made.json()).id;
    expect(
      (
        await page.request.put(`/api/projects/${id}/script`, {
          data: { text: SCRIPT },
        })
      ).ok(),
    ).toBeTruthy();

    await page.goto(`/b/${brandId}/videos/${id}`);
    await expect(
      page.getByRole("heading", { name: "Breakdown", level: 2 }),
    ).toBeVisible();
    await page.getByRole("button", { name: /Make shots/ }).click();
    await expect(page.getByRole("region", { name: "Scene 1" })).toBeVisible({
      timeout: 30_000,
    });
    await page.getByRole("button", { name: "Next: Assets" }).click();
    await expect(
      page.getByRole("heading", { name: "Assets", level: 2 }),
    ).toBeVisible();
    const sizes = await page.evaluate(() => ({
      scroll: document.documentElement.scrollWidth,
      window: document.documentElement.clientWidth,
    }));
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
    await expect(
      page.getByRole("button", { name: "Next: Storyboard" }),
    ).toBeEnabled();
  });
}

for (const width of [1440, 390]) {
  test(`at ${width}: the new page takes a script to a finished video, one-press storyboard, prompts read first`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    test.setTimeout(180_000);
    await signIn(page, "reed@example.com");
    await expect(
      page.getByRole("button", { name: "Account menu" }),
    ).toBeVisible();
    const brandId = await emptyBrand(page, `Video Flow Co ${width}`);
    const made = await page.request.post("/api/projects", {
      data: { brand_id: brandId, name: "Flow test", planned_seconds: 20 },
    });
    const id = (await made.json()).id;
    expect(
      (
        await page.request.put(`/api/projects/${id}/script`, {
          data: { text: SCRIPT },
        })
      ).ok(),
    ).toBeTruthy();

    await page.goto(`/b/${brandId}/videos/${id}`);
    await page.getByRole("button", { name: /Make shots/ }).click();
    await expect(page.getByRole("region", { name: "Scene 1" })).toBeVisible({
      timeout: 30_000,
    });
    await page.getByRole("button", { name: "Next: Assets" }).click();
    await page.getByRole("button", { name: "Next: Storyboard" }).click();

    // One press writes the frames and draws every still.
    await page.getByRole("button", { name: /Make storyboard/ }).click();
    const approve = page.getByRole("button", { name: "Approve", exact: true });
    await expect(approve.first()).toBeVisible({ timeout: 90_000 });
    while (await approve.count()) {
      await approve.first().click();
      await expect(page.getByText("✓ Approved").first()).toBeVisible();
    }
    await page.getByRole("button", { name: /Next: Clips/ }).click();

    // Each prompt is read and marked Looks good before the take is made.
    await page.getByRole("button", { name: /Write clip prompts/ }).click();
    await expect(page.getByRole("listitem", { name: "Clip c1" })).toBeVisible({
      timeout: 30_000,
    });
    await expect(
      page.getByRole("button", { name: /^Make clip/ }).first(),
    ).toBeDisabled();
    await page
      .getByRole("button", { name: /^Prompt for c1 looks good$/ })
      .click();
    await page
      .getByRole("button", { name: /^Make clip/ })
      .first()
      .click();
    await expect(
      page.getByRole("button", { name: "✓ Looks good" }).first(),
    ).toBeVisible({ timeout: 90_000 });
    await page.getByRole("button", { name: "✓ Looks good" }).first().click();
    await page.getByRole("button", { name: /Next: Downloads/ }).click();
    await page
      .getByRole("button", { name: "Make the video", exact: true })
      .click();
    await expect(page.getByRole("link", { name: "Download MP4" })).toBeVisible({
      timeout: 60_000,
    });
    const sizes = await page.evaluate(() => ({
      scroll: document.documentElement.scrollWidth,
      window: document.documentElement.clientWidth,
    }));
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
  });
}
