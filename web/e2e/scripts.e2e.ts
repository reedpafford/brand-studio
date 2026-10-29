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

  await page.getByRole("button", { name: "New script" }).first().click();
  await page.getByRole("menuitem", { name: /Dialogue/ }).click();
  await page.getByRole("button", { name: "Rename Untitled script" }).click();
  await page.getByRole("textbox", { name: "Title" }).fill("Bo tries salmon");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: /Bo tries salmon/ })).toBeVisible();
  // The title is the Rename button: at least 44 px tall on a phone.
  await page.setViewportSize({ width: 390, height: 900 });
  await expect.poll(async () => (await page.getByRole("button", { name: "Rename Bo tries salmon" }).boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
  await page.setViewportSize({ width: 1280, height: 720 });

  await expect(page.getByRole("heading", { name: "Script", exact: true, level: 2 })).toBeVisible();
  await expect(page.getByText("Draft · only you can see it")).toBeVisible();
  await page.getByLabel("Paste or write your script").fill("BO: Salmon? Again?\nMIA: Try it.");
  await page.getByRole("button", { name: "Save script" }).click();
  await expect(page.getByText("Saved.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Next: Directions" })).toBeEnabled();

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
  // The step opens on the scene plan (S6), which is optional: go straight to the shots.
  await page.getByRole("tab", { name: "Shots" }).click();
  await page.getByRole("button", { name: /^Make the breakdown/ }).click();
  await expect(page.getByText(/^Planned · \d+ s/)).toBeVisible({ timeout: 60_000 });
  // Resizing the open page re-lays it out for the new width a moment later (the layout follows a media query), so wait for it to settle; measuring at once can catch the old layout squeezed into the new width.
  for (const width of [390, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth), { message: `no sideways scroll at ${width}`, timeout: 10_000 }).toBeLessThanOrEqual(0);
  }
  // Remove the plan, then Undo brings the same plan back.
  await page.getByRole("button", { name: "More for this plan" }).click();
  await page.getByRole("menuitem", { name: "Remove the plan" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Remove" }).click();
  await expect(page.getByRole("button", { name: /^Make the breakdown/ })).toBeVisible();
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByText(/^Planned · \d+ s/)).toBeVisible();
  await page.getByRole("button", { name: "Next: Publish" }).click();
  await page.getByRole("button", { name: "Publish 2 versions" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Publish", exact: true }).click();
  await expect(page.getByText("Published. 2 versions are ready to make.")).toBeVisible();
  await expect(page.getByText("A · Ready to make")).toBeVisible();

  // Published is final, but Reed may still tidy its About (title, what it's for, notes), at 390 too.
  await page.setViewportSize({ width: 390, height: 900 });
  const library = new URL(page.url());
  const href = await page.getByRole("link", { name: "Bo tries salmon", exact: true }).getAttribute("href");
  await page.goto(href!.replace("step=publish", "step=script"));
  await page.getByText("About this script").click();
  await expect(page.getByText("Reference reel (optional)")).toHaveCount(0);
  await page.getByLabel("Notes (optional)").fill("Warm light, slow pour.");
  const save = page.getByRole("button", { name: "Save", exact: true });
  expect((await save.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await save.click();
  await expect(page.getByText("Saved.")).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
  await page.goto(library.pathname + library.search);

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
  await expect(page.getByText(/Includes finding the roles\./)).toBeVisible();
  await page.getByRole("button", { name: /^Have Claude write it for me · \d+ credits?$/ }).click();
  await expect(page.getByLabel("Paste or write your script")).not.toHaveValue("", { timeout: 60_000 });
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
