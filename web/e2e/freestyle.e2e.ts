import { expect, test, type Page } from "@playwright/test";
import { onBrand, signIn } from "./helpers";

// Freestyle (Reed's redesign; replaces Quick clip). One clip works now, made by the free stand-ins on the test server:
// Reed's send runs at once; an editor's waits for Reed's OK in Approvals and then runs.
const noSidewaysScroll = async (page: Page) => {
  const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
  expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
};

test("at 1440, Reed makes a One clip freestyle from the rail and it delivers, with a player and Download MP4", async ({ page }) => {
  test.setTimeout(90_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Freestyle" }).click();
  await expect(page).toHaveURL(/\/freestyle$/);
  const line = `MIA: The market opened at nine ${Date.now()}.`;
  await page.getByLabel("Paste a script, or describe the clip").fill(line);
  await expect(page.getByText(/^up to \d+ credits?$/)).toBeVisible();
  await page.getByLabel("Paste a script, or describe the clip").press("Enter");
  await expect(page).toHaveURL(/\/freestyle\/\d+$/);
  const top = page.getByRole("region", { name: "This freestyle" });
  await expect(top.getByText("Delivered")).toBeVisible({ timeout: 60_000 });
  await expect(top.getByRole("link", { name: "Download MP4" })).toBeVisible();
  await expect(page.getByLabel("The freestyle")).toBeVisible();
  await expect(page.getByRole("complementary", { name: "Your freestyles" }).getByRole("link", { name: new RegExp(line.slice(0, 30)) })).toBeVisible();
  await expect(page.getByLabel("Ask for a change")).toBeVisible();
  await noSidewaysScroll(page);
});

test("at 390, an editor's freestyle waits for approval, Reed approves it in Approvals, and it delivers", async ({ page, browser, baseURL }) => {
  test.setTimeout(120_000);
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  const name = `Fay ${Date.now() % 100000}`;
  const inv = await (await page.request.post("/api/team/invites", { data: { email: `freestyle-${Date.now()}@example.com` } })).json();
  const ed = await (await browser.newContext({ baseURL, viewport: { width: 390, height: 844 } })).newPage();
  expect((await ed.request.post("/api/auth/accept-invite", { data: { token: inv.token, name, password: "correct horse battery staple" } })).ok()).toBe(true);
  await ed.goto("/");
  await ed.getByRole("navigation", { name: "Tabs" }).getByRole("link", { name: "Freestyle" }).click();
  const line = `CAT: The dip is in ${Date.now()}.`;
  await ed.getByLabel("Paste a script, or describe the clip").fill(line);
  await ed.getByRole("button", { name: "Send for approval" }).click();
  const top = ed.getByRole("region", { name: "This freestyle" });
  await expect(top.getByText("Waiting for approval")).toBeVisible();
  await expect(top.getByRole("button", { name: "Withdraw" })).toBeVisible();
  await expect(ed.getByText(/\$/)).toHaveCount(0);
  await noSidewaysScroll(ed);

  await page.goto("/approvals");
  const row = page.getByRole("listitem").filter({ hasText: `asked by ${name}` }); // its own editor: the only send of theirs
  await row.getByRole("button", { name: /^Approve/ }).click();
  await expect(row).toHaveCount(0);

  await expect(top.getByText("Delivered")).toBeVisible({ timeout: 60_000 });
  await expect(top.getByRole("link", { name: "Download MP4" })).toBeVisible();
  await noSidewaysScroll(ed);
});
