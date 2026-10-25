import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

test("a script is pasted, edited into a new version, and an old version is restored", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brandId = await emptyBrand(page, "Script Shop");
  const made = await page.request.post("/api/projects", { data: { brand_id: brandId, name: "Script test", planned_seconds: 20 } });
  expect(made.ok()).toBeTruthy();
  await page.goto(`/b/${brandId}/projects/${(await made.json()).id}?stage=script`);

  await page.getByRole("button", { name: "Paste it in" }).click();
  await page.getByLabel("Your script").fill("SCENE 1 - KITCHEN\nMAX: Hello there.");
  await page.getByRole("button", { name: "Save script" }).click();
  const lines = page.getByRole("list", { name: "Script text" });
  await expect(lines).toContainText("MAX: Hello there.");
  await expect(page.getByText(/words · pasted/)).toContainText("Saved");

  await page.getByRole("button", { name: "Edit", exact: true }).click();
  await page.getByLabel("Your script").fill("SCENE 1 - KITCHEN\nMAX: Goodbye.");
  await page.getByRole("button", { name: "Save script" }).click();
  await expect(lines).toContainText("Goodbye.");

  await page.getByRole("button", { name: "Versions" }).click();
  await page.getByRole("menuitemradio").last().click(); // newest first, so the last is the first version
  await expect(page.getByRole("button", { name: "Back to the latest" })).toBeVisible();
  await expect(lines).toContainText("Hello there.");
  await page.getByRole("button", { name: "Restore this version" }).click();
  await expect(page.getByText("Restored an earlier version.")).toBeVisible();
  await expect(lines).toContainText("Hello there.");
  await expect(page.getByText(/words · .*Saved/)).toBeVisible();
  // Restoring adds a version; it doesn't overwrite. Three saves so far: first, second, and the restore.
  await page.getByRole("button", { name: "Versions" }).click();
  await expect(page.getByRole("menuitemradio")).toHaveCount(3);
});

test("a script document can be uploaded", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brandId = await emptyBrand(page, "Script Shop");
  const made = await page.request.post("/api/projects", { data: { brand_id: brandId, name: "Upload test", planned_seconds: 20 } });
  await page.goto(`/b/${brandId}/projects/${(await made.json()).id}?tab=script`);
  await page.getByLabel("Script file").setInputFiles({ name: "script.txt", mimeType: "text/plain", buffer: Buffer.from("MAX: From a file.") });
  await expect(page.getByRole("list", { name: "Script text" })).toContainText("MAX: From a file.");
  await expect(page.getByText(/words · uploaded/)).toContainText("Saved");
});
