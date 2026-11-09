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
  // The revision runs and delivers again: one more delivery note than before. On the stand-ins it can finish before the
  // header's Working is ever looked at (the page follows a run within 3 s since #1485), so the test waits on the run.
  type Read = { status: string; thread: { note?: object | null }[] };
  const read = async () => (await (await page.request.get(`/api/projects/${pid}/director`)).json()) as Read;
  const notes = (r: Read) => r.thread.filter((t) => t.note).length;
  const before = notes(await read());
  await makeIt(page, pid); // its start card again
  await expect.poll(async () => { const r = await read(); return r.status === "delivered" && notes(r) > before; }, { timeout: 200_000 }).toBe(true);
  await expect(ed.getByRole("banner").getByText(/^Delivered$/)).toBeVisible({ timeout: 30_000 });
  const sizes = await ed.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
  expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
});

// Runway #2: a delivered video's Make variations…, at 390: 44 px presses and no sideways scroll; each variation is a new video
// beside it that waits on its own card (Make it) before anything is made.
test("at 390, Make variations on a delivered video makes two, each waiting on its own card", async ({ page }) => {
  test.setTimeout(240_000);
  await page.setViewportSize({ width: 390, height: 900 });
  await signIn(page, "reed@example.com");
  approveCastWhenReady(page);
  await onBrand(page, "fomo");
  const fomo = ((await (await page.request.get("/api/brands")).json()) as { id: number; name: string }[]).find((b) => b.name === "fomo")!.id;
  const long = "and the chart keeps climbing while everyone at the table laughs at me again, ".repeat(3); // 8 s a line: two clips or more
  const text = ["SCENE 1 — INT. KITCHEN — DAY", `NATE: The dip is in, ${long}so I'm buying.`, `MOM: Nate, ${long}sit down.`, "SCENE 2 — EXT. STREET — NIGHT", `MOM: Nate? ${long}is that you?`, `NATE: Look who's laughing now, ${long}download fomo.`].join("\n");
  const s = await (await page.request.post("/api/scripts", { data: { brand_id: fomo, title: `Vary ${Date.now()}`, description: "", notes: "", reference_replace: "", text } })).json();
  expect((await page.request.post(`/api/scripts/${s.id}/drafts/0/approve`)).ok()).toBe(true);
  expect((await page.request.post(`/api/scripts/${s.id}/publish`)).ok()).toBe(true);
  const pid = (await (await page.request.post(`/api/scripts/${s.id}/drafts/0/produce`)).json()).project_id;
  await page.goto(`/b/${fomo}/videos/${pid}`);
  await page.getByRole("button", { name: /^Make it/ }).click();
  await makeIt(page, pid);
  await expect(page.getByRole("banner").getByText(/^Delivered$/)).toBeVisible({ timeout: 200_000 });
  await page.getByRole("button", { name: /^More for / }).click();
  await page.getByRole("menuitem", { name: "Make variations…" }).click();
  const ask = page.getByRole("alertdialog", { name: "Make variations" });
  for (const press of [...(await ask.getByRole("radio").all()), ask.getByRole("button", { name: "Make variations" })]) expect((await press.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
  expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
  await ask.getByRole("radio", { name: "2 variations" }).click();
  await ask.getByRole("button", { name: "Make variations" }).click();
  const links = page.getByRole("alertdialog", { name: "Variations" }).getByRole("link", { name: / · variation [AB]$/ });
  await expect(links).toHaveCount(2, { timeout: 30_000 });
  await links.first().click();
  await expect(page.getByRole("heading", { level: 1, name: / · variation A$/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Make it/ })).toBeVisible({ timeout: 30_000 }); // its own card: nothing made yet
});
