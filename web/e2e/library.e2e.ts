import { expect, test } from "@playwright/test";
import { image, onBrand, signIn } from "./helpers";

const MP3 = { name: "voice.mp3", mimeType: "audio/mpeg", buffer: Buffer.from("ID3" + "0".repeat(32)) };

// Runs after brand.e2e.ts, in order, on the fomo brand. Characters Max and Rex are made in the first tests.
test.describe.configure({ mode: "serial" });

test.beforeEach(async ({ page }) => {
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  await page.getByRole("link", { name: "Library" }).click();
  await expect(page.getByRole("heading", { name: "Library" })).toBeVisible();
});

async function newCharacter(page: import("@playwright/test").Page, name: string, withImage = false) {
  await page.getByRole("button", { name: "New character" }).click();
  await page.getByLabel("Name").fill(name);
  if (withImage) await page.getByLabel("Image (optional)").setInputFiles(image(`${name}.png`));
  await page.getByRole("button", { name: "Create character" }).click();
  await expect(page.getByText(name, { exact: true })).toBeVisible();
}

test("a new character shows up in this brand's library with its image", async ({ page }) => {
  await expect(page.getByText("No characters for this brand yet.")).toBeVisible();
  await newCharacter(page, "Max", true);
  await expect(page.getByRole("img", { name: "Max" })).toBeVisible();
  await expect(page.getByText("v1")).toBeVisible();
});

test("search narrows the list by name", async ({ page }) => {
  await newCharacter(page, "Rex");
  await page.getByLabel("Search").fill("ma");
  await expect(page.getByText("Max", { exact: true })).toBeVisible();
  await expect(page.getByText("Rex", { exact: true })).toHaveCount(0);
});

test("a character is not in another brand's library", async ({ page }) => {
  await page.getByLabel("Brand").selectOption({ label: "Iron Paws" });
  await expect(page.getByText("No characters for this brand yet.")).toBeVisible();
});

test("editing keeps history, and an old version can be restored", async ({ page }) => {
  await page.getByRole("link", { name: "Max" }).click();
  await page.getByLabel("Notes").fill("Tough but fair.");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("button", { name: "Restore v1" })).toBeVisible();

  await page.getByRole("button", { name: "Restore v1" }).click();
  await expect(page.getByLabel("Notes")).toHaveValue("");
  await expect(page.getByRole("button", { name: "Restore v2" })).toBeVisible();
});

test("a character always keeps at least one brand", async ({ page }) => {
  await page.getByRole("link", { name: "Max" }).click();
  await page.getByLabel("fomo").uncheck();
  await expect(page.getByText("Pick at least one brand.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Save" })).toBeDisabled();
});

test("outfits and a voice sample are saved on a character", async ({ page }) => {
  await page.getByRole("link", { name: "Max" }).click();
  await page.getByRole("button", { name: "Add outfit" }).click();
  await page.getByLabel("Outfit 1 name").fill("Gym kit");
  await page.getByLabel("Add picture to outfit 1").setInputFiles(image("gym.png"));
  await expect(page.getByRole("img", { name: "Gym kit" })).toBeVisible();
  await page.getByLabel("Voice file").setInputFiles(MP3);
  await expect(page.getByLabel("Voice sample")).toBeVisible();
  await page.getByRole("button", { name: "Save" }).click();

  await page.reload();
  await expect(page.getByLabel("Outfit 1 name")).toHaveValue("Gym kit");
  await expect(page.getByRole("img", { name: "Gym kit" })).toBeVisible();
  await expect(page.getByLabel("Voice sample")).toBeVisible();
});

test("archiving hides a character, and unarchiving brings it back", async ({ page }) => {
  await page.getByRole("link", { name: "Max" }).click();
  await page.getByRole("button", { name: "Archive character" }).click();
  await expect(page.getByText("Max", { exact: true })).toHaveCount(0);

  await page.getByLabel("Show archived").check();
  await page.getByRole("button", { name: "Unarchive Max" }).click();
  await page.getByLabel("Show archived").uncheck();
  await expect(page.getByText("Max", { exact: true })).toBeVisible();
});

test("archiving shows a message with Undo that puts the character back", async ({ page }) => {
  await page.getByRole("link", { name: "Max" }).click();
  await page.getByRole("button", { name: "Archive character" }).click();
  await expect(page.getByRole("status")).toContainText("Max archived.");
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByText("Max", { exact: true })).toBeVisible();
});

test("the owner can delete an archived character for good", async ({ page }) => {
  // Rex has no image, so the card's link is named "No image" (reported to the builder).
  await page.getByRole("listitem").filter({ hasText: "Rex" }).getByRole("link").click();
  await page.getByRole("button", { name: "Archive character" }).click();

  await page.getByLabel("Show archived").check();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Delete Rex forever" }).click();
  await expect(page.getByText("Nothing archived.")).toBeVisible();
});
