import { expect, test } from "@playwright/test";
import { approveCastWhenReady, emptyBrand, makeIt, planAndApprove, signIn } from "./helpers";

// A video made by hand on the video page (v6 S3: the preview panel's Plan, Cast, Clips and Cut tabs) on the free stand-ins.
const SCRIPT = [
  "SCENE 1 - KITCHEN",
  "Max stares at the empty bowl.",
  "MAX: Where did the food go?",
  "MIA: Ask him.",
].join("\n");

for (const width of [1440, 390]) {
  test(`at ${width}: shots are made, Cast opens from its tab, and nothing scrolls sideways`, async ({
    page,
  }) => {
    test.setTimeout(120_000);
    await page.setViewportSize({ width, height: 900 });
    await signIn(page, "reed@example.com");
    approveCastWhenReady(page); // the Cast tab's Approve cast & places (#1324)
    await expect(page.getByRole("button", { name: /^Brand: / }).first()).toBeVisible();
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

    await page.goto(`/b/${brandId}/videos/${id}?tab=plan`);
    await expect(page.getByRole("tab", { name: "Plan", selected: true })).toBeVisible();
    // The plan first (item 1b): the director makes and approves it (S8), stood in for here; approving makes the shots.
    await expect(page.getByText(/The director makes the plan after Make it/)).toBeVisible();
    await expect(page.getByRole("button", { name: /Make the plan|Approve the plan/ })).toHaveCount(0);
    await planAndApprove(page, id);
    await page.reload();
    await expect(page.getByRole("region", { name: "Scene 1" })).toBeVisible({
      timeout: 30_000,
    });
    await page.getByRole("tab", { name: /^Cast/ }).click();
    await expect(page.getByRole("tab", { name: /^Cast/, selected: true })).toBeVisible();
    await expect(page.getByText("Not in this video's shots")).toHaveCount(0);
    const sizes = await page.evaluate(() => ({
      scroll: document.documentElement.scrollWidth,
      window: document.documentElement.clientWidth,
    }));
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
    await expect(page.getByRole("tab", { name: /^Clips/ })).toBeEnabled();
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
  test(`at ${width}: the director takes a published script to a finished video, and the Cut tab downloads it`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    test.setTimeout(240_000);
    await signIn(page, "reed@example.com");
    approveCastWhenReady(page); // the Cast tab's Approve cast & places (#1324)
    await expect(page.getByRole("button", { name: /^Brand: / }).first()).toBeVisible();
    const brandId = await emptyBrand(page, `Video Flow Co ${width}`);
    // v6 screen 4: the director makes the stills, the prompts and the takes; the panel shows them as it goes.
    const s = await (await page.request.post("/api/scripts", { data: { brand_id: brandId, title: `Flow ${width} ${Date.now()}`, description: "", notes: "", reference_replace: "", text: SCRIPT } })).json();
    expect((await page.request.post(`/api/scripts/${s.id}/drafts/0/approve`)).ok()).toBe(true);
    expect((await page.request.post(`/api/scripts/${s.id}/publish`)).ok()).toBe(true);
    const id = (await (await page.request.post(`/api/scripts/${s.id}/drafts/0/produce`)).json()).project_id;

    await page.goto(`/b/${brandId}/videos/${id}`);
    await page.getByRole("button", { name: /^Make it/ }).click();
    await makeIt(page, id); // its treatment, then its start card (S3-02): no generation before this press
    const live = page.getByRole("region", { name: /^Making|^Writing|^Drawing|^Revising|^Made in/ }).first();
    await expect(live).toBeVisible({ timeout: 60_000 }); // the run's one card
    await expect(page.getByRole("banner").getByText(/^Delivered$/)).toBeVisible({ timeout: 200_000 });
    await expect(page.getByRole("region", { name: "Delivery note" })).toBeVisible({ timeout: 30_000 });
    if (width === 390) await page.getByRole("tab", { name: "Preview" }).click();
    await page.getByRole("tab", { name: "Cut" }).click();
    await expect(page.getByRole("tabpanel", { name: "Cut" }).getByRole("link", { name: "Download MP4" })).toBeVisible({ timeout: 60_000 });
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
  test(`at ${width}: the brand's videos list an idea, search it, and nothing scrolls sideways`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await signIn(page, "reed@example.com");
    approveCastWhenReady(page); // the Cast tab's Approve cast & places (#1324)
    await expect(page.getByRole("button", { name: /^Brand: / }).first()).toBeVisible();
    const brandId = await emptyBrand(page, `Videos View Co ${width}`);
    const made = await page.request.post("/api/projects", { data: { brand_id: brandId, name: "Listed video", planned_seconds: 20 } });
    expect(made.ok()).toBeTruthy();

    await page.goto(`/b/${brandId}/scripts`);
    if (width === 1440) await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: /Unsorted/ }).click(); // the rail's folders (S0-01)
    else await page.getByRole("navigation", { name: "Tabs" }).getByRole("link", { name: "Videos" }).click();
    await expect(page).toHaveURL(new RegExp(`/b/${brandId}/videos$`));
    if (width !== 1440) await page.getByRole("link", { name: /Unsorted/ }).click(); // a phone opens on its folders (P-01)
    await expect(page.getByRole("main").getByRole("link", { name: /Listed video/ })).toBeVisible(); // Unsorted opens when no folder is picked (S-gaps-02)
    await expect(page.getByText(width === 1440 ? "1 video idea · 1 needs you" : "1 idea · 1 needs you", { exact: false })).toBeVisible();
    if (width !== 1440) await page.getByRole("button", { name: "Search this folder" }).click();
    await page.getByRole("searchbox", { name: "Search this folder" }).fill("nothing like this");
    await expect(page.getByText("Nothing matches. Try another tab or search.")).toBeVisible();
    await page.getByRole("searchbox", { name: "Search this folder" }).fill("");
    await expect(page.getByRole("main").getByRole("link", { name: /Listed video/ })).toBeVisible();
    const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
  });
}
