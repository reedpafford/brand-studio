import { expect, test, type Locator, type Page } from "@playwright/test";
import { onBrand, signIn } from "./helpers";

// One clip from New video (Freestyle and Quick clip are New video now, v5), made by the free stand-ins on the test
// server: the owner's send runs at once; an editor's waits for the owner's OK in Needs you and then runs.
const noSidewaysScroll = async (page: Page) => {
  const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
  expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
};
const pickType = async (page: Page, name: string) => {
  await page.getByRole("button", { name: /^Type: / }).click();
  await page.getByRole("menuitemradio", { name }).click();
};

test("at 1440, the rail's New video makes a One clip at once, and it delivers with a player and Download MP4", async ({ page }) => {
  test.setTimeout(90_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "New video" }).click();
  await expect(page).toHaveURL(/\/videos\/new$/);
  await pickType(page, "One clip");
  const line = `MIA: The market opened at nine ${Date.now()}.`;
  await page.getByLabel("Paste a script, or describe the video").fill(line);
  await expect(page.getByRole("button", { name: /^Make it · up to \d+ credits?$/ })).toBeVisible(); // the price rides on the owner's press
  await page.getByLabel("Paste a script, or describe the video").press("Control+Enter");
  await expect(page).toHaveURL(/\/freestyle\/\d+$/); // a One clip has no video of its own: its freestyle page
  const top = page.getByRole("region", { name: "This freestyle" });
  await expect(top.getByText("Delivered")).toBeVisible({ timeout: 60_000 });
  await expect(top.getByRole("link", { name: "Download MP4" })).toBeVisible();
  await expect(page.getByLabel("The freestyle")).toBeVisible();
  await noSidewaysScroll(page);
});

test("at 390, an editor's One clip waits for approval, the owner approves it in Needs you, and it delivers", async ({ page, browser, baseURL }) => {
  test.setTimeout(120_000);
  await signIn(page, "reed@example.com");
  await onBrand(page, "fomo");
  const name = `Fay ${Date.now() % 100000}`;
  const inv = await (await page.request.post("/api/team/invites", { data: { email: `freestyle-${Date.now()}@example.com` } })).json();
  const ed = await (await browser.newContext({ baseURL, viewport: { width: 390, height: 844 } })).newPage();
  expect((await ed.request.post("/api/auth/accept-invite", { data: { token: inv.token, name, password: "correct horse battery staple" } })).ok()).toBe(true);
  await ed.goto("/");
  await ed.getByRole("navigation", { name: "Tabs" }).getByRole("link", { name: "New" }).click();
  await pickType(ed, "One clip");
  await ed.getByLabel("Paste a script, or describe the video").fill(`CAT: The dip is in ${Date.now()}.`);
  await ed.getByRole("button", { name: /^Send for approval · up to \d+ credits?$/ }).click();
  const top = ed.getByRole("region", { name: "This freestyle" });
  await expect(top.getByText("Waiting for approval")).toBeVisible();
  await expect(top.getByRole("button", { name: "Withdraw" })).toBeVisible();
  await expect(ed.getByText(/\$/)).toHaveCount(0);
  await noSidewaysScroll(ed);
  const height = async (l: Locator) => (await l.boundingBox())!.height;
  expect(await height(ed.getByRole("link", { name: "New video" }))).toBeGreaterThanOrEqual(44); // phones: touch (QA-9 on #1161)

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/approvals");
  const row = page.getByRole("listitem").filter({ hasText: `asked by ${name}` }); // its own editor: the only send of theirs
  await expect(row).toContainText("Freestyle · One clip");
  await row.getByRole("button", { name: /^Approve/ }).click();
  await expect(row).toHaveCount(0);

  await expect(top.getByText("Delivered")).toBeVisible({ timeout: 60_000 });
  await expect(top.getByRole("link", { name: "Download MP4" })).toBeVisible();
  await noSidewaysScroll(ed);
});
