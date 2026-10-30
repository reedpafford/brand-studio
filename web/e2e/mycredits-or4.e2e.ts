import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

const PASSWORD = "correct horse battery staple";

// OR4: an editor's own credits page, from the account menu; Usage sends them there. Credits only.
for (const width of [1440, 390]) {
  test(`at ${width}: an editor opens My credits from the account menu and sees their week in credits, never a dollar`, async ({ page, browser }) => {
    await signIn(page, "reed@example.com");
    await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
    const run = `${width}-${test.info().retry}`; // a CI retry shares the database
    const invite = await (await page.request.post("/api/team/invites", { data: { email: `kim-${run}@example.com` } })).json();
    const context = await browser.newContext({ viewport: { width, height: 900 } });
    const kim = await context.newPage();
    expect((await kim.request.post("/api/auth/accept-invite", { data: { token: invite.token, name: "Kim", password: PASSWORD } })).ok()).toBe(true);

    await kim.goto("/usage"); // the owner's page sends an editor to their own
    await expect(kim).toHaveURL(/\/usage\/mine$/);
    await expect(kim.getByRole("heading", { name: "My credits" })).toBeVisible();
    await expect(kim.getByText(/^0 credits of \d+ credits used/)).toBeVisible();
    await kim.goto("/b/1/videos");
    await kim.getByRole("button", { name: "Account menu" }).click();
    await kim.getByRole("link", { name: "My credits" }).click();
    await expect(kim).toHaveURL(/\/usage\/mine$/);
    await expect(kim.getByRole("heading", { name: "Videos" })).toBeVisible();
    if (width === 390) expect((await kim.getByRole("radio", { name: "This month" }).boundingBox())!.height).toBeGreaterThanOrEqual(44); // denser on desktop, as Usage
    const sizes = await kim.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
    await expect(kim.getByText("$")).toHaveCount(0);
    await kim.screenshot({ path: test.info().outputPath(`mycredits-${width}.png`), fullPage: true });
    await context.close();
  });
}
