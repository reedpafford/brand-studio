import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

// The brand's videos in the new look (/s/b/N/videos), on the real server (free: nothing here reaches a provider). A
// folder is made, a video is filed in it (dragged onto the rail at a desk; from its menu on a phone), renamed, archived
// and brought back. Each press is one request, the page sends nothing else, and nothing scrolls sideways.
for (const [width, height] of [[1440, 900], [390, 844]]) {
  test(`at ${width}, Videos in the new look: make a folder, move a video into it, rename it, archive it and undo`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await signIn(page, "reed@example.com");
    await expect(page.getByRole("button", { name: /^Brand: / }).first()).toBeVisible();
    const brandId = await emptyBrand(page, `Studio videos ${width}`);
    await page.request.post("/api/projects", { data: { brand_id: brandId, name: "A video to file", planned_seconds: 20 } });
    const writes: string[] = [];
    page.on("request", (r) => r.method() !== "GET" && new URL(r.url()).pathname.startsWith("/api/") && writes.push(`${r.method()} ${new URL(r.url()).pathname} ${r.postData() ?? ""}`.trim().replace(/\d+/g, "N")));

    await page.goto(`/s/b/${brandId}/videos`);
    const desk = width > 900;
    const main = page.getByRole("main");
    const folders = desk ? page.getByRole("navigation", { name: "Main" }) : main.getByRole("navigation", { name: "Folders" });
    const card = main.getByRole("link", { name: /A video to file/ });
    await expect(card).toBeVisible();

    await folders.getByRole("button", { name: "New folder" }).click();
    await folders.getByRole("textbox", { name: "New folder name" }).fill("Winter");
    await page.keyboard.press("Enter");
    const winter = folders.getByRole("link", { name: /Winter/ });
    await expect(winter).toBeVisible();

    if (desk) await card.dragTo(winter);
    else {
      await main.getByRole("button", { name: "More for A video to file" }).click();
      await page.getByRole("menuitemradio", { name: "Winter" }).click();
    }
    await expect(page.getByText(/^Moved .A video to file/)).toBeVisible();
    await winter.click();
    await expect(main.getByRole("heading", { level: 1, name: "Winter" })).toBeVisible();
    await expect(card).toBeVisible(); // it is in the folder now

    await main.getByRole("button", { name: "More for A video to file" }).click();
    await page.getByRole("menuitem", { name: "Rename…" }).click();
    await page.getByRole("dialog", { name: "Rename this video" }).getByRole("textbox", { name: "Name" }).fill("A video, filed");
    await page.keyboard.press("Enter");
    const renamed = main.getByRole("link", { name: /A video, filed/ });
    await expect(renamed).toBeVisible();

    await main.getByRole("button", { name: "More for A video, filed" }).click();
    await page.getByRole("menuitem", { name: "Archive" }).click();
    await page.getByRole("dialog", { name: "Archive “A video, filed”?" }).getByRole("button", { name: "Archive" }).click();
    await expect(main.getByText("Nothing in Winter yet")).toBeVisible();
    await page.getByRole("button", { name: "Undo" }).click();
    await expect(renamed).toBeVisible();

    expect(writes).toEqual(['POST /api/brands/N/folders {"name":"Winter","parent_id":null}', 'POST /api/folders/file {"kind":"video","ids":[N],"folder_id":N}', 'PATCH /api/projects/N {"name":"A video, filed"}', "POST /api/projects/N/archive", "POST /api/projects/N/restore"]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
  });
}
