import { expect, type Page } from "@playwright/test";

export const PASSWORD = "correct horse battery";

export async function fill(page: Page, values: Record<string, string>) {
  for (const [label, value] of Object.entries(values)) await page.getByLabel(label).fill(value);
}

export async function signIn(page: Page, email: string, password = PASSWORD) {
  await page.goto("/login");
  await fill(page, { Email: email, Password: password });
  await page.getByRole("button", { name: "Sign in" }).click();
}

/** Opens the account menu (the round button in the top bar). */
export async function openAccountMenu(page: Page) {
  await page.getByRole("button", { name: "Account menu" }).click();
}

/** The account menu shows who is signed in, with Sign out. */
export async function expectSignedInAs(page: Page, name: string) {
  await openAccountMenu(page);
  await expect(page.getByRole("banner").getByText(name, { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  await page.keyboard.press("Escape");
}

const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "base64",
);

/** A tiny valid PNG, in the shape setInputFiles wants. */
export const image = (name: string) => ({ name, mimeType: "image/png", buffer: PNG });
