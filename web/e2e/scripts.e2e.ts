import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

// The Script library with the real API and the stand-in providers: nothing paid is pressed.
test("a script is made in the library: describe it, write its words, and it is listed as Writing", async ({ page }) => {
  test.setTimeout(90_000); // the variation is written by the worker
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  await page.goto(`/b/${await emptyBrand(page, "Script Library Co")}`);
  await expect(page.getByRole("heading", { name: "Scripts", exact: true })).toBeVisible();
  await expect(page.getByText("No scripts for Script Library Co yet.")).toBeVisible();

  await page.getByRole("link", { name: "New script" }).first().click();
  await page.getByLabel("Title").fill("Bo tries salmon");
  await page.getByLabel("What it's for").fill("Show a picky dog finally loving the salmon.");
  await page.getByRole("button", { name: "Create script" }).click();

  await expect(page.getByRole("heading", { name: "Script", exact: true, level: 2 })).toBeVisible();
  await expect(page.getByText("Draft · only you can see it")).toBeVisible();
  await page.getByRole("button", { name: "Paste or write it yourself" }).click();
  await page.getByLabel("Your script").fill("BO: Salmon? Again?\nMIA: Try it.");
  await page.getByRole("button", { name: "Save script" }).click();
  await expect(page.getByRole("list", { name: "Script text" })).toContainText("MIA: Try it.");

  // Back in the library it is listed as Writing.
  await page.getByRole("link", { name: "Scripts", exact: true }).first().click();
  await expect(page.getByRole("link", { name: "Bo tries salmon", exact: true })).toBeVisible();
  await expect(page.getByText("A · Writing")).toBeVisible();

  // Write one variation (stand-in provider, no cost), read it next to the original, approve it.
  await page.getByRole("link", { name: "Bo tries salmon", exact: true }).click();
  await page.getByRole("list", { name: "Steps" }).getByRole("button", { name: "Variations" }).click();
  await page.getByRole("radio", { name: "1", exact: true }).click();
  await page.getByRole("button", { name: /^Write 1 variation/ }).click();
  const b = page.getByLabel("Version B", { exact: true });
  await expect(b).toBeVisible({ timeout: 60_000 });
  await b.getByRole("button", { name: "Approve" }).click();
  await expect(b.getByText("Approved · words final")).toBeVisible();

  // The write already found the roles (Bo and Mia); add one more by hand, step over the optional steps, publish: it becomes Ready to make.
  await page.getByRole("list", { name: "Steps" }).getByRole("button", { name: "Cast" }).click();
  await expect(page.getByText("2 roles · 0 locked")).toBeVisible();
  await page.getByRole("button", { name: "Add a role" }).first().click();
  await page.getByRole("textbox", { name: "Role" }).fill("Zed");
  await page.getByRole("button", { name: "Add role" }).click();
  await expect(page.getByText("3 roles · 0 locked")).toBeVisible();
  // Plan version A's shots first (stand-in provider, no cost), then publish.
  await page.getByRole("button", { name: "Next: Breakdown" }).click();
  await page.getByRole("button", { name: /^Make the breakdown/ }).click();
  await expect(page.getByText(/^Planned · \d+ s/)).toBeVisible({ timeout: 60_000 });
  for (const width of [390, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
  }
  await page.getByRole("button", { name: "Next: Publish" }).click();
  await page.getByRole("button", { name: "Publish 2 versions" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Publish", exact: true }).click();
  await expect(page.getByText("Published. 2 versions are ready to make.")).toBeVisible();
  await expect(page.getByText("A · Ready to make")).toBeVisible();

  // A ready version opens its panel; Make this version reserves it and opens the video at Breakdown.
  await page.getByRole("link", { name: "Version A, ready to make" }).click();
  const panel = page.getByRole("dialog", { name: "Bo tries salmon · Version A" });
  await expect(panel).toContainText("Salmon? Again?");
  await panel.getByRole("button", { name: "Make this version" }).click();
  await expect(page).toHaveURL(/\/videos\/\d+/);
});

test("Reed deletes a script from its row, and Undo brings it back", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brandId = await emptyBrand(page, "Removal Co");
  const made = await page.request.post("/api/scripts", { data: { brand_id: brandId, title: "Throwaway", description: "A script to delete.", notes: "", reference_replace: "", text: "" } });
  expect(made.ok()).toBeTruthy();
  await page.goto(`/b/${brandId}/scripts?status=any`);
  await page.getByRole("button", { name: "More for Throwaway" }).click();
  await page.getByRole("menuitem", { name: "Delete script" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Delete", exact: true }).click();
  await expect(page.getByText('Deleted "Throwaway".')).toBeVisible();
  await expect(page.getByRole("heading", { name: "Throwaway" })).toBeHidden();
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(page.getByText('Restored "Throwaway".')).toBeVisible();
  await expect(page.getByRole("heading", { name: "Throwaway" })).toBeVisible();
});

test("an empty script with a reel is written from the reference, at the price shown", async ({ page }) => {
  test.setTimeout(90_000);
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brandId = await emptyBrand(page, "Write Ref Co");
  const made = await page.request.post("/api/scripts", { data: { brand_id: brandId, title: "Altar again", description: "Remake the altar reel for this brand.", notes: "", reference_replace: "", reference_id: "fomo-DehudnaAmce", text: "" } });
  expect(made.ok()).toBeTruthy();
  await page.goto(`/b/${brandId}/scripts/${(await made.json()).id}?step=script`);
  await expect(page.getByRole("heading", { name: "Write from the reference" })).toBeVisible();
  await expect(page.getByText("Includes finding the roles.")).toBeVisible();
  await page.getByRole("button", { name: /^Write from the reference · \d+ credits?$/ }).click();
  await expect(page.getByRole("list", { name: "Script text" })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("heading", { name: "Write from the reference" })).toBeHidden();
  // The write also found the roles, so the Cast step already has them.
  await page.getByRole("list", { name: "Steps" }).getByRole("button", { name: "Cast" }).click();
  await expect(page.getByText(/^\d+ roles? · 0 locked$/)).toBeVisible();
});

test("a deleted script is found under Deleted and archived, and Restore puts it back", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brandId = await emptyBrand(page, "Removal Co");
  const made = await page.request.post("/api/scripts", { data: { brand_id: brandId, title: "Gone for now", description: "Deleted, then found.", notes: "", reference_replace: "", text: "" } });
  expect(made.ok()).toBeTruthy();
  expect((await page.request.delete(`/api/scripts/${(await made.json()).id}`)).ok()).toBeTruthy();
  await page.goto(`/b/${brandId}/scripts?removed=1`);
  await expect(page.getByRole("heading", { name: "Gone for now" })).toBeVisible();
  await expect(page.getByText(/^Deleted · /)).toBeVisible();
  await page.getByRole("button", { name: "Restore Gone for now" }).click();
  await expect(page.getByText('Restored "Gone for now".')).toBeVisible();
  await page.getByRole("button", { name: "Deleted and archived" }).click();
  await expect(page.getByRole("heading", { name: "Gone for now" })).toBeVisible();
});

test("Directions: Claude suggests lines for a written script, one is accepted and added, and the words stay", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  const brandId = await emptyBrand(page, "Removal Co");
  const words = "MIA: Hell no!\nBO: Salmon? Again?";
  const made = await page.request.post("/api/scripts", { data: { brand_id: brandId, title: "Needs directions", description: "Directions test.", notes: "", reference_replace: "", text: words } });
  expect(made.ok()).toBeTruthy();
  await page.goto(`/b/${brandId}/scripts/${(await made.json()).id}?step=directions`);
  await page.getByRole("button", { name: /^Suggest directions/ }).click();
  const add = page.getByRole("button", { name: /^Add \d+ directions?$/ });
  await expect(add.or(page.getByText("This script already reads well. Nothing to suggest."))).toBeVisible({ timeout: 90_000 });
  if (await add.isVisible()) {
    await page.getByRole("button", { name: /^Accept: / }).first().click();
    await expect(page.getByRole("button", { name: "Add 1 direction" })).toBeEnabled();
    await page.getByRole("button", { name: "Add 1 direction" }).click();
    await expect(page.getByText("Added 1 direction.")).toBeVisible();
  }
  await expect(page.getByRole("list", { name: "Script text" })).toContainText("MIA: Hell no!");
  await expect(page.getByRole("list", { name: "Script text" })).toContainText("BO: Salmon? Again?");
});
