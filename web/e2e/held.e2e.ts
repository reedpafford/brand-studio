import { expect, test } from "@playwright/test";
import { onBrand, signIn } from "./helpers";

// Hold requests (Reed, 30 Oct; #1068): an editor's Quick clip past the week waits for the owner, never runs, and can be
// withdrawn. The week is set to 1 credit for the test and put back after; nothing is generated (a held clip never runs).
test("at 390, an editor's Quick clip past the week waits for approval with why, and Withdraw takes it back for nothing", async ({ page, browser, baseURL }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  const limits = await (await page.request.get("/api/credits/limits")).json();
  await page.request.put("/api/credits/limits", { data: { ...limits, weekly_quick_clip_credits: 1 } });
  try {
    // Its own editor, so the test stands alone.
    const inv = await (await page.request.post("/api/team/invites", { data: { email: `held-${Date.now()}@example.com` } })).json();
    const ed = await (await browser.newContext({ baseURL, viewport: { width: 390, height: 900 } })).newPage();
    expect((await ed.request.post("/api/auth/accept-invite", { data: { token: inv.token, name: "Hana", password: "correct horse battery staple" } })).ok()).toBe(true);
    await ed.goto("/");
    await expect(ed.getByRole("button", { name: "Account menu" })).toBeVisible();
    const brands = (await (await ed.request.get("/api/brands")).json()) as { id: number; name: string }[];
    const fomo = brands.find((b) => b.name === "fomo")!.id;
    const models = (await (await ed.request.get("/api/models")).json()) as { id: string; kind: string; default?: boolean }[];
    const model = (models.find((m) => m.kind === "video" && m.default) ?? models.find((m) => m.kind === "video"))!.id;
    const made = await ed.request.post("/api/clips", { data: { brand_id: fomo, model_id: model, prompt: "The cat buys the dip, smiling.", aspect_ratio: "9:16", duration: 5, resolution: "480p", generate_audio: false, character_ids: [] } });
    expect(made.status()).toBe(201);
    expect((await made.json()).status).toBe("needs_owner_approval");

    await ed.goto(`/b/${fomo}/clip`);
    await expect(ed.getByText("Waiting for approval")).toBeVisible();
    await expect(ed.getByText(/Waiting for the owner's OK: this goes past your week's 1/)).toBeVisible();
    await expect(ed.getByText(/ask (Reed|the owner)/i)).toHaveCount(0);
    await ed.getByRole("button", { name: "Withdraw" }).click();
    await expect(ed.getByText("Withdrawn. Nothing was charged.")).toBeVisible();
    await expect(ed.getByText("Waiting for approval")).toHaveCount(0);
    const sizes = await ed.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
  } finally {
    await page.request.put("/api/credits/limits", { data: limits });
  }
});
