import { expect, test, type Page } from "@playwright/test";

// Runs in order against one fresh database: the first owner is created in the second test.
test.describe.configure({ mode: "serial" });

const PASSWORD = "correct horse battery";

async function fill(page: Page, values: Record<string, string>) {
  for (const [label, value] of Object.entries(values)) await page.getByLabel(label).fill(value);
}

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
  await expect(page).toHaveURL("/");
  await expect(page.getByText("Signed in as Reed.")).toBeVisible();
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

  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Signed in as Reed.")).toBeVisible();
});

test("an invited person joins from the link and is signed in", async ({ browser }) => {
  const owner = await browser.newContext();
  const ownerPage = await owner.newPage();
  await ownerPage.goto("/login");
  await fill(ownerPage, { Email: "reed@example.com", Password: PASSWORD });
  await ownerPage.getByRole("button", { name: "Sign in" }).click();
  await expect(ownerPage.getByText("Signed in as Reed.")).toBeVisible();
  // The team page doesn't exist yet; create the invite through the API as the owner.
  const invite = await ownerPage.request.post("/api/team/invites", { data: { email: "ed@example.com" } });
  const { token } = await invite.json();
  await owner.close();

  const guest = await browser.newContext();
  const page = await guest.newPage();
  await page.goto(`/invite/${token}`);
  await fill(page, { "Your name": "Ed", "Choose a password (10 or more characters)": PASSWORD });
  await page.getByRole("button", { name: "Create my account" }).click();
  await expect(page.getByText("Signed in as Ed.")).toBeVisible();
  await guest.close();
});
