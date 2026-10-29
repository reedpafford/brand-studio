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
    if (width === 390) {
      // A slow Assets list (Reed's Pit Bull 1): it says it's loading, never "0 assets" or "Not in this video's shots" from the list read before the shots.
      await page.route(`**/api/projects/${id}/assets`, async (route) => {
        await new Promise((r) => setTimeout(r, 1500));
        await route.fallback();
      });
    }
    await page.getByRole("button", { name: "Next: Assets" }).click();
    await expect(
      page.getByRole("heading", { name: "Assets", level: 2 }),
    ).toBeVisible();
    if (width === 390) {
      await expect(page.getByText("Loading assets…").first()).toBeVisible();
      await expect(page.getByText(/^0 assets/)).toHaveCount(0);
      await expect(page.getByText("Not in this video's shots")).toHaveCount(0);
      await expect(page.getByText("Loading assets…")).toHaveCount(0, { timeout: 10_000 });
      await page.unrouteAll({ behavior: "ignoreErrors" });
    }
    const sizes = await page.evaluate(() => ({
      scroll: document.documentElement.scrollWidth,
      window: document.documentElement.clientWidth,
    }));
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
    await expect(
      page.getByRole("button", { name: "Next: Storyboard" }),
    ).toBeEnabled();
    if (width === 390) {
      // An approved look the role's words contradict (Reed's Biscuit): the words to update fit a phone.
      await page.route(`**/api/projects/${id}/assets`, (route) =>
        route.fulfill({
          json: [{
            kind: "character", ref: "char:1", role: "Biscuit, the golden retriever", library_item_id: 1, name: "Biscuit", locked: false,
            sheet_status: "approved", ready: true, slot_id: 1, description: "A golden retriever, the narrator", shots: 2, only_here: "video", own_look_id: 1,
            text_fit: { seen: "The approved look is a French bulldog.", name: "Biscuit, the French bulldog", description: "A stocky French bulldog, the narrator", notes: "", update_look: true, update_script: true, note: "" },
          }],
        }),
      );
      await page.reload();
      const update = page.getByRole("button", { name: "Update to match" });
      await expect(update).toBeVisible();
      expect((await update.boundingBox())!.height).toBeGreaterThanOrEqual(44);
      // Its own row: the card's full width on a phone, not the text column beside the picture (QA-2 on #720).
      expect((await page.getByRole("note", { name: /Role words for/ }).boundingBox())!.width).toBeGreaterThan(300);
      await expect(page.getByLabel("How this video describes them")).toHaveValue("A stocky French bulldog, the narrator");
      expect((await page.getByRole("button", { name: "Update the script's role too" }).boundingBox())!.height).toBeGreaterThanOrEqual(44);
      const wide = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(wide).toBeLessThanOrEqual(0);
      await page.unrouteAll({ behavior: "ignoreErrors" });
    }
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
    await page.getByRole("button", { name: /Make the storyboard/ }).click();
    const approve = page.getByRole("button", { name: "Approve", exact: true });
    await expect(approve.first()).toBeVisible({ timeout: 90_000 });
    while (await approve.count()) {
      await approve.first().click();
      await expect(page.getByText("✓ Approved").first()).toBeVisible();
    }
    await page.getByRole("button", { name: /Next: Clips/ }).click();

    // Each prompt is read and marked Looks good before the take is made; Make clip marks it for you (Reed's #32 c6).
    await page.getByRole("button", { name: /Write clip prompts/ }).click();
    await expect(page.getByRole("listitem", { name: "Clip c1" })).toBeVisible({
      timeout: 30_000,
    });
    const make = page.getByRole("button", { name: /^Make clip/ }).first();
    await expect(make).toBeEnabled();
    if (width === 390) expect((await make.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    if (width === 390) {
      // A change that didn't finish (Reed's c5, job 876): a plain line, the words kept, Try again, nothing sideways.
      await page.route(`**/api/projects/${id}/clips`, async (route) => {
        const clips = await (await route.fetch()).json();
        clips[0].change = { note: "Slower, warmer light", job_id: 1, status: "failed", error: "That change didn't finish. Nothing was charged." };
        await route.fulfill({ json: clips });
      });
      await page.reload();
      await expect(page.getByText("That change didn't finish. Nothing was charged.")).toBeVisible();
      await expect(page.getByLabel("Change this… c1")).toHaveValue("Slower, warmer light");
      const again = page.getByRole("button", { name: /^Try again/ });
      expect((await again.boundingBox())!.height).toBeGreaterThanOrEqual(44);
      await expect(page.getByText(/Ask the owner/)).toHaveCount(0);
      const wide = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(wide).toBeLessThanOrEqual(0);
      await page.unrouteAll({ behavior: "ignoreErrors" }); // a poll still in route.fetch must not fail the reload
      await page.reload();
    }
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
    // The whole video is put together by itself.
    await expect(page.getByRole("link", { name: "Download MP4" })).toBeVisible({
      timeout: 60_000,
    });
    const zip = await page.request.get(`/api/projects/${id}/clips.zip`);
    expect(zip.headers()["content-type"]).toBe("application/zip");
    const sizes = await page.evaluate(() => ({
      scroll: document.documentElement.scrollWidth,
      window: document.documentElement.clientWidth,
    }));
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
  });
}

for (const width of [1440, 390]) {
  test(`at ${width}: the Videos view lists a video, filters it, and nothing scrolls sideways`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await signIn(page, "reed@example.com");
    await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
    const brandId = await emptyBrand(page, `Videos View Co ${width}`);
    const made = await page.request.post("/api/projects", { data: { brand_id: brandId, name: "Listed video", planned_seconds: 20 } });
    expect(made.ok()).toBeTruthy();

    await page.goto(`/b/${brandId}/scripts`);
    await page.getByRole("navigation", { name: "View" }).getByRole("link", { name: "Videos" }).click();
    await expect(page).toHaveURL(/view=videos/);
    await expect(page.getByRole("link", { name: /Listed video/ })).toBeVisible();
    await expect(page.getByText("1 video", { exact: true })).toBeVisible();
    await expect(page.getByText(/\(earlier way\)/)).toBeVisible();
    await page.getByRole("searchbox", { name: "Search videos" }).fill("nothing like this");
    await expect(page.getByText("Nothing matches these filters.")).toBeVisible();
    await page.getByRole("button", { name: "Clear filters" }).click();
    await expect(page.getByRole("link", { name: /Listed video/ })).toBeVisible();
    const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
  });
}
