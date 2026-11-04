import { expect, test, type Page } from "@playwright/test";
import { emptyBrand, image, onBrand, signIn } from "./helpers";

// v6 S8-05 as redrawn in S-gaps-05 L1: the Brand kit is the name, logo, colours, and tone and rules. Runs after
// auth.e2e.ts on a brand made for it (fomo and Iron Paws come with their real files: see fomo.e2e.ts).
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
  await page.getByRole("link", { name: "Brand", exact: true }).click();
  await expect(page.getByRole("link", { name: "Brand kit" })).toHaveAttribute("aria-current", "page");
});

test("tone and rules and a colour are saved and still there after a reload", async ({ page }) => {
  await expect(page.getByRole("button", { name: "Save changes" })).toBeDisabled();
  await page.getByLabel("Tone and rules").fill("Calm, confident, never hype.");
  await page.getByRole("button", { name: "Add colour" }).click();
  await saveKit(page);
  await page.reload();
  await expect(page.getByLabel("Tone and rules")).toHaveValue("Calm, confident, never hype.");
  await expect(page.getByRole("button", { name: /^Colour 2: #/ })).toBeVisible();
});

test("an uploaded logo shows and survives a reload", async ({ page }) => {
  await page.getByLabel("Logo file").setInputFiles(image("logo.png"));
  await expect(page.getByRole("img", { name: "Night Owl logo" })).toBeVisible();
  await saveKit(page);
  await page.reload();
  await expect(page.getByRole("img", { name: "Night Owl logo" })).toBeVisible();
});

test("leaving with unsaved changes asks first", async ({ page }) => {
  await page.getByLabel("Tone and rules").fill("Something new");
  await page.getByRole("navigation", { name: "Library" }).getByRole("link", { name: /^Characters/ }).click();
  const dialog = page.getByRole("alertdialog", { name: "Leave without saving?" });
  await dialog.getByRole("button", { name: "Keep editing" }).click();
  await expect(page.getByLabel("Tone and rules")).toHaveValue("Something new");
});
