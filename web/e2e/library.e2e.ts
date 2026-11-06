import { expect, test, type Page } from "@playwright/test";
import { image, onBrand, signIn, switchBrand } from "./helpers";

// v6 S8 (the brand library) on the stand-ins. Runs after brand.e2e.ts, in order, on the fomo brand: Max and Rex are made
// in the first tests.
test.describe.configure({ mode: "serial" });

test.beforeEach(async ({ page }) => {
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  await page.getByRole("link", { name: "Cast & places" }).click();
  await expect(page.getByRole("navigation", { name: "Library" })).toBeVisible();
});

// A retry (or a --repeat-each round) runs the serial group again from here: what an earlier attempt made goes first, so fomo starts empty again.
async function forget(page: Page, names: string[]) {
  const brands = (await (await page.request.get("/api/brands")).json()) as { id: number; name: string }[];
  const fomo = brands.find((b) => b.name === "fomo")!.id;
  for (const archived of [false, true]) {
    const items = (await (await page.request.get(`/api/library/character?brand_id=${fomo}&archived=${archived}`)).json()) as { id: number; name: string }[];
    for (const { id } of items.filter((i) => names.includes(i.name))) {
      if (!archived) await page.request.delete(`/api/library/character/${id}`);
      await page.request.delete(`/api/library/character/${id}/permanent`);
    }
  }
  await page.reload();
}

test("an empty brand's Make one draws a new character's sheet, its page opens, and a person approves it (S8-02, S8-07, L5)", async ({ page }, info) => {
  if (info.retry || info.repeatEachIndex) await forget(page, ["Max", "Rex"]);
  await expect(page.getByRole("heading", { name: "No characters in fomo yet" })).toBeVisible();
  await page.getByRole("button", { name: /^Make one · up to \$/ }).click();
  const form = page.getByRole("form", { name: "New character" });
  await form.getByPlaceholder("Name").fill("Max");
  await form.getByLabel("Description").fill("Man, 40s, gym coach, grey hoodie");
  await form.getByRole("button", { name: /^Make it · up to \$/ }).click();
  await expect(page.getByRole("heading", { name: "Max", level: 1 })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Needs your OK")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("In use")).toBeVisible();
});

test("a character from a photo, and search narrows the list by name (S8-01)", async ({ page }) => {
  await page.getByRole("button", { name: "New character" }).click();
  const form = page.getByRole("form", { name: "New character" });
  await form.getByPlaceholder("Name").fill("Rex");
  await form.getByText("Upload a photo").locator("input").setInputFiles(image("rex.png"));
  await form.getByRole("button", { name: /^Make it/ }).click();
  await expect(page.getByRole("heading", { name: "Rex", level: 1 })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("link", { name: "Back to characters" }).click();
  await expect(page.getByRole("link", { name: "Rex" })).toBeVisible();
  await page.getByLabel("Search the library").fill("ma");
  await expect(page.getByRole("link", { name: "Max" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Rex" })).toHaveCount(0);
});

test("a character is not in another brand's library", async ({ page }) => {
  await switchBrand(page, "Iron Paws");
  await expect(page.getByRole("heading", { name: "No characters in Iron Paws yet" })).toBeVisible();
});

test("More: a change to the words is saved, and the old version can be restored", async ({ page }) => {
  await page.getByRole("link", { name: "Max" }).click();
  await page.getByRole("button", { name: "More" }).click();
  await page.getByRole("textbox", { name: "Description" }).fill("Tough but fair.");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("status")).toContainText("Saved.");
  await expect(page.getByText("Tough but fair.").first()).toBeVisible();
  // The saved version opens the page afresh (its More folded) once it is read back: open More whenever it's folded, so the
  // check never depends on whether that happened before or after this press (it closed it again on CI).
  const more = page.getByRole("button", { name: "More" });
  await expect(async () => {
    if ((await more.getAttribute("aria-expanded")) !== "true") await more.click();
    await expect(page.getByRole("button", { name: /^Restore v\d+$/ }).first()).toBeVisible({ timeout: 1_000 });
  }).toPass({ timeout: 15_000 });
});

test("archiving says so with Undo; Show archived lists it with Unarchive (S8-08)", async ({ page }) => {
  await page.getByRole("link", { name: "Max" }).click();
  await page.getByRole("button", { name: "Archive" }).click();
  await expect(page.getByRole("status")).toContainText("Max archived.");
  await expect(page.getByRole("link", { name: "Max" })).toHaveCount(0);
  await page.getByLabel("Show archived").check();
  await expect(page.getByText(/^Archived \d+ \w+ · kept for old videos$/)).toBeVisible();
  await page.getByRole("button", { name: "Unarchive Max" }).click();
  await page.getByLabel("Show archived").uncheck();
  await expect(page.getByRole("link", { name: "Max" })).toBeVisible();
});

test("the owner deletes a character for good from its history", async ({ page }) => {
  await page.getByRole("link", { name: "Rex" }).click();
  await page.getByRole("button", { name: "More" }).click();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Delete forever" }).click();
  await expect(page.getByRole("link", { name: "Max" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Rex" })).toHaveCount(0);
});

test("Products: fomo's app holds its real screens; Iron Paws' bag holds its photos (S8-06, L1)", async ({ page }) => {
  await page.getByRole("navigation", { name: "Library" }).getByRole("link", { name: /^Products/ }).click();
  const app = page.getByRole("listitem").filter({ has: page.getByRole("link", { name: "fomo app" }) });
  await expect(app.getByText("App", { exact: true })).toBeVisible();
  await expect(app.getByText(/^5 screens · shown as given/)).toBeVisible();
  await switchBrand(page, "Iron Paws");
  await page.getByRole("navigation", { name: "Library" }).getByRole("link", { name: /^Products/ }).click();
  const bag = page.getByRole("listitem").filter({ has: page.getByRole("link", { name: "bag", exact: true }) });
  await expect(bag.getByText("Physical", { exact: true })).toBeVisible();
});
