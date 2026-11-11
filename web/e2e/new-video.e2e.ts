import { expect, test, type Page } from "@playwright/test";
import { approveCastWhenReady, onBrand, signIn } from "./helpers";

// The director-first video (Home, once New video): Home → the director plans, casts, makes and cuts it, on the free
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
  approveCastWhenReady(page); // the Cast tab's Approve cast & places (#1324)
  await onBrand(page, "fomo");
  await page.keyboard.press("n"); // N opens Home, on its words box
  await expect(page.getByRole("heading", { name: "Paste your script, pick a style. We handle the rest." })).toBeVisible();
  await expect(page.getByLabel("Paste a script, or describe the video")).toBeFocused();
  const script = ["SCENE 1 — INT. KITCHEN — DAY", `NATE: The dip is in. I'm buying ${Date.now()}.`, "NATE: Download fomo through the link in my bio."].join("\n");
  await page.getByLabel("Paste a script, or describe the video").fill(script);
  await expect(page.getByRole("radio", { name: /^A script/ })).toBeChecked(); // a scene heading and speaker lines: kept word for word
  await expect(page.getByRole("button", { name: "Mode: Ask before making" })).toBeVisible(); // the default: the start card below waits for the OK
  await page.getByRole("button", { name: /^Make it · up to \$\d+\.\d\d$/ }).click();
  await expect(page).toHaveURL(/\/b\/\d+\/videos\/\d+$/);
  await page.getByRole("button", { name: /^Make it · up to \$\d+\.\d\d$/ }).click({ timeout: 60_000 }); // its start card, after the treatment (S3-02): dollars to the owner
  // v6 S3-09: the chat beside the preview panel; delivered, the cut plays in the Cut tab.
  const thread = page.getByRole("list", { name: "Conversation with the director" });
  await expect(page.getByRole("banner").getByText("Delivered", { exact: true })).toBeVisible({ timeout: 240_000 });
  const cut = page.getByRole("tabpanel", { name: "Cut" });
  await expect(cut.getByLabel("The cut", { exact: true })).toBeVisible();
  await expect(cut.getByRole("link", { name: "Download MP4" })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Make it again/ })).toHaveCount(0); // a revision starts by talking (S3-12)
  expect(await thread.textContent()).not.toMatch(/[a-z]+_[a-z_]+|\bc\d+\b|[{}]/); // plain words: no tool names, codes or JSON
  await page.getByRole("tab", { name: /^Clips/ }).click();
  await expect(page.getByRole("tabpanel", { name: "Clips" })).toBeVisible();
  await expect(thread).toBeVisible(); // the chat stays beside it
  await noSidewaysScroll(page);
});

test("an editor sends pasted words for approval from New video, the owner approves it in Needs you, and it's delivered", async ({ page, browser, baseURL }) => {
  test.setTimeout(300_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page, "reed@example.com");
  approveCastWhenReady(page); // the Cast tab's Approve cast & places (#1324)
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

  // A published script planned in one pass costs far less than its video's budget, so an editor's send of it is no
  // longer held (S2-06: "Inside this video's budget, so it starts straight away"); their own pasted words always are.
  const quote = await (await ed.request.post("/api/freestyles/estimate", { data: { shape: "9:16", script_id: s.id } })).json();
  expect(quote.held).toBeFalsy();
  expect(quote.credits).toBeLessThanOrEqual(quote.budget);
  await ed.goto(`/b/${fomo}/videos/new`);
  await ed.getByLabel("Paste a script, or describe the video").fill(text.replace("buying.", `buying ${title}.`));
  await expect(ed.getByRole("radio", { name: /^A script/ })).toBeChecked();
  await expect(ed.getByText("The owner approves before any generation starts. You’ll see it in My requests.")).toBeVisible(); // S2-04
  await ed.getByRole("button", { name: /^Send to the owner · up to \d+ credits?$/ }).click();
  await expect(ed.getByText("Waiting for the owner’s OK")).toBeVisible({ timeout: 60_000 }); // its start card, after its plan (S3-07)
  await expect(ed.getByText(/\$/)).toHaveCount(0);

  await page.goto("/approvals"); // S9-01: the send's start card, "Dee's new video · up to $X"
  const row = page.getByRole("listitem").filter({ hasText: `${name}’s new video · up to $` });
  await row.getByRole("button", { name: "Approve and start" }).click();
  await expect(row).toHaveCount(0);

  await expect(ed).toHaveURL(/\/b\/\d+\/videos\/\d+$/, { timeout: 30_000 }); // its video is real from the owner's OK
  await expect(ed.getByRole("banner").getByText("Delivered", { exact: true })).toBeVisible({ timeout: 240_000 });
  await expect(ed.getByRole("tabpanel", { name: "Cut" }).getByRole("link", { name: "Download MP4" })).toBeVisible();
  await noSidewaysScroll(ed);

  // At 390 (S3-07, P-07): the editor's change waits for the owner on its card, with Withdraw the request.
  await ed.setViewportSize({ width: 390, height: 844 });
  await ed.getByLabel("Tell the director what to change").fill("Redo clip 1 with a punchier ending."); // names its clip: a one-pass plan changes only what a note touches
  await ed.getByLabel("Tell the director what to change").press("Enter");
  await expect(ed.getByText("Waiting for the owner’s OK")).toBeVisible({ timeout: 60_000 });
  const withdraw = ed.getByRole("button", { name: "Withdraw the request" });
  expect((await withdraw.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await withdraw.click();
  await expect(ed.getByText("Waiting for the owner’s OK")).toHaveCount(0);
  await noSidewaysScroll(ed);
});

test("at 390, the owner's change after a delivery starts the next run by talking, and its start card runs it", async ({ page }) => {
  test.setTimeout(300_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await signIn(page, "reed@example.com");
  approveCastWhenReady(page); // the Cast tab's Approve cast & places (#1324)
  await onBrand(page, "fomo");
  await page.getByRole("navigation", { name: "Tabs" }).getByRole("link", { name: "Videos" }).click(); // v6 P-01: New video sits under the folders
  await page.getByRole("main").getByRole("link", { name: /^(New video|Make the first video)$/ }).click(); // a brand with nothing yet shows its set-up list (S1-02); both open Home
  await expect(page.getByRole("heading", { name: "Paste your script, pick a style. We handle the rest." })).toBeVisible();
  const script = ["SCENE 1 — INT. KITCHEN — DAY", `NATE: The dip is in ${Date.now()}.`, "NATE: Download fomo through the link in my bio."].join("\n");
  await page.getByLabel("Paste a script, or describe the video").fill(script);
  await page.getByRole("button", { name: /^Make it · up to \$\d+\.\d\d$/ }).click();
  await expect(page).toHaveURL(/\/b\/\d+\/videos\/\d+$/);
  await page.getByRole("button", { name: /^Make it · up to \$\d+\.\d\d$/ }).click({ timeout: 60_000 }); // its start card
  await expect(page.getByRole("banner").getByText(/^Delivered/)).toBeVisible({ timeout: 240_000 });
  await page.getByLabel("Tell the director what to change").fill("Make clip 1 slower.");
  await page.getByLabel("Tell the director what to change").press("Enter"); // S3-12: the note starts the next run
  // a new take of clip 1 waits for its start card (a revision's free edits to the cut wouldn't: video 233)
  const again = page.getByRole("button", { name: /^Make it · up to \$\d+\.\d\d$/ }); // its start card, the owner's press
  await expect(again).toBeVisible({ timeout: 60_000 });
  expect((await again.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await again.click();
  await expect(again).toHaveCount(0); // pressed: the revision goes on (the stand-in may deliver it at once, so no race on "Working")
  await noSidewaysScroll(page);
});
