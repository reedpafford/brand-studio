import { expect, test } from "@playwright/test";
import { expectSignedInAs, fill, PASSWORD } from "./helpers";

// Runs in order against one fresh database: the first owner is created in the second test.
test.describe.configure({ mode: "serial" });

const setupForm = (code: string) => ({
  "Setup code (from your server settings)": code,
  "Studio name": "Studio",
  "Your name": "Reed",
  Email: "reed@example.com",
  "Password (10 or more characters)": PASSWORD,
});

test("signed-out visitors are sent to sign in", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});

test("first-run setup needs the right code, then creates the owner and signs in", async ({ page }) => {
  await page.goto("/setup");
  await fill(page, setupForm("wrong-code"));
  await page.getByRole("button", { name: "Create owner account" }).click();
  await expect(page.getByRole("alert")).toHaveText("Setup is not allowed.");

  await page.getByLabel("Setup code (from your server settings)").fill("e2e-setup-code");
  await page.getByRole("button", { name: "Create owner account" }).click();
  await expectSignedInAs(page, "Reed");
});

test("setup cannot be run a second time", async ({ page }) => {
  await page.goto("/setup");
  await fill(page, setupForm("e2e-setup-code"));
  await page.getByRole("button", { name: "Create owner account" }).click();
  await expect(page.getByRole("alert")).toHaveText("Already set up.");
});

test("sign-in rejects a wrong password, accepts the right one", async ({ page }) => {
  await page.goto("/login");
  await fill(page, { Email: "reed@example.com", Password: "not the password" });
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert")).toHaveText("Wrong email or password.");

  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expectSignedInAs(page, "Reed");
});
