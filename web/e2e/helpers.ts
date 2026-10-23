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

/** The top bar shows who is signed in, next to the Sign out button. */
export async function expectSignedInAs(page: Page, name: string) {
  await expect(page.getByRole("banner").getByText(name, { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
}
