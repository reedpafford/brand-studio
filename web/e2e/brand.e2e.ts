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

test("brand voice and a call to action are saved and still there after a reload (BR1)", async ({ page }) => {
  await page.getByRole("link", { name: "Brand", exact: true }).click();
  await expect(page.getByRole("button", { name: "Save changes" })).toBeDisabled();
  await page.getByLabel("How the brand talks").fill("Calm, confident, never hype.");
  for (const phrase of ["guaranteed returns", "get rich quick"]) {
    await page.getByLabel("Add to don't").fill(phrase);
    await page.getByLabel("Add to don't").press("Enter");
  }
  await saveKit(page);
  // A CTA line saves at once; the first is the Default.
  await page.getByLabel("Add a line").fill("Find us through the link in my bio.");
  await page.getByRole("button", { name: "Add line" }).click();
  await expect(page.getByLabel("Call to action lines").getByText("Default")).toBeVisible();

  await page.reload();
  await expect(page.getByLabel("How the brand talks")).toHaveValue("Calm, confident, never hype.");
  await expect(page.getByRole("button", { name: "Remove guaranteed returns" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Remove get rich quick" })).toBeVisible();
  await expect(page.getByLabel("Call to action lines").getByText("Find us through the link in my bio.")).toBeVisible();
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
  // The tag was saved too: it is there when the screen is opened again.
  await expect(page.getByRole("group", { name: "Tags" }).getByRole("button", { name: "Remove trading" })).toBeVisible();
  await page.getByRole("dialog", { name: "Edit buy-flow" }).getByRole("button", { name: "Delete screen" }).click();
  await expect(page.getByText('Deleted "buy-flow".')).toBeVisible(); // no dialog: the toast offers Undo
  await expect(page.getByText("No brand screens yet.")).toBeVisible();
  await page.getByRole("button", { name: "Show deleted (1)" }).click();
  await page.getByRole("button", { name: "Restore buy-flow" }).click();
  await expect(page.getByText('Restored "buy-flow".')).toBeVisible();
  await expect(tile).toBeVisible();
  // Delete it again for the tests that follow, and let the toast go.
  await tile.click();
  await page.getByRole("dialog", { name: "Edit buy-flow" }).getByRole("button", { name: "Delete screen" }).click();
  await expect(page.getByText("No brand screens yet.")).toBeVisible();
});
