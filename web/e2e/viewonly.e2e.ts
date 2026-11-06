import { expect, test } from "@playwright/test";
import { emptyBrand, signIn } from "./helpers";

const PASSWORD = "correct horse battery staple";

for (const width of [1440, 390]) {
  test(`at ${width}: a second editor can look at someone else's video, with every press greyed out (Builder-Server-8's 403s)`, async ({ page, browser }) => {
    await signIn(page, "reed@example.com");
    await expect(page.getByRole("button", { name: /^Brand: / }).first()).toBeVisible();
    const brandId = await emptyBrand(page, "View Only Co");
    const run = `${width}-${test.info().retry}`; // a CI retry shares the database
    const join = async (name: string) => {
      const invite = await (await page.request.post("/api/team/invites", { data: { email: `${name.toLowerCase()}-${run}@example.com` } })).json();
      const context = await browser.newContext({ viewport: { width, height: 900 } });
      const them = await context.newPage();
      expect((await them.request.post("/api/auth/accept-invite", { data: { token: invite.token, name, password: PASSWORD } })).ok()).toBe(true);
      return them;
    };
    const sam = await join("Sam");
    const made = await sam.request.post("/api/projects", { data: { brand_id: brandId, name: `Sam's video ${run}`, planned_seconds: 20 } });
    expect(made.ok()).toBe(true);
    const id = (await made.json()).id;

    const eli = await join("Eli");
    await eli.goto(`/b/${brandId}/videos/${id}?step=plan`);
    await expect(eli.getByText(/The director makes the plan after Make it/)).toBeVisible(); // S8: no plan press of its own
    // No press that changes the video is live; reads (the tabs, the script, Show all) are.
    const changes = await eli.evaluate(() =>
      [...document.querySelectorAll("main button")]
        .filter((b) => !(b as HTMLButtonElement).disabled)
        .map((b) => b.textContent?.trim() || b.getAttribute("aria-label") || "")
        .filter((n) => /^(Make|Approve|Redraw|Draw|Edit|Save|Switch|Use|Delete|Remove|Change|Add|Undo|Write|Keep|Fix|Update|Pick|Rewrite|Merge|Restore)\b/.test(n)),
    );
    expect(changes).toEqual([]);
    await eli.getByRole("tab", { name: "Script" }).click(); // reading is looking
    await expect(eli.getByRole("tabpanel", { name: "Script" })).toBeVisible();
    if (width === 390) await eli.getByRole("tab", { name: "Chat" }).click(); // P-04: the chat is the other side
    await expect(eli.getByPlaceholder("Only Sam or the owner can change this video.")).toBeVisible(); // the message box says why

    await sam.goto(`/b/${brandId}/videos/${id}?step=plan`); // its maker gets no banner
    await expect(sam.getByRole("heading", { name: `Sam's video ${run}` })).toBeVisible();
    await expect(sam.getByText(/You can look/)).toHaveCount(0);
    const sizes = await eli.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
  });
}
