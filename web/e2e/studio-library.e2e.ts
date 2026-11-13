import { expect, test } from "@playwright/test";
import { emptyBrand, onBrand, signIn } from "./helpers";

// The Library in the new look (/s/b/N/library), on the real server and the free stand-ins (nothing is sent to a
// provider). A person is added and their sheet drawn, they are opened and renamed; a product is saved and its "How it
// works" written, and the server holds exactly what was typed. The page sends those requests and nothing else.
test("at 1440, a person is drawn by the stand-in, opened and renamed, and a product's How it works is saved as typed", async ({ page }, info) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page, "reed@example.com");
  await expect(page.getByRole("button", { name: /^Brand: / }).first()).toBeVisible();
  const brandId = await emptyBrand(page, `Studio library ${info.retry}-${info.repeatEachIndex}`); // a fresh one each attempt
  const writes: string[] = [];
  page.on("request", (r) => r.method() !== "GET" && new URL(r.url()).pathname.startsWith("/api/") && writes.push(`${r.method()} ${new URL(r.url()).pathname.replace(/\d+/g, "N")}`));

  await page.goto(`/s/b/${brandId}/library?tab=cast`);
  await expect(page.getByText(/^Nobody saved in Studio library/)).toBeVisible();
  await page.getByRole("button", { name: "New person" }).click();
  const box = page.getByRole("dialog", { name: "New person" });
  await box.getByLabel("Name").fill("Mia");
  await box.getByLabel("Who they are, in a line").fill("A mom in her forties, tired, warm");
  await box.getByRole("button", { name: /^Draw their sheet · up to \$\d+\.\d\d$/ }).click();
  const panel = page.getByRole("region", { name: "Mia", exact: true });
  await expect(panel.getByRole("status")).toHaveText("Needs your OK", { timeout: 60_000 }); // the stand-in drew it
  await expect(panel.getByRole("img", { name: "Mia’s sheet" })).toBeVisible();
  await expect(panel.getByText("A mom in her forties, tired, warm")).toBeVisible();

  await panel.getByRole("button", { name: "Rename or describe…" }).click();
  const edit = page.getByRole("dialog", { name: "Rename or describe Mia" });
  await edit.getByLabel("Name").fill("Mia Torres");
  await edit.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("region", { name: "Mia Torres" }).getByRole("heading", { name: "Mia Torres" })).toBeVisible();
  await expect(page.getByRole("group", { name: "Saved people" }).getByRole("button", { name: "Mia Torres" })).toBeVisible();

  await page.getByRole("group", { name: "Kind" }).getByRole("button", { name: "Product" }).click();
  await page.getByRole("button", { name: "New product" }).click();
  const product = page.getByRole("dialog", { name: "New product" });
  await product.getByLabel("Name").fill("Protector alarm");
  await product.getByRole("button", { name: "Save product" }).click();
  const how = page.getByRole("region", { name: "How it works" });
  await how.getByRole("button", { name: "Write it" }).click();
  const typed = "  One hand holds the body.\n\nThe other pulls the ring straight out.  \n";
  await how.getByRole("textbox", { name: "How it works" }).fill(typed);
  await how.getByRole("button", { name: "Save" }).click();
  await expect(how.getByRole("button", { name: "Edit" })).toBeVisible();
  const saved = (await (await page.request.get(`/api/library/prop?brand_id=${brandId}`)).json()) as { notes: string }[];
  expect(saved[0].notes).toBe(typed); // every space and line, as typed
  await page.reload();
  await how.getByRole("button", { name: "Edit" }).click();
  await expect(how.getByRole("textbox", { name: "How it works" })).toHaveValue(typed);
  expect(writes).toEqual(["POST /api/library/character", "POST /api/library/character/N/sheet", "PATCH /api/library/character/N", "POST /api/library/prop", "PATCH /api/library/prop/N"]);
});

test("at 390, each tab of the Library fits a phone, only reads, and nothing scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  const brand = new URL(page.url()).pathname; // /b/N
  const writes: string[] = [];
  page.on("request", (r) => r.method() !== "GET" && new URL(r.url()).pathname.startsWith("/api/") && writes.push(`${r.method()} ${r.url()}`));
  await page.goto(`/s${brand}/library`);
  for (const tab of ["Product", "Cast", "Footage", "Voices"]) {
    await page.getByRole("group", { name: "Kind" }).getByRole("button", { name: tab }).click();
    await expect(page.getByText("Loading…")).toHaveCount(0);
    await expect(page.getByRole("alert")).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
  }
  await expect(page.getByRole("heading", { name: /^The app’s voices/ })).toBeVisible();
  expect(writes).toEqual([]);
});
