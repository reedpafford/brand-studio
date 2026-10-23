import { expect, test, type Page } from "@playwright/test";
import { emptyBrand, image, signIn } from "./helpers";

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
  await expect(page.getByRole("heading", { name: "Night Owl" })).toBeVisible();
});

test("brand kit text is saved and still there after a reload", async ({ page }) => {
  await page.getByRole("link", { name: "Kit" }).click();
  await expect(page.getByRole("button", { name: "Save changes" })).toBeDisabled();
  await page.getByLabel("Tone of voice").fill("Calm, confident, never hype.");
  await page.getByLabel("Never say (one per line)").fill("guaranteed returns\nget rich quick");
  await saveKit(page);

  await page.reload();
  await expect(page.getByLabel("Tone of voice")).toHaveValue("Calm, confident, never hype.");
  await expect(page.getByLabel("Never say (one per line)")).toHaveValue("guaranteed returns\nget rich quick");
});

test("an uploaded logo shows and survives a reload", async ({ page }) => {
  await page.getByRole("link", { name: "Kit" }).click();
  await page.getByLabel("Logo file").setInputFiles(image("logo.png"));
  await expect(page.getByRole("img", { name: "Logo" })).toBeVisible();
  await saveKit(page);

  await page.reload();
  await expect(page.getByRole("img", { name: "Logo" })).toBeVisible();
});

test("a brand screen can be added with tags and a moment", async ({ page }) => {
  await page.getByRole("link", { name: "Screens" }).click();
  await expect(page.getByText("No brand screens yet.")).toBeVisible();
  await page.getByRole("button", { name: "Add screen" }).click();
  await page.getByLabel("Screen image").setInputFiles(image("buy-flow.png"));
  await expect(page.getByLabel("Name")).toHaveValue("buy-flow");
  await page.getByLabel("What it shows (tags, separated by commas)").fill("Trading, Mobile");
  await page.getByLabel("Use automatically for these moments (separated by commas)").fill("trading");
  await page.getByRole("button", { name: "Save screen" }).click();

  await expect(page.getByRole("img", { name: "buy-flow" })).toBeVisible();
  await expect(page.getByText("★ Always used for: trading")).toBeVisible();
  await expect(page.getByText("mobile · trading")).toBeVisible();
});

test("a brand screen can be deleted", async ({ page }) => {
  await page.getByRole("link", { name: "Screens" }).click();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Delete buy-flow" }).click();
  await expect(page.getByText("No brand screens yet.")).toBeVisible();
});
