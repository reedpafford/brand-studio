import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

// The Script library with the real API and the stand-in providers: nothing paid is pressed.
test("a script is made in the library: describe it, write its words, and it is listed as Writing", async ({ page }) => {
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
  await page.getByLabel("Your script").fill("BO: Salmon? Again?\nMIA: Try it.");
  await page.getByRole("button", { name: "Save script" }).click();
  await expect(page.getByRole("list", { name: "Script text" })).toContainText("MIA: Try it.");

  // Back in the library it is listed as Writing.
  await page.getByRole("link", { name: "Scripts", exact: true }).first().click();
  await expect(page.getByRole("link", { name: "Bo tries salmon", exact: true })).toBeVisible();
  await expect(page.getByText("A · Writing")).toBeVisible();

  // Add a role, step over the optional steps, publish: it becomes Ready to make.
  await page.getByRole("link", { name: "Bo tries salmon", exact: true }).click();
  await page.getByRole("list", { name: "Steps" }).getByRole("button", { name: "Cast" }).click();
  await page.getByRole("button", { name: "Add a role" }).first().click();
  await page.getByRole("textbox", { name: "Role" }).fill("Bo");
  await page.getByRole("button", { name: "Add role" }).click();
  await expect(page.getByText("1 role · 0 locked")).toBeVisible();
  await page.getByRole("button", { name: "Next: Publish" }).click();
  await page.getByRole("button", { name: "Publish 1 version" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Publish", exact: true }).click();
  await expect(page.getByText("Published. 1 version is ready to make.")).toBeVisible();
  await expect(page.getByText("A · Ready to make")).toBeVisible();

  // A ready version opens its panel; Make this version reserves it and opens the video at Breakdown.
  await page.getByRole("link", { name: "Version A, ready to make" }).click();
  const panel = page.getByRole("dialog", { name: "Bo tries salmon · Version A" });
  await expect(panel).toContainText("Salmon? Again?");
  await panel.getByRole("button", { name: "Make this version" }).click();
  await expect(page).toHaveURL(/\/projects\/\d+\?step=breakdown/);
});
