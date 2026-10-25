import { expect, test, type Page } from "@playwright/test";
import { emptyBrand, image, onBrand, signIn } from "./helpers";

// Runs after auth.e2e.ts; Reed (owner) exists. These use a brand made for them, which starts
// empty (fomo and Iron Paws come with their real screens: see fomo.e2e.ts). Tests run in order.
test.describe.configure({ mode: "serial" });

async function saveKit(page: Page) {
  const saved = page.waitForResponse((r) => r.request().method() === "PATCH" && r.url().includes("/api/brands/"));
  await page.getByRole("button", { name: "Save changes" }).click();
  expect((await saved).ok()).toBe(true);
  await expect(page.getByText("Saved.")).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  await page.goto(`/b/${await emptyBrand(page)}`);
  await onBrand(page, "Night Owl");
});

test("brand kit text is saved and still there after a reload", async ({ page }) => {
  await page.getByRole("link", { name: "Brand", exact: true }).click();
  await expect(page.getByRole("button", { name: "Save changes" })).toBeDisabled();
  await page.getByLabel("How we sound").fill("Calm, confident, never hype.");
  for (const phrase of ["guaranteed returns", "get rich quick"]) {
    await page.getByLabel("Add to never say").fill(phrase);
    await page.getByLabel("Add to never say").press("Enter");
  }
  await saveKit(page);

  await page.reload();
  await expect(page.getByLabel("How we sound")).toHaveValue("Calm, confident, never hype.");
  await expect(page.getByRole("button", { name: "Remove guaranteed returns" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Remove get rich quick" })).toBeVisible();
});

test("an uploaded logo shows and survives a reload", async ({ page }) => {
  await page.getByRole("link", { name: "Brand", exact: true }).click();
  await page.getByLabel("Logo file").setInputFiles(image("logo.png"));
  await expect(page.getByRole("img", { name: "Logo" })).toBeVisible();
  await saveKit(page);

  await page.reload();
  await expect(page.getByRole("img", { name: "Logo" })).toBeVisible();
});

test("a brand screen can be added, given tags and a moment, and deleted", async ({ page }) => {
  await page.getByRole("link", { name: "Brand", exact: true }).click();
  await page.getByRole("tab", { name: /^App screens/ }).click();
  await expect(page.getByText("No brand screens yet.")).toBeVisible();
  await page.getByRole("button", { name: "Add screens" }).first().click();
  await page.getByLabel("Screen images").setInputFiles(image("buy-flow.png"));
  await expect(page.getByLabel("Name for buy-flow.png")).toHaveValue("buy-flow");
  await page.getByRole("button", { name: "Add screen", exact: true }).click();

  const tile = page.getByRole("button", { name: "buy-flow", exact: true });
  await expect(tile).toBeVisible();
  await tile.click();
  const panel = page.getByRole("dialog", { name: "Edit buy-flow" });
  await panel.getByLabel("Add to tags").fill("Trading");
  await panel.getByLabel("Add to tags").press("Enter");
  await panel.getByLabel("Add to always use this screen for").fill("trading");
  await panel.getByLabel("Add to always use this screen for").press("Enter");
  await panel.getByRole("button", { name: "Save screen" }).click();
  await expect(panel).toBeHidden();
  await expect(tile.getByText("trading")).toBeVisible(); // the moment badge on its tile

  await tile.click();
  await page.getByRole("dialog", { name: "Edit buy-flow" }).getByRole("button", { name: "Delete screen" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Delete screen" }).click();
  await expect(page.getByText("No brand screens yet.")).toBeVisible();
});
