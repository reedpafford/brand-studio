import { expect, test } from "@playwright/test";
import { image, signIn } from "./helpers";

// Spend, Settings and a brand's set-up in the new look (the redesign, stage 6), on the real server: a brand is made
// with its product from one press and lands on its empty New video page; "How it works" is stored and read back exactly
// as typed; Spend says an empty brand has spent nothing; archiving asks first and Undo brings the brand back. Every
// request that isn't a read is listed and compared, and nothing scrolls sideways at a desk or on a phone. Nothing here
// generates anything. The brand's name sorts after "fomo", so no other test's first brand changes.
const HOW = "  You flip the lid open with one thumb.\n\nThe needle  settles in two seconds.\n";

for (const [width, height] of [[1440, 900], [390, 844]]) {
  test(`at ${width}, a brand is made and set up, Spend and Settings read the server, and only the presses send anything`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await signIn(page, "reed@example.com");
    await expect(page.getByRole("button", { name: /^Brand: / }).first()).toBeVisible();
    const name = `Stage six ${width}`;
    const writes: string[] = [];
    page.on("request", (r) => r.method() !== "GET" && new URL(r.url()).pathname.startsWith("/api/") && writes.push(`${r.method()} ${new URL(r.url()).pathname}`));
    const fits = async () => expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
    const product = async (brandId: number) => (await (await page.request.get(`/api/library/prop?brand_id=${brandId}`)).json())[0];

    await page.goto("/s/settings");
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Set up fomo" })).toBeVisible();
    await expect(page.getByRole("switch").first()).toBeVisible(); // the looks, from the server
    await fits();

    await page.getByRole("link", { name: "New brand" }).click();
    await page.getByRole("textbox", { name: "Brand name" }).fill(name);
    await page.getByRole("button", { name: "Teal" }).click();
    await page.getByRole("textbox", { name: "Product name" }).fill("Trail compass");
    await page.getByLabel("Add photos of the product").setInputFiles(image("compass.png"));
    await page.getByRole("textbox", { name: "How it works" }).fill(HOW);
    await page.getByRole("textbox", { name: "Tone and rules" }).fill("Dry and practical.");
    await fits();
    expect(writes).toEqual([]); // nothing is sent before the press
    await page.getByRole("button", { name: "Create brand" }).click();
    await expect(page).toHaveURL(/\/s\/b\/\d+$/);
    await expect(page.getByRole("heading", { name: "New video" })).toBeVisible();
    const id = Number(new URL(page.url()).pathname.split("/").pop());
    expect(await (await page.request.get(`/api/brands/${id}`)).json()).toMatchObject({ name, colours: ["#1F9FB5"], tone_notes: "Dry and practical." });
    const made = await product(id);
    expect(made).toMatchObject({ name: "Trail compass", notes: HOW, product_type: "physical" });
    expect(made.pictures).toHaveLength(1);

    await page.goto(`/s/b/${id}/setup`);
    const how = page.getByRole("textbox", { name: "How it works" });
    await expect(how).toHaveValue(HOW); // as stored: not trimmed, split or rewritten
    await how.fill(`${HOW}It glows  green at night. `);
    await page.getByRole("button", { name: "Save how it works" }).click();
    await expect(page.getByText("Saved.")).toBeVisible();
    expect((await product(id)).notes).toBe(`${HOW}It glows  green at night. `);
    await fits();

    await page.goto(`/s/b/${id}/spend?brand=${id}&period=all`);
    await expect(page.getByText(`Nothing spent on ${name} yet`)).toBeVisible();
    await page.getByRole("button", { name: "Clear" }).click();
    await expect(page.getByText(/^(Spent on all brands, this month|Nothing spent this month)$/)).toBeVisible();
    await page.getByRole("button", { name: "Update now" }).click();
    await fits();

    await page.goto("/s/settings");
    await page.getByRole("button", { name: `Archive ${name}` }).click();
    await page.getByRole("dialog", { name: `Archive ${name}?` }).getByRole("button", { name: "Archive" }).click();
    await expect(page.getByText(`Archived ${name}.`)).toBeVisible();
    await expect(page.getByRole("button", { name: `Bring back ${name}` })).toBeVisible();
    await page.getByRole("button", { name: "Undo" }).click();
    await expect(page.getByText(`Brought back ${name}.`)).toBeVisible();
    await expect(page.getByRole("link", { name: `Set up ${name}` })).toBeVisible();
    expect(writes).toEqual(["POST /api/brands", "POST /api/library/prop", "POST /api/files", `POST /api/brands/${id}/screens`, `PATCH /api/library/prop/${made.id}`, `DELETE /api/brands/${id}`, `POST /api/brands/${id}/restore`]);
  });
}
