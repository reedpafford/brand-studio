import { expect, test } from "@playwright/test";
import { emptyBrand, onBrand, signIn } from "./helpers";

// One video in the new look (/s/b/N/videos/ID), on the real server: what only a real browser can measure. It fits the
// window at a desk and on a phone, the divider drags within its limits and is remembered, and opening it sends nothing
// but reads.
for (const [width, height] of [[1440, 900], [390, 844]]) {
  test(`at ${width}, a video opens in the new look, only reads, and nothing scrolls sideways; a desk's divider drags and is remembered`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await signIn(page, "reed@example.com");
    await expect(page.getByRole("button", { name: /^Brand: / }).first()).toBeVisible();
    const brandId = await emptyBrand(page, `Studio video ${width}`);
    const id = (await (await page.request.post("/api/projects", { data: { brand_id: brandId, name: "A video to read", planned_seconds: 20 } })).json()).id;
    const writes: string[] = [];
    page.on("request", (r) => r.method() !== "GET" && new URL(r.url()).pathname.startsWith("/api/") && writes.push(`${r.method()} ${r.url()}`));

    await page.goto(`/s/b/${brandId}/videos/${id}`);
    await expect(page.getByRole("heading", { name: "A video to read" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Tell the director what to change" })).toBeVisible();
    const film = page.getByRole("region", { name: "The video" });
    for (const view of ["Cut", "Cast", "Plan"]) await film.getByRole("button", { name: view }).click();
    await expect(film.getByText("The plan shows here first")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);

    const bar = page.getByRole("separator", { name: "Resize the chat and the film" });
    if (width > 900) {
      const chat = page.getByRole("region", { name: "The director" });
      const at = (await bar.boundingBox())!;
      const before = (await chat.boundingBox())!.width;
      await page.mouse.move(at.x + 4, at.y + 200);
      await page.mouse.down();
      await page.mouse.move(at.x + 4 - 150, at.y + 200, { steps: 5 });
      await page.mouse.up();
      expect(Math.abs((await chat.boundingBox())!.width - (before - 150))).toBeLessThanOrEqual(5); // it follows the pointer
      await page.mouse.move(at.x - 150 + 4, at.y + 200);
      await page.mouse.down();
      await page.mouse.move(0, at.y + 200, { steps: 5 }); // as far left as it goes: the chat keeps its least width
      await page.mouse.up();
      expect((await chat.boundingBox())!.width).toBe(320);
      await page.reload();
      await expect(page.getByRole("heading", { name: "A video to read" })).toBeVisible();
      expect((await chat.boundingBox())!.width).toBe(320);
      await bar.dblclick();
      expect((await chat.boundingBox())!.width).toBeGreaterThan(320);
    } else await expect(bar).toBeHidden(); // a phone stacks the two
    expect(writes).toEqual([]);
  });
}

// Stage 3, on the stand-ins (free; nothing is sent to a provider): a short video made end to end from the new look.
// New video → the start card → Approve and film → clips arrive → delivered → a note → the round's card. Each press
// is one request, and the page sends nothing else.
test("at 1440, a short video is made from the new look: Approve and film, the clips arrive, it is delivered, and a note comes back as a round", async ({ page }) => {
  test.setTimeout(420_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  await page.goto(`/s${new URL(page.url()).pathname}`);
  await page.getByRole("textbox", { name: "Your script" }).fill(["SCENE 1 — INT. KITCHEN — DAY", `NATE: The dip is in. I'm buying ${Date.now()}.`, "NATE: Download fomo through the link in my bio."].join("\n"));
  await page.getByRole("button", { name: /^Make it (about|up to) \$\d+\.\d\d$/ }).click({ timeout: 30_000 });
  await expect(page).toHaveURL(/\/s\/b\/\d+\/videos\/\d+$/, { timeout: 30_000 });
  const writes: string[] = [];
  page.on("request", (r) => r.method() !== "GET" && new URL(r.url()).pathname.startsWith("/api/") && writes.push(`${r.method()} ${new URL(r.url()).pathname.replace(/\d+/g, "N")} ${r.postData() ?? ""}`.trim()));

  const chat = page.getByRole("region", { name: "The director" });
  const film = page.getByRole("region", { name: "The video" });
  const header = page.locator("header.vhead");
  const start = chat.getByRole("region", { name: "The plan and the cast" });
  await expect(start.getByRole("list", { name: "What it will make" }).getByRole("listitem").first()).toBeVisible({ timeout: 90_000 }); // the plan, each clip with its price
  await expect(header.getByRole("button", { name: /^Approve and film (about|up to) \$\d+\.\d\d$/ })).toBeVisible(); // the header's same press
  await start.getByRole("button", { name: /^Approve and film/ }).click();
  await expect(header.getByRole("button", { name: "Stop" })).toBeVisible({ timeout: 30_000 }); // it is being made
  await expect(film.getByLabel(/^(Clip 1|The cut)$/)).toBeVisible({ timeout: 240_000 }); // a clip arrived: its take plays, then the cut
  await expect(header.getByText("Delivered", { exact: true })).toBeVisible({ timeout: 240_000 });
  await expect(film.getByLabel("The cut", { exact: true })).toBeVisible();
  await expect(header.getByRole("link", { name: "Download" })).toBeVisible();
  await expect(chat.getByRole("heading", { name: "What I made" })).toBeVisible();

  await chat.getByRole("textbox", { name: "Tell the director what to change" }).fill("Redo clip 1 with a punchier ending.");
  await chat.getByRole("textbox", { name: "Tell the director what to change" }).press("Enter");
  const round = chat.getByRole("region", { name: "Round 2" });
  await expect(round.getByRole("heading", { name: /^Round 2: \d+ clips? changes?$/ })).toBeVisible({ timeout: 120_000 });
  await expect(round.getByRole("list", { name: "What it will make" }).getByRole("listitem").first()).toContainText("$");
  await expect(round.getByRole("button", { name: /^Make round 2 (about|up to) \$\d+\.\d\d$/ })).toBeVisible();
  expect(writes).toEqual(['POST /api/asks/N/answer {"how":"make_it"}', 'POST /api/projects/N/director/messages {"text":"Redo clip 1 with a punchier ending."}']);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
});
