import { expect, test } from "@playwright/test";
import { PASSWORD, expectSignedInAs, fill, onBrand, openAccountMenu, signIn, switchBrand } from "./helpers";

// Runs after auth.e2e.ts, which created the owner (Reed). Ed is invited in the first team test and removed in the last.
test.describe.configure({ mode: "serial" });

test("the brand switcher changes brand and is remembered", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");

  await switchBrand(page, "Iron Paws");
  await onBrand(page, "Iron Paws");
  await expect(page).toHaveURL(/\/b\/\d+\/projects$/);

  await page.goto("/");
  await onBrand(page, "Iron Paws");
});

test("signing out ends the session", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await expectSignedInAs(page, "Reed");
  await openAccountMenu(page);
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/team");
  await expect(page).toHaveURL(/\/login$/);
});

test("the owner invites someone with a link, and they join", async ({ browser, page }) => {
  await signIn(page, "reed@example.com");
  await page.getByRole("link", { name: "Team" }).click();
  await page.getByLabel("Email to invite").fill("ed@example.com");
  await page.getByRole("button", { name: "Create invite link" }).click();
  const link = await page.getByLabel("Invite link").inputValue();
  expect(link).toMatch(/\/invite\/.+/);
  await expect(page.getByText("ed@example.com · editor · waiting")).toBeVisible();

  const guest = await browser.newContext();
  const guestPage = await guest.newPage();
  await guestPage.goto(link);
  await fill(guestPage, { "Your name": "Ed", "Choose a password (10 or more characters)": PASSWORD });
  await guestPage.getByRole("button", { name: "Create my account" }).click();
  await expectSignedInAs(guestPage, "Ed");
  await guest.close();

  await page.reload();
  await expect(page.getByText("ed@example.com · editor", { exact: true })).toBeVisible();
  await expect(page.getByText("ed@example.com · editor · waiting")).toHaveCount(0);
});

test("an editor sees the team but not the owner's controls", async ({ page }) => {
  await signIn(page, "ed@example.com");
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  // Team is Reed's: an editor has no link to it, but the page still opens and is read-only.
  await expect(page.getByRole("link", { name: "Team" })).toHaveCount(0);
  await page.goto("/team");
  await expect(page.getByRole("heading", { name: "Team" })).toBeVisible();
  await expect(page.getByText("reed@example.com")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Invite someone" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^Remove / })).toHaveCount(0);
});

test("the owner removes a member, who can no longer sign in", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await page.getByRole("link", { name: "Team" }).click();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Remove Ed" }).click();
  await expect(page.getByRole("button", { name: "Remove Ed" })).toHaveCount(0);

  await openAccountMenu(page);
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await signIn(page, "ed@example.com");
  await expect(page.getByRole("alert")).toHaveText("Wrong email or password.");
});
