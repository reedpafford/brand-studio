import { expect, type Page, test } from "@playwright/test";
import { onBrand, signIn } from "./helpers";

/** A fomo script of its own, published, with version A started (Make this version), so a test never depends on what
 *  another spec left behind. Returns its title. */
async function startVersion(page: Page, name: string): Promise<string> {
  const brands = (await (await page.request.get("/api/brands")).json()) as { id: number; name: string }[];
  const fomo = brands.find((b) => b.name === "fomo")!.id;
  const title = `${name} ${Date.now()}`;
  const s = await (await page.request.post("/api/scripts", { data: { brand_id: fomo, title, description: "", notes: "", reference_replace: "", text: "SCENE 1 — INT. KITCHEN — DAY\nNATE: The dip is in." } })).json();
  expect((await page.request.post(`/api/scripts/${s.id}/drafts/0/approve`)).ok()).toBe(true);
  expect((await page.request.post(`/api/scripts/${s.id}/publish`)).ok()).toBe(true);
  expect((await page.request.post(`/api/scripts/${s.id}/drafts/0/produce`)).ok()).toBe(true);
  return title;
}

// Runs after shell.e2e.ts; Reed is the owner. Nothing here costs anything.
test("Reed opens Usage: the totals, a row for every brand, and one brand's page", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Usage" }).click();
  await expect(page.getByRole("heading", { name: "Usage", exact: true, level: 1 })).toBeVisible();
  await expect(page.getByRole("group", { name: "Totals" })).toContainText("Cost per finished video");
  const fomo = page.getByRole("link", { name: /^fomo: \$[\d,.]+ spent, \d+ finished$/ });
  await expect(fomo).toBeVisible();
  await page.getByRole("radio", { name: "All time" }).click();
  await expect(page).toHaveURL(/period=all/);
  await fomo.click();
  await expect(page.getByRole("heading", { name: "fomo", level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: "Usage", exact: true }).first()).toBeVisible();
  await expect(page.getByRole("tab", { name: /^Videos/ })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: /^Scripts/ }).click();
  await expect(page).toHaveURL(/tab=scripts/);
});

test("Reed opens In production from the rail and sees the version being made, with no sideways scroll on a phone", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  const title = await startVersion(page, "Being made");
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: /^In production/ }).click();
  await expect(page.getByRole("heading", { name: "In production", level: 1 })).toBeVisible();
  const row = page.getByRole("link", { name: new RegExp(`^${title}, version A, .*, at [A-Z][a-z]+`) });
  await expect(row).toBeVisible();
  await row.click();
  await expect(page).toHaveURL(/\/projects\/\d+/);
  await page.setViewportSize({ width: 390, height: 800 });
  await page.goto("/production");
  await expect(page.getByRole("link", { name: new RegExp(`^${title}, version A, `) })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("Reed changes the editors' weekly allowance in Settings, and Undo puts it back", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Settings" }).click();
  await page.getByRole("tab", { name: "Limits" }).click();
  const weekly = page.getByLabel("Each editor's own week");
  const before = await weekly.inputValue();
  await weekly.fill(String(Number(before) + 5));
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("Limits saved.")).toBeVisible();
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await page.reload();
  await expect(page.getByLabel("Each editor's own week")).toHaveValue(before);
});

test("Reed releases a version he started by mistake, and it leaves In production", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  const title = await startVersion(page, "Started by mistake");
  await page.goto("/production");
  const row = page.getByRole("link", { name: new RegExp(`^${title}, version A, `) });
  await expect(row).toBeVisible();
  await row.click();
  await expect(page).toHaveURL(/\/projects\/\d+/);
  // The video page's own menu, by its exact name: In production's row menu ("More for <title> · A") can still be on screen
  // while the navigation finishes, and opening that one instead was the intermittent timeout.
  await page.getByRole("button", { name: `More for ${title}`, exact: true }).click();
  await page.getByRole("menuitem", { name: "Release this version" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Release", exact: true }).click();
  await expect(page.getByText("The version is ready to make again.")).toBeVisible();
  await expect(page).toHaveURL(/\/scripts$/);
  await page.goto("/production");
  await expect(page.getByRole("link", { name: new RegExp(`^${title}, version A, `) })).toBeHidden();
});

test("Reed adds a brand from the brand menu on its own page and lands on its Look page", async ({ page }) => {
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  await page.getByRole("button", { name: /^Brand: / }).click();
  await page.getByRole("menuitem", { name: "New brand" }).click();
  const form = page.getByRole("form", { name: "New brand" });
  await form.getByLabel("Name", { exact: true }).fill("Zephyr Studio");
  await form.getByRole("button", { name: "Make the brand" }).click();
  await expect(page.getByText("Zephyr Studio is ready. Add its look next.")).toBeVisible();
  await expect(page).toHaveURL(/\/b\/\d+\/brand$/);
  await expect(page.getByRole("button", { name: "Brand: Zephyr Studio" })).toBeVisible();
});
