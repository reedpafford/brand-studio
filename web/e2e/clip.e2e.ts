import { expect, test } from "@playwright/test";
import { emptyBrand, image, signIn } from "./helpers";

// Runs after brand.e2e.ts and library.e2e.ts. These cover the controls only: no test presses
// Generate (paid generation is switched off on the test server). The screen with a
// "buy-moment" is added to a fresh brand through the API.
test.describe.configure({ mode: "serial" });

test.beforeEach(async ({ page }) => {
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("banner")).toBeVisible();
  await page.getByRole("link", { name: "Quick clip" }).click();
  await expect(page.getByRole("heading", { name: /^Quick clip/ })).toBeVisible();
});

test("Generate stays off, and says why, until the prompt is written; then it shows the server's price", async ({ page }) => {
  const generate = page.getByRole("button", { name: /^Generate/ });
  await expect(generate).toBeDisabled();
  await expect(page.getByText("Describe the clip (8+ characters)")).toBeVisible();
  await page.getByLabel("Prompt").fill("The cat buys the dip.");
  await expect(page.getByRole("button", { name: "Generate · 8 credits" })).toBeEnabled();
  // Never pressed: this server has paid generation switched off, and no test starts a clip.
});

test("the credits on the button follow the quality chosen", async ({ page }) => {
  await expect(page.getByRole("button", { name: "Generate · 8 credits" })).toBeVisible();
  await page.getByRole("button", { name: "720p", exact: true }).click();
  await expect(page.getByRole("button", { name: "Generate · 18 credits" })).toBeVisible();
});

test("a screen whose moment the prompt mentions is added, and stays out once removed", async ({ page }) => {
  const brandId = await emptyBrand(page);
  const upload = await page.request.post("/api/files", { multipart: { upload: image("buy.png") } });
  const file = await upload.json();
  await page.request.post(`/api/brands/${brandId}/screens`, {
    data: { name: "Buy button", file_id: file.id, tags: ["trading"], default_for: ["buy-moment"] },
  });
  await page.goto(`/b/${brandId}/clip`);

  await page.getByLabel("Prompt").fill("She taps the buy moment and smiles.");
  await expect(page.getByText("Buy button was added because your prompt mentions buy-moment.")).toBeVisible();

  await page.getByRole("button", { name: "Remove Buy button" }).click();
  await expect(page.getByRole("button", { name: "Remove Buy button" })).toHaveCount(0);
  await page.getByLabel("Prompt").fill("She taps the buy moment again and again.");
  await expect(page.getByRole("button", { name: "Remove Buy button" })).toHaveCount(0);
});
