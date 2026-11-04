import { expect, test, type Page } from "@playwright/test";
import { onBrand, signIn } from "./helpers";

// The director-first video (v6 New video, S2): New video → the director plans, casts, makes and cuts it, on the free
// stand-ins. The owner's Make it runs at once and says the most in dollars; an editor's send from a script past its
// video's budget waits for the owner's OK in Needs you.
const noSidewaysScroll = async (page: Page) => {
  const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
  expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
};

test("at 1440, the owner pastes a script, presses Make it, and the director delivers the cut in the video's chat", async ({ page }) => {
  test.setTimeout(300_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  await page.keyboard.press("n"); // N opens New video
  await expect(page.getByRole("heading", { name: "What should the director make?" })).toBeVisible();
  const script = ["SCENE 1 — INT. KITCHEN — DAY", `NATE: The dip is in. I'm buying ${Date.now()}.`, "NATE: Download fomo through the link in my bio."].join("\n");
  await page.getByLabel("Paste a script, or describe the video").fill(script);
  await page.getByRole("button", { name: /^Make it · up to \$\d+\.\d\d$/ }).click();
  await expect(page).toHaveURL(/\/b\/\d+\/videos\/\d+$/);
  const thread = page.getByRole("list", { name: "Thread" });
  await expect(thread.getByText("Delivered.", { exact: true })).toBeVisible({ timeout: 240_000 });
  await expect(thread.getByLabel("The cut", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Download MP4" })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Make it again · up to \d+ credits?$/ })).toBeVisible();
  expect(await thread.textContent()).not.toMatch(/[a-z]+_[a-z_]+|\bc\d+\b|[{}]/); // plain words: no tool names, codes or JSON
  await page.getByRole("button", { name: "Open the steps" }).click();
  await expect(page.getByRole("tab", { name: /Clips/ })).toBeVisible();
  await page.getByRole("button", { name: "Close the steps" }).click();
  await expect(thread).toBeVisible();
  await noSidewaysScroll(page);
});

test("an editor sends a script for approval from New video, the owner approves it in Needs you, and it's delivered", async ({ page, browser, baseURL }) => {
  test.setTimeout(300_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  const brands = (await (await page.request.get("/api/brands")).json()) as { id: number; name: string }[];
  const fomo = brands.find((b) => b.name === "fomo")!.id;
  const title = `Salmon ${Date.now()}`;
  const text = ["SCENE 1 — INT. KITCHEN — DAY", "NATE: The dip is in. I'm buying.", "NATE: Download fomo through the link in my bio."].join("\n");
  const s = await (await page.request.post("/api/scripts", { data: { brand_id: fomo, title, description: "", notes: "", reference_replace: "", text } })).json();
  expect((await page.request.post(`/api/scripts/${s.id}/drafts/0/approve`)).ok()).toBe(true);
  expect((await page.request.post(`/api/scripts/${s.id}/publish`)).ok()).toBe(true);
  const name = `Dee ${Date.now() % 100000}`;
  const inv = await (await page.request.post("/api/team/invites", { data: { email: `newvideo-${Date.now()}@example.com` } })).json();
  const ed = await (await browser.newContext({ baseURL, viewport: { width: 1440, height: 900 } })).newPage();
  expect((await ed.request.post("/api/auth/accept-invite", { data: { token: inv.token, name, password: "correct horse battery staple" } })).ok()).toBe(true);

  await ed.goto(`/b/${fomo}/videos/new`);
  await ed.getByRole("tab", { name: "From a saved script" }).click();
  await ed.getByLabel("Search scripts").fill(title);
  await ed.getByRole("radio", { name: new RegExp(title) }).click();
  await expect(ed.getByText(/is past this video’s budget of \d+, so it goes to the owner first/)).toBeVisible(); // S2-05
  await ed.getByRole("button", { name: /^Send to the owner · up to \d+ credits?$/ }).click();
  await expect(ed.getByText("Sent to the owner for approval")).toBeVisible();
  await expect(ed.getByText(`From script ${title} · version A`)).toBeVisible();
  await expect(ed.getByText(/\$/)).toHaveCount(0);

  await page.goto("/approvals");
  const row = page.getByRole("listitem").filter({ hasText: `asked by ${name}` });
  await row.getByRole("button", { name: /^Approve/ }).click();
  await expect(row).toHaveCount(0);

  await expect(ed).toHaveURL(/\/b\/\d+\/videos\/\d+$/, { timeout: 30_000 }); // its video is real from the owner's OK
  await expect(ed.getByRole("list", { name: "Thread" }).getByText("Delivered.", { exact: true })).toBeVisible({ timeout: 240_000 });
  await expect(ed.getByRole("link", { name: "Download MP4" })).toBeVisible();
  await noSidewaysScroll(ed);

  // At 390 (QA on #1194): the editor's change waits for the owner, and the phone's bar has Withdraw change.
  await ed.setViewportSize({ width: 390, height: 844 });
  await ed.getByLabel("Tell the director what to change").fill("Punchier ending.");
  await ed.getByLabel("Tell the director what to change").press("Enter");
  await expect(ed.getByText("Change asked · waiting for the owner")).toBeVisible();
  const withdraw = ed.getByRole("button", { name: "Withdraw change" });
  expect((await withdraw.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await withdraw.click();
  await expect(ed.getByText("Change asked · waiting for the owner")).toHaveCount(0);
  await noSidewaysScroll(ed);
});

test("at 390, the owner's saved change after a delivery has Make it again in the phone's bar, and it runs", async ({ page }) => {
  test.setTimeout(300_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  await page.getByRole("navigation", { name: "Tabs" }).getByRole("link", { name: "New" }).click();
  const script = ["SCENE 1 — INT. KITCHEN — DAY", `NATE: The dip is in ${Date.now()}.`, "NATE: Download fomo through the link in my bio."].join("\n");
  await page.getByLabel("Paste a script, or describe the video").fill(script);
  await page.getByRole("button", { name: /^Make it · up to \$\d+\.\d\d$/ }).click();
  await expect(page).toHaveURL(/\/b\/\d+\/videos\/\d+$/);
  const again = page.getByRole("button", { name: /^Make it again · up to \d+ credits?$/ });
  await expect(again).toBeVisible({ timeout: 240_000 }); // delivered: its press is in the phone's bar
  await page.getByLabel("Tell the director what to change").fill("Make it slower.");
  await page.getByLabel("Tell the director what to change").press("Enter");
  await expect(page.getByText("Saved. Press Make it again to make this change.")).toBeVisible();
  expect((await again.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await again.click();
  await expect(page.getByRole("button", { name: "Stop" })).toBeVisible();
  await noSidewaysScroll(page);
});
