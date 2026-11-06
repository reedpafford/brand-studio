import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

test("a video started the earlier way opens on its video page and is listed", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: /^Brand: / }).first()).toBeVisible();
  // The earlier way to start a video stays on Scripts, under "Videos made before scripts"; the old list is Videos now.
  const brandId = await emptyBrand(page);
  await page.goto(`/b/${brandId}/projects`);
  await expect(page).toHaveURL(new RegExp(`/b/${brandId}/videos$`));
  await page.goto(`/b/${brandId}/scripts`);
  await page.getByRole("link", { name: "New video (the earlier way)" }).click();
  await page.getByLabel("Title").fill("Launch teaser");
  await page.getByLabel("What's it for?").fill("Announce the new drop.");
  await page.getByRole("button", { name: "1:1" }).click();
  await page.getByLabel("Planned length (seconds)").fill("20");
  await page.getByRole("button", { name: "Create project" }).click();

  await expect(page).toHaveURL(new RegExp(`/b/${brandId}/videos/\\d+$`)); // the video page (v6 S3); the old step page is gone
  await expect(page.getByRole("heading", { name: "Launch teaser" })).toBeVisible();
  await expect(page.getByText(/^Length\s*about 20 s$/)).toBeVisible();

  await page.getByRole("navigation", { name: "Where it is" }).getByRole("link").first().click(); // the brand's videos
  await expect(page).toHaveURL(new RegExp(`/b/${brandId}/videos$`));
  const card = page.getByRole("main").getByRole("link", { name: /Launch teaser/ }); // an idea card in Unsorted (v6 S1)
  await expect(card).toHaveAttribute("href", /\/projects\/\d+$/); // an earlier-way video opens its own page
});
