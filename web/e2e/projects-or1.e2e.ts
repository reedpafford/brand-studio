import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

for (const width of [1440, 390]) {
  test(`at ${width}: make a project, file a video into it and back, filter by it, delete it with Undo (flows OR1)`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await signIn(page, "reed@example.com");
    await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
    const brandId = await emptyBrand(page, "Projects Co"); // one brand for both widths: the brand menu has no room to spare (see the menu height fix)
    const run = `${width}${test.info().retry ? `-${test.info().retry}` : ""}`; // a CI retry shares the database: new names, so no "already exists"
    const video = `Filed video ${run}`;
    const id = (await (await page.request.post("/api/projects", { data: { brand_id: brandId, name: video, planned_seconds: 20 } })).json()).id;
    const name = `November launch ${run}`;

    await page.goto(`/b/${brandId}/videos`);
    const list = width === 1440 ? page.getByRole("region", { name: "Projects" }) : page.getByRole("dialog", { name: "Projects" });
    if (width === 390) await page.getByRole("button", { name: "Project: All" }).click();
    await list.getByRole("button", { name: "New project" }).click();
    await page.getByRole("alertdialog", { name: "New project" }).getByLabel("Name").fill(name);
    await page.getByRole("alertdialog", { name: "New project" }).getByRole("button", { name: "Make the project" }).click();
    await expect(list.getByRole("button", { name: `${name} · 0 items` })).toBeVisible();
    if (width === 390) await page.keyboard.press("Escape");

    await page.goto(`/b/${brandId}/videos/${id}`);
    await page.getByRole("button", { name: "Project: none" }).click();
    await page.getByRole("menuitemradio", { name }).click();
    await expect(page.getByText(`Moved to ${name}.`)).toBeVisible();
    await expect(page.getByRole("button", { name: `Project: ${name}` })).toBeVisible();

    await page.goto(`/b/${brandId}/videos`);
    if (width === 390) await page.getByRole("button", { name: "Project: All" }).click();
    await list.getByRole("button", { name: `${name} · 1 item` }).click();
    await expect(page).toHaveURL(/folder=\d+/);
    await expect(page.getByRole("link", { name: new RegExp(video) })).toBeVisible();

    if (width === 390) await page.getByRole("button", { name: `Project: ${name}` }).click();
    await list.getByRole("button", { name: `More for ${name}` }).click();
    await page.getByRole("menuitem", { name: "Delete" }).click();
    const ask = page.getByRole("alertdialog", { name: `Delete ${name}?` });
    await expect(ask).toContainText("Its 1 item move to No project. Nothing inside is deleted.");
    await ask.getByRole("button", { name: "Delete" }).click();
    await page.getByRole("button", { name: "Undo" }).click();
    await expect(list.getByRole("button", { name: `${name} · 1 item` })).toBeVisible();
    const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
  });
}
