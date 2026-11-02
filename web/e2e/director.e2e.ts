import { expect, test } from "@playwright/test";
import { onBrand, runToEnd, signIn } from "./helpers";

// The director (first slice, #1087), on the stand-ins: an editor on a video from a published script presses Make it, sees
// each move as it goes (it watches its cut, fixes what it found and cuts again, #1145), and gets the finished cut with
// its note. Credits only, never dollars; nothing paid is called.
test("at 390, an editor presses Make it and the director delivers the finished cut with its note", async ({ page, browser, baseURL }) => {
  test.setTimeout(240_000);
  await page.setViewportSize({ width: 390, height: 900 });
  await signIn(page, "reed@example.com");
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
  await ed.getByRole("button", { name: "Make it" }).click();
  await expect(ed.getByRole("button", { name: "Step 1 of 5 · Director" })).toBeVisible(); // at 390 the tabs are one step button
  await expect(ed.getByText(/ · up to \d+(\.\d)? credits? so far · you can leave this page$/)).toBeVisible();
  await expect(ed.getByRole("button", { name: "Stop" })).toBeVisible();
  await runToEnd(page, pid); // past the director's own limit it waits, and the owner OKs it
  await expect(ed.getByText("Delivered", { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(ed.getByLabel("The finished video")).toBeVisible();
  await expect(ed.getByRole("link", { name: /Download MP4/ })).toBeVisible();
  await expect(ed.getByText(/^\d+ s · up to \d+(\.\d)? credits? for this run$/)).toBeVisible();
  await expect(ed.getByRole("heading", { name: "Talk to the director" })).toBeVisible();
  await expect(ed.getByRole("list", { name: "Locked" })).toBeVisible(); // the locks it builds around, above the conversation
  const thread = ed.getByRole("list", { name: "Conversation with the director" });
  if (await ed.getByRole("button", { name: /^Show earlier/ }).isVisible()) await ed.getByRole("button", { name: /^Show earlier/ }).click();
  const moves = await thread.textContent();
  expect(moves).not.toMatch(/[a-z]+_[a-z_]+|\bc\d+\b|[{}]/); // plain words only: no tool names, clip codes or JSON
  expect(moves).toContain("Watching the cut."); // it watched its cut (#1145)
  expect(moves).toMatch(/OK'd: up to \d+ more credits of the director's time\./); // the owner's OK at its limit
  expect((moves ?? "").match(/Made the cut\./g)?.length ?? 0).toBeGreaterThanOrEqual(2); // and cut again after its fixes
  const noted = /^The cut is made\b.*Muted a stretch of clip \d+ instead of remaking it\./; // the delivery note names the mute
  await expect(ed.locator("p").filter({ hasText: noted }).first()).toBeVisible();
  expect(await ed.locator("main").textContent()).not.toMatch(/\$\d|ask (Reed|the owner)/i);
  // Chat (v4): ask for a change after the delivery; the stand-in remakes that clip, cuts and delivers again.
  await ed.getByLabel("Tell the director what to change").fill("Make clip 1 slower.");
  await ed.getByRole("button", { name: "Send to the director" }).click();
  await expect(thread.getByText("Make clip 1 slower.")).toBeVisible();
  // A message never starts a run by itself (the Producer, 2 Nov): it's saved, and Make it again makes it.
  const again = ed.getByRole("button", { name: "Make it again" });
  await expect(ed.getByText("Saved. Press Make it again to make this change.").or(ed.getByRole("button", { name: "Stop" }))).toBeVisible();
  if (await again.isVisible()) await again.click();
  await expect(ed.getByRole("button", { name: "Stop" })).toBeVisible();
  await runToEnd(page, pid);
  await expect(ed.getByText("Delivered", { exact: true })).toBeVisible({ timeout: 30_000 });
  const sizes = await ed.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
  expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
  await ed.getByRole("button", { name: "Step 1 of 5 · Director" }).click(); // the phone keeps its step sheet, the Director first
  await ed.getByRole("dialog").getByRole("button", { name: /Plan/ }).click();
  await expect(ed).toHaveURL(/step=plan/);
  await expect(ed.getByRole("button", { name: /^Step 2 of 5 · Plan/ })).toBeVisible();
});
