import { expect, test, type Locator, type Page } from "@playwright/test";
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
  await expect(page.getByRole("button", { name: /^Send · up to \d+ credits?$/ })).toBeVisible(); // the price rides on Reed's send
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
  const height = async (l: Locator) => (await l.boundingBox())!.height;
  expect(await height(ed.getByRole("link", { name: "All freestyles" }))).toBeGreaterThanOrEqual(44); // phones: touch (QA-9 on #1161)

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/freestyle");
  for (const n of ["Mine", "Everyone's"]) expect(await height(page.getByRole("button", { name: n, exact: true }))).toBeGreaterThanOrEqual(44);
  await page.goto("/approvals");
  const row = page.getByRole("listitem").filter({ hasText: `asked by ${name}` }); // its own editor: the only send of theirs
  await expect(row).toContainText("Freestyle · One clip");
  await expect(row).toContainText("First send");
  await expect(row).not.toContainText("Quick clip");
  await expect(row.getByRole("link", { name: /^Open freestyle/ })).toHaveAttribute("href", /\/freestyle\/\d+$/);
  await row.getByRole("button", { name: /^Approve/ }).click();
  await expect(row).toHaveCount(0);

  await expect(top.getByText("Delivered")).toBeVisible({ timeout: 60_000 });
  await expect(top.getByRole("link", { name: "Download MP4" })).toBeVisible();
  await noSidewaysScroll(ed);
});

test("at 1440, Reed sends a Dialogue: the director makes it on the stand-ins, its moves read plainly, and the cut plays", async ({ page }) => {
  test.setTimeout(240_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  await page.goto("/freestyle");
  await page.getByLabel("Type").selectOption({ label: "Dialogue" });
  const script = ["SCENE 1 — INT. KITCHEN — DAY", `NATE: The dip is in. I'm buying ${Date.now()}.`, "NATE: Download fomo through the link in my bio."].join("\n");
  await page.getByLabel("Paste a script, or describe the clip").fill(script);
  await page.getByRole("button", { name: /^Send · up to \d+ credits?$/ }).click();
  await expect(page).toHaveURL(/\/freestyle\/\d+$/);
  const top = page.getByRole("region", { name: "This freestyle" });
  await expect(top.getByText("Delivered")).toBeVisible({ timeout: 200_000 });
  await expect(page.getByLabel("The freestyle")).toBeVisible();
  await expect(top.getByRole("link", { name: "Download MP4" })).toBeVisible();
  const thread = page.getByRole("list", { name: "Thread" });
  await expect(thread.getByText(/Made the cut\./).first()).toBeVisible();
  expect(await thread.textContent()).not.toMatch(/[a-z]+_[a-z_]+|\bc\d+\b|[{}]/); // no tool names, clip codes or JSON
  await noSidewaysScroll(page);
});
