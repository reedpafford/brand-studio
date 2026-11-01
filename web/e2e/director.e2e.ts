import { expect, test } from "@playwright/test";
import { onBrand, signIn } from "./helpers";

// The director (first slice, #1087), on the stand-ins: an editor on a video from a published script presses Make it, sees
// each move as it goes, and gets the finished cut with its note. Credits only, never dollars; nothing paid is called.
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
  await expect(ed.getByRole("tab", { name: "Director" })).toHaveAttribute("aria-selected", "true");
  await expect(ed.getByText(/ · up to \d+(\.\d)? credits? so far · you can leave this page$/)).toBeVisible();
  await expect(ed.getByRole("button", { name: "Stop" })).toBeVisible();
  await expect(ed.getByText("Delivered", { exact: true })).toBeVisible({ timeout: 200_000 });
  await expect(ed.getByLabel("The finished video")).toBeVisible();
  await expect(ed.getByRole("link", { name: /Download MP4/ })).toBeVisible();
  await expect(ed.getByText(/^\d+(\.\d)? credits? for this run$/)).toBeVisible();
  expect(await ed.locator("main").textContent()).not.toMatch(/\$\d|ask (Reed|the owner)/i);
  const sizes = await ed.evaluate(() => ({ scroll: document.documentElement.scrollWidth, window: document.documentElement.clientWidth }));
  expect(sizes.scroll).toBeLessThanOrEqual(sizes.window);
  await ed.getByRole("tab", { name: "Look inside" }).click();
  await expect(ed).toHaveURL(/step=plan/);
  await expect(ed.getByRole("button", { name: /^Step 1 of 5/ })).toBeVisible(); // the phone step picker
});
