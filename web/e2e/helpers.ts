import { expect, type Page } from "@playwright/test";

export const PASSWORD = "correct horse battery";

export async function fill(page: Page, values: Record<string, string>) {
  for (const [label, value] of Object.entries(values)) await page.getByLabel(label).and(page.locator("input, textarea")).fill(value); // not the password eye, whose label also says password
}

/**
 * The owner auth.e2e.ts creates in the UI (same studio, name and password), made through the
 * API when a spec runs without it first. Once set up, the server answers 409 and nothing changes.
 */
async function ensureOwner(page: Page) {
  const made = await page.request.post("/api/auth/setup", {
    data: { setup_token: "e2e-setup-code", workspace_name: "Studio", email: "reed@example.com", name: "Reed", password: PASSWORD },
  });
  if (made.status() === 201) await page.request.post("/api/auth/logout"); // setup signs in; the test signs in itself
  else if (made.status() !== 409) throw new Error(`Setup for the e2e owner failed: ${made.status()}`);
}

export async function signIn(page: Page, email: string, password = PASSWORD) {
  await ensureOwner(page);
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
  await expect(page.getByRole("menuitem", { name: "Sign out" })).toBeVisible();
  await page.keyboard.press("Escape");
}

const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "base64",
);

/** A tiny valid PNG, in the shape setInputFiles wants. */
export const image = (name: string) => ({ name, mimeType: "image/png", buffer: PNG });

/**
 * A brand that starts empty (fomo and Iron Paws come with their real screens). Made through the
 * API as the signed-in person; asking again for the same name returns the one already made.
 */
export async function emptyBrand(page: Page, name = "Night Owl"): Promise<number> {
  const made = await page.request.post("/api/brands", { data: { name } });
  if (made.ok()) return (await made.json()).id;
  const brands = await (await page.request.get("/api/brands")).json();
  return brands.find((b: { name: string }) => b.name === name).id;
}

/** A brand's home is its Scripts library; the brand name shows in the switcher button in the top bar. */
export async function onBrand(page: Page, name: string) {
  await expect(page.getByRole("heading", { name: "Scripts", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: `Brand: ${name}` })).toBeVisible();
}

/** The brand switcher is a menu: open it, pick the brand. */
export async function switchBrand(page: Page, name: string) {
  await page.getByRole("button", { name: /^Brand: / }).click();
  await page.getByRole("menuitemradio", { name }).click();
}
