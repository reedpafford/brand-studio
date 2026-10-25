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

  await page.getByRole("link", { name: "Scripts", exact: true }).first().click();
  await expect(page.getByRole("heading", { name: "Bo tries salmon" })).toBeVisible();
  await expect(page.getByText("A · Writing")).toBeVisible();
});
