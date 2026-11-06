import { expect, test } from "@playwright/test";
import { approveCastWhenReady, makeIt, onBrand, signIn } from "./helpers";

// The director (first slice, #1087; v6 S3/P-04/P-05), on the stand-ins: an editor on a video from a published script presses Make it, sees
// its run's progress (it watches its cut, fixes what it found and cuts again, #1145), and gets the finished cut with
// its note. Credits only, never dollars; nothing paid is called.
test("at 390, an editor presses Make it and the director delivers the finished cut with its note", async ({ page, browser, baseURL }) => {
  test.setTimeout(240_000);
  await page.setViewportSize({ width: 390, height: 900 });
  await signIn(page, "reed@example.com");
  approveCastWhenReady(page); // the Cast tab's Approve cast & places (#1324)
  await onBrand(page, "fomo");
  const brands = (await (await page.request.get("/api/brands")).json()) as { id: number; name: string }[];
  const fomo = brands.find((b) => b.name === "fomo")!.id;
  const text = ["SCENE 1 — INT. KITCHEN — DAY", "NATE: The dip is in. I'm buying.", "★ fomo screen: Token chart up — fills the frame", "NATE: Download fomo through the link in my bio."].join("\n");
  const s = await (await page.request.post("/api/scripts", { data: { brand_id: fomo, title: `Director ${Date.now()}`, description: "", notes: "", reference_replace: "", text } })).json();
  expect((await page.request.post(`/api/scripts/${s.id}/drafts/0/approve`)).ok()).toBe(true);
  expect((await page.request.post(`/api/scripts/${s.id}/publish`)).ok()).toBe(true);

  const inv = await (await page.request.post("/api/team/invites", { data: { email: `director-${Date.now()}@example.com` } })).json();
  const ed = await (await browser.newContext({ baseURL, viewport: { width: 390, height: 900 } })).newPage();
  expect((await ed.request.post("/api/auth/accept-invite", { data: { token: inv.token, name: "Dee", password: "correct horse battery staple" } })).ok()).toBe(true);
  const made = await ed.request.post(`/api/scripts/${s.id}/drafts/0/produce`);
  expect(made.ok()).toBe(true);
  const pid = (await made.json()).project_id;

  await ed.goto(`/b/${fomo}/videos/${pid}`);
  // v6 P-04: at 390 the video is the chat, with a Chat | Preview switch; Make it starts the director.
  await ed.getByRole("button", { name: /^Make it/ }).click();
  await expect(ed.getByRole("tablist", { name: "Chat or preview" })).toBeVisible();
  // Its plan first, then its start card (S3-02): no generation until Make it (its whole "up to" is past what's left of this
  // video's budget, so the owner presses it).
  await makeIt(page, pid);
  await expect(ed.getByRole("banner").getByText(/^Working/)).toBeVisible();
  await expect(ed.getByRole("banner").getByText(/^Delivered$/)).toBeVisible({ timeout: 200_000 });
  await expect(ed.getByRole("banner").getByText(/of up to \d+ credits$/)).toBeVisible(); // credits, never dollars (rule 4)
  const thread = ed.getByRole("list", { name: "Conversation with the director" });
  await expect(thread).toContainText(/Made in \d+ min/, { timeout: 30_000 }); // one progress card a run (v6 piece C), not a row a turn
  const moves = await thread.textContent();
  expect(moves).not.toMatch(/[a-z]+_[a-z_]+|\bc\d+\b|[{}]/); // plain words only: no tool names, clip codes or JSON
  expect(moves).toMatch(/Clip \d+: .*Muted a stretch of clip \d+ instead of remaking it\./); // the note's "watched and redid"
  expect(moves).toMatch(/\d+ credits used of up to \d+ \(\d+% of the budget\)/); // its cost, in credits to an editor
  expect(await ed.locator("body").textContent()).not.toMatch(/\$\d|ask (Reed|the owner)/i);
  // P-05: the cut plays in Preview, with its downloads; the tab row always shows (S-gaps-03).
  await ed.getByRole("tab", { name: "Preview" }).click();
  await expect(ed.getByRole("tablist", { name: "Preview", exact: true })).toBeVisible();
  await expect(ed.getByRole("tabpanel", { name: "Cut" }).getByLabel("The cut", { exact: true })).toBeVisible();
  await expect(ed.getByRole("tabpanel", { name: "Cut" }).getByRole("link", { name: "Download MP4" })).toBeVisible();
  await ed.getByRole("tab", { name: "Plan" }).click();
  await expect(ed.getByRole("tabpanel", { name: "Plan" })).toBeVisible();
  // Chat: ask for a change after the delivery: the note starts the next run (S3-12), whose start card the owner presses.
  await ed.getByRole("tab", { name: "Chat" }).click();
  await ed.getByLabel("Tell the director what to change").fill("Make clip 1 slower.");
  await ed.getByRole("button", { name: "Send to the director" }).click();
  await expect(thread.getByText("Make clip 1 slower.")).toBeVisible();
  await makeIt(page, pid); // its start card again
  await expect(ed.getByRole("banner").getByText(/^Working/)).toBeVisible();
  await expect(ed.getByRole("banner").getByText(/^Delivered$/)).toBeVisible({ timeout: 200_000 });
  const sizes = await ed.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
  expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
});
